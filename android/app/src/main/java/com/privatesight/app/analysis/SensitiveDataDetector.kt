package com.privatesight.app.analysis

/**
 * Sensitive information detector — Kotlin port of ml/sensitive_data/detector.py.
 *
 * Detects PII and sensitive data using on-device regex patterns.
 * Nothing detected here ever leaves the device.
 */
class SensitiveDataDetector {

    private val phonePatterns = listOf(
        Regex("\\b0\\d{2,4}[\\s-]?\\d{3,4}[\\s-]?\\d{3,4}\\b"),
        Regex("\\+44[\\s-]?\\d{2,4}[\\s-]?\\d{3,4}[\\s-]?\\d{3,4}\\b"),
        Regex("\\b\\d{5}\\s?\\d{6}\\b"),
        Regex("\\b\\d{3}[\\s-]\\d{3}[\\s-]\\d{4}\\b"),
    )

    private val emailPattern = Regex("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
    private val postcodePattern = Regex("\\b[A-Z]{1,2}\\d{1,2}[A-Z]?\\s?\\d[A-Z]{2}\\b", RegexOption.IGNORE_CASE)
    private val sortCodePattern = Regex("\\b\\d{2}[\\s-]?\\d{2}[\\s-]?\\d{2}\\b")
    private val accountNumberPattern = Regex("\\b\\d{8}\\b")
    private val cardPattern = Regex("\\b(?:\\d[\\s-]*){13,19}\\b")
    private val niPattern = Regex("\\b[A-Z]{2}\\s?\\d{2}\\s?\\d{2}\\s?\\d{2}\\s?[A-D]\\b", RegexOption.IGNORE_CASE)
    private val nhsPattern = Regex("\\b\\d{3}[\\s-]?\\d{3}[\\s-]?\\d{4}\\b")

    private val moneyPatterns = listOf(
        Regex("[£$€]\\s*\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2})\\b"),
        Regex("\\b\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2})\\s*(?:pounds?|dollars?|euros?|GBP|USD|EUR)\\b", RegexOption.IGNORE_CASE),
        Regex("\\b(?:total|amount|sum|balance|payment|due|charge|fee)\\s*(?:of|:)?\\s*[£$€]?\\s*\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2})\\b", RegexOption.IGNORE_CASE),
    )

    private val dobPatterns = listOf(
        Regex("\\b(?:DOB|Date\\s+of\\s+Birth|Born)[:\\s]*\\d{1,2}[/\\-. ]\\d{1,2}[/\\-. ]\\d{2,4}\\b", RegexOption.IGNORE_CASE),
        Regex("\\b\\d{1,2}[/\\-.]\\d{1,2}[/\\-.]\\d{2,4}\\b"),
    )

    private val medicationPatterns = listOf(
        Regex("\\b[A-Z][a-z]*(?:cillin|cycline|azole|prazole|sartan|statin|pril|olol|dipine|zepam|profen|thromycin|oxacin)\\b"),
        Regex("\\b(?:paracetamol|ibuprofen|aspirin|omeprazole|simvastatin|atorvastatin|metformin|amlodipine|ramipril|lisinopril|salbutamol|amoxicillin|fluoxetine|sertraline|citalopram|codeine|tramadol|morphine|gabapentin|pregabalin|insulin|warfarin|apixaban|rivaroxaban)\\b", RegexOption.IGNORE_CASE),
    )

    private val dosagePatterns = listOf(
        Regex("\\b\\d+\\s*(?:mg|mcg|microgram|gram|g|ml|IU|units?)\\b", RegexOption.IGNORE_CASE),
        Regex("\\b(?:take|apply|use|inject|inhale)\\s+(?:one|two|three|\\d+)\\b", RegexOption.IGNORE_CASE),
        Regex("\\b(?:once|twice|three\\s+times?|four\\s+times?)\\s+(?:daily|a\\s+day|per\\s+day)\\b", RegexOption.IGNORE_CASE),
        Regex("\\b(?:morning|evening|bedtime|night|with\\s+food|after\\s+food|before\\s+food|on\\s+empty\\s+stomach)\\b", RegexOption.IGNORE_CASE),
    )

    private val idPatterns = listOf(
        Regex("\\b(?:passport|document|ID|license|licence|reference)[\\s#:]*[A-Z0-9]{6,}\\b", RegexOption.IGNORE_CASE),
        Regex("\\b[A-Z0-9]{9}\\b"),
        Regex("\\b[A-Z]{1,2}\\d{6,7}\\b"),
    )

    private val addressPatterns = listOf(
        Regex("\\b\\d{1,4}\\s+[A-Z][a-z]+(?:\\s+(?:Street|Road|Avenue|Lane|Drive|Close|Way|Court|Place|Gardens|Terrace|Crescent|Square|Row|Walk|Gate|Mews|Rise|Hill|Park|Green|Wood|Heath|Field|View))\\b", RegexOption.IGNORE_CASE),
        Regex("\\b(?:Flat|Apartment|Unit)\\s+\\d+[A-Z]?\\b", RegexOption.IGNORE_CASE),
    )

    private val namePattern = Regex("\\b((?:Mr|Mrs|Ms|Miss|Dr|Prof)\\.?\\s+[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)\\b")

    fun detect(text: String): SensitiveDataResult {
        if (text.isBlank()) {
            return SensitiveDataResult(detected = false)
        }

        val entities = mutableListOf<SensitiveEntity>()

        fun addAll(type: EntityType, patterns: List<Regex>, confidence: Float = 1.0f) {
            for (p in patterns) {
                for (m in p.findAll(text)) {
                    entities.add(SensitiveEntity(type, m.value.trim(), context(text, m.range), confidence))
                }
            }
        }

        addAll(EntityType.PHONE_NUMBER, phonePatterns)
        for (m in emailPattern.findAll(text)) entities.add(SensitiveEntity(EntityType.EMAIL, m.value.trim(), context(text, m.range)))
        for (m in postcodePattern.findAll(text)) entities.add(SensitiveEntity(EntityType.POSTCODE, m.value.trim(), context(text, m.range)))

        // Context-scoped matches need the surrounding line to avoid false positives.
        addContextScoped(text, entities, EntityType.SORT_CODE, Regex("sort\\s*code", RegexOption.IGNORE_CASE), sortCodePattern)
        addContextScoped(text, entities, EntityType.ACCOUNT_NUMBER, Regex("account|acct|a/c", RegexOption.IGNORE_CASE), accountNumberPattern)
        addContextScoped(text, entities, EntityType.NHS_NUMBER, Regex("NHS", RegexOption.IGNORE_CASE), nhsPattern)

        addAll(EntityType.MONETARY_VALUE, moneyPatterns)
        addAll(EntityType.DATE_OF_BIRTH, dobPatterns)
        addAll(EntityType.MEDICATION, medicationPatterns)
        addAll(EntityType.DOSAGE, dosagePatterns)
        addAll(EntityType.ID_NUMBER, idPatterns)
        addAll(EntityType.ADDRESS, addressPatterns)

        for (m in niPattern.findAll(text)) entities.add(SensitiveEntity(EntityType.NATIONAL_INSURANCE, m.value.trim(), context(text, m.range)))

        for (m in cardPattern.findAll(text)) {
            val digits = m.value.replace(" ", "").replace("-", "")
            if (digits.length in 13..19 && digits.all { it.isDigit() }) {
                entities.add(SensitiveEntity(EntityType.CREDIT_CARD, m.value.trim(), context(text, m.range)))
            }
        }

        for (m in namePattern.findAll(text)) {
            entities.add(SensitiveEntity(EntityType.PERSON_NAME, m.groupValues[1].trim(), context(text, m.range), 0.7f))
        }

        val unique = entities.distinctBy { "${it.type.id}|${it.value}" }
        return SensitiveDataResult(
            detected = unique.isNotEmpty(),
            entities = unique,
            riskLevel = assessRisk(unique),
        )
    }

    private fun addContextScoped(
        text: String,
        out: MutableList<SensitiveEntity>,
        type: EntityType,
        contextMarker: Regex,
        valuePattern: Regex,
    ) {
        for (line in text.lines()) {
            if (contextMarker.containsMatchIn(line)) {
                for (m in valuePattern.findAll(line)) {
                    out.add(SensitiveEntity(type, m.value.trim(), line.trim()))
                }
            }
        }
    }

    private fun context(text: String, range: IntRange, window: Int = 60): String {
        val start = (range.first - window).coerceAtLeast(0)
        val end = (range.last + window).coerceAtMost(text.length - 1)
        return text.substring(start, end + 1).trim()
    }

    private fun assessRisk(entities: List<SensitiveEntity>): String {
        val high = setOf(
            EntityType.CREDIT_CARD, EntityType.ACCOUNT_NUMBER, EntityType.NATIONAL_INSURANCE,
            EntityType.NHS_NUMBER, EntityType.DATE_OF_BIRTH, EntityType.MEDICATION, EntityType.DOSAGE,
        )
        val medium = setOf(
            EntityType.PERSON_NAME, EntityType.ADDRESS, EntityType.PHONE_NUMBER, EntityType.EMAIL,
            EntityType.POSTCODE, EntityType.SORT_CODE, EntityType.ID_NUMBER,
        )
        val highCount = entities.count { it.type in high }
        val mediumCount = entities.count { it.type in medium }
        return when {
            highCount >= 2 -> "high"
            highCount >= 1 || mediumCount >= 3 -> "medium"
            mediumCount >= 1 -> "low"
            else -> "none"
        }
    }
}
