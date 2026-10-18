package dev.smash.capture;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import com.lynx.jsbridge.LynxMethod;
import com.lynx.jsbridge.LynxModule;
import com.lynx.react.bridge.Callback;

/** Only commands/status cross the bridge; encoded media stays in the service. */
public final class CaptureModule extends LynxModule {
    public CaptureModule(Context context) { super(context); }

    @LynxMethod public void getState(Callback callback) {
        callback.invoke(CaptureService.snapshot(mContext).toString());
    }

    @LynxMethod public void command(String command) {
        new Handler(Looper.getMainLooper()).post(() -> {
            MainActivity activity = MainActivity.current();
            if (activity != null) activity.command(command);
        });
    }
}
