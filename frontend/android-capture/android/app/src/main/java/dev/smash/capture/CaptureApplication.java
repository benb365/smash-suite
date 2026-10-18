package dev.smash.capture;

import android.app.Application;
import com.lynx.tasm.LynxEnv;

public final class CaptureApplication extends Application {
    @Override public void onCreate() {
        super.onCreate();
        LynxEnv.inst().init(this, null, null, null);
        LynxEnv.inst().registerModule("Capture", CaptureModule.class);
    }
}
