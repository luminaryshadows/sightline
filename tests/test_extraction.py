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


class TestWrittenDateExtraction:
    """Dates written in prose (e.g. '31 January 2027') must be extracted."""

    def setup_method(self):
        self.extractor = DocumentExtractor()

    def test_govt_deadline_across_lines(self):
        text = (
            "HM Revenue & Customs\n"
            "The deadline for submitting your return online is\n"
            "31 January 2027.\n"
        )
        result = self.extractor.extract(text, DocumentType.GOVERNMENT)
        assert any("2027" in date for _, date in result.deadlines), result.deadlines

    def test_bill_written_due_date(self):
        text = "INVOICE\nAmount Due: £168.00\nDue Date: 15 October 2026\n"
        result = self.extractor.extract(text, DocumentType.BILL)
        assert any("2026" in date for _, date in result.deadlines), result.deadlines

    def test_ordinal_written_date(self):
        text = "This Agreement is made this 1st day of October 2026\n"
        # Should not crash; extraction is best-effort
        result = self.extractor.extract(text, DocumentType.LEGAL)
        assert result is not None


class TestExtractionDeterminism:
    """Extraction must be deterministic — no randomness, no network."""

    def test_repeated_extraction_is_stable(self):
        from ml.extraction.extractor import DocumentExtractor as DE
        ex = DE()
        text = "Medication: Amoxicillin 500mg\nDosage: Take ONE capsule THREE times daily"
        a = ex.extract(text, DocumentType.PRESCRIPTION)
        b = ex.extract(text, DocumentType.PRESCRIPTION)
        assert [(f.label, f.value) for f in a.fields] == [(f.label, f.value) for f in b.fields]


class TestStorageDeletion:
    """Document store must fully delete image, text, and analysis."""

    def test_in_memory_store_add_delete(self):
        from ml.storage import DocumentStore
        store = DocumentStore(persist_images=False)
        doc_id = store.add(analysis={"document_type": "prescription"}, original_filename="x.png")
        assert store.count == 1
        assert store.get(doc_id) is not None

        report = store.delete(doc_id)
        assert report["found"] is True
        assert report["analysis_deleted"] is True
        assert report["image_deleted"] is False  # no image persisted
        assert store.count == 0
        assert store.get(doc_id) is None

    def test_persisted_image_is_deleted(self):
        import os
        from ml.storage import DocumentStore
        store = DocumentStore(persist_images=True)
        doc_id = store.add(image_bytes=b"\x89PNG\r\n\x1a\nfakedata", analysis={"a": 1})
        img_path = store.get_image_path(doc_id)
        assert img_path is not None and os.path.exists(img_path)

        store.delete(doc_id)
        assert not os.path.exists(img_path)
        assert store.count == 0

    def test_delete_all_wipes_everything(self):
        import os
        from ml.storage import DocumentStore
        store = DocumentStore(persist_images=True)
        ids = [store.add(image_bytes=b"data", analysis={"i": i}) for i in range(3)]
        paths = [store.get_image_path(i) for i in ids]
        assert store.count == 3

        report = store.delete_all()
        assert report["deleted_count"] == 3
        assert store.count == 0
        assert all(p is None or not os.path.exists(p) for p in paths)

    def test_deleting_missing_document_is_safe(self):
        from ml.storage import DocumentStore
        store = DocumentStore()
        report = store.delete("does-not-exist")
        assert report["found"] is False


class TestKeywordBoundaries:
    """Short keywords must not fire on unrelated substrings."""

    def setup_method(self):
        self.extractor = DocumentExtractor()

    def test_transactions_is_not_an_action(self):
        text = (
            "METROPOLITAN BANK PLC\n"
            "Recent Transactions:\n"
            "25 Sep  TESCO STORE  -£45.20\n"
            "Please contact us to renew your overdraft."
        )
        result = self.extractor.extract(text, DocumentType.BANKING)
        assert "transactions" not in result.action_required.lower(), result.action_required
        assert "contact" in result.action_required.lower()

    def test_org_field_does_not_span_lines(self):
        text = (
            "HM Revenue & Customs\n"
            "Self Assessment Division\n"
            "BX9 1AS\n"
            "The deadline for submitting your return online is\n"
            "31 January 2027."
        )
        result = self.extractor.extract(text, DocumentType.GOVERNMENT)
        from_field = next((f.value for f in result.fields if f.label == "From"), "")
        assert "\n" not in from_field, repr(from_field)
        assert "Division" not in from_field
