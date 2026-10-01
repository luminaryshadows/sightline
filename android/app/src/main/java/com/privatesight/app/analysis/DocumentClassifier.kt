package com.privatesight.app.analysis

/**
 * Rule-based document classifier — Kotlin port of ml/classifier/engine.py.
 *
 * Scores each document type by keyword/pattern matches in the OCR text and
 * returns the best type with a confidence score.
 *
 * All processing is local. No text leaves the device.
 */
class DocumentClassifier {

    private val patterns: Map<DocumentType, List<Regex>> = mapOf(
        DocumentType.PRESCRIPTION to listOf(
            "\\bprescri(be|ption)\\b", "\\bmedication\\b", "\\bdosage\\b", "\\bdose\\b",
            "\\btablet\\b", "\\bcapsule\\b", "\\bmg\\b", "\\bmcg\\b", "\\bmicrogram\\b",
            "\\btake\\s+(one|two|three|\\d+)\\b", "\\btwice\\s+daily\\b", "\\bonce\\s+daily\\b",
            "\\bpharmac(y|ist)\\b", "\\brefill\\b", "\\bdispense\\b", "\\brx\\b",
            "\\bq\\.?d\\.?\\b", "\\bb\\.?i\\.?d\\.?\\b", "\\bt\\.?i\\.?d\\.?\\b",
            "\\bq\\.?i\\.?d\\.?\\b", "\\bprn\\b", "\\bstat\\b",
            "\\broute\\b", "\\bquantity\\b", "\\bdirections?\\b",
            "\\bdoctor\\b", "\\bphysician\\b", "\\bclinic\\b", "\\bmedical\\s+centre\\b",
            "\\bdea\\b", "\\bnpi\\b", "\\bprescriber\\b",
        ),
        DocumentType.BANKING to listOf(
            "\\bbank\\b", "\\bbanking\\b", "\\baccount\\s+number\\b", "\\bsort\\s+code\\b",
            "\\btransaction\\b", "\\bdeposit\\b", "\\bwithdrawal\\b", "\\btransfer\\b",
            "\\bstatement\\b", "\\bbalance\\b", "\\boverdraft\\b", "\\binterest\\s+rate\\b",
            "\\bstanding\\s+order\\b", "\\bdirect\\s+debit\\b", "\\bcheque\\b",
            "\\bcredit\\b", "\\bdebit\\b", "\\biban\\b", "\\bswift\\b", "\\bbic\\b",
            "\\bwire\\b", "\\bach\\b", "\\brouting\\s+number\\b", "\\bifsc\\b",
            "\\bsavings?\\b", "\\bcurrent\\s+account\\b", "\\bmortgage\\b",
            "[£$€]\\s*\\d+[.,]\\d{2}",
        ),
        DocumentType.GOVERNMENT to listOf(
            "\\bgovernment\\b", "\\bhm\\s+revenue\\b", "\\bhmrc\\b", "\\birs\\b",
            "\\bhousing\\s+benefit\\b", "\\buniversal\\s+credit\\b", "\\bcouncil\\s+tax\\b",
            "\\bdepartment\\s+for\\s+work\\b", "\\bdwp\\b", "\\bnhs\\b",
            "\\bnational\\s+insurance\\b", "\\btax\\s+return\\b", "\\btax\\s+credit\\b",
            "\\bpassport\\b", "\\bdriving\\s+licen[cs]e\\b", "\\bdvla\\b",
            "\\bbenefit\\b", "\\bpension\\b", "\\bsocial\\s+security\\b",
            "\\bhome\\s+office\\b", "\\bvisa\\b", "\\bimmigration\\b",
            "\\bofficial\\s+notice\\b", "\\bpublic\\s+notice\\b",
        ),
        DocumentType.BILL to listOf(
            "\\binvoice\\b", "\\bbill\\b",
            "\\bamount\\s+due\\b", "\\bdue\\s+date\\b", "\\bpayment\\s+due\\b",
            "\\butility\\b", "\\belectricity\\b", "\\bwater\\b",
            "\\btelecom\\b", "\\bbroadband\\b", "\\bmobile\\s+bill\\b",
            "\\bsubscription\\b", "\\bmonthly\\s+(charge|fee|payment)\\b",
            "\\baccount\\s+summary\\b", "\\bprevious\\s+balance\\b",
            "\\bnew\\s+charges\\b", "\\btotal\\s+due\\b", "\\bpay\\s+by\\b",
            "\\bpayment\\s+method\\b", "\\bcustomer\\s+number\\b",
            "\\breference\\s+number\\b", "\\bbilling\\s+period\\b",
            "\\bvat\\b", "\\btax\\s+invoice\\b",
        ),
        DocumentType.LEGAL to listOf(
            "\\blegal\\b", "\\bsolicitor\\b", "\\battorney\\b", "\\blaw\\s+firm\\b",
            "\\bcontract\\b", "\\bagreement\\b", "\\bterms?\\s+and\\s+conditions?\\b",
            "\\bcourt\\b", "\\btribunal\\b", "\\bjudgment\\b", "\\bwrit\\b",
            "\\bsummons\\b", "\\baffidavit\\b", "\\bnotar\\w+\\b",
            "\\bplaintiff\\b", "\\bdefendant\\b", "\\bclaim(ant)?\\b",
            "\\bherein\\b", "\\bhereto\\b", "\\bhereunder\\b", "\\bwhereof\\b",
            "\\bwhereas\\b", "\\bwitnesseth\\b", "\\bhereinafter\\b",
            "\\bindemnif\\w+\\b", "\\bliability\\b", "\\barbitration\\b",
            "\\bjurisdiction\\b", "\\bgoverning\\s+law\\b",
        ),
        DocumentType.ID to listOf(
            "\\bpassport\\b", "\\bidentity\\b", "\\bidentification\\b",
            "\\bdriving\\s+licen[cs]e\\b", "\\bnational\\s+id\\b",
            "\\bbirth\\s+certificate\\b", "\\bdate\\s+of\\s+birth\\b",
            "\\bplace\\s+of\\s+birth\\b", "\\bnationality\\b", "\\bsex\\b.*\\b[mfo]\\b",
            "\\bissued?\\s+(by|on|at)\\b", "\\bexpir\\w+\\s+date\\b",
            "\\bdocument\\s+number\\b", "\\bcitizenship\\b",
            "\\bholder\\b", "\\bbearer\\b",
        ),
    ).mapValues { (_, list) -> list.map { Regex(it, RegexOption.IGNORE_CASE) } }

    fun classify(text: String): ClassificationResult {
        if (text.isBlank()) {
            return ClassificationResult(DocumentType.UNKNOWN, 0f, listOf("No text to classify."))
        }

        val scores = mutableMapOf<DocumentType, Pair<Float, List<String>>>()

        for ((type, regexes) in patterns) {
            val matched = mutableListOf<String>()
            var totalMatches = 0
            for (regex in regexes) {
                val count = regex.findAll(text).count()
                if (count > 0) {
                    matched.add("Matched: ${regex.pattern.take(40)}")
                    totalMatches += count
                }
            }
            if (matched.isNotEmpty()) {
                val raw = minOf(matched.size.coerceAtMost(15) / 15f, 1f)
                val densityBonus = minOf(totalMatches / 20f, 0.3f)
                val score = minOf(raw + densityBonus, 1f)
                scores[type] = score to matched
            }
        }

        if (scores.isEmpty()) {
            return ClassificationResult(DocumentType.UNKNOWN, 0f, listOf("No patterns matched."))
        }

        val ranked = scores.entries.sortedByDescending { it.value.first }
        val (topType, topPair) = ranked.first()
        val (topScore, topEvidence) = topPair

        val confidence = if (ranked.size == 1) {
            topScore
        } else {
            val second = ranked[1].value.first
            minOf(0.5f + (topScore - second) * 0.5f, topScore)
        }

        return ClassificationResult(topType, confidence, topEvidence.take(10))
    }
}
