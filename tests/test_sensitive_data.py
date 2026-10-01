"""Tests for sensitive data detector."""
import pytest
from ml.sensitive_data.detector import SensitiveDataDetector, EntityType


class TestSensitiveDataDetector:
    def setup_method(self):
        self.detector = SensitiveDataDetector()

    def test_detects_phone_number(self):
        text = "Tel: 020 7946 0123"
        result = self.detector.detect(text)
        assert result.sensitive_information_detected
        phone_entities = [e for e in result.entities if e.entity_type == EntityType.PHONE_NUMBER]
        assert len(phone_entities) > 0

    def test_detects_email(self):
        text = "Contact: jamie.chen@example.com"
        result = self.detector.detect(text)
        email_entities = [e for e in result.entities if e.entity_type == EntityType.EMAIL]
        assert len(email_entities) > 0

    def test_detects_postcode(self):
        text = "London NW1 4NP"
        result = self.detector.detect(text)
        postcode_entities = [e for e in result.entities if e.entity_type == EntityType.POSTCODE]
        assert len(postcode_entities) > 0

    def test_detects_monetary_values(self):
        text = "Balance: £2,847.35"
        result = self.detector.detect(text)
        money_entities = [e for e in result.entities if e.entity_type == EntityType.MONETARY_VALUE]
        assert len(money_entities) > 0

    def test_detects_medication(self):
        text = "Take Amoxicillin 500mg capsules"
        result = self.detector.detect(text)
        med_entities = [e for e in result.entities if e.entity_type == EntityType.MEDICATION]
        assert len(med_entities) > 0

    def test_detects_dosage(self):
        text = "Take ONE capsule THREE times daily"
        result = self.detector.detect(text)
        dosage_entities = [e for e in result.entities if e.entity_type == EntityType.DOSAGE]
        assert len(dosage_entities) > 0

    def test_detects_date_of_birth(self):
        text = "Date of Birth: 15/03/1985"
        result = self.detector.detect(text)
        dob_entities = [e for e in result.entities if e.entity_type == EntityType.DATE_OF_BIRTH]
        assert len(dob_entities) > 0

    def test_detects_account_numbers_with_context(self):
        text = "Account Number: 12345678"
        result = self.detector.detect(text)
        acct_entities = [e for e in result.entities if e.entity_type == EntityType.ACCOUNT_NUMBER]
        assert len(acct_entities) > 0

    def test_empty_text(self):
        result = self.detector.detect("")
        assert not result.sensitive_information_detected
        assert len(result.entities) == 0

    def test_risk_level_high_for_multiple_critical(self):
        text = "NHS Number: 485 721 9362\nDOB: 15/03/1985\nMedication: Amoxicillin 500mg\nDosage: Take ONE daily"
        result = self.detector.detect(text)
        assert result.risk_level == "high"

    def test_deduplicates_entities(self):
        text = "Tel: 020 7946 0123 also reachable at 020 7946 0123"
        result = self.detector.detect(text)
        phone_entities = [e for e in result.entities if e.entity_type == EntityType.PHONE_NUMBER]
        assert len(phone_entities) == 1  # Deduplicated
