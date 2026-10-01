"""
Main Privacy-First Document Analysis Pipeline.

Coordinates all modules: preprocessing, OCR, classification,
sensitive data detection, extraction, and question answering.

All processing is 100% local. No data leaves the device.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import time

from ml.preprocessing.pipeline import ImagePreprocessor, PreprocessingResult
from ml.ocr.engine import DocumentOCR, OCRResult
from ml.classifier.engine import DocumentClassifier, ClassificationResult, DocumentType
from ml.sensitive_data.detector import SensitiveDataDetector, SensitiveDataResult
from ml.extraction.extractor import DocumentExtractor, ExtractionResult
from ml.qa.engine import OfflineQuestionAnswerer, QAAnswer


@dataclass
class DocumentAnalysis:
    """Complete analysis of a document image."""
    # Metadata
    image_path: str = ""
    processing_time_ms: float = 0.0
    pipeline_version: str = "0.1.0"

    # Preprocessing
    preprocessing: Optional[PreprocessingResult] = None

    # OCR
    ocr: Optional[OCRResult] = None

    # Classification
    classification: Optional[ClassificationResult] = None

    # Sensitive data
    sensitive_data: Optional[SensitiveDataResult] = None

    # Extraction
    extraction: Optional[ExtractionResult] = None

    # Warnings
    warnings: list[str] = field(default_factory=list)

    # Accessible summary
    accessible_summary: str = ""

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        result = {
            "image_path": self.image_path,
            "processing_time_ms": self.processing_time_ms,
            "pipeline_version": self.pipeline_version,
            "document_type": self.classification.document_type.value if self.classification else "unknown",
            "confidence": self.classification.confidence if self.classification else 0.0,
            "warnings": self.warnings,
            "accessible_summary": self.accessible_summary,
        }

        if self.ocr:
            result["ocr"] = {
                "full_text": self.ocr.full_text,
                "confidence": self.ocr.confidence,
                "regions_count": len(self.ocr.regions),
                "low_confidence_count": len(self.ocr.low_confidence_regions),
                "ocr_warnings": self.ocr.warnings,
            }

        if self.classification:
            result["classification"] = {
                "document_type": self.classification.document_type.value,
                "confidence": self.classification.confidence,
                "alternatives": [
                    {"type": dt.value, "confidence": round(c, 3)}
                    for dt, c in self.classification.alternative_types
                ],
            }

        if self.sensitive_data:
            result["sensitive_data"] = {
                "detected": self.sensitive_data.sensitive_information_detected,
                "entity_count": self.sensitive_data.entity_count,
                "risk_level": self.sensitive_data.risk_level,
                "entity_types": list(set(
                    e.entity_type.value for e in self.sensitive_data.entities
                )),
            }

        if self.extraction:
            result["extraction"] = {
                "fields": [
                    {"label": f.label, "value": f.value}
                    for f in self.extraction.fields
                ],
                "action_required": self.extraction.action_required,
                "monetary_values": [
                    {"description": d, "amount": v}
                    for d, v in self.extraction.monetary_values
                ],
                "deadlines": [
                    {"description": d, "date": v}
                    for d, v in self.extraction.deadlines
                ],
                "contacts": [
                    {"type": t, "value": v}
                    for t, v in self.extraction.contacts
                ],
                "summary": self.extraction.summary_lines,
                "medical_disclaimer": self.extraction.medical_disclaimer,
            }

        if self.preprocessing:
            result["image_quality"] = {
                "brightness_score": round(self.preprocessing.brightness_score, 3),
                "blur_score": round(self.preprocessing.blur_score, 3),
                "contrast_score": round(self.preprocessing.contrast_score, 3),
                "document_visible": self.preprocessing.document_visible,
                "is_acceptable": self.preprocessing.is_acceptable,
                "guidance": self.preprocessing.guidance_messages,
            }

        return result


class DocumentPipeline:
    """
    Complete document analysis pipeline.

    Coordinates: Preprocess → OCR → Classify → Detect Sensitive Data → Extract → Summary.

    All processing is local. Designed for both desktop and mobile deployment.
    """

    def __init__(
        self,
        ocr_engine: Optional[DocumentOCR] = None,
        classifier: Optional[DocumentClassifier] = None,
        detector: Optional[SensitiveDataDetector] = None,
        extractor: Optional[DocumentExtractor] = None,
        qa_engine: Optional[OfflineQuestionAnswerer] = None,
    ):
        """
        Initialize pipeline with optional custom components.

        Args:
            ocr_engine: OCR engine. Creates default if None.
            classifier: Document classifier. Creates default if None.
            detector: Sensitive data detector. Creates default if None.
            extractor: Document extractor. Creates default if None.
            qa_engine: Question answering engine. Creates default if None.
        """
        self.preprocessor = ImagePreprocessor()
        self.ocr_engine = ocr_engine or DocumentOCR()
        self.classifier = classifier or DocumentClassifier()
        self.detector = detector or SensitiveDataDetector()
        self.extractor = extractor or DocumentExtractor()
        self.qa_engine = qa_engine or OfflineQuestionAnswerer()

    def analyze(self, image_path: str) -> DocumentAnalysis:
        """
        Run the complete analysis pipeline on a document image.

        Args:
            image_path: Path to the document image.

        Returns:
            DocumentAnalysis with all results.
        """
        start_time = time.time()
        analysis = DocumentAnalysis(image_path=image_path)
        warnings: list[str] = []

        # Step 1: Preprocess
        try:
            preprocessing = self.preprocessor.process(image_path)
            analysis.preprocessing = preprocessing
            if preprocessing.guidance_messages:
                warnings.extend(preprocessing.guidance_messages)
        except Exception as e:
            warnings.append(f"Preprocessing error: {e}")
            # Continue with original image if possible
            preprocessing = None

        # Get image for OCR
        if preprocessing and preprocessing.is_acceptable:
            ocr_image = preprocessing.processed_image
        elif preprocessing:
            ocr_image = preprocessing.processed_image
        else:
            import cv2
            ocr_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

        if ocr_image is None:
            warnings.append("Failed to load image for OCR.")
            analysis.warnings = warnings
            return analysis

        # Step 2: OCR
        try:
            ocr_result = self.ocr_engine.process(ocr_image)
            analysis.ocr = ocr_result
            if ocr_result.warnings:
                warnings.extend(ocr_result.warnings)
        except Exception as e:
            warnings.append(f"OCR error: {e}")
            analysis.warnings = warnings
            return analysis

        if not ocr_result.full_text.strip():
            warnings.append("No text could be read from the document.")
            analysis.warnings = warnings
            return analysis

        text = ocr_result.full_text

        # Step 3: Classify
        try:
            classification = self.classifier.classify(text)
            analysis.classification = classification
        except Exception as e:
            warnings.append(f"Classification error: {e}")
            classification = ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
            )

        # Determine if critical document
        is_critical = classification.document_type in (
            DocumentType.PRESCRIPTION,
            DocumentType.BANKING,
            DocumentType.LEGAL,
        )

        # Step 4: Sensitive Data Detection
        try:
            sensitive_data = self.detector.detect(text, ocr_result.regions)
            analysis.sensitive_data = sensitive_data
        except Exception as e:
            warnings.append(f"Sensitive data detection error: {e}")
            sensitive_data = SensitiveDataResult(sensitive_information_detected=False)

        # Step 5: Extract structured information
        try:
            extraction = self.extractor.extract(
                text,
                classification.document_type,
                sensitive_data.entities,
            )
            analysis.extraction = extraction
            if extraction.warnings:
                warnings.extend(extraction.warnings)
        except Exception as e:
            warnings.append(f"Extraction error: {e}")
            extraction = ExtractionResult(document_type=classification.document_type)

        # Step 6: Build accessible summary
        analysis.accessible_summary = self._build_accessible_summary(
            classification, extraction, sensitive_data, ocr_result, is_critical
        )

        # Finalize
        analysis.warnings = warnings
        analysis.processing_time_ms = round((time.time() - start_time) * 1000)

        return analysis

    def ask_question(self, analysis: DocumentAnalysis, question: str) -> QAAnswer:
        """
        Answer a question about the analyzed document.

        Args:
            analysis: Completed document analysis.
            question: User's question.

        Returns:
            QAAnswer with the answer.
        """
        if not analysis.ocr or not analysis.ocr.full_text.strip():
            return QAAnswer(
                question=question,
                answer="No document text is available. Please scan a document first.",
                confidence=0.0,
            )

        return self.qa_engine.answer(
            question=question,
            full_text=analysis.ocr.full_text,
            extraction_result=analysis.extraction,
            document_type=analysis.classification.document_type if analysis.classification else DocumentType.UNKNOWN,
        )

    def _build_accessible_summary(
        self,
        classification: ClassificationResult,
        extraction: ExtractionResult,
        sensitive_data: SensitiveDataResult,
        ocr_result: OCRResult,
        is_critical: bool,
    ) -> str:
        """Build an accessible spoken summary of the document."""
        parts: list[str] = []

        # Document type
        type_names = {
            DocumentType.PRESCRIPTION: "prescription",
            DocumentType.BANKING: "banking document",
            DocumentType.BILL: "bill or invoice",
            DocumentType.GOVERNMENT: "government document",
            DocumentType.LEGAL: "legal document",
            DocumentType.ID: "identification document",
            DocumentType.UNKNOWN: "document",
        }
        doc_type_name = type_names.get(classification.document_type, "document")
        parts.append(f"This appears to be a {doc_type_name}.")

        # Confidence warning
        if classification.confidence < 0.5:
            parts.append(f"However, I am only {classification.confidence:.0%} confident in this classification.")

        # OCR confidence
        if ocr_result.confidence < 0.6:
            parts.append("The text quality is low. Please scan the document again with better lighting.")

        # Sensitive data
        if sensitive_data.sensitive_information_detected:
            parts.append(
                f"Sensitive information was detected. "
                f"Risk level: {sensitive_data.risk_level}."
            )

        # Extraction summary
        if extraction.summary_lines:
            parts.extend(extraction.summary_lines)

        # Action required
        if extraction.action_required and extraction.action_required not in (
            "No immediate action identified.",
            "No action required.",
            "No specific action identified. Please review the document.",
        ):
            parts.append(extraction.action_required)

        # Deadlines
        if extraction.deadlines:
            for desc, date in extraction.deadlines:
                parts.append(f"{desc}: {date}.")

        # Monetary values
        if extraction.monetary_values:
            for desc, amount in extraction.monetary_values:
                parts.append(f"{desc}: {amount}.")

        # Medical disclaimer
        if extraction.medical_disclaimer:
            parts.append(extraction.medical_disclaimer)

        return " ".join(parts)


def create_pipeline() -> DocumentPipeline:
    """Factory function for creating the analysis pipeline."""
    return DocumentPipeline()
