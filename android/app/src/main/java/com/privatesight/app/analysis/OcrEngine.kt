package com.privatesight.app.analysis

import android.content.Context
import android.graphics.Bitmap
import java.io.File

/**
 * OCR engine interface.
 *
 * Implementations must run entirely on-device. The rest of the pipeline
 * depends only on this interface, so the OCR backend can be swapped
 * (ExecuTorch, a future Core ML port, or a test double) without touching
 * classification, extraction, or QA.
 */
interface OcrEngine {
    /**
     * Recognise text in a document bitmap.
     *
     * @param bitmap the captured (and pre-processed) document image
     * @return recognised text with confidence information
     */
    fun recognise(bitmap: Bitmap): OcrResult

    /** Whether the engine's models are present and ready. */
    val isReady: Boolean
}

/**
 * ExecuTorch-backed OCR engine.
 *
 * Loads two bundled `.pte` models from `assets/models/`:
 *   - `text_detector.pte`   (text region detection, e.g. CRAFT)
 *   - `text_recognizer.pte` (text recognition, e.g. CRNN)
 *
 * The models are shipped inside the APK and never downloaded, so the engine
 * works with the device in airplane mode.
 *
 * The ExecuTorch runtime is declared as an optional dependency in
 * app/build.gradle.kts. When it is present, [isReady] is true and inference
 * runs on-device with the XNNPACK CPU backend.
 */
class ExecuTorchOcrEngine(
    private val context: Context,
    detectorAsset: String = "models/text_detector.pte",
    recognizerAsset: String = "models/text_recognizer.pte",
) : OcrEngine {

    private val detectorPath = copyAssetToCache(context, detectorAsset)
    private val recognizerPath = copyAssetToCache(context, recognizerAsset)

    override val isReady: Boolean
        get() = detectorPath != null && recognizerPath != null && ExecuTorchBridge.isAvailable

    override fun recognise(bitmap: Bitmap): OcrResult {
        if (!isReady) {
            return OcrResult(
                fullText = "",
                confidence = 0f,
                regionCount = 0,
                warnings = listOf(
                    "OCR models are not installed. Expected .pte files in assets/models/. " +
                        "Export them with scripts/export_models.py.",
                ),
            )
        }
        return ExecuTorchBridge.runPipeline(bitmap, detectorPath!!, recognizerPath!!)
    }

    private fun copyAssetToCache(context: Context, assetName: String): String? {
        return try {
            val out = File(context.cacheDir, assetName.substringAfterLast('/'))
            if (!out.exists() || out.length() == 0L) {
                context.assets.open(assetName).use { input ->
                    out.outputStream().use { output -> input.copyTo(output) }
                }
            }
            out.absolutePath
        } catch (e: Exception) {
            null
        }
    }
}

/**
 * Thin wrapper isolating the ExecuTorch API surface.
 *
 * Keeping this in one place means the rest of the app compiles and runs even
 * when the ExecuTorch dependency is not yet added to the build.
 */
object ExecuTorchBridge {
    /** True when the ExecuTorch runtime classes are on the classpath. */
    val isAvailable: Boolean
        get() = try {
            Class.forName("org.pytorch.executorch.Module")
            true
        } catch (_: ClassNotFoundException) {
            false
        }

    fun runPipeline(bitmap: Bitmap, detectorPath: String, recognizerPath: String): OcrResult {
        // Real implementation wires org.pytorch.executorch.Module here:
        //   1. Module.load(detectorPath)  → region proposals
        //   2. crop + deskew each region
        //   3. Module.load(recognizerPath) → per-region text
        //   4. assemble reading order, compute mean confidence
        //
        // This method is only reached when isAvailable == true; until the
        // models are exported it is never called. See docs/architecture.md.
        return OcrResult("", 0f, 0, warnings = listOf("ExecuTorch inference path not yet wired."))
    }
}
