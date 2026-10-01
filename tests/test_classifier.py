"""Tests for document classifier."""
import pytest
from ml.classifier.engine import DocumentClassifier, DocumentType


class TestDocumentClassifier:
    def setup_method(self):
        self.classifier = DocumentClassifier()

    def test_prescription_classification(self):
        text = """
        OAKWOOD MEDICAL CENTRE
        Dr. Sarah Mitchell
        PRESCRIPTION
        Medication: Amoxicillin 500mg capsules
        Dosage: Take ONE capsule THREE times daily
        Pharmacy: Boots Pharmacy
        """
        result = self.classifier.classify(text)
        assert result.document_type == DocumentType.PRESCRIPTION
        assert result.confidence > 0.3

    def test_banking_classification(self):
        text = """
        METROPOLITAN BANK PLC
        STATEMENT OF ACCOUNT
        Account Holder: Jamie Chen
        Account Number: 12345678
        Sort Code: 12-34-56
        Current Balance: £2,847.35
        """
        result = self.classifier.classify(text)
        assert result.document_type == DocumentType.BANKING
        assert result.confidence > 0.3

    def test_bill_classification(self):
        text = """
        INVOICE
        Amount Due: £168.00
        Due Date: 15/10/2026
        Customer Number: 98765
        Please pay by bank transfer.
        """
        result = self.classifier.classify(text)
        assert result.document_type == DocumentType.BILL
        assert result.confidence > 0.3

    def test_government_classification(self):
        text = """
        HM Revenue & Customs
        RE: YOUR TAX RETURN
        Deadline: 31 January 2027
        National Insurance Number: AB123456C
        """
        result = self.classifier.classify(text)
        assert result.document_type == DocumentType.GOVERNMENT
        assert result.confidence > 0.3

    def test_legal_classification(self):
        text = """
        CONTRACT OF EMPLOYMENT
        This Agreement is made this 1st day of October 2026
        BETWEEN the Employer and the Employee
        WHEREAS the Employer agrees to employ
        """
        result = self.classifier.classify(text)
        assert result.document_type == DocumentType.LEGAL
        assert result.confidence > 0.3

    def test_id_classification(self):
        text = """
        PASSPORT
        Date of Birth: 15/03/1985
        Nationality: British
        Passport Number: 123456789
        Expiry Date: 15/03/2030
        """
        result = self.classifier.classify(text)
        assert result.document_type == DocumentType.ID
        assert result.confidence > 0.3

    def test_unknown_on_empty(self):
        result = self.classifier.classify("")
        assert result.document_type == DocumentType.UNKNOWN
        assert result.confidence == 0.0

    def test_unknown_on_gibberish(self):
        result = self.classifier.classify("asdfghjkl qwertyuiop zxcvbnm")
        assert result.document_type == DocumentType.UNKNOWN
        assert result.confidence == 0.0

    def test_returns_evidence(self):
        text = "PRESCRIPTION Amoxicillin 500mg Dosage: Take ONE tablet daily"
        result = self.classifier.classify(text)
        assert len(result.evidence) > 0

    def test_returns_alternatives(self):
        text = """
        ACCOUNT STATEMENT
        Sort Code: 12-34-56
        Account Number: 12345678
        Amount Due: £168.00
        Due Date: 15/10/2026
        """
        result = self.classifier.classify(text)
        # Should detect some alternatives
        assert isinstance(result.alternative_types, list)
