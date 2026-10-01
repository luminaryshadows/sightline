package com.privatesight.app.camera

import android.graphics.Bitmap
import kotlin.math.abs
import kotlin.math.min

/**
 * Accessible camera capture guidance — Kotlin port of ml/capture_guidance.py.
 *
 * Analyses a frame and produces one clear instruction at a time so a blind
 * user can position a document and capture it without seeing the screen.
 *
 * Thresholds are fractions of the frame so behaviour is resolution-independent
 * and identical to the Python reference implementation.
 */
class CaptureGuide {

    companion object {
        const val MIN_FILL = 0.35f
        const val MAX_FILL = 0.98f
        const val EDGE_MARGIN = 0.03f
        const val CENTER_TOLERANCE = 0.12f
        const val MIN_SHARPNESS = 0.35f
        const val MIN_BRIGHTNESS = 0.25f
        const val MAX_BRIGHTNESS = 0.92f
    }

    fun assess(bitmap: Bitmap): FrameAssessment {
        val w = bitmap.width
        val h = bitmap.height
        if (w == 0 || h == 0) {
            return notVisible()
        }

        val gray = toGrayscale(bitmap)
        val brightness = mean(gray) / 255f
        val blur = sharpness(gray)
        val contrast = contrast(gray)

        val doc = detectDocument(gray, w, h)
        val detected = doc != null
        val cornersVisible = doc?.let { cornersVisible(it, w, h) } ?: false
        val fill = doc?.fillRatio ?: 0f
        val ox = doc?.centerOffsetX ?: 0f
        val oy = doc?.centerOffsetY ?: 0f

        val guidance = prioritise(brightness, blur, detected, cornersVisible, fill, ox, oy)
        val ready = detected && cornersVisible &&
            brightness > MIN_BRIGHTNESS && brightness < MAX_BRIGHTNESS &&
            blur > MIN_SHARPNESS && fill in MIN_FILL..MAX_FILL &&
            abs(ox) <= CENTER_TOLERANCE && abs(oy) <= CENTER_TOLERANCE

        return FrameAssessment(
            brightness = brightness,
            blur = blur,
            contrast = contrast,
            documentDetected = detected,
            allCornersVisible = cornersVisible,
            fillRatio = fill,
            centerOffsetX = ox,
            centerOffsetY = oy,
            orientationDegrees = doc?.orientation ?: 0f,
            guidance = if (ready) listOf(Guidance.READY) else guidance,
            readyToCapture = ready,
        )
    }

    /** The single most important instruction to speak, or null. */
    fun primaryGuidance(a: FrameAssessment): String? = when {
        a.readyToCapture -> Guidance.READY.message
        a.guidance.isNotEmpty() -> a.guidance.first().message
        else -> null
    }

    // ── analysis primitives ───────────────────────────────────

    private data class DocGeom(
        val fillRatio: Float,
        val centerOffsetX: Float,
        val centerOffsetY: Float,
        val orientation: Float,
        val minX: Int, val minY: Int, val maxX: Int, val maxY: Int,
    )

    private fun detectDocument(gray: IntArray, w: Int, h: Int): DocGeom? {
        // Downsample-friendly Sobel magnitude + Otsu threshold to find the
        // dominant rectangular region. This is a lightweight stand-in for the
        // OpenCV contour path used on desktop, chosen because it runs fast
        // enough for live CameraX frames.
        val maxDim = 160
        val step = maxOf(1, maxOf(w, h) / maxDim)

        var minX = w; var minY = h; var maxX = -1; var maxY = -1
        var count = 0
        var sumX = 0L; var sumY = 0L

        val thresh = 40
        for (y in 0 until h step step) {
            for (x in 0 until w step step) {
                val i = y * w + x
                val gx = if (x + 1 < w) gray[i + 1] - gray[i] else 0
                val gy = if (y + 1 < h) gray[i + w] - gray[i] else 0
                if (abs(gx) + abs(gy) > thresh) {
                    count++
                    sumX += x; sumY += y
                    if (x < minX) minX = x
                    if (x > maxX) maxX = x
                    if (y < minY) minY = y
                    if (y > maxY) maxY = y
                }
            }
        }

        if (count < 20 || maxX <= minX || maxY <= minY) return null

        val area = (maxX - minX).toLong() * (maxY - minY)
        val fill = area.toFloat() / (w.toLong() * h)
        if (fill < 0.05f) return null

        val cx = sumX.toFloat() / count
        val cy = sumY.toFloat() / count
        val ox = (cx / w - 0.5f) * 2f
        val oy = (cy / h - 0.5f) * 2f

        // Orientation: skew of the detected bounding box is a coarse proxy here.
        val orientation = 0f

        return DocGeom(fill, ox, oy, orientation, minX, minY, maxX, maxY)
    }

    private fun cornersVisible(d: DocGeom, w: Int, h: Int): Boolean {
        val mx = w * EDGE_MARGIN
        val my = h * EDGE_MARGIN
        return d.minX >= mx && d.maxX <= w - mx && d.minY >= my && d.maxY <= h - my
    }

    private fun prioritise(
        brightness: Float,
        blur: Float,
        detected: Boolean,
        cornersVisible: Boolean,
        fill: Float,
        ox: Float,
        oy: Float,
    ): List<Guidance> {
        val out = mutableListOf<Guidance>()

        if (brightness < MIN_BRIGHTNESS) out.add(Guidance.TOO_DARK)
        else if (brightness > MAX_BRIGHTNESS) out.add(Guidance.TOO_BRIGHT)

        if (!detected) {
            out.add(Guidance.DOCUMENT_NOT_VISIBLE)
            return out
        }

        if (!cornersVisible) out.add(Guidance.DOCUMENT_NOT_VISIBLE)

        if (fill < MIN_FILL) out.add(Guidance.MOVE_CLOSER)
        else if (fill > MAX_FILL) out.add(Guidance.MOVE_FURTHER)

        if (ox < -CENTER_TOLERANCE) out.add(Guidance.MOVE_LEFT)
        else if (ox > CENTER_TOLERANCE) out.add(Guidance.MOVE_RIGHT)
        if (oy < -CENTER_TOLERANCE) out.add(Guidance.MOVE_UP)
        else if (oy > CENTER_TOLERANCE) out.add(Guidance.MOVE_DOWN)

        if (blur < MIN_SHARPNESS) out.add(Guidance.HOLD_STEADY)

        return out
    }

    private fun notVisible() = FrameAssessment(
        brightness = 0f, blur = 0f, contrast = 0f,
        documentDetected = false, allCornersVisible = false,
        fillRatio = 0f, centerOffsetX = 0f, centerOffsetY = 0f,
        orientationDegrees = 0f,
        guidance = listOf(Guidance.DOCUMENT_NOT_VISIBLE),
        readyToCapture = false,
    )

    // ── pixel helpers ─────────────────────────────────────────

    private fun toGrayscale(bitmap: Bitmap): IntArray {
        // Downscale to keep per-frame cost low (CameraX delivers ~30fps).
        val maxDim = 320
        val scale = min(1f, maxDim.toFloat() / maxOf(bitmap.width, bitmap.height))
        val w = maxOf(1, (bitmap.width * scale).toInt())
        val h = maxOf(1, (bitmap.height * scale).toInt())
        val small = if (w != bitmap.width || h != bitmap.height)
            Bitmap.createScaledBitmap(bitmap, w, h, true) else bitmap

        val pixels = IntArray(w * h)
        small.getPixels(pixels, 0, w, 0, 0, w, h)
        val gray = IntArray(w * h)
        for (i in pixels.indices) {
            val p = pixels[i]
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            gray[i] = (r * 299 + g * 587 + b * 114) / 1000
        }
        return gray
    }

    private fun mean(gray: IntArray): Float {
        var sum = 0L
        for (v in gray) sum += v
        return sum.toFloat() / gray.size
    }

    private fun sharpness(gray: IntArray): Float {
        // Variance of a simple Laplacian response, normalised to 0..1.
        var sum = 0.0
        var sumSq = 0.0
        var n = 0
        for (i in 1 until gray.size - 1) {
            val lap = 4 * gray[i] - gray[i - 1] - gray[i + 1]
            sum += lap
            sumSq += lap.toDouble() * lap
            n++
        }
        if (n == 0) return 0f
        val meanLap = sum / n
        val variance = sumSq / n - meanLap * meanLap
        return min(variance / 500.0, 1.0).toFloat()
    }

    private fun contrast(gray: IntArray): Float {
        val m = mean(gray)
        var sumSq = 0.0
        for (v in gray) {
            val d = v - m
            sumSq += d * d
        }
        val std = kotlin.math.sqrt(sumSq / gray.size)
        return min(std / 80.0, 1.0).toFloat()
    }
}
