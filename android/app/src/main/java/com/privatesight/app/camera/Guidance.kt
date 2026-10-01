package com.privatesight.app.camera

/**
 * Fixed spoken guidance strings — Kotlin port of ml/capture_guidance.py.
 *
 * These exact strings are spoken by the TTS engine and must stay in sync
 * with the Python reference and res/values/strings.xml.
 */
enum class Guidance(val message: String) {
    DOCUMENT_NOT_VISIBLE("Document not fully visible."),
    MOVE_LEFT("Move phone left."),
    MOVE_RIGHT("Move phone right."),
    MOVE_UP("Move phone upward."),
    MOVE_DOWN("Move phone downward."),
    MOVE_CLOSER("Move closer."),
    MOVE_FURTHER("Move further away."),
    TOO_DARK("Too dark."),
    TOO_BRIGHT("Too bright."),
    HOLD_STEADY("Hold steady."),
    READY("Document captured."),
}

/** Assessment of a single camera frame. Mirrors FrameAssessment in Python. */
data class FrameAssessment(
    val brightness: Float,
    val blur: Float,
    val contrast: Float,
    val documentDetected: Boolean,
    val allCornersVisible: Boolean,
    val fillRatio: Float,
    val centerOffsetX: Float,
    val centerOffsetY: Float,
    val orientationDegrees: Float,
    val guidance: List<Guidance>,
    val readyToCapture: Boolean,
)
