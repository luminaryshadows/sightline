package com.privatesight.app.analysis

import android.graphics.Bitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * End-to-end offline document analysis pipeline (Kotlin).
 *
 * Mirrors ml/pipeline.py:
 *   OCR -> classify -> detect sensitive data -> extract -> summary
 *
 * Everything runs on-device. The analyzer never performs network I/O.
 */
class DocumentAnalyzer(
    private val ocrEngine: OcrEngine,
    private val classifier: DocumentClassifier = DocumentClassifier(),
    private val detector: SensitiveDataDetector = SensitiveDataDetector(),
    private val extractor: DocumentExtractor = DocumentExtractor(),
    private val qa: OfflineQuestionAnswerer = OfflineQuestionAnswerer(),
) {

    /** Run the full pipeline on a captured document bitmap. */
    suspend fun analyze(bitmap: Bitmap): DocumentAnalysis = withContext(Dispatchers.Default) {
        val start = System.currentTimeMillis()
        val warnings = mutableListOf<String>()

        val ocr = ocrEngine.recognise(bitmap)
        warnings += ocr.warnings

        if (ocr.fullText.isBlank()) {
            warnings += "No text could be read from the document."
            return@withContext DocumentAnalysis(
                documentType = DocumentType.UNKNOWN,
                classificationConfidence = 0f,
                ocr = ocr,
                sensitiveData = SensitiveDataResult(false),
                extraction = ExtractionResult(DocumentType.UNKNOWN),
                warnings = warnings,
                accessibleSummary = "I could not read any text from the document. Please scan it again.",
                processingTimeMs = System.currentTimeMillis() - start,
            )
        }

        val classification = classifier.classify(ocr.fullText)
        if (classification.documentType.isCritical && ocr.confidence < 0.65f) {
            warnings += "I am not confident I read this correctly. Please scan the document again."
        }

        val sensitive = detector.detect(ocr.fullText)
        val extraction = extractor.extract(ocr.fullText, classification.documentType)
        warnings += extraction.warnings

        val summary = buildSummary(classification, ocr, sensitive, extraction)

        DocumentAnalysis(
            documentType = classification.documentType,
            classificationConfidence = classification.confidence,
            ocr = ocr,
            sensitiveData = sensitive,
            extraction = extraction,
            warnings = warnings.distinct(),
            accessibleSummary = summary,
            processingTimeMs = System.currentTimeMillis() - start,
        )
    }

    /** Answer a question about an already-analysed document. */
    fun ask(analysis: DocumentAnalysis, question: String): QaAnswer {
        if (analysis.ocr.fullText.isBlank()) {
            return QaAnswer(question, "No document text is available. Please scan a document first.", 0f, false)
        }
        return qa.answer(question, analysis.ocr.fullText, analysis.extraction, analysis.documentType)
    }

    private fun buildSummary(
        classification: ClassificationResult,
        ocr: OcrResult,
        sensitive: SensitiveDataResult,
        extraction: ExtractionResult,
    ): String {
        val parts = mutableListOf<String>()
        parts.add("This appears to be a ${classification.documentType.displayName.lowercase()}.")

        if (classification.confidence < 0.5f) {
            parts.add("However, I am only ${(classification.confidence * 100).toInt()} percent confident in this classification.")
        }
        if (ocr.confidence < 0.6f) {
            parts.add("The text quality is low. Please scan the document again with better lighting.")
        }
        if (sensitive.detected) {
            parts.add("Sensitive information was detected. Risk level: ${sensitive.riskLevel}.")
        }

        parts += extraction.summaryLines

        val trivial = listOf("", "No immediate action identified.", "No action required.",
            "No specific action identified. Please review the document.")
        if (extraction.actionRequired !in trivial) {
            parts.add(extraction.actionRequired)
        }

        extraction.deadlines.forEach { parts.add("${it.first}: ${it.second}.") }
        extraction.monetaryValues.forEach { parts.add("${it.first}: ${it.second}.") }

        if (extraction.medicalDisclaimer.isNotEmpty()) {
            parts.add(extraction.medicalDisclaimer)
        }

        return parts.joinToString(" ")
    }
}
