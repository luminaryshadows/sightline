package com.privatesight.app.analysis

/**
 * Document types recognised by the offline pipeline.
 * Mirrors the Python `DocumentType` enum exactly.
 */
enum class DocumentType(val id: String, val displayName: String) {
    PRESCRIPTION("prescription", "Prescription"),
    BANKING("banking", "Banking document"),
    GOVERNMENT("government", "Government document"),
    BILL("bill", "Bill or invoice"),
    LEGAL("legal", "Legal document"),
    ID("id", "Identification document"),
    UNKNOWN("unknown", "Unknown document");

    companion object {
        fun fromId(id: String): DocumentType =
            entries.firstOrNull { it.id == id } ?: UNKNOWN
    }

    /** Whether critical fields in this document type need stricter confidence. */
    val isCritical: Boolean
        get() = this == PRESCRIPTION || this == BANKING || this == LEGAL
}

/** Types of sensitive entity detected in document text. */
enum class EntityType(val id: String) {
    PERSON_NAME("person_name"),
    PHONE_NUMBER("phone_number"),
    EMAIL("email"),
    ADDRESS("address"),
    POSTCODE("postcode"),
    ACCOUNT_NUMBER("account_number"),
    SORT_CODE("sort_code"),
    CREDIT_CARD("credit_card"),
    ID_NUMBER("id_number"),
    MEDICATION("medication"),
    DOSAGE("dosage"),
    MONETARY_VALUE("monetary_value"),
    DATE_OF_BIRTH("date_of_birth"),
    NATIONAL_INSURANCE("national_insurance"),
    NHS_NUMBER("nhs_number");
}

data class SensitiveEntity(
    val type: EntityType,
    val value: String,
    val context: String = "",
    val confidence: Float = 1.0f,
)

data class SensitiveDataResult(
    val detected: Boolean,
    val entities: List<SensitiveEntity> = emptyList(),
    val riskLevel: String = "none",
) {
    val entityCount: Int get() = entities.size
    val entityTypes: List<String> get() = entities.map { it.type.id }.distinct()
}

data class ExtractedField(val label: String, val value: String)

data class ExtractionResult(
    val documentType: DocumentType,
    val fields: List<ExtractedField> = emptyList(),
    val actionRequired: String = "",
    val deadlines: List<Pair<String, String>> = emptyList(),
    val monetaryValues: List<Pair<String, String>> = emptyList(),
    val contacts: List<Pair<String, String>> = emptyList(),
    val summaryLines: List<String> = emptyList(),
    val medicalDisclaimer: String = "",
    val warnings: List<String> = emptyList(),
)

data class ClassificationResult(
    val documentType: DocumentType,
    val confidence: Float,
    val evidence: List<String> = emptyList(),
)

/** Result of an OCR pass. */
data class OcrResult(
    val fullText: String,
    val confidence: Float,
    val regionCount: Int,
    val lowConfidenceCount: Int = 0,
    val warnings: List<String> = emptyList(),
)

/** Complete analysis of a scanned document. */
data class DocumentAnalysis(
    val documentType: DocumentType,
    val classificationConfidence: Float,
    val ocr: OcrResult,
    val sensitiveData: SensitiveDataResult,
    val extraction: ExtractionResult,
    val warnings: List<String>,
    val accessibleSummary: String,
    val processingTimeMs: Long,
)

/** Answer to a question about the current document. */
data class QaAnswer(
    val question: String,
    val answer: String,
    val confidence: Float,
    val isMedical: Boolean,
    val medicalDisclaimer: String = "",
)
