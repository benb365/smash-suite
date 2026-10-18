package dev.smash.capture;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.SurfaceTexture;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureFailure;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.AudioTimestamp;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.media.MediaRecorder;
import android.opengl.EGL14;
import android.opengl.EGLConfig;
import android.opengl.EGLContext;
import android.opengl.EGLDisplay;
import android.opengl.EGLSurface;
import android.opengl.GLES11Ext;
import android.opengl.GLES20;
import android.opengl.Matrix;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.SystemClock;
import android.system.Os;
import android.system.OsConstants;
import android.util.Log;
import android.util.Range;
import android.util.Size;
import android.util.SizeF;
import android.view.Surface;

import org.json.JSONObject;

import java.io.File;
import java.io.FileDescriptor;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Camera and microphone live for one session, independently of the Activity's preview surface. */
public final class CaptureEngine {
    public interface Listener {
        boolean canWrite(long nextBytes);
        void onSegment(File file, JSONObject metadata);
        void onError(String message);
        void onRecording();
    }

    private static final String TAG = "SmashCapture";
    private static final int WIDTH = 1920;
    private static final int HEIGHT = 1080;
    private static final int FPS = 30;
    private static final int VIDEO_BIT_RATE = 4_000_000;
    private static final int SAMPLE_RATE = 48_000;
    private static final int AUDIO_BIT_RATE = 128_000;
    private static final int PCM_BYTES_PER_FRAME = 2; // Mono PCM16.
    private static final long SEGMENT_US = 2_000_000;
    private static final long AAC_FRAME_US = 1024L * 1_000_000 / SAMPLE_RATE;
    private static final long MAX_AV_LEAD_US = 3_000_000;
    private static final long MAX_PENDING_BYTES = 8L * 1024 * 1024;
    private static final long MUX_RESERVE_BYTES = 64 * 1024;
    private static final long STOP_TIMEOUT_MS = 8_000;

    private final Context context;
    private final File spool;
    private final Listener listener;
    private final CountDownLatch stopped = new CountDownLatch(1);
    private final ArrayDeque<Sample> videoSamples = new ArrayDeque<>();
    private final ArrayDeque<Sample> audioSamples = new ArrayDeque<>();
    private volatile Handler handler;
    private HandlerThread thread;
    private volatile boolean recording;
    private volatile boolean startCalled;
    private boolean stopping;
    private boolean finished;
    private boolean errorReported;
    private long startMonoUs;
    private long requestedEpochMs;
    private long captureEpochMs;
    private long initializedAtMs;
    private long cameraStartedAtMs;
    private long stoppingAtMs;
    private String session;
    private int sequence;
    private String cameraId;
    private CameraCharacteristics characteristics;
    private CameraDevice camera;
    private CameraCaptureSession cameraSession;
    private MediaCodec videoCodec;
    private MediaCodec audioCodec;
    private MediaFormat videoFormat;
    private MediaFormat audioFormat;
    private Surface encoderSurface;
    private Preview preview;
    private Surface requestedPreview;
    private int orientation;
    private AudioRecord audioRecord;
    private boolean audioStarted;
    private long audioStartedAtMs;
    private long audioBaseUs = -1;
    private long audioSubmittedFrames;
    private boolean audioInputEos;
    private int audioInputIndex = -1;
    private long audioStopUs;
    private boolean videoOutputEos;
    private boolean audioOutputEos;
    private long firstVideoUs = -1;
    private long firstSensorNs = -1;
    private long bootToMonoUs;
    private int timestampSource;
    private long latestVideoUs = -1;
    private long latestAudioUs = -1;
    private long lastVideoStepUs = 1_000_000 / FPS;
    private long lastVideoArrivalMs;
    private long lastAudioArrivalMs;
    private long pendingBytes;
    private long boundaryUs = -1;
    private long syncRequestedAtUs = -1;
    private Segment segment;

    public CaptureEngine(Context context, File spool, Listener listener) {
        this.context = context.getApplicationContext();
        this.spool = spool;
        this.listener = listener;
    }

    /** Call off the main thread. Each engine is used for exactly one recording. */
    public synchronized void start(String session, long captureEpochMs, Surface preview,
                                   int displayRotation) throws Exception {
        if (startCalled) throw new IllegalStateException("采集引擎不能重复启动");
        if (session == null || !session.matches("[A-Za-z0-9_-]{1,96}")) {
            throw new IllegalArgumentException("录像会话名称无效");
        }
        if (context.checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED
                || context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            throw new SecurityException("需要相机和麦克风权限；本次录像不会省略音轨");
        }
        if (!spool.isDirectory() && !spool.mkdirs()) throw new IOException("不能创建录像缓存目录");
        File[] existing = spool.listFiles((dir, name) -> name.startsWith(session + "-"));
        if (existing == null || existing.length != 0) throw new IOException("录像会话已存在或缓存目录不可读");
        startCalled = true;
        this.session = session;
        this.requestedEpochMs = captureEpochMs;
        this.requestedPreview = preview;
        startMonoUs = System.nanoTime() / 1000;
        thread = new HandlerThread("capture-engine");
        thread.start();
        handler = new Handler(thread.getLooper());
        handler.post(() -> {
            try {
                initialize(displayRotation);
                handler.post(tick);
            } catch (Exception e) {
                reportError("采集启动失败：" + diagnostic(e));
                finish();
            }
        });
    }

    /** Surface ownership stays with the caller. Null detaches only the visible preview. */
    public void setPreview(Surface surface) {
        Handler h = handler;
        if (h == null) return;
        h.post(() -> {
            requestedPreview = surface;
            if (!finished && preview != null) preview.setWindow(surface);
        });
    }

    /** Waits for EOS drain and durable final publication; run off the main thread. */
    public void stop() {
        Handler h = handler;
        if (h == null || stopped.getCount() == 0) return;
        if (Looper.myLooper() == h.getLooper()) {
            beginStop();
            return;
        }
        h.post(this::beginStop);
        try {
            if (!stopped.await(STOP_TIMEOUT_MS + 5_000, TimeUnit.MILLISECONDS)) {
                reportError("停止采集等待超时：驱动或存储仍在结束当前录像，请等待完成后再开始新录像");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public boolean isRecording() {
        return recording;
    }

    public boolean isStopped() {
        return !startCalled || stopped.getCount() == 0;
    }

    private void initialize(int displayRotation) throws Exception {
        if (!listener.canWrite(MAX_PENDING_BYTES + MUX_RESERVE_BYTES)) {
            throw new IOException("本地缓存达到上限或剩余空间不足，请先上传缓存");
        }
        initializedAtMs = SystemClock.elapsedRealtime();
        CameraManager manager = (CameraManager) context.getSystemService(Context.CAMERA_SERVICE);
        selectCamera(manager);
        Integer sensor = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION);
        if (sensor == null) throw new IOException("相机未提供传感器方向");
        int degrees;
        switch (displayRotation) {
            case Surface.ROTATION_0: degrees = 0; break;
            case Surface.ROTATION_90: degrees = 90; break;
            case Surface.ROTATION_180: degrees = 180; break;
            case Surface.ROTATION_270: degrees = 270; break;
            default: throw new IOException("屏幕旋转信息无效");
        }
        orientation = (sensor - degrees + 360) % 360;
        // MPEG-TS/HLS and raw-frame analysis cannot rely on an MP4 display-rotation hint.
        // Keep the encoded pixels upright without adding a video re-encoding stage.
        if (orientation != 0) {
            throw new IOException("请将手机换到另一侧横屏后重试，以统一录像和在线播放的方向"
                    + "（传感器方向=" + sensor + "，屏幕方向=" + degrees + "）");
        }
        Integer source = characteristics.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE);
        timestampSource = source == null ? CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_UNKNOWN : source;
        bootToMonoUs = (SystemClock.elapsedRealtimeNanos() - System.nanoTime()) / 1000;
        if (timestampSource == CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_UNKNOWN) {
            Log.w(TAG, "相机时间源为UNKNOWN；按Android规定与MONOTONIC音频同步，必须真机检查音画同步");
        }

        MediaFormat video = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, WIDTH, HEIGHT);
        video.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
        video.setInteger(MediaFormat.KEY_BIT_RATE, VIDEO_BIT_RATE);
        video.setInteger(MediaFormat.KEY_FRAME_RATE, FPS);
        video.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 2);
        video.setInteger(MediaFormat.KEY_PROFILE, MediaCodecInfo.CodecProfileLevel.AVCProfileBaseline);
        if (Build.VERSION.SDK_INT >= 29) video.setInteger(MediaFormat.KEY_MAX_B_FRAMES, 0);
        String videoName = chooseVideoEncoder(video);
        videoCodec = MediaCodec.createByCodecName(videoName);
        videoCodec.configure(video, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        encoderSurface = videoCodec.createInputSurface();
        videoCodec.start();

        MediaFormat audio = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, SAMPLE_RATE, 1);
        audio.setInteger(MediaFormat.KEY_BIT_RATE, AUDIO_BIT_RATE);
        audio.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC);
        audio.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 4096);
        String audioName = new MediaCodecList(MediaCodecList.REGULAR_CODECS).findEncoderForFormat(audio);
        if (audioName == null) throw new IOException("设备不支持AAC-LC 48kHz单声道128kbps编码");
        audioCodec = MediaCodec.createByCodecName(audioName);
        audioCodec.configure(audio, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        audioCodec.start();
        int min = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
        if (min <= 0) throw new IOException("设备麦克风不支持48kHz单声道PCM16录音");
        audioRecord = new AudioRecord(MediaRecorder.AudioSource.CAMCORDER, SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                Math.max(min * 4, SAMPLE_RATE * PCM_BYTES_PER_FRAME * 2));
        if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED || audioRecord.getSampleRate() != SAMPLE_RATE) {
            throw new IOException("麦克风初始化失败，不能按指定规格录音");
        }

        StreamConfigurationMap map = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
        Size previewSize = choosePreviewSize(map);
        preview = new Preview(previewSize, orientation, handler);
        preview.setWindow(requestedPreview);
        Log.i(TAG, "camera=" + cameraId + " video=" + videoName + " audio=" + audioName
                + " sensor=" + sensor + " rotation=" + degrees + " preview=" + previewSize
                + " timestampSource=" + timestampSource + " bootToMonoUs=" + bootToMonoUs);
        manager.openCamera(cameraId, new CameraDevice.StateCallback() {
            @Override public void onOpened(CameraDevice device) {
                if (stopping || finished) { device.close(); return; }
                camera = device;
                configureCamera();
            }
            @Override public void onDisconnected(CameraDevice device) {
                device.close();
                fail("相机断开连接，已停止本次录像");
            }
            @Override public void onError(CameraDevice device, int error) {
                device.close();
                fail("相机错误 " + error + "，已停止本次录像");
            }
        }, handler);
    }

    private void selectCamera(CameraManager manager) throws Exception {
        double bestArea = -1;
        for (String id : manager.getCameraIdList()) {
            CameraCharacteristics c = manager.getCameraCharacteristics(id);
            Integer facing = c.get(CameraCharacteristics.LENS_FACING);
            if (facing == null || facing != CameraCharacteristics.LENS_FACING_BACK) continue;
            // The largest physical sensor selects the main rear camera over macro/ultrawide modules.
            SizeF physical = c.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
            double area = physical == null ? 0 : physical.getWidth() * physical.getHeight();
            if (cameraId == null || area > bestArea) {
                cameraId = id;
                characteristics = c;
                bestArea = area;
            }
        }
        if (cameraId == null) throw new IOException("未找到后置摄像头");
        StreamConfigurationMap map = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
        Size wanted = new Size(WIDTH, HEIGHT);
        if (map == null || map.getOutputSizes(MediaCodec.class) == null
                || !Arrays.asList(map.getOutputSizes(MediaCodec.class)).contains(wanted)) {
            throw new IOException("后置主摄不支持1920×1080编码输出；不会自动降低画质");
        }
        Range<Integer>[] ranges = characteristics.get(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES);
        if (ranges == null || !Arrays.asList(ranges).contains(new Range<>(FPS, FPS))) {
            throw new IOException("后置主摄没有固定30fps模式，支持范围=" + Arrays.toString(ranges));
        }
        long duration = map.getOutputMinFrameDuration(MediaCodec.class, wanted);
        if (duration > 1_000_000_000L / FPS + 1) throw new IOException("后置主摄1080p最大帧率不足30fps");
    }

    private static String chooseVideoEncoder(MediaFormat format) throws IOException {
        for (MediaCodecInfo info : new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()) {
            if (!info.isEncoder()) continue;
            String name = info.getName().toLowerCase(Locale.US);
            boolean hardware = Build.VERSION.SDK_INT >= 29 ? info.isHardwareAccelerated()
                    : !name.startsWith("omx.google.") && !name.startsWith("c2.android.") && !name.contains(".sw.");
            if (!hardware) continue;
            for (String type : info.getSupportedTypes()) {
                if (!MediaFormat.MIMETYPE_VIDEO_AVC.equalsIgnoreCase(type)) continue;
                MediaCodecInfo.CodecCapabilities caps = info.getCapabilitiesForType(type);
                boolean surface = false;
                boolean baseline = false;
                for (int color : caps.colorFormats) surface |= color == MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface;
                for (MediaCodecInfo.CodecProfileLevel profile : caps.profileLevels) {
                    baseline |= profile.profile == MediaCodecInfo.CodecProfileLevel.AVCProfileBaseline;
                }
                MediaCodecInfo.VideoCapabilities vc = caps.getVideoCapabilities();
                if (surface && baseline && vc != null && vc.areSizeAndRateSupported(WIDTH, HEIGHT, FPS)
                        && vc.getBitrateRange().contains(VIDEO_BIT_RATE) && caps.isFormatSupported(format)) {
                    return info.getName();
                }
            }
        }
        throw new IOException("未找到支持1080p/30fps、4Mbps、H.264 Baseline的硬件编码器");
    }

    private static Size choosePreviewSize(StreamConfigurationMap map) throws IOException {
        Size[] sizes = map.getOutputSizes(SurfaceTexture.class);
        if (sizes == null || sizes.length == 0) throw new IOException("相机不支持独立预览输出");
        for (Size size : sizes) if (size.getWidth() == 1280 && size.getHeight() == 720) return size;
        for (Size size : sizes) if (size.getWidth() == WIDTH && size.getHeight() == HEIGHT) return size;
        throw new IOException("相机缺少720p或1080p预览输出，不能保证录制与预览共存");
    }

    private void configureCamera() {
        try {
            camera.createCaptureSession(Arrays.asList(encoderSurface, preview.cameraSurface),
                    new CameraCaptureSession.StateCallback() {
                @Override public void onConfigured(CameraCaptureSession configured) {
                    if (stopping || finished) { configured.close(); return; }
                    cameraSession = configured;
                    try {
                        CaptureRequest.Builder request = camera.createCaptureRequest(CameraDevice.TEMPLATE_RECORD);
                        request.addTarget(encoderSurface);
                        request.addTarget(preview.cameraSurface);
                        request.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, new Range<>(FPS, FPS));
                        int[] af = characteristics.get(CameraCharacteristics.CONTROL_AF_AVAILABLE_MODES);
                        if (af != null) for (int mode : af) {
                            if (mode == CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_VIDEO) {
                                request.set(CaptureRequest.CONTROL_AF_MODE, mode);
                                break;
                            }
                        }
                        configured.setRepeatingRequest(request.build(), cameraCallback, handler);
                        cameraStartedAtMs = SystemClock.elapsedRealtime();
                    } catch (Exception e) { fail("不能启动连续采集：" + diagnostic(e)); }
                }
                @Override public void onConfigureFailed(CameraCaptureSession configured) {
                    configured.close();
                    fail("相机不支持1080p/30fps编码与预览的组合，未降低录制规格");
                }
            }, handler);
        } catch (Exception e) { fail("不能配置相机：" + diagnostic(e)); }
    }

    private final CameraCaptureSession.CaptureCallback cameraCallback = new CameraCaptureSession.CaptureCallback() {
        @Override public void onCaptureStarted(CameraCaptureSession session, CaptureRequest request,
                                                long timestamp, long frameNumber) {
            if (firstSensorNs < 0) firstSensorNs = timestamp;
        }
        @Override public void onCaptureFailed(CameraCaptureSession session, CaptureRequest request,
                                               CaptureFailure failure) {
            if (!stopping && !finished) fail("相机采集帧失败，原因=" + failure.getReason());
        }
        @Override public void onCaptureBufferLost(CameraCaptureSession session, CaptureRequest request,
                                                   Surface target, long frameNumber) {
            if (!stopping && !finished && target == encoderSurface) fail("相机编码输出丢帧，帧号=" + frameNumber);
        }
    };

    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (finished) return;
            try {
                long now = SystemClock.elapsedRealtime();
                if (!stopping) {
                    // Reserve bounded encoder/queue output before admitting more input. The final
                    // drain can then save those bytes even when the user-visible cache limit is near.
                    if (!listener.canWrite(MAX_PENDING_BYTES + MUX_RESERVE_BYTES)) {
                        fail("本地缓存达到上限或空间不足，已停止录制并保留待上传片段");
                    }
                    if (cameraStartedAtMs == 0 && now - initializedAtMs > 10_000) fail("相机启动超时");
                    if (cameraStartedAtMs != 0 && firstVideoUs < 0 && now - cameraStartedAtMs > 5_000) {
                        fail("相机没有产生编码视频帧");
                    }
                    if (recording && (now - lastVideoArrivalMs > 3_000 || now - lastAudioArrivalMs > 3_000)) {
                        fail("音视频编码输出中断，已停止本次录像");
                    }
                }
                drain(videoCodec, true);
                feedAudio();
                drain(audioCodec, false);
                processSamples(false);
                if (stopping && videoOutputEos && audioOutputEos) { finish(); return; }
                if (stopping && now - stoppingAtMs > STOP_TIMEOUT_MS) {
                    reportError("编码器停止排空超时，已保存可封口片段；未封口.part保留在本地");
                    finish();
                    return;
                }
            } catch (Exception e) {
                reportError("采集失败：" + diagnostic(e));
                beginStop();
                finish();
                return;
            }
            handler.postDelayed(this, 5);
        }
    };

    private void feedAudio() throws Exception {
        if (audioCodec == null || audioInputEos) return;
        if (stopping && !audioStarted) {
            endAudioInput();
            return;
        }
        if (!audioStarted) return;
        AudioTimestamp stamp = new AudioTimestamp();
        if (audioRecord.getTimestamp(stamp, AudioTimestamp.TIMEBASE_MONOTONIC) == AudioRecord.SUCCESS
                && stamp.nanoTime > 0 && stamp.framePosition >= 0) {
            long base = stamp.nanoTime / 1000 - stamp.framePosition * 1_000_000 / SAMPLE_RATE;
            if (audioBaseUs < 0) {
                audioBaseUs = base;
                long delta = base - firstVideoUs;
                if (delta < -AAC_FRAME_US || delta > 1_000_000) {
                    throw new IOException("麦克风与视频时间源不一致，初始偏移=" + delta + "µs");
                }
                Log.i(TAG, "audio clock=MONOTONIC, first audio-video offsetUs=" + delta);
            } else if (Math.abs(base - audioBaseUs) > 100_000) {
                throw new IOException("麦克风时钟发生跳变，偏移=" + (base - audioBaseUs) + "µs");
            }
        }
        if (audioBaseUs < 0) {
            if (SystemClock.elapsedRealtime() - audioStartedAtMs > 1_000) {
                throw new IOException("麦克风未提供单调时钟时间戳，不能保证音画同步");
            }
            return;
        }
        for (int count = 0; count < 8; count++) {
            long remainingFrames = stopping
                    ? Math.max(0, (audioStopUs - audioBaseUs) * SAMPLE_RATE / 1_000_000 - audioSubmittedFrames)
                    : Long.MAX_VALUE;
            if (remainingFrames == 0) {
                audioRecord.stop();
                audioStarted = false;
                endAudioInput();
                return;
            }
            if (audioInputIndex < 0) audioInputIndex = audioCodec.dequeueInputBuffer(0);
            if (audioInputIndex < 0) return;
            ByteBuffer input = audioCodec.getInputBuffer(audioInputIndex);
            if (input == null) throw new IOException("AAC编码器输入缓冲区为空");
            input.clear();
            int wanted = Math.min(input.capacity(), 2048) / PCM_BYTES_PER_FRAME * PCM_BYTES_PER_FRAME;
            wanted = (int) Math.min(wanted, Math.min(remainingFrames, 2048) * PCM_BYTES_PER_FRAME);
            int read = audioRecord.read(input, wanted, AudioRecord.READ_NON_BLOCKING);
            if (read < 0) throw new IOException("麦克风读取失败，错误=" + read);
            if (read % PCM_BYTES_PER_FRAME != 0) throw new IOException("麦克风返回了不完整PCM采样");
            // Hold a dequeued input across polls instead of sending empty buffers with repeated PTS.
            if (read == 0) return;
            audioCodec.queueInputBuffer(audioInputIndex, 0, read, audioTime(audioSubmittedFrames), 0);
            audioInputIndex = -1;
            audioSubmittedFrames += read / PCM_BYTES_PER_FRAME;
        }
    }

    private void endAudioInput() {
        if (audioInputIndex < 0) audioInputIndex = audioCodec.dequeueInputBuffer(0);
        if (audioInputIndex >= 0) {
            long pts = audioBaseUs < 0 ? System.nanoTime() / 1000 : audioTime(audioSubmittedFrames);
            audioCodec.queueInputBuffer(audioInputIndex, 0, 0, pts, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
            audioInputIndex = -1;
            audioInputEos = true;
        }
    }

    private long audioTime(long frames) {
        return audioBaseUs + frames * 1_000_000 / SAMPLE_RATE;
    }

    private void drain(MediaCodec codec, boolean video) throws Exception {
        if (codec == null || (video ? videoOutputEos : audioOutputEos)) return;
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        for (int count = 0; count < 32; count++) {
            int index = codec.dequeueOutputBuffer(info, 0);
            if (index == MediaCodec.INFO_TRY_AGAIN_LATER) return;
            if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                if (video ? videoFormat != null : audioFormat != null) {
                    throw new IOException("录像过程中编码格式变化，不能安全续接片段");
                }
                if (video) videoFormat = codec.getOutputFormat(); else audioFormat = codec.getOutputFormat();
                continue;
            }
            if (index < 0) continue;
            try {
                if (info.size > 0 && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
                    ByteBuffer output = codec.getOutputBuffer(index);
                    if (output == null) throw new IOException("编码输出缓冲区为空");
                    output.position(info.offset);
                    output.limit(info.offset + info.size);
                    byte[] bytes = new byte[info.size];
                    output.get(bytes);
                    acceptSample(new Sample(video, bytes, info.presentationTimeUs,
                            info.flags & ~MediaCodec.BUFFER_FLAG_END_OF_STREAM));
                }
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                    if (video) videoOutputEos = true; else audioOutputEos = true;
                    return;
                }
            } finally { codec.releaseOutputBuffer(index, false); }
        }
    }

    private void acceptSample(Sample sample) throws Exception {
        long now = SystemClock.elapsedRealtime();
        long latest = sample.video ? latestVideoUs : latestAudioUs;
        if (sample.ptsUs <= latest) throw new IOException((sample.video ? "视频" : "音频") + "编码时间戳未单调递增");
        if (sample.video) {
            if (firstVideoUs < 0) {
                if (!sample.keyframe()) throw new IOException("视频首帧不是可独立解码的关键帧");
                long monoNow = System.nanoTime() / 1000;
                if (Math.abs(monoNow - sample.ptsUs) > 5_000_000) {
                    throw new IOException("视频编码时间戳未采用MONOTONIC时钟，无法同步录音");
                }
                if (firstSensorNs >= 0) {
                    // Camera2 converts REALTIME sensor timestamps to MONOTONIC for encoder
                    // surfaces. Never subtract bootToMonoUs from the already converted codec PTS.
                    long expected = firstSensorNs / 1000;
                    if (timestampSource == CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME) expected -= bootToMonoUs;
                    long delta = sample.ptsUs - expected;
                    Log.i(TAG, "first encoder-sensor offsetUs=" + delta);
                    if (Math.abs(delta) > 250_000) throw new IOException("相机与编码器时间基准不一致，偏移=" + delta + "µs");
                } else {
                    Log.w(TAG, "视频首帧先于Camera2回调，已校验MONOTONIC范围；需真机验证同步");
                }
                firstVideoUs = sample.ptsUs;
                captureEpochMs = requestedEpochMs + (firstVideoUs - startMonoUs) / 1000;
                // Start audio after the first video frame so no pre-video AAC packet is silently
                // discarded to make timestamps nonnegative. The initial audio offset is retained.
                if (!stopping) {
                    audioRecord.startRecording();
                    if (audioRecord.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                        throw new IOException("麦克风无法开始录音");
                    }
                    audioStarted = true;
                    audioStartedAtMs = now;
                    lastAudioArrivalMs = now;
                    recording = true;
                    listener.onRecording();
                }
            }
            if (latestVideoUs >= 0) lastVideoStepUs = sample.ptsUs - latestVideoUs;
            latestVideoUs = sample.ptsUs;
            lastVideoArrivalMs = now;
            videoSamples.add(sample);
        } else {
            if (firstVideoUs < 0 || sample.ptsUs < firstVideoUs) {
                throw new IOException("音频时间戳早于会话视频起点，无法无损归零");
            }
            latestAudioUs = sample.ptsUs;
            lastAudioArrivalMs = now;
            audioSamples.add(sample);
        }
        pendingBytes += sample.bytes.length;
        if (pendingBytes > MAX_PENDING_BYTES) throw new IOException("音视频等待队列达到8MiB上限，已停止采集");
        if (!stopping && latestVideoUs >= 0 && latestAudioUs >= 0
                && Math.abs(latestVideoUs - latestAudioUs) > MAX_AV_LEAD_US) {
            fail("音视频输出相差超过3秒，已停止采集并保存现有片段");
        }
    }

    private void processSamples(boolean finalDrain) throws Exception {
        if (videoFormat == null || audioFormat == null || firstVideoUs < 0) return;
        if (segment == null) {
            if (videoSamples.isEmpty()) return;
            Sample first = videoSamples.peek();
            if (!first.keyframe()) throw new IOException("新片段未从关键帧开始");
            segment = new Segment(first.ptsUs);
        }
        while (true) {
            if (boundaryUs < 0) for (Sample sample : videoSamples) {
                if (sample.keyframe() && sample.ptsUs - segment.startUs >= SEGMENT_US - 1_000_000 / FPS / 2) {
                    boundaryUs = sample.ptsUs;
                    break;
                }
            }
            // If stop lands just after an IDR but before the next AAC packet, keep that final
            // IDR in the preceding file rather than creating an audio-less final fragment.
            if (finalDrain && boundaryUs >= 0 && latestAudioUs < boundaryUs) boundaryUs = -1;
            long horizon = finalDrain ? Long.MAX_VALUE : Math.min(latestVideoUs, latestAudioUs) + 1;
            if (boundaryUs >= 0) horizon = Math.min(horizon, boundaryUs);
            while (true) {
                Sample v = videoSamples.peek();
                Sample a = audioSamples.peek();
                Sample next = v == null ? a : a == null || v.ptsUs <= a.ptsUs ? v : a;
                if (next == null || next.ptsUs >= horizon) break;
                segment.write(next);
                if (next.video) videoSamples.remove(); else audioSamples.remove();
                pendingBytes -= next.bytes.length;
            }
            if (boundaryUs >= 0 && (finalDrain || latestAudioUs >= boundaryUs)) {
                long nextStart = boundaryUs;
                segment.publish(nextStart, false);
                segment = null;
                boundaryUs = -1;
                syncRequestedAtUs = -1;
                if (videoSamples.isEmpty()) throw new IOException("片段边界缺少视频关键帧");
                segment = new Segment(nextStart);
                continue;
            }
            if (!stopping && latestVideoUs - segment.startUs >= SEGMENT_US && syncRequestedAtUs < 0) {
                Bundle params = new Bundle();
                params.putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME, 0);
                videoCodec.setParameters(params);
                syncRequestedAtUs = latestVideoUs;
            }
            if (!stopping && latestVideoUs - segment.startUs > SEGMENT_US * 3) {
                fail("H.264编码器未按要求生成关键帧，已停止采集");
            }
            return;
        }
    }

    private void fail(String message) {
        if (finished) return;
        reportError(message);
        beginStop();
    }

    private void reportError(String message) {
        Log.e(TAG, message);
        if (errorReported) return;
        errorReported = true;
        try { listener.onError(message); } catch (RuntimeException e) { Log.e(TAG, "采集错误回调失败", e); }
    }

    private void beginStop() {
        if (finished || stopping) return;
        stopping = true;
        recording = false;
        stoppingAtMs = SystemClock.elapsedRealtime();
        audioStopUs = System.nanoTime() / 1000;
        if (cameraSession != null) {
            try { cameraSession.stopRepeating(); } catch (Exception e) { Log.w(TAG, "停止相机请求失败", e); }
            cameraSession.close();
            cameraSession = null;
        }
        if (camera != null) { camera.close(); camera = null; }
        // Keep draining microphone samples through this stop instant before queuing AAC EOS.
        // Stopping AudioRecord here could discard PCM already waiting in its native ring buffer.
        if (videoCodec != null) {
            try { videoCodec.signalEndOfInputStream(); }
            catch (RuntimeException e) { videoOutputEos = true; reportError("视频编码器不能正常结束：" + diagnostic(e)); }
        } else videoOutputEos = true;
        if (audioCodec == null) audioOutputEos = true;
    }

    private void finish() {
        if (finished) return;
        beginStop();
        try {
            processSamples(true);
            if (segment != null) {
                long end = latestVideoUs + Math.max(1, lastVideoStepUs);
                segment.publish(end, true);
                segment = null;
            } else if (firstVideoUs >= 0) {
                reportError("缺少完整音视频编码格式，当前录像无法封口；已完成片段仍可上传");
            }
        } catch (Exception e) {
            reportError("当前片段未封口，.part保留用于排查：" + diagnostic(e));
        } finally {
            finished = true;
            recording = false;
            if (segment != null) segment.releaseUnpublished();
            releaseCodec(videoCodec);
            releaseCodec(audioCodec);
            if (audioRecord != null) {
                try {
                    if (audioRecord.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) audioRecord.stop();
                    audioRecord.release();
                } catch (RuntimeException e) { Log.w(TAG, "释放麦克风失败", e); }
            }
            if (encoderSurface != null) encoderSurface.release();
            try {
                if (preview != null) preview.release();
            } catch (RuntimeException e) { Log.w(TAG, "释放预览失败", e); }
            finally {
                videoSamples.clear();
                audioSamples.clear();
                pendingBytes = 0;
                stopped.countDown();
                thread.quitSafely();
            }
        }
    }

    private static void releaseCodec(MediaCodec codec) {
        if (codec == null) return;
        try { codec.stop(); } catch (RuntimeException e) { Log.w(TAG, "停止编码器失败", e); }
        try { codec.release(); } catch (RuntimeException e) { Log.w(TAG, "释放编码器失败", e); }
    }

    private static String diagnostic(Exception e) {
        return e.getClass().getSimpleName() + (e.getMessage() == null ? "" : ": " + e.getMessage());
    }

    private static final class Sample {
        final boolean video;
        final byte[] bytes;
        final long ptsUs;
        final int flags;
        Sample(boolean video, byte[] bytes, long ptsUs, int flags) {
            this.video = video;
            this.bytes = bytes;
            this.ptsUs = ptsUs;
            this.flags = flags;
        }
        boolean keyframe() { return (flags & MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0; }
    }

    private final class Segment {
        final long startUs;
        final String base;
        final File part;
        final FileOutputStream output;
        MediaMuxer muxer;
        final int videoTrack;
        final int audioTrack;
        long lastVideo = -1;
        long lastAudio = -1;
        int videoCount;
        boolean closed;

        Segment(long startUs) throws Exception {
            if (!listener.canWrite(MUX_RESERVE_BYTES)) throw new IOException("缓存空间不足，无法创建视频片段");
            this.startUs = startUs;
            base = String.format(Locale.US, "%s-%06d", session, sequence);
            part = new File(spool, base + ".mp4.part");
            if (part.exists()) throw new IOException("片段文件已经存在：" + part.getName());
            output = new FileOutputStream(part);
            MediaMuxer created = null;
            try {
                created = new MediaMuxer(output.getFD(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
                created.setOrientationHint(orientation);
                videoTrack = created.addTrack(videoFormat);
                audioTrack = created.addTrack(audioFormat);
                created.start();
                muxer = created;
            } catch (Exception e) {
                if (created != null) created.release();
                output.close();
                throw e;
            }
        }

        void write(Sample sample) throws Exception {
            if (sample.ptsUs < startUs) throw new IOException("片段样本时间戳早于公共起点");
            if (!listener.canWrite(sample.bytes.length + MUX_RESERVE_BYTES)) {
                throw new IOException("写入片段时缓存空间耗尽，已保留未封口文件");
            }
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            info.set(0, sample.bytes.length, sample.ptsUs - startUs, sample.flags);
            muxer.writeSampleData(sample.video ? videoTrack : audioTrack, ByteBuffer.wrap(sample.bytes), info);
            if (sample.video) { lastVideo = sample.ptsUs; videoCount++; } else lastAudio = sample.ptsUs;
        }

        void publish(long endUs, boolean finalSegment) throws Exception {
            if (lastVideo < 0 || lastAudio < 0) throw new IOException("片段缺少视频或录音，不会发布不完整录像");
            if (endUs <= lastVideo) throw new IOException("视频片段结束时间无效");
            if (endUs - startUs > SEGMENT_US * 3) {
                throw new IOException("关键帧间隔超过6秒，当前.part保留且不上传");
            }
            MediaCodec.BufferInfo eos = new MediaCodec.BufferInfo();
            // An explicit empty EOS gives the final video frame its true duration, rather than
            // letting MediaMuxer infer it from an unrelated audio packet or a previous frame.
            eos.set(0, 0, endUs - startUs, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
            muxer.writeSampleData(videoTrack, ByteBuffer.allocate(0), eos);
            // AAC access units cannot be split at arbitrary video keyframes. Each packet belongs
            // to exactly one segment by its PTS; at most 21.334ms can extend beyond video endUs.
            // Consumers must concatenate using metadata's video timeline, not container duration.
            eos.set(0, 0, lastAudio + AAC_FRAME_US - startUs, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
            muxer.writeSampleData(audioTrack, ByteBuffer.allocate(0), eos);
            muxer.stop();
            muxer.release();
            muxer = null;
            output.getFD().sync();
            output.close();
            closed = true;
            File file = new File(spool, base + ".mp4");
            Os.rename(part.getAbsolutePath(), file.getAbsolutePath());
            JSONObject metadata = new JSONObject();
            metadata.put("session", session);
            metadata.put("sequence", sequence);
            metadata.put("startUs", startUs - firstVideoUs);
            metadata.put("endUs", endUs - firstVideoUs);
            metadata.put("captureEpochMs", captureEpochMs);
            metadata.put("sha256", sha256(file));
            metadata.put("final", finalSegment);
            File jsonPart = new File(spool, base + ".json.part");
            try (FileOutputStream json = new FileOutputStream(jsonPart)) {
                json.write(metadata.toString().getBytes(StandardCharsets.UTF_8));
                json.getFD().sync();
            }
            Os.rename(jsonPart.getAbsolutePath(), new File(spool, base + ".json").getAbsolutePath());
            FileDescriptor directory = Os.open(spool.getAbsolutePath(), OsConstants.O_RDONLY, 0);
            try { Os.fsync(directory); } finally { Os.close(directory); }
            sequence++;
            Log.i(TAG, "saved=" + file.getName() + " videoDurationUs=" + (endUs - startUs)
                    + " videoFrames=" + videoCount + " measuredFps=" + (videoCount * 1_000_000d / (endUs - startUs))
                    + " bytes=" + file.length() + " pendingBytes=" + pendingBytes);
            try { listener.onSegment(file, metadata); }
            catch (RuntimeException e) { fail("片段保存回调失败，文件仍可恢复上传：" + diagnostic(e)); }
        }

        void releaseUnpublished() {
            if (muxer != null) {
                try { muxer.release(); } catch (RuntimeException e) { Log.w(TAG, "释放未封口片段失败", e); }
                muxer = null;
            }
            if (!closed) try { output.getFD().sync(); output.close(); }
            catch (IOException e) { Log.w(TAG, "保存未封口片段失败", e); }
        }
    }

    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[64 * 1024];
        try (FileInputStream input = new FileInputStream(file)) {
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder hex = new StringBuilder(64);
        for (byte value : digest.digest()) hex.append(String.format(Locale.US, "%02x", value & 0xff));
        return hex.toString();
    }

    /** Permanent camera output; swapping the Activity window never reconfigures the camera. */
    private final class Preview {
        SurfaceTexture texture;
        Surface cameraSurface;
        EGLDisplay display = EGL14.EGL_NO_DISPLAY;
        EGLContext glContext = EGL14.EGL_NO_CONTEXT;
        EGLConfig config;
        EGLSurface pbuffer = EGL14.EGL_NO_SURFACE;
        int program;
        int textureId;
        final int rotation;
        final Size size;
        final FloatBuffer positions = floats(-1, -1, 1, -1, -1, 1, 1, 1);
        final FloatBuffer coordinates = floats(0, 0, 1, 0, 0, 1, 1, 1);
        final float[] textureMatrix = new float[16];
        final float[] geometryMatrix = new float[16];
        EGLSurface window = EGL14.EGL_NO_SURFACE;

        Preview(Size size, int rotation, Handler handler) throws IOException {
            this.size = size;
            this.rotation = rotation;
            try { initialize(handler); }
            catch (IOException | RuntimeException e) {
                release();
                throw e;
            }
        }

        private void initialize(Handler handler) throws IOException {
            display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
            int[] version = new int[2];
            if (display == EGL14.EGL_NO_DISPLAY || !EGL14.eglInitialize(display, version, 0, version, 1)) {
                throw new IOException("OpenGL预览初始化失败");
            }
            EGLConfig[] configs = new EGLConfig[1];
            int[] count = new int[1];
            int[] attrs = {EGL14.EGL_RED_SIZE, 8, EGL14.EGL_GREEN_SIZE, 8, EGL14.EGL_BLUE_SIZE, 8,
                    EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT,
                    EGL14.EGL_SURFACE_TYPE, EGL14.EGL_WINDOW_BIT | EGL14.EGL_PBUFFER_BIT, EGL14.EGL_NONE};
            if (!EGL14.eglChooseConfig(display, attrs, 0, configs, 0, 1, count, 0) || count[0] == 0) {
                throw new IOException("设备没有可用的OpenGL ES2预览配置");
            }
            config = configs[0];
            glContext = EGL14.eglCreateContext(display, config, EGL14.EGL_NO_CONTEXT,
                    new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE}, 0);
            pbuffer = EGL14.eglCreatePbufferSurface(display, config,
                    new int[]{EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE}, 0);
            if (glContext == EGL14.EGL_NO_CONTEXT || pbuffer == EGL14.EGL_NO_SURFACE
                    || !EGL14.eglMakeCurrent(display, pbuffer, pbuffer, glContext)) {
                throw new IOException("设备不能创建独立的相机预览上下文");
            }
            int[] ids = new int[1];
            GLES20.glGenTextures(1, ids, 0);
            textureId = ids[0];
            GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, textureId);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
            program = GLES20.glCreateProgram();
            int vertex = shader(GLES20.GL_VERTEX_SHADER, "attribute vec4 p; attribute vec4 t; uniform mat4 g; uniform mat4 m; varying vec2 uv; void main(){gl_Position=g*p;uv=(m*t).xy;}");
            int fragment = shader(GLES20.GL_FRAGMENT_SHADER, "#extension GL_OES_EGL_image_external : require\nprecision mediump float; varying vec2 uv; uniform samplerExternalOES s; void main(){gl_FragColor=texture2D(s,uv);}");
            GLES20.glAttachShader(program, vertex);
            GLES20.glAttachShader(program, fragment);
            GLES20.glLinkProgram(program);
            GLES20.glDeleteShader(vertex);
            GLES20.glDeleteShader(fragment);
            int[] linked = new int[1];
            GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, linked, 0);
            if (linked[0] == 0) throw new IOException("OpenGL预览着色器连接失败：" + GLES20.glGetProgramInfoLog(program));
            texture = new SurfaceTexture(textureId);
            texture.setDefaultBufferSize(size.getWidth(), size.getHeight());
            cameraSurface = new Surface(texture);
            texture.setOnFrameAvailableListener(ignored -> {
                if (finished) return;
                try {
                    EGL14.eglMakeCurrent(display, pbuffer, pbuffer, glContext);
                    texture.updateTexImage();
                    if (window != EGL14.EGL_NO_SURFACE) draw();
                } catch (RuntimeException e) {
                    fail("相机预览缓冲区读取失败：" + diagnostic(e));
                }
            }, handler);
        }

        void setWindow(Surface surface) {
            EGL14.eglMakeCurrent(display, pbuffer, pbuffer, glContext);
            if (window != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(display, window);
            window = EGL14.EGL_NO_SURFACE;
            if (surface != null && surface.isValid()) {
                try {
                    window = EGL14.eglCreateWindowSurface(display, config, surface, new int[]{EGL14.EGL_NONE}, 0);
                    if (window == EGL14.EGL_NO_SURFACE) Log.w(TAG, "显示预览连接失败，录制继续，EGL=" + EGL14.eglGetError());
                } catch (RuntimeException e) { Log.w(TAG, "显示预览连接失败，录制继续", e); }
            }
        }

        void draw() {
            if (!EGL14.eglMakeCurrent(display, window, window, glContext)) { detachWindow(); return; }
            int[] width = new int[1];
            int[] height = new int[1];
            EGL14.eglQuerySurface(display, window, EGL14.EGL_WIDTH, width, 0);
            EGL14.eglQuerySurface(display, window, EGL14.EGL_HEIGHT, height, 0);
            if (width[0] <= 0 || height[0] <= 0) { detachWindow(); return; }
            GLES20.glViewport(0, 0, width[0], height[0]);
            GLES20.glClearColor(0, 0, 0, 1);
            GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);
            Matrix.setIdentityM(geometryMatrix, 0);
            float imageRatio = (float) size.getWidth() / size.getHeight();
            float windowRatio = (float) width[0] / height[0];
            if (windowRatio > imageRatio) Matrix.scaleM(geometryMatrix, 0, imageRatio / windowRatio, 1, 1);
            else Matrix.scaleM(geometryMatrix, 0, 1, windowRatio / imageRatio, 1);
            Matrix.rotateM(geometryMatrix, 0, rotation, 0, 0, 1);
            texture.getTransformMatrix(textureMatrix);
            GLES20.glUseProgram(program);
            int position = GLES20.glGetAttribLocation(program, "p");
            int coordinate = GLES20.glGetAttribLocation(program, "t");
            GLES20.glEnableVertexAttribArray(position);
            GLES20.glEnableVertexAttribArray(coordinate);
            GLES20.glVertexAttribPointer(position, 2, GLES20.GL_FLOAT, false, 0, positions);
            GLES20.glVertexAttribPointer(coordinate, 2, GLES20.GL_FLOAT, false, 0, coordinates);
            GLES20.glUniformMatrix4fv(GLES20.glGetUniformLocation(program, "g"), 1, false, geometryMatrix, 0);
            GLES20.glUniformMatrix4fv(GLES20.glGetUniformLocation(program, "m"), 1, false, textureMatrix, 0);
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
            GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, textureId);
            GLES20.glUniform1i(GLES20.glGetUniformLocation(program, "s"), 0);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
            GLES20.glDisableVertexAttribArray(position);
            GLES20.glDisableVertexAttribArray(coordinate);
            if (!EGL14.eglSwapBuffers(display, window)) detachWindow();
            else EGL14.eglMakeCurrent(display, pbuffer, pbuffer, glContext);
        }

        void detachWindow() {
            Log.i(TAG, "显示预览窗口不可用，后台录制继续");
            EGL14.eglMakeCurrent(display, pbuffer, pbuffer, glContext);
            if (window != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(display, window);
            window = EGL14.EGL_NO_SURFACE;
        }

        void release() {
            if (texture != null) texture.setOnFrameAvailableListener(null);
            if (display == EGL14.EGL_NO_DISPLAY) return;
            if (glContext != EGL14.EGL_NO_CONTEXT) EGL14.eglMakeCurrent(display, pbuffer, pbuffer, glContext);
            if (cameraSurface != null) cameraSurface.release();
            if (texture != null) texture.release();
            if (textureId != 0) GLES20.glDeleteTextures(1, new int[]{textureId}, 0);
            if (program != 0) GLES20.glDeleteProgram(program);
            EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT);
            if (window != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(display, window);
            if (pbuffer != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(display, pbuffer);
            if (glContext != EGL14.EGL_NO_CONTEXT) EGL14.eglDestroyContext(display, glContext);
            EGL14.eglReleaseThread();
            EGL14.eglTerminate(display);
        }
    }

    private static FloatBuffer floats(float... values) {
        FloatBuffer result = ByteBuffer.allocateDirect(values.length * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        result.put(values).position(0);
        return result;
    }

    private static int shader(int type, String source) throws IOException {
        int shader = GLES20.glCreateShader(type);
        GLES20.glShaderSource(shader, source);
        GLES20.glCompileShader(shader);
        int[] compiled = new int[1];
        GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, compiled, 0);
        if (compiled[0] == 0) {
            String error = GLES20.glGetShaderInfoLog(shader);
            GLES20.glDeleteShader(shader);
            throw new IOException("OpenGL预览着色器编译失败：" + error);
        }
        return shader;
    }
}
