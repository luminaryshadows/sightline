package com.privatesight.app.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineQuestionAnswererTest {

    private val qa = OfflineQuestionAnswerer()
    private val extractor = DocumentExtractor()

    private fun extraction(text: String, type: DocumentType) = extractor.extract(text, type)

    @Test
    fun answersDosage() {
        val text = "Medication: Amoxicillin 500mg\nDosage: Take ONE capsule THREE times daily"
        val ex = extraction(text, DocumentType.PRESCRIPTION)
        val a = qa.answer("How many tablets should I take?", text, ex, DocumentType.PRESCRIPTION)
        assertTrue(a.answer.contains("ONE") || a.answer.lowercase().contains("capsule"))
        assertTrue(a.isMedical)
        assertTrue(a.medicalDisclaimer.isNotEmpty())
    }

    @Test
    fun answersDeadline() {
        val text = "The deadline for submitting your return online is\n31 January 2027."
        val ex = extraction(text, DocumentType.GOVERNMENT)
        val a = qa.answer("When is the deadline?", text, ex, DocumentType.GOVERNMENT)
        assertTrue(a.answer.contains("2027"))
    }

    @Test
    fun notFoundForMissingInfo() {
        val text = "Simple document with no dates."
        val ex = extraction(text, DocumentType.UNKNOWN)
        val a = qa.answer("When is the deadline?", text, ex, DocumentType.UNKNOWN)
        assertTrue(a.answer.lowercase().contains("could not find"))
        assertEquals(0f, a.confidence, 0.001f)
    }

    @Test
    fun medicalSafetyQuestionIsRefusedSafely() {
        val text = "Medication: Amoxicillin"
        val ex = extraction(text, DocumentType.PRESCRIPTION)
        val a = qa.answer("Is this medication safe?", text, ex, DocumentType.PRESCRIPTION)
        assertTrue(a.answer.lowercase().contains("cannot determine") || a.answer.lowercase().contains("not medical advice"))
        assertTrue(a.isMedical)
    }

    @Test
    fun whatIsDocument() {
        val text = "Medication: Amoxicillin 500mg\nDosage: Take ONE daily"
        val ex = extraction(text, DocumentType.PRESCRIPTION)
        val a = qa.answer("What is this document?", text, ex, DocumentType.PRESCRIPTION)
        assertTrue(a.answer.lowercase().contains("prescription"))
    }
}
