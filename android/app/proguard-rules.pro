# Keep ExecuTorch / PyTorch JNI entry points
-keep class org.pytorch.** { *; }
-dontwarn org.pytorch.**

# Keep our model boundary classes
-keep class com.privatesight.app.analysis.** { *; }
