"""Tests for document extraction."""
import pytest
from ml.extraction.extractor import DocumentExtractor
from ml.classifier.engine import DocumentType


class TestDocumentExtractor:
    def setup_method(self):
        self.extractor = DocumentExtractor()

    def test_extracts_prescription_fields(self):
        text = """
        Medication: Amoxicillin 500mg capsules
        Dosage: Take ONE capsule THREE times daily
        Instructions: Take with or after food.
        Dr. Sarah Mitchell
        Pharmacy: Boots Pharmacy
        """
        result = self.extractor.extract(text, DocumentType.PRESCRIPTION)
        assert len(result.fields) > 0
        field_labels = [f.label for f in result.fields]
        assert "Medication" in field_labels or "Dosage" in field_labels or "Frequency" in field_labels
        assert len(result.medical_disclaimer) > 0

    def test_extracts_banking_fields(self):
        text = """
        Sort Code: 12-34-56
        Account Number: 12345678
        Balance: £2,847.35
        METROPOLITAN BANK PLC
        """
        result = self.extractor.extract(text, DocumentType.BANKING)
        assert len(result.fields) > 0 or len(result.monetary_values) > 0

    def test_extracts_bill_fields(self):
        text = """
        Amount Due: £168.00
        Due Date: 15/10/2026
        Reference: INV12345
        """
        result = self.extractor.extract(text, DocumentType.BILL)
        has_money = len(result.monetary_values) > 0
        has_deadlines = len(result.deadlines) > 0
        assert has_money or has_deadlines

    def test_extracts_government_fields(self):
        text = """
        HM Revenue & Customs
        RE: YOUR TAX RETURN
        Deadline: 31 January 2027
        """
        result = self.extractor.extract(text, DocumentType.GOVERNMENT)
        assert len(result.fields) > 0 or len(result.deadlines) > 0

    def test_handles_empty_text(self):
        result = self.extractor.extract("", DocumentType.PRESCRIPTION)
        assert len(result.warnings) > 0

    def test_prescription_has_disclaimer(self):
        text = "Medication: Amoxicillin"
        result = self.extractor.extract(text, DocumentType.PRESCRIPTION)
        assert "NOT medical advice" in result.medical_disclaimer

    def test_bill_has_action(self):
        text = "Amount Due: £100\nDue Date: 15/10/2026"
        result = self.extractor.extract(text, DocumentType.BILL)
        assert len(result.action_required) > 0
