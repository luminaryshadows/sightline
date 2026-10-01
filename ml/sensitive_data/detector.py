"""
Sensitive information detection engine.

Detects PII and sensitive data in document text using regex patterns.
All processing is local — no data leaves the device.

Detects: names, phone numbers, emails, addresses, account numbers,
credit card numbers, ID numbers, medication info, monetary values.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any


class EntityType(Enum):
    """Types of sensitive entities detected."""
    PERSON_NAME = "person_name"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    ADDRESS = "address"
    POSTCODE = "postcode"
    ACCOUNT_NUMBER = "account_number"
    SORT_CODE = "sort_code"
    CREDIT_CARD = "credit_card"
    ID_NUMBER = "id_number"
    MEDICATION = "medication"
    DOSAGE = "dosage"
    MEDICAL_INFO = "medical_info"
    MONETARY_VALUE = "monetary_value"
    DATE_OF_BIRTH = "date_of_birth"
    NATIONAL_INSURANCE = "national_insurance"
    NHS_NUMBER = "nhs_number"


@dataclass
class SensitiveEntity:
    """A detected sensitive information entity."""
    entity_type: EntityType
    value: str
    context: str = ""  # Surrounding text for context
    confidence: float = 1.0  # Regex has 1.0; NLP models would have < 1.0


@dataclass
class SensitiveDataResult:
    """Complete sensitive data detection result."""
    sensitive_information_detected: bool
    entities: list[SensitiveEntity] = field(default_factory=list)
    entity_count: int = 0
    risk_level: str = "none"  # none, low, medium, high
    warnings: list[str] = field(default_factory=list)


# --- Pattern Definitions ---

# UK Phone Numbers
PHONE_PATTERNS = [
    re.compile(r'\b0\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b'),
    re.compile(r'\+44[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b'),
    re.compile(r'\b\d{5}\s?\d{6}\b'),
    re.compile(r'\b\d{3}[\s-]\d{3}[\s-]\d{4}\b'),
]

# UK Postcodes
POSTCODE_PATTERN = re.compile(
    r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b',
    re.IGNORECASE
)

# UK Sort Codes
SORT_CODE_PATTERN = re.compile(r'\b\d{2}[\s-]?\d{2}[\s-]?\d{2}\b')

# Account Numbers
ACCOUNT_NUMBER_PATTERN = re.compile(r'\b\d{8}\b')

# Credit/Debit Card Numbers (13-19 digits, with/without spaces)
CARD_PATTERN = re.compile(r'\b(?:\d[\s-]*){13,19}\b')

# Email
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Monetary values
MONEY_PATTERNS = [
    re.compile(r'[£$€]\s*\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})\b'),
    re.compile(r'\b\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})\s*(?:pounds?|dollars?|euros?|GBP|USD|EUR)\b', re.IGNORECASE),
    re.compile(r'\b(?:total|amount|sum|balance|payment|due|charge|fee)\s*(?:of|:)?\s*[£$€]?\s*\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})\b', re.IGNORECASE),
]

# National Insurance Number (UK)
NI_PATTERN = re.compile(
    r'\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b',
    re.IGNORECASE
)

# NHS Number
NHS_PATTERN = re.compile(r'\b\d{3}[\s-]?\d{3}[\s-]?\d{4}\b')

# Date of Birth
DOB_PATTERNS = [
    re.compile(r'\b(?:DOB|Date\s+of\s+Birth|Born)[:\s]*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b', re.IGNORECASE),
    re.compile(r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b'),
]

# Medication names (common prefixes/suffixes and patterns)
MEDICATION_PATTERNS = [
    re.compile(r'\b[A-Z][a-z]*(?:cillin|cycline|azole|prazole|sartan|statin|pril|olol|dipine|zepam|profen|thromycin|oxacin|vir|mab|nib|parin|vastatin)\b'),
    re.compile(r'\b(?:paracetamol|ibuprofen|aspirin|omeprazole|simvastatin|atorvastatin|metformin|amlodipine|ramipril|lisinopril|salbutamol|amoxicillin|fluoxetine|sertraline|citalopram|codeine|tramadol|morphine|gabapentin|pregabalin|insulin|warfarin|apixaban|rivaroxaban)\b', re.IGNORECASE),
]

# Dosage patterns
DOSAGE_PATTERNS = [
    re.compile(r'\b\d+\s*(?:mg|mcg|microgram|gram|g|ml|IU|units?)\b', re.IGNORECASE),
    re.compile(r'\b(?:take|apply|use|inject|inhale)\s+(?:one|two|three|\d+)\b', re.IGNORECASE),
    re.compile(r'\b(?:once|twice|three\s+times?|four\s+times?)\s+(?:daily|a\s+day|per\s+day)\b', re.IGNORECASE),
    re.compile(r'\b(?:morning|evening|bedtime|night|with\s+food|after\s+food|before\s+food|on\s+empty\s+stomach)\b', re.IGNORECASE),
]

# ID Numbers (passport, driving license, etc.)
ID_PATTERNS = [
    re.compile(r'\b(?:passport|document|ID|license|licence|reference)[\s#:]*[A-Z0-9]{6,}\b', re.IGNORECASE),
    re.compile(r'\b[A-Z0-9]{9}\b'),  # UK passport number format
    re.compile(r'\b[A-Z]{1,2}\d{6,7}\b'),  # Various ID formats
]

# Address patterns (UK)
ADDRESS_PATTERNS = [
    re.compile(r'\b\d{1,4}\s+[A-Z][a-z]+(?:\s+(?:Street|Road|Avenue|Lane|Drive|Close|Way|Court|Place|Gardens|Terrace|Crescent|Square|Row|Walk|Gate|Mews|Rise|Hill|Park|Green|Wood|Heath|Field|View))\b', re.IGNORECASE),
    re.compile(r'\b(?:Flat|Apartment|Unit)\s+\d+[A-Z]?\b', re.IGNORECASE),
]


class SensitiveDataDetector:
    """
    Detects sensitive/personal information in document text.

    Uses regex patterns and rule-based detection.
    Designed for easy replacement/addition of a PyTorch NER model later.

    All processing is local — detected data never leaves the device.
    """

    def __init__(self):
        """Initialize patterns."""
        self._name_prefixes = {'mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'rev', 'sir', 'lord', 'lady'}

    def detect(self, text: str, ocr_regions: list[Any] | None = None) -> SensitiveDataResult:
        """
        Detect sensitive information in document text.

        Args:
            text: Full OCR text from the document.
            ocr_regions: Optional list of TextRegion objects for context.

        Returns:
            SensitiveDataResult with all detected entities.
        """
        entities: list[SensitiveEntity] = []
        warnings: list[str] = []

        if not text or not text.strip():
            return SensitiveDataResult(
                sensitive_information_detected=False,
                warnings=["No text available for sensitive data detection."],
            )

        # Phone numbers
        for pattern in PHONE_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.PHONE_NUMBER,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # Emails
        for match in EMAIL_PATTERN.finditer(text):
            entities.append(SensitiveEntity(
                entity_type=EntityType.EMAIL,
                value=match.group().strip(),
                context=self._get_context(text, match.start(), match.end()),
            ))

        # Postcodes
        for match in POSTCODE_PATTERN.finditer(text):
            entities.append(SensitiveEntity(
                entity_type=EntityType.POSTCODE,
                value=match.group().strip(),
                context=self._get_context(text, match.start(), match.end()),
            ))

        # Sort codes (narrower context: look for "sort code" nearby)
        sort_code_lines = [l for l in text.split('\n') if re.search(r'sort\s*code', l, re.IGNORECASE)]
        for line in sort_code_lines:
            for match in SORT_CODE_PATTERN.finditer(line):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.SORT_CODE,
                    value=match.group().strip(),
                    context=line.strip(),
                ))

        # Account numbers (need context to avoid false positives)
        acct_lines = [l for l in text.split('\n') if re.search(r'account|acct|a/c', l, re.IGNORECASE)]
        for line in acct_lines:
            for match in ACCOUNT_NUMBER_PATTERN.finditer(line):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.ACCOUNT_NUMBER,
                    value=match.group().strip(),
                    context=line.strip(),
                ))

        # Credit/debit cards
        for match in CARD_PATTERN.finditer(text):
            val = match.group().strip().replace(' ', '').replace('-', '')
            if 13 <= len(val) <= 19 and val.isdigit():
                entities.append(SensitiveEntity(
                    entity_type=EntityType.CREDIT_CARD,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # Monetary values
        for pattern in MONEY_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.MONETARY_VALUE,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # National Insurance
        for match in NI_PATTERN.finditer(text):
            entities.append(SensitiveEntity(
                entity_type=EntityType.NATIONAL_INSURANCE,
                value=match.group().strip(),
                context=self._get_context(text, match.start(), match.end()),
            ))

        # NHS Number (with context)
        nhs_lines = [l for l in text.split('\n') if re.search(r'NHS', l, re.IGNORECASE)]
        for line in nhs_lines:
            for match in NHS_PATTERN.finditer(line):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.NHS_NUMBER,
                    value=match.group().strip(),
                    context=line.strip(),
                ))

        # Date of birth
        for pattern in DOB_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.DATE_OF_BIRTH,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # Medication names
        for pattern in MEDICATION_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.MEDICATION,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # Dosage
        for pattern in DOSAGE_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.DOSAGE,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # ID numbers
        for pattern in ID_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.ID_NUMBER,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # Addresses
        for pattern in ADDRESS_PATTERNS:
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    entity_type=EntityType.ADDRESS,
                    value=match.group().strip(),
                    context=self._get_context(text, match.start(), match.end()),
                ))

        # Person names (simple heuristic: title + capitalized words)
        for match in re.finditer(r'\b((?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', text):
            entities.append(SensitiveEntity(
                entity_type=EntityType.PERSON_NAME,
                value=match.group().strip(),
                context=self._get_context(text, match.start(), match.end()),
                confidence=0.7,
            ))

        # Deduplicate
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e.entity_type.value, e.value)
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        # Assess risk level
        risk_level = self._assess_risk(unique_entities)

        return SensitiveDataResult(
            sensitive_information_detected=len(unique_entities) > 0,
            entities=unique_entities,
            entity_count=len(unique_entities),
            risk_level=risk_level,
            warnings=warnings,
        )

    def _get_context(self, text: str, start: int, end: int, window: int = 60) -> str:
        """Get surrounding text context for an entity."""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        return text[ctx_start:ctx_end].strip()

    def _assess_risk(self, entities: list[SensitiveEntity]) -> str:
        """Assess overall sensitivity risk level."""
        high_risk_types = {
            EntityType.CREDIT_CARD,
            EntityType.ACCOUNT_NUMBER,
            EntityType.NATIONAL_INSURANCE,
            EntityType.NHS_NUMBER,
            EntityType.DATE_OF_BIRTH,
            EntityType.MEDICATION,
            EntityType.DOSAGE,
        }
        medium_risk_types = {
            EntityType.PERSON_NAME,
            EntityType.ADDRESS,
            EntityType.PHONE_NUMBER,
            EntityType.EMAIL,
            EntityType.POSTCODE,
            EntityType.SORT_CODE,
            EntityType.ID_NUMBER,
        }

        high_count = sum(1 for e in entities if e.entity_type in high_risk_types)
        medium_count = sum(1 for e in entities if e.entity_type in medium_risk_types)

        if high_count >= 2:
            return "high"
        elif high_count >= 1 or medium_count >= 3:
            return "medium"
        elif medium_count >= 1:
            return "low"
        return "none"


def create_detector() -> SensitiveDataDetector:
    """Factory function for creating a sensitive data detector."""
    return SensitiveDataDetector()
