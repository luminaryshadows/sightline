package com.privatesight.app.analysis

/**
 * Offline question answering — Kotlin port of ml/qa/engine.py.
 *
 * Answers questions using only the current document's text and extracted
 * fields. Never hallucinates: returns "I could not find that information"
 * when the answer is absent.
 *
 * SAFETY: medical questions are answered only from document text and always
 * carry a disclaimer. The engine never gives medical advice.
 */
class OfflineQuestionAnswerer {

    companion object {
        const val MEDICAL_DISCLAIMER: String =
            "I am reading directly from the document. This is NOT medical advice. " +
                "Always follow the instructions on your prescription label. " +
                "Contact your doctor or pharmacist if you have questions about your medication."

        private val INTENTS: List<Pair<String, List<Regex>>> = listOf(
            "dosage" to listOf(
                Regex("how\\s+(?:many|much)\\s+(?:tablets?|capsules?|pills?|doses?)", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:is\\s+)?(?:the\\s+)?(?:dosage|dose)", RegexOption.IGNORE_CASE),
                Regex("how\\s+(?:often|frequently)", RegexOption.IGNORE_CASE),
                Regex("how\\s+(?:do\\s+i\\s+)?take", RegexOption.IGNORE_CASE),
            ),
            "amount" to listOf(
                Regex("how\\s+much\\s+(?:do\\s+i\\s+)?(?:owe|pay|need\\s+to\\s+pay)", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:is\\s+)?(?:the\\s+)?(?:amount|total|price|cost|fee|charge|balance)", RegexOption.IGNORE_CASE),
                Regex("how\\s+much\\s+(?:is|was)", RegexOption.IGNORE_CASE),
            ),
            "deadline" to listOf(
                Regex("when\\s+(?:is|was)\\s+(?:the\\s+)?(?:due|deadline|payment|date)", RegexOption.IGNORE_CASE),
                Regex("by\\s+when", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:is\\s+)?(?:the\\s+)?(?:due|deadline|pay\\s+by)", RegexOption.IGNORE_CASE),
                Regex("when\\s+(?:do\\s+i\\s+)?(?:need\\s+to|must\\s+i|should\\s+i)", RegexOption.IGNORE_CASE),
            ),
            "action" to listOf(
                Regex("what\\s+(?:do\\s+i\\s+)?(?:need\\s+to|should\\s+i|must\\s+i)\\s+do", RegexOption.IGNORE_CASE),
                Regex("is\\s+there\\s+(?:anything|something|an\\s+action)", RegexOption.IGNORE_CASE),
                Regex("what\\s+action", RegexOption.IGNORE_CASE),
                Regex("do\\s+i\\s+need\\s+to", RegexOption.IGNORE_CASE),
                Regex("next\\s+steps?", RegexOption.IGNORE_CASE),
            ),
            "who" to listOf(
                Regex("who\\s+(?:is|sent|from|wrote|issued|signed)", RegexOption.IGNORE_CASE),
                Regex("from\\s+whom", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:is\\s+)?(?:the\\s+)?(?:company|organization|sender|doctor|pharmacy|hospital)", RegexOption.IGNORE_CASE),
            ),
            "what_is" to listOf(
                Regex("what\\s+(?:is|are)\\s+this\\s+document", RegexOption.IGNORE_CASE),
                Regex("what\\s+kind\\s+of\\s+document", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:is|are)\\s+(?:this|it|the\\s+document)", RegexOption.IGNORE_CASE),
            ),
            "medication" to listOf(
                Regex("what\\s+(?:is\\s+)?(?:the\\s+)?(?:medication|medicine|drug|pill|tablet|capsule)", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:am\\s+i|is\\s+)\\s+(?:taking|prescribed)", RegexOption.IGNORE_CASE),
                Regex("what\\s+(?:is|are)\\s+(?:the\\s+)?(?:side\\s+effects?)", RegexOption.IGNORE_CASE),
                Regex("is\\s+(?:it|this)\\s+(?:\\w+\\s+)?safe", RegexOption.IGNORE_CASE),
                Regex("safe|safety|dangerous|risk", RegexOption.IGNORE_CASE),
            ),
        )

        private val STOP_WORDS = setOf(
            "the", "is", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "it",
            "this", "that", "what", "when", "where", "who", "how", "do", "does", "did", "can",
            "could", "would", "should", "will", "shall", "may", "might", "must", "i", "my", "me",
            "you", "your", "there", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "having",
        )
    }

    fun answer(question: String, text: String, extraction: ExtractionResult, type: DocumentType): QaAnswer {
        val q = question.trim()
        if (q.isEmpty()) {
            return QaAnswer(q, "Please ask a question about the document.", 0f, false)
        }
        return when (classifyIntent(q)) {
            "dosage" -> answerDosage(q, text, extraction)
            "amount" -> answerAmount(q, text, extraction)
            "deadline" -> answerDeadline(q, text, extraction)
            "action" -> answerAction(q, text, extraction)
            "who" -> answerWho(q, text, extraction)
            "what_is" -> answerWhatIs(q, extraction, type)
            "medication" -> answerMedication(q, text, extraction)
            else -> answerGeneral(q, text)
        }
    }

    private fun classifyIntent(question: String): String {
        for ((intent, regexes) in INTENTS) {
            if (regexes.any { it.containsMatchIn(question) }) return intent
        }
        return "general"
    }

    private fun answerDosage(q: String, text: String, ex: ExtractionResult): QaAnswer {
        val map = ex.fields.associate { it.label.lowercase() to it.value }
        val dosage = map["dosage"] ?: ""
        val freq = map["frequency"] ?: ""
        val instructions = map["instructions"] ?: ""
        if (dosage.isNotEmpty() || freq.isNotEmpty() || instructions.isNotEmpty()) {
            val parts = mutableListOf<String>()
            if (dosage.isNotEmpty()) parts.add("The dosage is $dosage.")
            if (freq.isNotEmpty()) parts.add("Take $freq.")
            if (instructions.isNotEmpty()) parts.add("Instructions: $instructions.")
            return QaAnswer(q, parts.joinToString(" "), 0.8f, true, MEDICAL_DISCLAIMER)
        }
        val m = Regex("(?:take|dosage|dose)[^.]*?(?:one|two|three|\\d+)[^.]*?(?:tablet|capsule|pill|daily|day)[^.]*\\.",
            RegexOption.IGNORE_CASE).find(text)
        if (m != null) {
            return QaAnswer(q, "The document says: ${m.value.trim()}", 0.6f, true, MEDICAL_DISCLAIMER)
        }
        return QaAnswer(q, "I could not find dosage instructions in the document. Please check the prescription label carefully.", 0f, true, MEDICAL_DISCLAIMER)
    }

    private fun answerAmount(q: String, text: String, ex: ExtractionResult): QaAnswer {
        if (ex.monetaryValues.isNotEmpty()) {
            val s = ex.monetaryValues.joinToString("; ") { "${it.first}: ${it.second}" }
            return QaAnswer(q, "The document shows: $s.", 0.8f, false)
        }
        val money = Regex("[£$€]\\s*\\d{1,3}(?:[,.]\\d{3})*(?:[.,]\\d{2})").findAll(text).take(3).map { it.value }.toList()
        if (money.isNotEmpty()) {
            return QaAnswer(q, "The document mentions: ${money.joinToString(", ")}.", 0.6f, false)
        }
        return QaAnswer(q, "I could not find a specific amount in the document.", 0f, false)
    }

    private fun answerDeadline(q: String, text: String, ex: ExtractionResult): QaAnswer {
        if (ex.deadlines.isNotEmpty()) {
            val s = ex.deadlines.joinToString("; ") { "${it.first}: ${it.second}" }
            return QaAnswer(q, "Key dates: $s.", 0.8f, false)
        }
        val dm = Regex("[^.]*?(?:due|deadline|by|before)[^.]*?(?:$DATE_PATTERN)[^.]*\\.", RegexOption.IGNORE_CASE).find(text)
        if (dm != null) {
            return QaAnswer(q, "The document indicates: ${dm.value.trim()}", 0.5f, false)
        }
        return QaAnswer(q, "I could not find a specific deadline in the document.", 0f, false)
    }

    private fun answerAction(q: String, text: String, ex: ExtractionResult): QaAnswer {
        val a = ex.actionRequired
        val trivial = listOf("", "No immediate action identified.", "No action required.",
            "No specific action identified. Please review the document.")
        if (a.isNotEmpty() && a !in trivial) {
            return QaAnswer(q, "Action required: $a", 0.8f, false)
        }
        return QaAnswer(q, "I could not identify a specific action required from this document.", 0f, false)
    }

    private fun answerWho(q: String, text: String, ex: ExtractionResult): QaAnswer {
        val map = ex.fields.associate { it.label.lowercase() to it.value }
        for (key in listOf("from", "institution", "company", "doctor", "pharmacy", "organization")) {
            map[key]?.let { return QaAnswer(q, "From: $it.", 0.8f, false) }
        }
        if (ex.contacts.isNotEmpty()) {
            return QaAnswer(q, "Contacts found: ${ex.contacts.joinToString("; ") { "${it.first}: ${it.second}" }}.", 0.6f, false)
        }
        return QaAnswer(q, "I could not identify who sent this document.", 0f, false)
    }

    private fun answerWhatIs(q: String, ex: ExtractionResult, type: DocumentType): QaAnswer {
        val desc = when (type) {
            DocumentType.PRESCRIPTION -> "a medical prescription"
            DocumentType.BANKING -> "a banking document or statement"
            DocumentType.BILL -> "a bill or invoice"
            DocumentType.GOVERNMENT -> "a government document"
            DocumentType.LEGAL -> "a legal document"
            DocumentType.ID -> "an identification document"
            DocumentType.UNKNOWN -> "an unidentified document"
        }
        return if (ex.summaryLines.isNotEmpty()) {
            QaAnswer(q, "This is $desc. ${ex.summaryLines.joinToString(" ")}", 0.8f, type == DocumentType.PRESCRIPTION, if (type == DocumentType.PRESCRIPTION) MEDICAL_DISCLAIMER else "")
        } else {
            QaAnswer(q, "This appears to be $desc. I could not extract more details.", 0.4f, false)
        }
    }

    private fun answerMedication(q: String, text: String, ex: ExtractionResult): QaAnswer {
        if (Regex("side\\s+effects?", RegexOption.IGNORE_CASE).containsMatchIn(q)) {
            val se = Regex("(?:side\\s+effects?|warning|caution|may\\s+cause)[^.]*\\.", RegexOption.IGNORE_CASE).find(text)
            return if (se != null) {
                QaAnswer(q, "The document mentions: ${se.value.trim()}", 0.6f, true, MEDICAL_DISCLAIMER)
            } else {
                QaAnswer(q, "The document does not list specific side effects. Please consult the medication leaflet or your pharmacist.", 0f, true, MEDICAL_DISCLAIMER)
            }
        }
        if (Regex("safe|safety|dangerous|risk", RegexOption.IGNORE_CASE).containsMatchIn(q)) {
            return QaAnswer(q,
                "I cannot determine if this medication is safe for you. This document reading is not medical advice. Please consult your doctor or pharmacist.",
                0f, true, MEDICAL_DISCLAIMER)
        }
        val map = ex.fields.associate { it.label.lowercase() to it.value }
        map["medication"]?.let {
            return QaAnswer(q, "The medication is $it. ${map["dosage"] ?: ""}.", 0.8f, true, MEDICAL_DISCLAIMER)
        }
        return QaAnswer(q, "I could not identify the specific medication in this document.", 0f, true, MEDICAL_DISCLAIMER)
    }

    private fun answerGeneral(q: String, text: String): QaAnswer {
        val keywords = Regex("\\b[a-z]{3,}\\b").findAll(q.lowercase())
            .map { it.value }.filter { it !in STOP_WORDS }.toList()
        if (keywords.isEmpty()) {
            return QaAnswer(q, "I'm not sure what you're asking. Please try rephrasing your question.", 0f, false)
        }
        val matches = text.lines().filter { line -> keywords.any { line.lowercase().contains(it) } }
        return if (matches.isNotEmpty()) {
            QaAnswer(q, "Relevant text from the document: ${matches.take(3).joinToString("; ")}", 0.4f, false)
        } else {
            QaAnswer(q, "I could not find that information in the document.", 0f, false)
        }
    }
}
