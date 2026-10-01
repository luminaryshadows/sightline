package com.privatesight.app.analysis

import org.junit.Assert.assertTrue
import org.junit.Test

class DocumentExtractorTest {

    private val extractor = DocumentExtractor()

    @Test
    fun prescriptionExtractsFieldsAndDisclaimer() {
        val text = "Medication: Amoxicillin 500mg capsules\nDosage: Take ONE capsule THREE times daily"
        val result = extractor.extract(text, DocumentType.PRESCRIPTION)
        assertTrue(result.fields.isNotEmpty())
        assertTrue(result.medicalDisclaimer.contains("NOT medical advice"))
    }

    @Test
    fun governmentDeadlineAcrossLines() {
        val text = "HM Revenue & Customs\nThe deadline for submitting your return online is\n31 January 2027."
        val result = extractor.extract(text, DocumentType.GOVERNMENT)
        assertTrue(result.deadlines.any { it.second.contains("2027") })
    }

    @Test
    fun billWrittenDueDate() {
        val text = "INVOICE\nAmount Due: £168.00\nDue Date: 15 October 2026"
        val result = extractor.extract(text, DocumentType.BILL)
        assertTrue(result.deadlines.any { it.second.contains("2026") })
    }

    @Test
    fun emptyTextWarns() {
        assertTrue(extractor.extract("", DocumentType.PRESCRIPTION).warnings.isNotEmpty())
    }

    @Test
    fun extractionIsDeterministic() {
        val text = "Medication: Amoxicillin 500mg\nDosage: Take ONE capsule THREE times daily"
        val a = extractor.extract(text, DocumentType.PRESCRIPTION).fields.map { it.label to it.value }
        val b = extractor.extract(text, DocumentType.PRESCRIPTION).fields.map { it.label to it.value }
        assertTrue(a == b)
    }

    @Test
    fun transactionsIsNotAnAction() {
        val text = """
            METROPOLITAN BANK PLC
            Recent Transactions:
            25 Sep  TESCO STORE  -£45.20
            Please contact us to renew your overdraft.
        """.trimIndent()
        val result = extractor.extract(text, DocumentType.BANKING)
        assertTrue(!result.actionRequired.lowercase().contains("transactions"))
        assertTrue(result.actionRequired.lowercase().contains("contact"))
    }

    @Test
    fun orgFieldDoesNotSpanLines() {
        val text = """
            HM Revenue & Customs
            Self Assessment Division
            BX9 1AS
            The deadline for submitting your return online is
            31 January 2027.
        """.trimIndent()
        val result = extractor.extract(text, DocumentType.GOVERNMENT)
        val from = result.fields.firstOrNull { it.label == "From" }?.value ?: ""
        assertTrue(!from.contains("\n"))
        assertTrue(!from.contains("Division"))
    }
}
