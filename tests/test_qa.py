"""Tests for question answering engine."""
import pytest
from ml.qa.engine import OfflineQuestionAnswerer
from ml.extraction.extractor import DocumentExtractor
from ml.classifier.engine import DocumentType


class TestOfflineQuestionAnswerer:
    def setup_method(self):
        self.qa = OfflineQuestionAnswerer()
        self.extractor = DocumentExtractor()

    def _get_extraction(self, text, doc_type):
        return self.extractor.extract(text, doc_type)

    def test_answers_dosage_question(self):
        text = "Medication: Amoxicillin 500mg\nDosage: Take ONE capsule THREE times daily"
        extraction = self._get_extraction(text, DocumentType.PRESCRIPTION)
        answer = self.qa.answer(
            "How many tablets should I take?",
            text, extraction, DocumentType.PRESCRIPTION
        )
        assert "ONE" in answer.answer or "capsule" in answer.answer.lower()
        assert answer.is_medical

    def test_answers_amount_question(self):
        text = "Total Due: £168.00"
        extraction = self._get_extraction(text, DocumentType.BILL)
        answer = self.qa.answer(
            "How much do I owe?",
            text, extraction, DocumentType.BILL
        )
        assert len(answer.answer) > 0

    def test_answers_deadline_question(self):
        text = "Deadline: 31 January 2027"
        extraction = self._get_extraction(text, DocumentType.GOVERNMENT)
        answer = self.qa.answer(
            "When is the deadline?",
            text, extraction, DocumentType.GOVERNMENT
        )
        assert len(answer.answer) > 0

    def test_answers_who_question(self):
        text = "Dr. Sarah Mitchell\nOAKWOOD MEDICAL CENTRE"
        extraction = self._get_extraction(text, DocumentType.PRESCRIPTION)
        answer = self.qa.answer(
            "Who sent this?",
            text, extraction, DocumentType.PRESCRIPTION
        )
        assert len(answer.answer) > 0

    def test_returns_not_found_for_unknown_info(self):
        text = "Simple document with no dates."
        extraction = self._get_extraction(text, DocumentType.UNKNOWN)
        answer = self.qa.answer(
            "When is the deadline?",
            text, extraction, DocumentType.UNKNOWN
        )
        assert "could not find" in answer.answer.lower()
        assert answer.confidence == 0.0

    def test_medical_safety_response(self):
        text = "Medication: Amoxicillin"
        extraction = self._get_extraction(text, DocumentType.PRESCRIPTION)
        answer = self.qa.answer(
            "Is this medication safe?",
            text, extraction, DocumentType.PRESCRIPTION
        )
        assert "cannot determine" in answer.answer.lower() or "not medical advice" in answer.answer.lower()
        assert answer.is_medical

    def test_handles_empty_text(self):
        extraction = self._get_extraction("", DocumentType.UNKNOWN)
        answer = self.qa.answer(
            "What is this document?",
            "", extraction, DocumentType.UNKNOWN
        )
        assert len(answer.answer) > 0
