"""
Offline question answering for document content.

Answers user questions using only information extracted from the
current document. Uses keyword matching and extraction-based retrieval.
Never hallucinates — returns "I could not find that information" when
information is unavailable.

IMPORTANT: For medical questions, does not invent or infer medical advice.
Reads and reports only what is actually written in the document.

All processing is local — questions and document text never leave the device.
"""

from dataclasses import dataclass, field
import re
from typing import Any

from ml.classifier.engine import DocumentType


@dataclass
class QAAnswer:
    """Answer to a user's question about a document."""
    question: str
    answer: str
    confidence: float  # 0.0 to 1.0
    source: str = ""  # The text passage that informed the answer
    is_medical: bool = False
    medical_disclaimer: str = ""


@dataclass
class QAResult:
    """Result of a question answering session."""
    answers: list[QAAnswer] = field(default_factory=list)
    document_text: str = ""
    document_type: DocumentType = DocumentType.UNKNOWN


class OfflineQuestionAnswerer:
    """
    Answers questions about the current document using only
    information extracted from it.

    Uses keyword matching and text retrieval — no LLM required.
    Designed for reliable, deterministic answers without hallucination.
    """

    MEDICAL_DISCLAIMER = (
        "I am reading directly from the document. This is NOT medical advice. "
        "Always follow the instructions on your prescription label. "
        "Contact your doctor or pharmacist if you have questions about your medication."
    )

    # Question intent patterns
    INTENT_PATTERNS: dict[str, list[str]] = {
        "dosage": [
            r'how\s+(?:many|much)\s+(?:tablets?|capsules?|pills?|doses?)',
            r'what\s+(?:is\s+)?(?:the\s+)?(?:dosage|dose)',
            r'how\s+(?:often|frequently)',
            r'how\s+(?:do\s+I\s+)?take',
        ],
        "amount": [
            r'how\s+much\s+(?:do\s+I\s+)?(?:owe|pay|need\s+to\s+pay)',
            r'what\s+(?:is\s+)?(?:the\s+)?(?:amount|total|price|cost|fee|charge|balance)',
            r'how\s+much\s+(?:is|was)',
        ],
        "deadline": [
            r'when\s+(?:is|was)\s+(?:the\s+)?(?:due|deadline|payment|date)',
            r'by\s+when',
            r'what\s+(?:is\s+)?(?:the\s+)?(?:due|deadline|pay\s+by)',
            r'when\s+(?:do\s+I\s+)?(?:need\s+to|must\s+I|should\s+I)',
        ],
        "action": [
            r'what\s+(?:do\s+I\s+)?(?:need\s+to|should\s+I|must\s+I)\s+do',
            r'is\s+there\s+(?:anything|something|an\s+action)',
            r'what\s+action',
            r'do\s+I\s+need\s+to',
            r'next\s+steps?',
        ],
        "who": [
            r'who\s+(?:is|sent|from|wrote|issued|signed)',
            r'from\s+whom',
            r'what\s+(?:is\s+)?(?:the\s+)?(?:company|organization|sender|doctor|pharmacy|hospital)',
        ],
        "what_is": [
            r'what\s+(?:is|are)\s+this\s+document',
            r'what\s+kind\s+of\s+document',
            r'what\s+(?:is|are)\s+(?:this|it|the\s+document)',
        ],
        "medication": [
            r'what\s+(?:is\s+)?(?:the\s+)?(?:medication|medicine|drug|pill|tablet|capsule)',
            r'what\s+(?:am\s+I|is\s+)\s+(?:taking|prescribed)',
            r'what\s+(?:is|are)\s+(?:the\s+)?(?:side\s+effects?)',
            r'is\s+(?:it|this)\s+(?:\w+\s+)?safe',
            r'safe|safety|dangerous|risk',
        ],
    }

    def __init__(self):
        """Initialize QA engine."""
        pass

    def answer(
        self,
        question: str,
        full_text: str,
        extraction_result: Any,  # ExtractionResult
        document_type: DocumentType,
    ) -> QAAnswer:
        """
        Answer a question about the current document.

        Args:
            question: User's question.
            full_text: Full OCR text of the document.
            extraction_result: Structured extraction result.
            document_type: Classified document type.

        Returns:
            QAAnswer with answer text and confidence.
        """
        question_lower = question.lower().strip()

        # Determine intent
        intent = self._classify_intent(question_lower)

        # Route to appropriate answerer
        if intent == "dosage":
            return self._answer_dosage(question, full_text, extraction_result)
        elif intent == "amount":
            return self._answer_amount(question, full_text, extraction_result)
        elif intent == "deadline":
            return self._answer_deadline(question, full_text, extraction_result)
        elif intent == "action":
            return self._answer_action(question, full_text, extraction_result)
        elif intent == "who":
            return self._answer_who(question, full_text, extraction_result)
        elif intent == "what_is":
            return self._answer_what_is(question, full_text, extraction_result, document_type)
        elif intent == "medication":
            return self._answer_medication(question, full_text, extraction_result)
        else:
            return self._answer_general(question, full_text, extraction_result)

    def _classify_intent(self, question: str) -> str:
        """Classify the intent of a user question."""
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    return intent
        return "general"

    def _answer_dosage(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """Answer dosage/taking questions."""
        is_medical = True

        # Search for dosage information in extraction fields
        fields_dict = {f.label.lower(): f.value for f in getattr(extraction, 'fields', [])}

        dosage = fields_dict.get('dosage', '')
        frequency = fields_dict.get('frequency', '')
        instructions = fields_dict.get('instructions', '')

        if dosage or frequency or instructions:
            parts = []
            if dosage:
                parts.append(f"The dosage is {dosage}.")
            if frequency:
                parts.append(f"Take {frequency}.")
            if instructions:
                parts.append(f"Instructions: {instructions}.")

            answer = " ".join(parts)
            source = "; ".join(parts)
            return QAAnswer(
                question=question,
                answer=answer,
                confidence=0.8,
                source=source,
                is_medical=True,
                medical_disclaimer=self.MEDICAL_DISCLAIMER,
            )

        # Fall back to text search
        dosage_match = re.search(
            r'(?:take|dosage|dose)[^.]*?(?:one|two|three|\d+)[^.]*?(?:tablet|capsule|pill|daily|day)[^.]*\.',
            text, re.IGNORECASE
        )
        if dosage_match:
            return QAAnswer(
                question=question,
                answer=f"The document says: {dosage_match.group(0).strip()}",
                confidence=0.6,
                source=dosage_match.group(0).strip(),
                is_medical=True,
                medical_disclaimer=self.MEDICAL_DISCLAIMER,
            )

        return QAAnswer(
            question=question,
            answer="I could not find dosage instructions in the document. Please check the prescription label carefully.",
            confidence=0.0,
            is_medical=True,
            medical_disclaimer=self.MEDICAL_DISCLAIMER,
        )

    def _answer_amount(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """Answer monetary amount questions."""
        monetary = getattr(extraction, 'monetary_values', [])
        if monetary:
            amounts = [f"{desc}: {val}" for desc, val in monetary]
            return QAAnswer(
                question=question,
                answer=f"The document shows: {'; '.join(amounts)}.",
                confidence=0.8,
                source="; ".join(amounts),
            )

        # Search text
        money_matches = re.findall(r'[£$€]\s*\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})', text)
        if money_matches:
            return QAAnswer(
                question=question,
                answer=f"The document mentions: {', '.join(money_matches[:3])}.",
                confidence=0.6,
                source=", ".join(money_matches[:3]),
            )

        return QAAnswer(
            question=question,
            answer="I could not find a specific amount in the document.",
            confidence=0.0,
        )

    def _answer_deadline(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """Answer deadline/timing questions."""
        deadlines = getattr(extraction, 'deadlines', [])
        if deadlines:
            items = [f"{desc}: {date}" for desc, date in deadlines]
            return QAAnswer(
                question=question,
                answer=f"Key dates: {'; '.join(items)}.",
                confidence=0.8,
                source="; ".join(items),
            )

        # Search for dates with deadline context
        date_lines = re.findall(
            r'[^.]*?(?:due|deadline|by|before)[^.]*?(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})[^.]*\.',
            text, re.IGNORECASE
        )
        if date_lines:
            return QAAnswer(
                question=question,
                answer=f"The document indicates: {date_lines[0].strip()}",
                confidence=0.5,
                source=date_lines[0].strip(),
            )

        return QAAnswer(
            question=question,
            answer="I could not find a specific deadline in the document.",
            confidence=0.0,
        )

    def _answer_action(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """Answer action-required questions."""
        action = getattr(extraction, 'action_required', '')
        if action and action != "No immediate action identified." and action != "No action required.":
            return QAAnswer(
                question=question,
                answer=f"Action required: {action}",
                confidence=0.8,
                source=action,
            )

        return QAAnswer(
            question=question,
            answer="I could not identify a specific action required from this document.",
            confidence=0.0,
        )

    def _answer_who(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """Answer sender/origin questions."""
        # Check extracted fields
        fields_dict = {f.label.lower(): f.value for f in getattr(extraction, 'fields', [])}
        for key in ['from', 'institution', 'company', 'doctor', 'pharmacy', 'organization']:
            if key in fields_dict:
                return QAAnswer(
                    question=question,
                    answer=f"From: {fields_dict[key]}.",
                    confidence=0.8,
                    source=fields_dict[key],
                )

        # Search contacts
        contacts = getattr(extraction, 'contacts', [])
        if contacts:
            return QAAnswer(
                question=question,
                answer=f"Contacts found: {'; '.join(f'{t}: {v}' for t, v in contacts)}.",
                confidence=0.6,
            )

        return QAAnswer(
            question=question,
            answer="I could not identify who sent this document.",
            confidence=0.0,
        )

    def _answer_what_is(self, question: str, text: str, extraction: Any, doc_type: DocumentType) -> QAAnswer:
        """Answer 'what is this document' questions."""
        type_names = {
            DocumentType.PRESCRIPTION: "a medical prescription",
            DocumentType.BANKING: "a banking document or statement",
            DocumentType.BILL: "a bill or invoice",
            DocumentType.GOVERNMENT: "a government document",
            DocumentType.LEGAL: "a legal document",
            DocumentType.ID: "an identification document",
            DocumentType.UNKNOWN: "an unidentified document",
        }
        doc_desc = type_names.get(doc_type, "a document")

        summary = getattr(extraction, 'summary_lines', [])
        if summary:
            return QAAnswer(
                question=question,
                answer=f"This is {doc_desc}. {' '.join(summary)}",
                confidence=0.8,
            )

        return QAAnswer(
            question=question,
            answer=f"This appears to be {doc_desc}. I could not extract more details.",
            confidence=0.4,
        )

    def _answer_medication(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """Answer medication questions."""
        is_medical = True

        # Check if asking about side effects
        if re.search(r'side\s+effects?', question, re.IGNORECASE):
            side_effects = re.findall(
                r'(?:side\s+effects?|warning|caution|may\s+cause)[^.]*\.',
                text, re.IGNORECASE
            )
            if side_effects:
                return QAAnswer(
                    question=question,
                    answer=f"The document mentions: {side_effects[0].strip()}",
                    confidence=0.6,
                    source=side_effects[0].strip(),
                    is_medical=True,
                    medical_disclaimer=self.MEDICAL_DISCLAIMER,
                )
            return QAAnswer(
                question=question,
                answer="The document does not list specific side effects. Please consult the medication leaflet or your pharmacist.",
                confidence=0.0,
                is_medical=True,
                medical_disclaimer=self.MEDICAL_DISCLAIMER,
            )

        # Check if asking about safety
        if re.search(r'safe|safety|dangerous|risk', question, re.IGNORECASE):
            return QAAnswer(
                question=question,
                answer=(
                    "I cannot determine if this medication is safe for you. "
                    "This document reading is not medical advice. "
                    "Please consult your doctor or pharmacist."
                ),
                confidence=0.0,
                is_medical=True,
                medical_disclaimer=self.MEDICAL_DISCLAIMER,
            )

        # General medication info
        fields_dict = {f.label.lower(): f.value for f in getattr(extraction, 'fields', [])}
        medication = fields_dict.get('medication', '')
        if medication:
            dosage = fields_dict.get('dosage', '')
            return QAAnswer(
                question=question,
                answer=f"The medication is {medication}. {dosage}.",
                confidence=0.8,
                is_medical=True,
                medical_disclaimer=self.MEDICAL_DISCLAIMER,
            )

        return QAAnswer(
            question=question,
            answer="I could not identify the specific medication in this document.",
            confidence=0.0,
            is_medical=True,
            medical_disclaimer=self.MEDICAL_DISCLAIMER,
        )

    def _answer_general(self, question: str, text: str, extraction: Any) -> QAAnswer:
        """General keyword-based search for other questions."""
        # Extract keywords from question (remove stop words)
        stop_words = {'the', 'is', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'it', 'this', 'that', 'what', 'when', 'where', 'who', 'how', 'do', 'does', 'did', 'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might', 'must', 'i', 'my', 'me', 'you', 'your', 'there', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having'}
        keywords = [w for w in re.findall(r'\b[a-z]{3,}\b', question.lower()) if w not in stop_words]

        if not keywords:
            return QAAnswer(
                question=question,
                answer="I'm not sure what you're asking. Please try rephrasing your question.",
                confidence=0.0,
            )

        # Search for lines containing keywords
        lines = text.split('\n')
        matching_lines = []
        for line in lines:
            if any(kw in line.lower() for kw in keywords):
                matching_lines.append(line.strip())

        if matching_lines:
            relevant = matching_lines[:3]
            return QAAnswer(
                question=question,
                answer=f"Relevant text from the document: {'; '.join(relevant)}",
                confidence=0.4,
                source="; ".join(relevant),
            )

        return QAAnswer(
            question=question,
            answer="I could not find that information in the document.",
            confidence=0.0,
        )


def create_qa_engine() -> OfflineQuestionAnswerer:
    """Factory function for creating a QA engine."""
    return OfflineQuestionAnswerer()
