package com.privatesight.app.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DocumentClassifierTest {

    private val classifier = DocumentClassifier()

    @Test
    fun classifiesPrescription() {
        val text = """
            OAKWOOD MEDICAL CENTRE
            Dr. Sarah Mitchell
            PRESCRIPTION
            Medication: Amoxicillin 500mg capsules
            Dosage: Take ONE capsule THREE times daily
            Pharmacy: Boots Pharmacy
        """.trimIndent()
        val result = classifier.classify(text)
        assertEquals(DocumentType.PRESCRIPTION, result.documentType)
        assertTrue(result.confidence > 0.3f)
    }

    @Test
    fun classifiesBanking() {
        val text = """
            METROPOLITAN BANK PLC
            STATEMENT OF ACCOUNT
            Account Number: 12345678
            Sort Code: 12-34-56
            Current Balance: £2,847.35
        """.trimIndent()
        assertEquals(DocumentType.BANKING, classifier.classify(text).documentType)
    }

    @Test
    fun classifiesBill() {
        val text = "INVOICE\nAmount Due: £168.00\nDue Date: 15/10/2026\nCustomer Number: 98765"
        assertEquals(DocumentType.BILL, classifier.classify(text).documentType)
    }

    @Test
    fun classifiesGovernment() {
        val text = "HM Revenue & Customs\nRE: YOUR TAX RETURN\nDeadline: 31 January 2027"
        assertEquals(DocumentType.GOVERNMENT, classifier.classify(text).documentType)
    }

    @Test
    fun classifiesLegal() {
        val text = "CONTRACT OF EMPLOYMENT\nThis Agreement is made\nWHEREAS the Employer agrees"
        assertEquals(DocumentType.LEGAL, classifier.classify(text).documentType)
    }

    @Test
    fun classifiesId() {
        val text = "PASSPORT\nDate of Birth: 15/03/1985\nNationality: British\nExpiry Date: 15/03/2030"
        assertEquals(DocumentType.ID, classifier.classify(text).documentType)
    }

    @Test
    fun unknownOnEmpty() {
        val result = classifier.classify("")
        assertEquals(DocumentType.UNKNOWN, result.documentType)
        assertEquals(0f, result.confidence, 0.001f)
    }

    @Test
    fun unknownOnGibberish() {
        assertEquals(DocumentType.UNKNOWN, classifier.classify("asdfghjkl qwertyuiop zxcvbnm").documentType)
    }
}
