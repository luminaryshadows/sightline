package com.privatesight.app.camera

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy

/**
 * CameraX frame analyzer that turns each frame into spoken guidance.
 *
 * Speech is throttled: the same instruction is not repeated more than once
 * every [repeatIntervalMs], and a new instruction is spoken as soon as the
 * guidance changes. This keeps audio useful rather than noisy.
 *
 * All analysis is on-device. Frames are never stored or transmitted.
 */
class DocumentCaptureAnalyzer(
    private val guide: CaptureGuide,
    private val onGuidance: (String, FrameAssessment) -> Unit,
    private val onReady: (FrameAssessment) -> Unit,
    private val repeatIntervalMs: Long = 2500L,
) : ImageAnalysis.Analyzer {

    private var lastMessage: String? = null
    private var lastSpokenAt: Long = 0L

    @Volatile
    var paused: Boolean = false

    override fun analyze(image: ImageProxy) {
        if (paused) {
            image.close()
            return
        }
        try {
            val bitmap = image.toBitmapSafe()
            val assessment = guide.assess(bitmap)
            val message = guide.primaryGuidance(assessment)

            if (assessment.readyToCapture) {
                if (lastMessage != Guidance.READY.message) {
                    lastMessage = Guidance.READY.message
                    onReady(assessment)
                }
                return
            }

            if (message != null) {
                val now = System.currentTimeMillis()
                val changed = message != lastMessage
                val cooledDown = now - lastSpokenAt >= repeatIntervalMs
                if (changed || cooledDown) {
                    lastMessage = message
                    lastSpokenAt = now
                    onGuidance(message, assessment)
                }
            }
        } catch (_: Exception) {
            // A dropped frame must never crash the preview.
        } finally {
            image.close()
        }
    }

    /** Reset throttling state (e.g. after a capture). */
    fun reset() {
        lastMessage = null
        lastSpokenAt = 0L
    }

    private fun ImageProxy.toBitmapSafe(): Bitmap {
        val bitmap = toBitmap()
        // CameraX frames arrive rotated relative to the device; normalise to
        // portrait so guidance distances are consistent for the user.
        val rotation = imageInfo.rotationDegrees
        if (rotation == 0) return bitmap
        val matrix = Matrix().apply { postRotate(rotation.toFloat()) }
        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        if (rotated != bitmap) bitmap.recycle()
        return rotated
    }
}
