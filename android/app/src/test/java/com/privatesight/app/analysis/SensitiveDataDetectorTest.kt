package com.privatesight.app.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SensitiveDataDetectorTest {

    private val detector = SensitiveDataDetector()

    private fun types(text: String) = detector.detect(text).entities.map { it.type }.toSet()

    @Test fun detectsPhone() = assertTrue(EntityType.PHONE_NUMBER in types("Tel: 020 7946 0123"))
    @Test fun detectsEmail() = assertTrue(EntityType.EMAIL in types("Contact: jamie.chen@example.com"))
    @Test fun detectsPostcode() = assertTrue(EntityType.POSTCODE in types("London NW1 4NP"))
    @Test fun detectsMoney() = assertTrue(EntityType.MONETARY_VALUE in types("Balance: £2,847.35"))
    @Test fun detectsMedication() = assertTrue(EntityType.MEDICATION in types("Take Amoxicillin 500mg capsules"))
    @Test fun detectsDosage() = assertTrue(EntityType.DOSAGE in types("Take ONE capsule THREE times daily"))
    @Test fun detectsDob() = assertTrue(EntityType.DATE_OF_BIRTH in types("Date of Birth: 15/03/1985"))
    @Test fun detectsAccount() = assertTrue(EntityType.ACCOUNT_NUMBER in types("Account Number: 12345678"))

    @Test
    fun emptyTextDetectsNothing() {
        val result = detector.detect("")
        assertTrue(!result.detected)
        assertEquals(0, result.entityCount)
    }

    @Test
    fun highRiskForMultipleCritical() {
        val text = "NHS Number: 485 721 9362\nDOB: 15/03/1985\nMedication: Amoxicillin 500mg"
        assertEquals("high", detector.detect(text).riskLevel)
    }

    @Test
    fun deduplicatesEntities() {
        val text = "Tel: 020 7946 0123 also 020 7946 0123"
        val phones = detector.detect(text).entities.filter { it.type == EntityType.PHONE_NUMBER }
        assertEquals(1, phones.size)
    }
}
