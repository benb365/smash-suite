-keep class * extends com.lynx.jsbridge.LynxModule { *; }
-keepclasseswithmembers,includedescriptorclasses class * { native <methods>; }
-keepclasseswithmembers class * { @com.lynx.tasm.base.CalledByNative <methods>; }
-keepclasseswithmembers class * { @com.lynx.jsbridge.LynxMethod <methods>; }
-keepclassmembers class * {
    @com.lynx.tasm.behavior.LynxProp <methods>;
    @com.lynx.tasm.behavior.LynxPropGroup <methods>;
    @com.lynx.tasm.behavior.LynxUIMethod <methods>;
}
-keep class * extends com.lynx.tasm.behavior.ui.LynxBaseUI
-keep class * extends com.lynx.tasm.behavior.shadow.ShadowNode
-keep class * implements com.lynx.tasm.behavior.utils.Settable
-keep class * implements com.lynx.tasm.behavior.utils.LynxUISetter
-keep class * implements com.lynx.tasm.behavior.utils.LynxUIMethodInvoker
-keep class com.lynx.tasm.rendernode.compat.** { *; }
-keepclassmembers class com.lynx.tasm.LynxTemplateRender {
    private com.lynx.tasm.core.resource.LynxResourceLoader mLoader;
    private com.lynx.tasm.core.resource.LynxResourceLoader mResourceLoader;
}
