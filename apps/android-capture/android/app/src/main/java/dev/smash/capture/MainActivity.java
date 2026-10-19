package dev.smash.capture;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.SurfaceTexture;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Surface;
import android.view.TextureView;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;
import com.lynx.tasm.LynxView;
import com.lynx.tasm.LynxViewBuilder;
import com.lynx.tasm.provider.AbsTemplateProvider;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.lang.ref.WeakReference;
import java.net.URI;
import java.util.ArrayList;

public final class MainActivity extends Activity implements TextureView.SurfaceTextureListener {
    private static WeakReference<MainActivity> active = new WeakReference<>(null);
    private Surface preview;
    private TextureView texture;
    private LynxView controls;

    static MainActivity current() { return active.get(); }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.rgb(10, 17, 19));
        getWindow().setNavigationBarColor(Color.rgb(10, 17, 19));
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout layout = new LinearLayout(this);
        layout.setBackgroundColor(Color.BLACK);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        texture = new TextureView(this);
        texture.setSurfaceTextureListener(this);
        layout.addView(texture, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1.6f));
        LynxViewBuilder builder = new LynxViewBuilder();
        builder.setTemplateProvider(new AbsTemplateProvider() {
            @Override public void loadTemplate(String uri, Callback callback) {
                try (InputStream input = getAssets().open(uri);
                     ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                    callback.onSuccess(output.toByteArray());
                } catch (Exception e) { callback.onFailed(e.toString()); }
            }
        });
        controls = builder.build(this);
        layout.addView(controls, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        setContentView(layout);
        controls.renderTemplateUrl("main.lynx.bundle", "");
    }

    @Override protected void onResume() {
        super.onResume();
        active = new WeakReference<>(this);
        if (texture.isAvailable() && preview == null)
            onSurfaceTextureAvailable(texture.getSurfaceTexture(), texture.getWidth(), texture.getHeight());
        CaptureService.setPreview(preview);
    }

    @Override protected void onPause() {
        active.clear();
        CaptureService.setPreview(null);
        super.onPause();
    }

    @Override protected void onDestroy() {
        controls.destroy();
        if (preview != null) { preview.release(); preview = null; }
        super.onDestroy();
    }

    void command(String command) {
        try {
            switch (command) {
                case "start":
                    ArrayList<String> missing = new ArrayList<>();
                    for (String permission : new String[]{Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO})
                        if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) missing.add(permission);
                    SharedPreferences prefs = getSharedPreferences("capture-settings", MODE_PRIVATE);
                    if (Build.VERSION.SDK_INT >= 33 && !prefs.getBoolean("notificationAsked", false)
                            && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                        missing.add(Manifest.permission.POST_NOTIFICATIONS);
                        prefs.edit().putBoolean("notificationAsked", true).apply();
                    }
                    if (!missing.isEmpty()) { requestPermissions(missing.toArray(new String[0]), 1); return; }
                    beginCapture();
                    break;
                case "stop": CaptureService.stopCapture(this); break;
                case "retry": CaptureService.resumeUploads(this); break;
                case "settings": settings(); break;
                default: throw new IllegalArgumentException("未知操作");
            }
        } catch (Exception e) { Toast.makeText(this, e.getMessage(), Toast.LENGTH_LONG).show(); }
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(request, permissions, grants);
        if (request == 1 && checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            beginCapture();
        } else Toast.makeText(this, "录制需要相机和麦克风权限", Toast.LENGTH_LONG).show();
    }

    private void beginCapture() {
        SharedPreferences prefs = getSharedPreferences("capture-settings", MODE_PRIVATE);
        if (prefs.getString("endpoint", "").isEmpty() || prefs.getString("token", "").isEmpty()) {
            settings(); return;
        }
        try { CaptureService.startCapture(this, preview, getWindowManager().getDefaultDisplay().getRotation()); }
        catch (Exception e) { Toast.makeText(this, e.getMessage(), Toast.LENGTH_LONG).show(); }
    }

    private void settings() {
        if (CaptureService.snapshot(this).optBoolean("recording") || CaptureService.snapshot(this).optBoolean("starting")) {
            Toast.makeText(this, "请先停止拍摄再修改接收设置", Toast.LENGTH_LONG).show(); return;
        }
        SharedPreferences prefs = getSharedPreferences("capture-settings", MODE_PRIVATE);
        LinearLayout fields = new LinearLayout(this);
        fields.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        fields.setPadding(padding, padding / 2, padding, padding / 2);
        EditText url = new EditText(this);
        url.setHint("接收端地址，例如 http://192.168.1.2:8787");
        url.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        url.setText(prefs.getString("endpoint", ""));
        fields.addView(url);
        EditText token = new EditText(this);
        token.setHint("接收端启动时的令牌");
        token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        token.setText(prefs.getString("token", ""));
        fields.addView(token);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("接收设置").setView(fields)
            .setNegativeButton("取消", null).setPositiveButton("保存", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                URI endpoint = new URI(url.getText().toString().trim());
                if (!("http".equals(endpoint.getScheme()) || "https".equals(endpoint.getScheme()))
                        || endpoint.getHost() == null || endpoint.getRawUserInfo() != null
                        || endpoint.getRawQuery() != null || endpoint.getRawFragment() != null)
                    throw new IllegalArgumentException("请输入有效的 HTTP 或 HTTPS 接收端地址");
                String secret = token.getText().toString().trim();
                if (secret.isEmpty()) throw new IllegalArgumentException("请填写接收令牌");
                CaptureService.configure(this, endpoint.toString().replaceAll("/+$", ""), secret);
                dialog.dismiss();
            } catch (Exception e) { url.setError(e.getMessage()); }
        }));
        dialog.show();
    }

    @Override public void onSurfaceTextureAvailable(SurfaceTexture surface, int width, int height) {
        surface.setDefaultBufferSize(1920, 1080);
        preview = new Surface(surface);
        fitPreview(width, height);
        CaptureService.setPreview(preview);
    }
    @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) {
        CaptureService.setPreview(null);
        if (preview != null) { preview.release(); preview = null; }
        return true;
    }
    private void fitPreview(int width, int height) {
        float contentWidth = Math.min(width, height * 16f / 9f);
        float contentHeight = contentWidth * 9f / 16f;
        Matrix matrix = new Matrix();
        matrix.setScale(contentWidth / width, contentHeight / height, width / 2f, height / 2f);
        texture.setTransform(matrix);
    }
    @Override public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int width, int height) { fitPreview(width, height); }
    @Override public void onSurfaceTextureUpdated(SurfaceTexture surface) { }
}
