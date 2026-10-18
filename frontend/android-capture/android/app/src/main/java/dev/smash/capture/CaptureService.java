package dev.smash.capture;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.net.ConnectivityManager;
import android.net.Network;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;
import android.view.Surface;

import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;

/** User-started recording service; a process restart never automatically opens the camera. */
public final class CaptureService extends Service {
    private static final String PREFS = "capture-settings";
    private static final String START = "capture.START";
    private static final String RESUME = "capture.RESUME";
    private static final String CHANNEL = "capture";
    private static final int NOTIFICATION_ID = 1;
    // Android 15 limits dataSync foreground work. Pause conservatively before its six-hour limit.
    private static final long UPLOAD_ONLY_LIMIT_MS = 4L * 60 * 60 * 1000;
    private static volatile CaptureService instance;
    private static volatile Surface preview;
    private static volatile int rotation;

    private final Object monitor = new Object();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService camera = Executors.newSingleThreadExecutor();
    private final LocalBinder binder = new LocalBinder();
    private SegmentStore store;
    private SharedPreferences preferences;
    private volatile CaptureEngine engine;
    private PowerManager.WakeLock wakeLock;
    private ConnectivityManager connectivity;
    private volatile boolean running = true;
    private volatile boolean recording;
    private volatile boolean starting;
    private volatile boolean stopping;
    private volatile boolean uploading;
    private volatile String session = "";
    private volatile String lastError = "";
    private volatile String endpoint = "";
    private volatile String token = "";
    private volatile long configVersion;
    private long retryRevision;
    private long networkRevision;
    private long eventRevision;
    private volatile long uploadOnlySince;
    private volatile int latestStartId;
    private Thread uploadThread;

    public final class LocalBinder extends Binder {
        public CaptureService getService() { return CaptureService.this; }
    }

    public static void configure(Context context, String endpoint, String token) {
        String address = endpoint.trim().isEmpty() ? "" : TusUploader.normalizeEndpoint(endpoint);
        if (token.contains("\r") || token.contains("\n")) throw new IllegalArgumentException("令牌不能包含换行符");
        boolean saved = context.getApplicationContext().getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("endpoint", address).putString("token", token).commit();
        if (!saved) throw new IllegalStateException("接收设置保存失败，请检查手机存储空间");
        CaptureService service = instance;
        if (service != null) service.reloadConfiguration();
    }

    /** Call only after camera/microphone permission is granted and the Activity is visible. */
    public static void startCapture(Context context, Surface surface, int displayRotation) {
        preview = surface;
        rotation = displayRotation;
        context.getApplicationContext().startForegroundService(
                new Intent(context, CaptureService.class).setAction(START));
    }

    public static void stopCapture(Context context) {
        CaptureService service = instance;
        if (service != null) service.requestStopCapture();
    }

    /** User action only: Android restricts starting foreground work from a background app. */
    public static void resumeUploads(Context context) {
        context.getApplicationContext().startForegroundService(
                new Intent(context, CaptureService.class).setAction(RESUME));
    }

    public static void setPreview(Surface surface) {
        preview = surface;
        CaptureService service = instance;
        if (service != null && service.running) {
            try { service.camera.execute(() -> {
                if (service.engine != null) service.engine.setPreview(surface);
            }); }
            catch (java.util.concurrent.RejectedExecutionException ignored) { /* Service already stopped. */ }
        }
    }

    public static JSONObject snapshot(Context context) {
        CaptureService service = instance;
        if (service != null) return service.state();
        SharedPreferences prefs = context.getApplicationContext().getSharedPreferences(PREFS, MODE_PRIVATE);
        SegmentStore files = new SegmentStore(new File(context.getApplicationContext().getFilesDir(), "spool"));
        return makeState(files, prefs, false, false, false, false,
                prefs.getString("session", ""), prefs.getString("last_error", ""),
                prefs.getString("endpoint", ""));
    }

    private final ConnectivityManager.NetworkCallback networkCallback = new ConnectivityManager.NetworkCallback() {
        @Override public void onAvailable(Network network) {
            synchronized (monitor) { networkRevision++; eventRevision++; monitor.notifyAll(); }
        }
        @Override public void onLost(Network network) { signal(); }
    };

    @Override public void onCreate() {
        super.onCreate();
        instance = this;
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        store = new SegmentStore(new File(getFilesDir(), "spool"));
        lastError = preferences.getString("last_error", "");
        reloadConfiguration();
        PowerManager power = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, getPackageName() + ":capture");
        wakeLock.setReferenceCounted(false);
        connectivity = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        connectivity.registerDefaultNetworkCallback(networkCallback);
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "录像与补传", NotificationManager.IMPORTANCE_LOW));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        latestStartId = startId;
        boolean begin = intent != null && START.equals(intent.getAction());
        if (!showForeground(begin || captureActive())) return START_NOT_STICKY;
        if (!wakeLock.isHeld()) wakeLock.acquire();
        synchronized (monitor) { retryRevision++; eventRevision++; monitor.notifyAll(); }
        if (begin) beginCapture();
        else if (!captureActive()) uploadOnlySince = SystemClock.elapsedRealtime();
        if (uploadThread == null) {
            uploadThread = new Thread(this::uploadLoop, "capture-upload");
            uploadThread.start();
        }
        return START_NOT_STICKY;
    }

    private void reloadConfiguration() {
        synchronized (monitor) {
            endpoint = preferences.getString("endpoint", "");
            token = preferences.getString("token", "");
            configVersion++;
            retryRevision++;
            eventRevision++;
            monitor.notifyAll();
        }
    }

    private void beginCapture() {
        if (captureActive()) return;
        starting = true;
        preferences.edit().remove("capture_error").apply();
        setError("");
        session = UUID.randomUUID().toString();
        preferences.edit().putString("session", session).apply();
        String captureSession = session;
        long epoch = System.currentTimeMillis();
        int displayRotation = rotation;
        camera.execute(() -> {
            if (!running) return;
            engine = new CaptureEngine(this, store.directory(), new CaptureEngine.Listener() {
                @Override public boolean canWrite(long nextBytes) { return store.canWrite(nextBytes); }
                @Override public void onSegment(File file, JSONObject metadata) { signal(); }
                @Override public void onError(String error) {
                    setCaptureError(error);
                    requestStopCapture();
                }
                @Override public void onRecording() {
                    starting = false;
                    recording = true;
                    signal();
                    main.post(() -> showForeground(true));
                }
            });
            try { engine.start(captureSession, epoch, preview, displayRotation); }
            catch (Exception error) {
                Log.e("CaptureService", "Camera start failed", error);
                setCaptureError("摄像头启动失败：" + error.getClass().getSimpleName()
                        + (error.getMessage() == null ? "" : "：" + error.getMessage()));
                requestStopCapture();
            }
        });
    }

    private void requestStopCapture() {
        if (!running || !captureActive() || stopping) return;
        stopping = true;
        camera.execute(() -> {
            CaptureEngine previous = engine;
            try { if (previous != null) previous.stop(); }
            catch (Exception error) {
                Log.e("CaptureService", "Camera stop failed", error);
                setCaptureError("封装最后片段失败，未封口文件已保留");
            }
            finally { main.post(() -> finishCaptureStop(previous)); }
        });
    }

    private void finishCaptureStop(CaptureEngine previous) {
        if (!running || engine != previous) return;
        if (previous != null && !previous.isStopped()) {
            // A blocked device driver may outlive stop()'s bounded wait. Keep the foreground
            // camera/microphone ownership and reject a second recording until release completes.
            main.postDelayed(() -> finishCaptureStop(previous), 1000);
            return;
        }
        engine = null;
        recording = false;
        starting = false;
        stopping = false;
        uploadOnlySince = SystemClock.elapsedRealtime();
        showForeground(false);
        signal();
    }

    private boolean captureActive() { return recording || starting || stopping; }

    private void uploadLoop() {
        TusUploader uploader = new TusUploader(store);
        long blockedRevision = -1;
        int failures = 0;
        while (running) {
            long event;
            synchronized (monitor) { event = eventRevision; }
            List<SegmentStore.Segment> queue = store.pending();
            if (!captureActive() && (queue.isEmpty() || uploadBudgetExpired())) {
                if (uploadBudgetExpired() && !queue.isEmpty()) setError("补传已运行 4 小时，队列已保存，请打开应用继续上传");
                finishWhenIdle();
                return;
            }
            long actionRevision;
            long connectionRevision;
            long version;
            String address;
            String bearer;
            synchronized (monitor) {
                actionRevision = retryRevision;
                connectionRevision = networkRevision;
                version = configVersion;
                address = endpoint;
                bearer = token;
            }
            if (blockedRevision == actionRevision || address.isEmpty() || bearer.isEmpty()) {
                if (address.isEmpty() || bearer.isEmpty()) setError("请设置接收地址和令牌；已封口片段保留在手机");
                if (!captureActive()) { finishWhenIdle(); return; }
                awaitEvent(event);
                continue;
            }
            if (queue.isEmpty()) { awaitEvent(event); continue; }
            uploading = true;
            try {
                long latency = uploader.upload(queue.get(0), address, bearer,
                        () -> running && configVersion == version && !uploadBudgetExpired());
                preferences.edit().putLong("uploaded_segments", preferences.getLong("uploaded_segments", 0) + 1)
                        .putLong("last_latency_ms", latency).apply();
                setError("");
                failures = 0;
            } catch (TusUploader.UploadException error) {
                setError(error.getMessage());
                if (error.permanent) blockedRevision = actionRevision;
                else awaitRetry(backoff(++failures), actionRevision, connectionRevision);
            } catch (IOException error) {
                if (running && version == configVersion) {
                    Log.w("CaptureService", "Upload interrupted: " + error.getClass().getSimpleName());
                    setError("网络暂不可用，已保留片段并自动重试");
                    awaitRetry(backoff(++failures), actionRevision, connectionRevision);
                }
            } catch (Exception error) {
                Log.e("CaptureService", "Upload queue failed", error);
                setError("上传队列异常，片段已保留：" + error.getClass().getSimpleName());
                blockedRevision = actionRevision;
            } finally { uploading = false; }
        }
    }

    private boolean uploadBudgetExpired() {
        return !captureActive() && uploadOnlySince > 0
                && SystemClock.elapsedRealtime() - uploadOnlySince >= UPLOAD_ONLY_LIMIT_MS;
    }

    private static long backoff(int failures) {
        long ceiling = Math.min(30_000, 1000L << Math.min(5, failures - 1));
        return ThreadLocalRandom.current().nextLong(Math.max(1, ceiling / 2), ceiling + 1);
    }

    private void awaitRetry(long milliseconds, long action, long network) {
        long deadline = SystemClock.elapsedRealtime() + milliseconds;
        synchronized (monitor) {
            while (running && action == retryRevision && network == networkRevision) {
                long remaining = deadline - SystemClock.elapsedRealtime();
                if (remaining <= 0) return;
                // A new sealed segment wakes an idle queue; it does not bypass a network backoff.
                try { monitor.wait(remaining); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); return; }
            }
        }
    }

    private void awaitEvent(long event) {
        synchronized (monitor) {
            if (running && event == eventRevision) {
                try { monitor.wait(30_000); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
            }
        }
    }

    private void signal() { synchronized (monitor) { eventRevision++; monitor.notifyAll(); } }

    private void finishWhenIdle() {
        long finishingRevision;
        synchronized (monitor) { finishingRevision = retryRevision; }
        main.post(() -> {
            if (captureActive() || finishingRevision != retryRevision) {
                uploadThread = new Thread(this::uploadLoop, "capture-upload");
                uploadThread.start();
                return;
            }
            uploadThread = null;
            stopForeground(STOP_FOREGROUND_REMOVE);
            if (wakeLock.isHeld()) wakeLock.release();
            stopSelfResult(latestStartId);
        });
    }

    private void setError(String error) {
        if (error == null) error = "未知错误";
        if (!error.equals(lastError)) {
            lastError = error;
            preferences.edit().putString("last_error", error).apply();
        }
    }

    private void setCaptureError(String error) {
        preferences.edit().putString("capture_error", error).apply();
        setError(error);
    }

    private boolean showForeground(boolean capture) {
        try {
            Notification.Builder builder = new Notification.Builder(this, CHANNEL)
                    .setSmallIcon(android.R.drawable.presence_video_online)
                    .setContentTitle("Smash 视频采集")
                    .setContentText(capture ? "正在录像，音视频会自动上传" : "正在补传已保存的视频")
                    .setOngoing(true).setOnlyAlertOnce(true);
            Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (launch != null) builder.setContentIntent(PendingIntent.getActivity(this, 0, launch,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
            int types = capture ? ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA | ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                    : ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC;
            if (Build.VERSION.SDK_INT >= 29) startForeground(NOTIFICATION_ID, builder.build(), types);
            else startForeground(NOTIFICATION_ID, builder.build());
            return true;
        } catch (RuntimeException error) {
            setError("无法启动前台录制或补传，请从应用界面重试：" + error.getClass().getSimpleName());
            stopSelf();
            return false;
        }
    }

    private JSONObject state() {
        return makeState(store, preferences, recording, starting, stopping, uploading, session, lastError, endpoint);
    }

    private static JSONObject makeState(SegmentStore store, SharedPreferences prefs, boolean recording,
                                         boolean starting, boolean stopping, boolean uploading, String session, String error, String endpoint) {
        JSONObject value = new JSONObject();
        String cameraError = prefs.getString("capture_error", "");
        if (!cameraError.isEmpty() && !cameraError.equals(error)) {
            error = cameraError + (error.isEmpty() ? "" : "；" + error);
        }
        List<SegmentStore.Segment> queue = store.pending();
        long bytes = 0;
        long oldest = Long.MAX_VALUE;
        for (SegmentStore.Segment segment : queue) {
            bytes += segment.video.length();
            oldest = Math.min(oldest, segment.metadata.optLong("captureEpochMs", System.currentTimeMillis())
                    + segment.metadata.optLong("startUs", 0) / 1000);
        }
        int parts = store.interruptedParts(recording || starting ? session : "");
        String warning = store.warning();
        if (parts > 0) warning += (warning.isEmpty() ? "" : "；")
                + parts + " 个未封口片段已保留，不能自动上传；封口片段可继续补传";
        long latency = prefs.getLong("last_latency_ms", -1);
        long clockSkew = prefs.contains("last_latency_ms") && latency < 0 ? -latency : 0;
        if (clockSkew > 0) warning += (warning.isEmpty() ? "" : "；") + "手机系统时钟发生跳变，延迟数值需重新测量";
        try {
            value.put("recording", recording).put("starting", starting).put("stopping", stopping).put("uploading", uploading)
                    .put("status", stopping ? "正在停止并保存最后片段" : starting ? "正在启动" : recording ? "正在录制" : uploading ? "正在补传" : queue.isEmpty() ? "已停止" : "等待补传")
                    .put("pendingSegments", queue.size()).put("pendingBytes", bytes)
                    .put("cacheBytes", store.totalBytes()).put("cacheLimitBytes", SegmentStore.LIMIT_BYTES)
                    .put("uploadedSegments", prefs.getLong("uploaded_segments", 0)).put("endpoint", endpoint)
                    .put("lastError", error).put("warning", warning).put("interruptedParts", parts)
                    .put("lastUploadLatencyMs", latency).put("clockSkewMs", clockSkew)
                    .put("oldestPendingAgeMs", queue.isEmpty() ? 0 : Math.max(0, System.currentTimeMillis() - oldest))
                    .put("session", session);
        } catch (org.json.JSONException impossible) { throw new IllegalStateException(impossible); }
        return value;
    }

    @Override public IBinder onBind(Intent intent) { return binder; }

    @Override public void onTimeout(int startId, int foregroundServiceType) {
        setError("系统补传时限已到，队列已保存，请打开应用继续上传");
        running = false;
        signal();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    @Override public void onDestroy() {
        running = false;
        signal();
        if (instance == this) instance = null;
        try { connectivity.unregisterNetworkCallback(networkCallback); }
        catch (RuntimeException ignored) { }
        camera.execute(() -> { if (engine != null) engine.stop(); });
        camera.shutdown();
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
}
