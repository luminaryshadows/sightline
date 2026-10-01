package com.privatesight.app.analysis

/**
 * Document-specific field extraction — Kotlin port of ml/extraction/extractor.py.
 *
 * SAFETY: For prescriptions this reports only what the document states and
 * attaches a medical disclaimer. It never invents or infers medical advice.
 */
class DocumentExtractor {

    companion object {
        /**
         * Numeric date (15/03/1985) or written date (31 January 2027, 1st October 2026).
         * Written dates often sit on a different line from their keyword, so callers
         * also do a proximity search across the whole text.
         */
        val DATE_PATTERN: String =
            "(?:" +
                "\\d{1,2}[/\\-.]\\d{1,2}[/\\-.]\\d{2,4}" +
                "|" +
                "\\d{1,2}(?:st|nd|rd|th)?\\s+(?:January|February|March|April|May|June|July|" +
                "August|September|October|November|December)\\s+\\d{2,4}" +
                "|" +
                "(?:January|February|March|April|May|June|July|August|September|October|" +
                "November|December)\\s+\\d{1,2}(?:st|nd|rd|th)?,?\\s+\\d{2,4}" +
                ")"

        private val dateRegex = Regex(DATE_PATTERN, RegexOption.IGNORE_CASE)

        const val MEDICAL_DISCLAIMER: String =
            "IMPORTANT: This information is read directly from the document. " +
                "This is NOT medical advice. Always follow the instructions on your " +
                "prescription label. If anything is unclear, contact your doctor or pharmacist. " +
                "Do not change your medication based on this reading."
    }

    fun extract(text: String, type: DocumentType): ExtractionResult {
        if (text.isBlank()) {
            return ExtractionResult(type, warnings = listOf("No text available for extraction."))
        }
        return when (type) {
            DocumentType.PRESCRIPTION -> extractPrescription(text)
            DocumentType.BANKING -> extractBanking(text)
            DocumentType.BILL -> extractBill(text)
            DocumentType.GOVERNMENT, DocumentType.LEGAL -> extractGovernmentLegal(text, type)
            DocumentType.ID -> extractId(text)
            DocumentType.UNKNOWN -> extractGeneric(text)
        }
    }

    // ── PRESCRIPTION ───────────────────────────────────────────

    private fun extractPrescription(text: String): ExtractionResult {
        val fields = mutableListOf<ExtractedField>()

        firstOf(text,
            "\\b([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)\\s+\\d+\\s*(?:mg|mcg|g|ml)\\b",
            "\\b(?:medication|drug|medicine)[:\\s]*([A-Za-z\\s]+)\\b",
        )?.let { fields.add(ExtractedField("Medication", it)) }

        firstOf(text,
            "\\b(\\d+\\s*(?:mg|mcg|microgram|g|ml|IU|unit)s?)\\b",
            "\\b(?:dosage|dose|strength)[:\\s]*(\\d+\\s*(?:mg|mcg|g|ml))\\b",
        )?.let { fields.add(ExtractedField("Dosage", it)) }

        firstOf(text,
            "(?:take|use|apply)\\s+((?:one|two|three|\\d+)\\s+(?:tablet|capsule|pill|dose)s?\\s+(?:once|twice|three\\s+times?|four\\s+times?)\\s+(?:daily|a\\s+day|per\\s+day))",
            "\\b((?:once|twice|three\\s+times?|four\\s+times?)\\s+(?:daily|a\\s+day|per\\s+day))\\b",
            "\\b((?:morning|evening|bedtime|night)\\s+(?:and|&)\\s+(?:morning|evening|bedtime|night))\\b",
        )?.let { fields.add(ExtractedField("Frequency", it)) }

        findLineContaining(text.lines(),
            listOf("direction", "instruction", "how to take", "how to use", "take", "apply", "use", "administer")
        )?.takeIf { it.length > 5 }?.let { fields.add(ExtractedField("Instructions", it)) }

        findLineContaining(text.lines(),
            listOf("warning", "caution", "do not", "avoid", "side effect", "contraindication", "precaution", "allergy")
        )?.let { fields.add(ExtractedField("Warnings", it)) }

        firstOf(text,
            "(?:Dr|Doctor|Physician|Prescriber)[.:\\s]*([A-Z][a-z]+\\s+[A-Z][a-z]+)",
            "(?:Dr\\.?\\s*)([A-Z][a-z]+\\s+[A-Z][a-z]+)",
        )?.let { fields.add(ExtractedField("Doctor", it)) }

        firstOf(text, "(?:Pharmacy|Dispenser|Chemist)[:\\s]*([A-Za-z\\s',]+)")
            ?.let { fields.add(ExtractedField("Pharmacy", it)) }

        val summary = buildPrescriptionSummary(fields)
        return ExtractionResult(
            documentType = DocumentType.PRESCRIPTION,
            fields = fields,
            summaryLines = summary,
            medicalDisclaimer = MEDICAL_DISCLAIMER,
        )
    }

    private fun buildPrescriptionSummary(fields: List<ExtractedField>): List<String> {
        val map = fields.associate { it.label to it.value }
        val out = mutableListOf<String>()
        if (map.containsKey("Medication")) {
            out.add("This prescription is for ${map["Medication"]} ${map["Dosage"] ?: ""}.".replace("  ", " ").trim())
        }
        map["Frequency"]?.let { out.add("Take $it.") }
        map["Instructions"]?.let { out.add("Instructions: $it") }
        map["Warnings"]?.let { out.add("Warning: $it") }
        if (out.isEmpty()) out.add("This appears to be a prescription. Please verify the details.")
        return out
    }

    // ── BANKING ────────────────────────────────────────────────

    private fun extractBanking(text: String): ExtractionResult {
        val fields = mutableListOf<ExtractedField>()
        val deadlines = mutableListOf<Pair<String, String>>()
        val monetary = mutableListOf<Pair<String, String>>()
        val lines = text.lines()

        firstOf(text, "(?:HSBC|Barclays|Lloyds|NatWest|Santander|Halifax|TSB|RBS|Monzo|Starling|Revolut|Nationwide|Metro|Chase)\\b")
            ?.let { fields.add(ExtractedField("Institution", it)) }

        Regex("[£$€]\\s*\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2})").findAll(text)
            .take(3).forEach { monetary.add("Amount" to it.value.trim()) }

        firstOf(text, "(?:reference|ref|transaction|payment)[\\s#:]*([A-Z0-9\\-]{4,})")
            ?.let { fields.add(ExtractedField("Reference", it)) }

        firstOf(text, "sort\\s*code[:\\s]*(\\d{2}[\\s-]?\\d{2}[\\s-]?\\d{2})")
            ?.let { fields.add(ExtractedField("Sort Code", it)) }

        firstOf(text, "account\\s*(?:number|no)?[:\\s]*(\\d{8,})")
            ?.let { fields.add(ExtractedField("Account Number", it)) }

        for (line in lines) {
            val dm = dateRegex.find(line) ?: continue
            when {
                Regex("due|payment|deadline", RegexOption.IGNORE_CASE).containsMatchIn(line) ->
                    deadlines.add("Payment Date" to dm.value)
                Regex("statement|period|from|to", RegexOption.IGNORE_CASE).containsMatchIn(line) ->
                    deadlines.add("Statement Date" to dm.value)
            }
        }

        val action = findLineContaining(lines,
            listOf("action", "required", "please contact", "notice", "overdrawn", "overdue", "payment required", "urgent"))

        val summary = mutableListOf("This is a document from ${fields.firstOrNull { it.label == "Institution" }?.value ?: "your bank"}.")
        monetary.take(2).forEach { summary.add("It involves ${it.second}.") }
        action?.let { summary.add("Action: $it") }

        return ExtractionResult(
            documentType = DocumentType.BANKING,
            fields = fields,
            monetaryValues = monetary,
            deadlines = deadlines,
            actionRequired = action ?: "No immediate action identified.",
            summaryLines = summary,
        )
    }

    // ── BILL ───────────────────────────────────────────────────

    private fun extractBill(text: String): ExtractionResult {
        val fields = mutableListOf<ExtractedField>()
        val deadlines = mutableListOf<Pair<String, String>>()
        val monetary = mutableListOf<Pair<String, String>>()
        val lines = text.lines()

        firstOf(text, "^([A-Z][A-Za-z\\s&.,']{3,40})$")?.takeIf {
            !Regex("(?:invoice|bill|statement|total|amount|date|page)", RegexOption.IGNORE_CASE).containsMatchIn(it)
        }?.let { fields.add(ExtractedField("Company", it)) }

        firstOf(text,
            "(?:total\\s+due|amount\\s+due|total\\s+payable|balance\\s+due)[:\\s]*[£$€]?\\s*(\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2}))",
            "(?:total|sum)[:\\s]*[£$€]?\\s*(\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2}))",
        )?.let { monetary.add("Amount Due" to it) }

        Regex("(?:due\\s+date|payment\\s+due|pay\\s+by)[:\\s]*($DATE_PATTERN)", RegexOption.IGNORE_CASE)
            .find(text)?.let { deadlines.add("Due Date" to it.groupValues[1]) }

        firstOf(text, "(?:reference|ref|invoice|account|customer)[\\s#:]*([A-Z0-9\\-]{4,})")
            ?.let { fields.add(ExtractedField("Reference", it)) }

        findLineContaining(lines,
            listOf("payment", "pay by", "bank transfer", "direct debit", "sort code", "account number", "how to pay"))
            ?.let { fields.add(ExtractedField("Payment Instructions", it)) }

        val amount = monetary.firstOrNull()?.second
        val due = deadlines.firstOrNull()?.second
        val action = if (amount != null && due != null) "Payment of $amount is due by $due."
        else "Please review this bill."

        val summary = mutableListOf<String>()
        summary.add("This is a bill from ${fields.firstOrNull { it.label == "Company" }?.value ?: "a company"}.")
        monetary.forEach { summary.add("The ${it.first.lowercase()} is ${it.second}.") }
        deadlines.forEach { summary.add("The ${it.first.lowercase()} is ${it.second}.") }

        return ExtractionResult(
            documentType = DocumentType.BILL,
            fields = fields,
            monetaryValues = monetary,
            deadlines = deadlines,
            actionRequired = action,
            summaryLines = summary,
        )
    }

    // ── GOVERNMENT / LEGAL ─────────────────────────────────────

    private fun extractGovernmentLegal(text: String, type: DocumentType): ExtractionResult {
        val fields = mutableListOf<ExtractedField>()
        val deadlines = mutableListOf<Pair<String, String>>()
        val contacts = mutableListOf<Pair<String, String>>()
        val lines = text.lines()

        firstOf(text,
            "(?:HM\\s+Revenue|HMRC|DWP|NHS|Home\\s+Office|DVLA|Council|Department\\s+for|Ministry\\s+of)[ ]+[A-Za-z &]+",
            "^([A-Z][A-Za-z &.,()]{5,50})$",
        )?.let { fields.add(ExtractedField("From", it)) }

        firstOf(text, "(?:Re|Subject|Reference|Our Ref|Your Ref)[:\\s]+(.+?)(?:\\n|$)")
            ?.let { fields.add(ExtractedField("Subject", it)) }

        for (line in lines) {
            val dm = dateRegex.find(line) ?: continue
            when {
                Regex("deadline|by|before|due|respond|reply", RegexOption.IGNORE_CASE).containsMatchIn(line) ->
                    deadlines.add("Deadline" to dm.value)
                Regex("hearing|court|appointment|interview", RegexOption.IGNORE_CASE).containsMatchIn(line) ->
                    deadlines.add("Date" to dm.value)
            }
        }

        if (deadlines.isEmpty()) {
            val kw = Regex("deadline|due\\s+by|before|no\\s+later\\s+than|respond\\s+by|expires?", RegexOption.IGNORE_CASE)
            for (m in kw.findAll(text)) {
                val window = text.substring(m.range.first, minOf(m.range.first + 160, text.length))
                val dm = dateRegex.find(window)
                if (dm != null) {
                    deadlines.add("Deadline" to dm.value)
                    break
                }
            }
        }

        val action = findLineContaining(lines,
            listOf("you must", "you need to", "required to", "action", "please respond", "please contact",
                "failure to", "by law", "obligation", "deadline", "respond by"))

        Regex("(?:Tel|Telephone|Phone|Call)[:\\s]*(\\+?[\\d\\s\\-]{8,})", RegexOption.IGNORE_CASE)
            .findAll(text).forEach { contacts.add("Phone" to it.groupValues[1].trim()) }
        Regex("[\\w.+-]+@[\\w-]+\\.[\\w.]+").findAll(text).take(2)
            .forEach { contacts.add("Email" to it.value) }

        val summary = mutableListOf<String>()
        fields.firstOrNull { it.label == "From" }?.let { summary.add("This is a ${type.id} document from ${it.value}.") }
        fields.firstOrNull { it.label == "Subject" }?.let { summary.add("It concerns: ${it.value}.") }
        deadlines.forEach { summary.add("${it.first}: ${it.second}.") }
        action?.let { summary.add("Action required: $it") }

        return ExtractionResult(
            documentType = type,
            fields = fields,
            deadlines = deadlines,
            contacts = contacts,
            actionRequired = action ?: "No specific action identified. Please review the document.",
            summaryLines = summary,
        )
    }

    // ── ID ─────────────────────────────────────────────────────

    private fun extractId(text: String): ExtractionResult {
        val fields = mutableListOf<ExtractedField>()
        firstOf(text, "(?:Name|Surname|Given\\s+Names?|Holder)[:\\s]+([A-Z][a-z]+\\s+[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)")
            ?.let { fields.add(ExtractedField("Name", it)) }
        firstOf(text, "(?:Date\\s+of\\s+Birth|DOB|Born)[:\\s]*($DATE_PATTERN)")
            ?.let { fields.add(ExtractedField("Date of Birth", it)) }
        firstOf(text, "(?:Passport|Document|ID|License|Number)[\\s#:]*([A-Z0-9]{6,})")
            ?.let { fields.add(ExtractedField("Document Number", it)) }
        firstOf(text, "(?:Nationality|Citizenship)[:\\s]*([A-Za-z\\s]+)")
            ?.let { fields.add(ExtractedField("Nationality", it)) }
        firstOf(text, "(?:Expir\\w+|Valid\\s+Until)[:\\s]*($DATE_PATTERN)")
            ?.let { fields.add(ExtractedField("Expiry Date", it)) }

        val summary = mutableListOf("This appears to be an identification document.")
        fields.firstOrNull { it.label == "Name" }?.let { summary.add("Name: ${it.value}") }

        return ExtractionResult(
            documentType = DocumentType.ID,
            fields = fields,
            summaryLines = summary,
            actionRequired = "No action required.",
        )
    }

    // ── GENERIC ────────────────────────────────────────────────

    private fun extractGeneric(text: String): ExtractionResult {
        val lines = text.lines().filter { it.trim().length > 10 }
        val summary = mutableListOf<String>()
        if (lines.isNotEmpty()) {
            summary.add("Document content was extracted but the type could not be identified.")
            summary.add("First line: ${lines[0].take(100)}")
        }
        return ExtractionResult(
            documentType = DocumentType.UNKNOWN,
            summaryLines = summary,
            actionRequired = "Could not identify document type. Please review manually.",
            warnings = listOf("Document type unknown. Extraction may be incomplete."),
        )
    }

    // ── helpers ────────────────────────────────────────────────

    private fun firstOf(text: String, vararg patterns: String): String? {
        for (p in patterns) {
            val m = Regex(p, setOf(RegexOption.IGNORE_CASE, RegexOption.MULTILINE)).find(text) ?: continue
            return if (m.groupValues.size > 1 && m.groupValues[1].isNotEmpty()) m.groupValues[1].trim()
            else m.value.trim()
        }
        return null
    }

    /**
     * Find the first line containing any keyword, matched on word boundaries so
     * short keywords do not fire on unrelated substrings (e.g. "action" must
     * not match "Transactions").
     */
    private fun findLineContaining(lines: List<String>, keywords: List<String>): String? {
        val compiled = keywords.map { Regex("\\b" + Regex.escape(it) + "\\b", RegexOption.IGNORE_CASE) }
        for (line in lines) {
            if (compiled.any { it.containsMatchIn(line) }) return line.trim()
        }
        return null
    }
}
