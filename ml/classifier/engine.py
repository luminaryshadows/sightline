"""
Lightweight document classifier combining regex rules and keyword matching.

Classifies documents into: prescription, banking, government, bill/invoice,
legal, ID, or unknown. Returns confidence scores.

All processing is local — no data leaves the device.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re


class DocumentType(Enum):
    PRESCRIPTION = "prescription"
    BANKING = "banking"
    GOVERNMENT = "government"
    BILL = "bill"
    LEGAL = "legal"
    ID = "id"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Document classification result."""
    document_type: DocumentType
    confidence: float  # 0.0 to 1.0
    alternative_types: list[tuple[DocumentType, float]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # Keywords/rules that matched


# Keyword and pattern definitions for each document type
DOCUMENT_PATTERNS: dict[DocumentType, list[str]] = {
    DocumentType.PRESCRIPTION: [
        # Medication-related terms
        r'\bprescri(be|ption)\b', r'\bmedication\b', r'\bdosage\b', r'\bdose\b',
        r'\btablet\b', r'\bcapsule\b', r'\bmg\b', r'\bmcg\b', r'\bmicrogram\b',
        r'\btake\s+(one|two|three|\d+)\b', r'\btwice\s+daily\b', r'\bonce\s+daily\b',
        r'\bpharmac(y|ist)\b', r'\brefill\b', r'\bdispense\b', r'\bRX\b',
        r'\bsigma\b', r'\bq\.?d\.?\b', r'\bb\.?i\.?d\.?\b', r'\bt\.?i\.?d\.?\b',
        r'\bq\.?i\.?d\.?\b', r'\bprn\b', r'\bstat\b', r'\bpo\b',
        r'\broute\b', r'\bquantity\b', r'\bdirections?\b',
        # Doctor/pharmacy headers
        r'\bdoctor\b', r'\bphysician\b', r'\bclinic\b', r'\bmedical\s+centre\b',
        r'\bDEA\b', r'\bNPI\b', r'\bprescriber\b',
    ],
    DocumentType.BANKING: [
        r'\bbank\b', r'\bbanking\b', r'\baccount\s+number\b', r'\bsort\s+code\b',
        r'\btransaction\b', r'\bdeposit\b', r'\bwithdrawal\b', r'\btransfer\b',
        r'\bstater?ment\b', r'\bbalance\b', r'\boverdraft\b', r'\binterest\s+rate\b',
        r'\bstanding\s+order\b', r'\bdirect\s+debit\b', r'\bcheque\b', r'\bcheck\b',
        r'\bcredit\b', r'\bdebit\b', r'\bIBAN\b', r'\bSWIFT\b', r'\bBIC\b',
        r'\bwire\b', r'\bACH\b', r'\brouting\s+number\b', r'\bIFSC\b',
        r'\bsavings?\b', r'\bcurrent\s+account\b', r'\bmortgage\b',
        r'£\s*\d+[\.,]\d{2}', r'\$\s*\d+[\.,]\d{2}', r'€\s*\d+[\.,]\d{2}',
    ],
    DocumentType.GOVERNMENT: [
        r'\bgovernment\b', r'\bHM\s+Revenue\b', r'\bHMRC\b', r'\bIRS\b',
        r'\bHousing\s+Benefit\b', r'\bUniversal\s+Credit\b', r'\bCouncil\s+Tax\b',
        r'\bDepartment\s+for\s+Work\b', r'\bDWP\b', r'\bNHS\b',
        r'\bNational\s+Insurance\b', r'\btax\s+return\b', r'\btax\s+credit\b',
        r'\bpassport\b', r'\bdri?v?ing\s+licen[cs]e\b', r'\bDVLA\b',
        r'\bbenefit\b', r'\bpension\b', r'\bsocial\s+security\b',
        r'\bHome\s+Office\b', r'\bvisa\b', r'\bimmigration\b',
        r'\bofficial\s+notice\b', r'\bpublic\s+notice\b',
    ],
    DocumentType.BILL: [
        r'\binvoice\b', r'\bbill\b', r'\bstatement\b',
        r'\bamount\s+due\b', r'\bdue\s+date\b', r'\bpayment\s+due\b',
        r'\butility\b', r'\belectricity\b', r'\bgas\b', r'\bwater\b',
        r'\btelecom\b', r'\bbroadband\b', r'\bmobile\s+bill\b',
        r'\bsubscription\b', r'\bmonthly\s+(charge|fee|payment)\b',
        r'\baccount\s+summary\b', r'\bprevious\s+balance\b',
        r'\bnew\s+charges\b', r'\btotal\s+due\b', r'\bpay\s+by\b',
        r'\bpayment\s+method\b', r'\bcustomer\s+number\b',
        r'\breference\s+number\b', r'\bbilling\s+period\b',
        r'\bVAT\b', r'\btax\s+invoice\b',
    ],
    DocumentType.LEGAL: [
        r'\blegal\b', r'\bsolicitor\b', r'\battorney\b', r'\blaw\s+firm\b',
        r'\bcontract\b', r'\bagreement\b', r'\bterms?\s+and\s+conditions?\b',
        r'\bcourt\b', r'\btribunal\b', r'\bjudgment\b', r'\bwrit\b',
        r'\bsummons\b', r'\baffidavit\b', r'\bnotar\w+\b',
        r'\bplaintiff\b', r'\bdefendant\b', r'\bclaim(ant)?\b',
        r'\bherein\b', r'\bhereto\b', r'\bhereunder\b', r'\bwhereof\b',
        r'\bwhereas\b', r'\bwitnesseth\b', r'\bhereinafter\b',
        r'\bindemnif\w+\b', r'\bliability\b', r'\barbitration\b',
        r'\bjurisdiction\b', r'\bgoverning\s+law\b',
    ],
    DocumentType.ID: [
        r'\bpassport\b', r'\bidentity\b', r'\bidentification\b',
        r'\bdri?v?ing\s+licen[cs]e\b', r'\bnational\s+ID\b',
        r'\bbirth\s+certificate\b', r'\bdate\s+of\s+birth\b',
        r'\bplace\s+of\s+birth\b', r'\bnationality\b', r'\bsex\b.*\b[MFO]\b',
        r'\bissued?\s+(by|on|at)\b', r'\bexpir\w+\s+date\b',
        r'\bdocument\s+number\b', r'\bcitizenship\b',
        r'\bholder\b', r'\bbearer\b',
    ],
}


class DocumentClassifier:
    """
    Rule-based document classifier.

    Scores each document type based on keyword/pattern matches in OCR text.
    Also considers visual layout features when available.

    Designed for easy replacement with a PyTorch classifier later.
    """

    def __init__(self):
        """Compile regex patterns for each document type."""
        self._compiled_patterns: dict[DocumentType, list[re.Pattern]] = {}
        for doc_type, patterns in DOCUMENT_PATTERNS.items():
            self._compiled_patterns[doc_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document based on OCR text content.

        Args:
            text: Full OCR text from the document.

        Returns:
            ClassificationResult with document type, confidence, and evidence.
        """
        if not text or not text.strip():
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                evidence=["No text available for classification."],
            )

        text_lower = text.lower()

        # Score each document type
        scores: dict[DocumentType, tuple[float, list[str]]] = {}
        for doc_type, patterns in self._compiled_patterns.items():
            matched = []
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    matched.append(f"Matched: {pattern.pattern[:50]}...")

            if matched:
                # Score based on unique pattern matches, normalized
                raw_score = min(len(matched), 15) / 15.0
                # Bonus for multiple matches of same pattern
                total_matches = sum(len(pattern.findall(text_lower)) for pattern in patterns)
                density_bonus = min(total_matches / 20.0, 0.3)
                score = min(raw_score + density_bonus, 1.0)
                scores[doc_type] = (score, matched)

        if not scores:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                evidence=["No document type patterns matched."],
            )

        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)
        top_type, (top_score, top_evidence) = ranked[0]

        # Determine confidence
        if len(ranked) == 1:
            confidence = top_score
        else:
            second_score = ranked[1][1][0]
            # Confidence is ratio of top to second, scaled
            margin = top_score - second_score
            confidence = 0.5 + margin * 0.5  # Scale margin to [0.5, 1.0]
            confidence = min(confidence, top_score)

        # Alternative types
        alternatives = [
            (dt, sc) for dt, (sc, _) in ranked[1:4] if sc > 0.1
        ]

        return ClassificationResult(
            document_type=top_type,
            confidence=round(confidence, 3),
            alternative_types=alternatives,
            evidence=top_evidence[:10],  # Limit evidence
        )


def create_classifier() -> DocumentClassifier:
    """Factory function for creating a document classifier."""
    return DocumentClassifier()
