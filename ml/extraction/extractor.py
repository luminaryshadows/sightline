"""
Document-specific information extraction.

Extracts structured fields from document text based on document type.
For each type, extracts: key fields, actions required, deadlines, monetary values.

All processing is local — extracted data never leaves the device.

IMPORTANT SAFETY: For medical documents, distinguishes between
what the document SAYS vs. medical advice. Never invents or infers
medical recommendations.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from ml.classifier.engine import DocumentType


# Matches either a numeric date (15/03/1985, 15-03-1985, 15.03.1985)
# or a written date (31 January 2027, 1st October 2026, Jan 31, 2027).
DATE_PATTERN = (
    r'(?:'
    r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}'
    r'|'
    r'\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|'
    r'August|September|October|November|December)\s+\d{2,4}'
    r'|'
    r'(?:January|February|March|April|May|June|July|August|September|October|'
    r'November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}'
    r')'
)


class ExtractionMode(Enum):
    """Extraction mode based on document type."""
    PRESCRIPTION = "prescription"
    BANKING = "banking"
    BILL = "bill"
    GOVERNMENT = "government"
    LEGAL = "legal"
    ID = "id"
    GENERIC = "generic"


@dataclass
class ExtractedField:
    """A single extracted field from the document."""
    label: str
    value: str
    confidence: float = 1.0
    source_text: str = ""  # The text from which this was extracted


@dataclass
class ExtractionResult:
    """Complete extraction result for a document."""
    document_type: DocumentType
    fields: list[ExtractedField] = field(default_factory=list)
    action_required: str = ""
    deadlines: list[tuple[str, str]] = field(default_factory=list)  # (description, date)
    monetary_values: list[tuple[str, str]] = field(default_factory=list)  # (description, amount)
    contacts: list[tuple[str, str]] = field(default_factory=list)  # (type, value)
    summary_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    medical_disclaimer: str = ""


class DocumentExtractor:
    """
    Extracts structured information from document OCR text.

    Uses regex patterns tailored to each document type.
    Extracts: key fields, actions required, deadlines, contacts, monetary values.

    SAFETY: For prescription documents, outputs only what the document says.
    Never invents medical advice.
    """

    MEDICAL_DISCLAIMER = (
        "IMPORTANT: This information is read directly from the document. "
        "This is NOT medical advice. Always follow the instructions on your "
        "prescription label. If anything is unclear, contact your doctor or pharmacist. "
        "Do not change your medication based on this reading."
    )

    def extract(
        self,
        text: str,
        document_type: DocumentType,
        sensitive_entities: list[Any] | None = None,
    ) -> ExtractionResult:
        """
        Extract structured information based on document type.

        Args:
            text: Full OCR text.
            document_type: Classified document type.
            sensitive_entities: Optional list of already-detected sensitive entities.

        Returns:
            ExtractionResult with extracted fields, actions, deadlines, etc.
        """
        if not text or not text.strip():
            return ExtractionResult(
                document_type=document_type,
                warnings=["No text available for extraction."],
            )

        if document_type == DocumentType.PRESCRIPTION:
            return self._extract_prescription(text)
        elif document_type == DocumentType.BANKING:
            return self._extract_banking(text)
        elif document_type == DocumentType.BILL:
            return self._extract_bill(text)
        elif document_type in (DocumentType.GOVERNMENT, DocumentType.LEGAL):
            return self._extract_government_legal(text, document_type)
        elif document_type == DocumentType.ID:
            return self._extract_id(text)
        else:
            return self._extract_generic(text)

    # ─── PRESCRIPTION ────────────────────────────────────────────

    def _extract_prescription(self, text: str) -> ExtractionResult:
        """Extract prescription-specific fields."""
        fields: list[ExtractedField] = []
        lines = text.split('\n')

        # Medication name
        med = self._find_first(text, [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+\d+\s*(?:mg|mcg|g|ml)\b',
            r'\b(?:medication|drug|medicine)[:\s]*([A-Za-z\s]+)\b',
        ])
        if med:
            fields.append(ExtractedField(label="Medication", value=med.strip()))

        # Dosage
        dosage = self._find_first(text, [
            r'\b(\d+\s*(?:mg|mcg|microgram|g|ml|IU|unit)s?)\b',
            r'\b(?:dosage|dose|strength)[:\s]*(\d+\s*(?:mg|mcg|g|ml))\b',
        ])
        if dosage:
            fields.append(ExtractedField(label="Dosage", value=dosage.strip()))

        # Frequency
        freq_patterns = [
            r'(?:take|use|apply)\s+((?:one|two|three|\d+)\s+(?:tablet|capsule|pill|dose)s?\s+(?:once|twice|three\s+times?|four\s+times?)\s+(?:daily|a\s+day|per\s+day))',
            r'\b((?:once|twice|three\s+times?|four\s+times?)\s+(?:daily|a\s+day|per\s+day))\b',
            r'\b((?:morning|evening|bedtime|night)\s+(?:and|&)\s+(?:morning|evening|bedtime|night))\b',
        ]
        frequency = self._find_first(text, freq_patterns)
        if frequency:
            fields.append(ExtractedField(label="Frequency", value=frequency.strip()))

        # Instructions
        instructions = self._find_line_containing(lines, [
            'direction', 'instruction', 'how to take', 'how to use',
            'take', 'apply', 'use', 'administer',
        ])
        if instructions and len(instructions) > 5:
            fields.append(ExtractedField(label="Instructions", value=instructions.strip()))

        # Warnings
        warnings = self._find_line_containing(lines, [
            'warning', 'caution', 'do not', 'avoid', 'side effect',
            'contraindication', 'precaution', 'allergy',
        ])
        if warnings:
            fields.append(ExtractedField(label="Warnings", value=warnings.strip()))

        # Doctor
        doctor = self._find_first(text, [
            r'(?:Dr|Doctor|Physician|Prescriber)[.:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:Dr\.?\s*)([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ])
        if doctor:
            fields.append(ExtractedField(label="Doctor", value=doctor.strip()))

        # Pharmacy
        pharmacy = self._find_first(text, [
            r'(?:Pharmacy|Dispenser|Chemist)[:\s]*([A-Za-z\s\',]+)',
        ])
        if pharmacy:
            fields.append(ExtractedField(label="Pharmacy", value=pharmacy.strip()))

        # Summary
        summary = self._build_prescription_summary(fields)

        return ExtractionResult(
            document_type=DocumentType.PRESCRIPTION,
            fields=fields,
            summary_lines=summary,
            medical_disclaimer=self.MEDICAL_DISCLAIMER,
        )

    def _build_prescription_summary(self, fields: list[ExtractedField]) -> list[str]:
        """Build accessible summary for prescription."""
        summary = []
        field_dict = {f.label: f.value for f in fields}

        if 'Medication' in field_dict:
            med = field_dict['Medication']
            dosage = field_dict.get('Dosage', '')
            summary.append(f"This prescription is for {med} {dosage}.".strip())

        if 'Frequency' in field_dict:
            summary.append(f"Take {field_dict['Frequency']}.")

        if 'Instructions' in field_dict:
            summary.append(f"Instructions: {field_dict['Instructions']}")

        if 'Warnings' in field_dict:
            summary.append(f"Warning: {field_dict['Warnings']}")

        if not summary:
            summary.append("This appears to be a prescription. Please verify the details.")

        return summary

    # ─── BANKING ──────────────────────────────────────────────────

    def _extract_banking(self, text: str) -> ExtractionResult:
        """Extract banking-specific fields."""
        fields: list[ExtractedField] = []
        deadlines: list[tuple[str, str]] = []
        monetary_values: list[tuple[str, str]] = []
        lines = text.split('\n')

        # Institution
        institution = self._find_first(text, [
            r'(?:HSBC|Barclays|Lloyds|NatWest|Santander|Halifax|TSB|RBS|Monzo|Starling|Revolut|Nationwide|Metro|Chase)\b',
        ])
        if institution:
            fields.append(ExtractedField(label="Institution", value=institution.strip()))

        # Amount
        amounts = re.findall(r'[£$€]\s*\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})', text)
        for amt in amounts[:3]:
            monetary_values.append(("Amount", amt.strip()))

        # Transaction reference
        ref = self._find_first(text, [
            r'(?:reference|ref|transaction|payment)[\s#:]*([A-Z0-9\-]{4,})',
        ])
        if ref:
            fields.append(ExtractedField(label="Reference", value=ref.strip()))

        # Account info
        sort_code = self._find_first(text, [r'sort\s*code[:\s]*(\d{2}[\s-]?\d{2}[\s-]?\d{2})'])
        if sort_code:
            fields.append(ExtractedField(label="Sort Code", value=sort_code.strip()))

        acct_num = self._find_first(text, [r'account\s*(?:number|no)?[:\s]*(\d{8,})'])
        if acct_num:
            fields.append(ExtractedField(label="Account Number", value=acct_num.strip()))

        # Dates
        for line in lines:
            date_match = re.search(DATE_PATTERN, line)
            if date_match:
                if re.search(r'due|payment|deadline', line, re.IGNORECASE):
                    deadlines.append(("Payment Date", date_match.group(0)))
                elif re.search(r'statement|period|from|to', line, re.IGNORECASE):
                    deadlines.append(("Statement Date", date_match.group(0)))

        # Action required
        action = self._find_line_containing(lines, [
            'action', 'required', 'please contact', 'notice', 'overdrawn',
            'overdue', 'payment required', 'urgent',
        ])
        action_required = action or "No immediate action identified."

        summary = self._build_banking_summary(fields, monetary_values)
        if action:
            summary.append(f"Action: {action}")

        return ExtractionResult(
            document_type=DocumentType.BANKING,
            fields=fields,
            monetary_values=monetary_values,
            deadlines=deadlines,
            action_required=action_required,
            summary_lines=summary,
        )

    def _build_banking_summary(
        self, fields: list[ExtractedField], monetary_values: list[tuple[str, str]]
    ) -> list[str]:
        """Build accessible summary for banking documents."""
        summary = []
        field_dict = {f.label: f.value for f in fields}

        inst = field_dict.get('Institution', 'your bank')
        summary.append(f"This is a document from {inst}.")

        if monetary_values:
            for _, amt in monetary_values[:2]:
                summary.append(f"It involves {amt}.")

        return summary

    # ─── BILL/INVOICE ─────────────────────────────────────────────

    def _extract_bill(self, text: str) -> ExtractionResult:
        """Extract bill-specific fields."""
        fields: list[ExtractedField] = []
        deadlines: list[tuple[str, str]] = []
        monetary_values: list[tuple[str, str]] = []
        lines = text.split('\n')

        # Company name
        company = self._find_first(text, [
            r'^([A-Z][A-Za-z\s&.,\']{3,40})$',
        ])
        if company and not re.search(r'(?:invoice|bill|statement|total|amount|date|page)', company, re.IGNORECASE):
            fields.append(ExtractedField(label="Company", value=company.strip()))

        # Amount due
        amt_due = self._find_first(text, [
            r'(?:total\s+due|amount\s+due|total\s+payable|balance\s+due)[:\s]*[£$€]?\s*(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2}))',
            r'(?:total|sum)[:\s]*[£$€]?\s*(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2}))',
        ])
        if amt_due:
            monetary_values.append(("Amount Due", amt_due.strip()))

        # Due date
        due_date = self._find_first(text, [
            r'(?:due\s+date|payment\s+due|pay\s+by)[:\s]*(' + DATE_PATTERN + r')',
        ])
        if due_date:
            deadlines.append(("Due Date", due_date.strip()))

        # Reference
        ref = self._find_first(text, [
            r'(?:reference|ref|invoice|account|customer)[\s#:]*([A-Z0-9\-]{4,})',
        ])
        if ref:
            fields.append(ExtractedField(label="Reference", value=ref.strip()))

        # Payment instructions
        payment = self._find_line_containing(lines, [
            'payment', 'pay by', 'bank transfer', 'direct debit',
            'sort code', 'account number', 'how to pay',
        ])
        if payment:
            fields.append(ExtractedField(label="Payment Instructions", value=payment.strip()))

        summary = self._build_bill_summary(fields, monetary_values, deadlines)

        action = f"Payment of {amt_due} is due by {due_date}." if amt_due and due_date else "Please review this bill."

        return ExtractionResult(
            document_type=DocumentType.BILL,
            fields=fields,
            monetary_values=monetary_values,
            deadlines=deadlines,
            action_required=action,
            summary_lines=summary,
        )

    def _build_bill_summary(
        self, fields: list[ExtractedField],
        monetary_values: list[tuple[str, str]],
        deadlines: list[tuple[str, str]],
    ) -> list[str]:
        """Build accessible summary for bills."""
        summary = []
        field_dict = {f.label: f.value for f in fields}

        company = field_dict.get('Company', 'a company')
        summary.append(f"This is a bill from {company}.")

        for label, value in monetary_values:
            summary.append(f"The {label.lower()} is {value}.")

        for label, date in deadlines:
            summary.append(f"The {label.lower()} is {date}.")

        return summary

    # ─── GOVERNMENT / LEGAL ───────────────────────────────────────

    def _extract_government_legal(self, text: str, doc_type: DocumentType) -> ExtractionResult:
        """Extract fields from government and legal documents."""
        fields: list[ExtractedField] = []
        deadlines: list[tuple[str, str]] = []
        monetary_values: list[tuple[str, str]] = []
        contacts: list[tuple[str, str]] = []
        lines = text.split('\n')

        # Organization
        org = self._find_first(text, [
            r'(?:HM\s+Revenue|HMRC|DWP|NHS|Home\s+Office|DVLA|Council|Department\s+for|Ministry\s+of)[ ]+[A-Za-z &]+',
            r'^([A-Z][A-Za-z &.,()]{5,50})$',
        ])
        if org:
            fields.append(ExtractedField(label="From", value=org.strip()))

        # Subject / Reference
        subject = self._find_first(text, [
            r'(?:Re|Subject|Reference|Our Ref|Your Ref)[:\s]+(.+?)(?:\n|$)',
        ])
        if subject:
            fields.append(ExtractedField(label="Subject", value=subject.strip()))

        # Dates — line-local first
        for line in lines:
            date_match = re.search(DATE_PATTERN, line)
            if date_match:
                if re.search(r'deadline|by|before|due|respond|reply', line, re.IGNORECASE):
                    deadlines.append(("Deadline", date_match.group(0)))
                elif re.search(r'hearing|court|appointment|interview', line, re.IGNORECASE):
                    deadlines.append(("Date", date_match.group(0)))

        # Dates — proximity search across the whole text, since the keyword
        # ("deadline is") and the date often fall on different lines.
        if not deadlines:
            for kw_match in re.finditer(
                r'deadline|due\s+by|must\s+(?:be\s+)?(?:submitted|paid|respond)|'
                r'before|no\s+later\s+than|respond\s+by|expires?',
                text, re.IGNORECASE,
            ):
                window = text[kw_match.start(): kw_match.start() + 160]
                dm = re.search(DATE_PATTERN, window)
                if dm:
                    deadlines.append(("Deadline", dm.group(0)))
                    break

        # Action required
        action = self._find_line_containing(lines, [
            'you must', 'you need to', 'required to', 'action',
            'please respond', 'please contact', 'failure to',
            'by law', 'obligation', 'deadline', 'respond by',
        ])

        # Contacts
        phone_matches = re.findall(r'(?:Tel|Telephone|Phone|Call)[:\s]*(\+?[\d\s\-]{8,})', text, re.IGNORECASE)
        for pm in phone_matches:
            contacts.append(("Phone", pm.strip()))

        email_matches = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        for em in email_matches[:2]:
            contacts.append(("Email", em.strip()))

        summary = []
        if org:
            summary.append(f"This is a {doc_type.value} document from {org}.")
        if subject:
            summary.append(f"It concerns: {subject}.")
        if deadlines:
            for desc, date in deadlines:
                summary.append(f"{desc}: {date}.")
        if action:
            summary.append(f"Action required: {action}")

        action_required = action if action else "No specific action identified. Please review the document."

        return ExtractionResult(
            document_type=doc_type,
            fields=fields,
            deadlines=deadlines,
            monetary_values=monetary_values,
            contacts=contacts,
            action_required=action_required,
            summary_lines=summary,
        )

    # ─── ID ───────────────────────────────────────────────────────

    def _extract_id(self, text: str) -> ExtractionResult:
        """Extract ID document fields."""
        fields: list[ExtractedField] = []

        # Name
        name = self._find_first(text, [
            r'(?:Name|Surname|Given\s+Names?|Holder)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ])
        if name:
            fields.append(ExtractedField(label="Name", value=name.strip()))

        # DOB
        dob = self._find_first(text, [
            r'(?:Date\s+of\s+Birth|DOB|Born)[:\s]*(' + DATE_PATTERN + r')',
        ])
        if dob:
            fields.append(ExtractedField(label="Date of Birth", value=dob.strip()))

        # Document number
        doc_num = self._find_first(text, [
            r'(?:Passport|Document|ID|License|Number)[\s#:]*([A-Z0-9]{6,})',
        ])
        if doc_num:
            fields.append(ExtractedField(label="Document Number", value=doc_num.strip()))

        # Nationality
        nat = self._find_first(text, [
            r'(?:Nationality|Citizenship)[:\s]*([A-Za-z\s]+)',
        ])
        if nat:
            fields.append(ExtractedField(label="Nationality", value=nat.strip()))

        # Expiry
        expiry = self._find_first(text, [
            r'(?:Expir\w+|Valid\s+Until)[:\s]*(' + DATE_PATTERN + r')',
        ])
        if expiry:
            fields.append(ExtractedField(label="Expiry Date", value=expiry.strip()))

        summary = ["This appears to be an identification document."]
        if name:
            summary.append(f"Name: {name}")

        return ExtractionResult(
            document_type=DocumentType.ID,
            fields=fields,
            summary_lines=summary,
            action_required="No action required.",
        )

    # ─── GENERIC ──────────────────────────────────────────────────

    def _extract_generic(self, text: str) -> ExtractionResult:
        """Extract generic fields from unknown document types."""
        fields: list[ExtractedField] = []
        lines = [l for l in text.split('\n') if len(l.strip()) > 10]

        summary = []
        if lines:
            summary.append("Document content was extracted but the type could not be identified.")
            summary.append(f"First line: {lines[0][:100]}")

        return ExtractionResult(
            document_type=DocumentType.UNKNOWN,
            fields=fields,
            summary_lines=summary,
            action_required="Could not identify document type. Please review manually.",
            warnings=["Document type unknown. Extraction may be incomplete."],
        )

    # ─── HELPERS ──────────────────────────────────────────────────

    def _find_first(self, text: str, patterns: list[str]) -> str | None:
        """Find the first match across multiple patterns."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        return None

    def _find_line_containing(self, lines: list[str], keywords: list[str]) -> str | None:
        """
        Find the first line containing any of the keywords.

        Matching uses word boundaries so short keywords do not fire on
        unrelated substrings (e.g. "action" must not match "Transactions").
        """
        compiled = [re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE) for k in keywords]
        for line in lines:
            for pattern in compiled:
                if pattern.search(line):
                    return line.strip()
        return None


def create_extractor() -> DocumentExtractor:
    """Factory function for creating a document extractor."""
    return DocumentExtractor()
