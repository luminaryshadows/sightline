"""
Local PyTorch-based OCR engine using EasyOCR.

All processing is on-device. Models are cached locally after first download.
No text or image data is sent to any server.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging
import os
import warnings

import numpy as np

# Suppress verbose EasyOCR and PyTorch warnings
os.environ.setdefault("EASYOCR_MODULE_PATH", "")
logging.getLogger("easyocr").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

import easyocr  # noqa: E402


@dataclass
class TextRegion:
    """A detected text region in the document."""
    text: str
    confidence: float
    bbox: list[list[int]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    line_number: int = 0


@dataclass
class OCRResult:
    """Complete OCR result for a document image."""
    full_text: str
    regions: list[TextRegion] = field(default_factory=list)
    confidence: float = 0.0  # Average confidence across all regions
    low_confidence_regions: list[TextRegion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_reliable(self) -> bool:
        """Whether overall OCR confidence is sufficient for downstream tasks."""
        return self.confidence >= 0.5 and len(self.low_confidence_regions) < len(self.regions) * 0.3


class DocumentOCR:
    """
    Offline document OCR engine.

    Uses EasyOCR with PyTorch backend. All processing is local.
    Separately handles text detection and text recognition.

    Interface designed for easy replacement with ExecuTorch models later.
    """

    # Confidence threshold for flagging low-confidence regions
    LOW_CONFIDENCE_THRESHOLD: float = 0.4
    # Critical confidence threshold for sensitive fields
    CRITICAL_CONFIDENCE_THRESHOLD: float = 0.65

    def __init__(self, use_gpu: bool = False, languages: list[str] | None = None):
        """
        Args:
            use_gpu: Whether to use GPU acceleration. Default False for privacy.
            languages: List of language codes. Default ['en'].
        """
        self.languages = languages or ['en']
        self.use_gpu = use_gpu
        self._reader: Optional[easyocr.Reader] = None

    @property
    def reader(self) -> easyocr.Reader:
        """Lazy-initialize the EasyOCR reader."""
        if self._reader is None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._reader = easyocr.Reader(
                    self.languages,
                    gpu=self.use_gpu,
                    model_storage_directory=None,
                    download_enabled=False,
                    verbose=False,
                )
        return self._reader

    def detect_text_regions(self, image: np.ndarray) -> list[TextRegion]:
        """
        Detect and recognize text regions in the image.

        Returns list of TextRegion objects with text, confidence, and bounding boxes.
        """
        raw_results = self.reader.readtext(image, detail=1, paragraph=False)

        regions: list[TextRegion] = []
        for i, (bbox, text, conf) in enumerate(raw_results):
            region = TextRegion(
                text=text.strip(),
                confidence=round(float(conf), 3),
                bbox=[[int(p[0]), int(p[1])] for p in bbox],
                line_number=i + 1,
            )
            regions.append(region)

        return regions

    def process(self, image: np.ndarray, is_critical_document: bool = False) -> OCRResult:
        """
        Run full OCR on a preprocessed image.

        Args:
            image: Preprocessed image as numpy array (grayscale or RGB).
            is_critical_document: If True, use stricter confidence thresholds
                                  (for prescriptions, financial documents, etc.)

        Returns:
            OCRResult with full text, regions, confidence, and warnings.
        """
        regions = self.detect_text_regions(image)

        if not regions:
            return OCRResult(
                full_text="",
                regions=[],
                confidence=0.0,
                low_confidence_regions=[],
                warnings=["No text detected in the image. Please ensure the document is clearly visible."],
            )

        # Compute average confidence
        avg_conf = sum(r.confidence for r in regions) / len(regions)

        # Identify low-confidence regions
        threshold = self.CRITICAL_CONFIDENCE_THRESHOLD if is_critical_document else self.LOW_CONFIDENCE_THRESHOLD
        low_conf = [r for r in regions if r.confidence < threshold]

        # Build full text, grouped by approximate vertical position
        full_text = self._build_full_text(regions)

        # Warnings
        warnings_list: list[str] = []
        if low_conf:
            pct = len(low_conf) / len(regions) * 100
            warnings_list.append(
                f"Low confidence on {len(low_conf)} text regions ({pct:.0f}%). "
                "Please scan the document again with better lighting."
            )
        if is_critical_document and len(low_conf) > 0:
            for region in low_conf:
                warnings_list.append(
                    f"Critical: Low confidence reading '{region.text[:40]}...' — "
                    "please verify this text carefully."
                )

        return OCRResult(
            full_text=full_text,
            regions=regions,
            confidence=round(avg_conf, 3),
            low_confidence_regions=low_conf,
            warnings=warnings_list,
        )

    def _build_full_text(self, regions: list[TextRegion]) -> str:
        """
        Reconstruct document text from regions, grouping by vertical position.
        Attempts to preserve reading order (top-to-bottom, left-to-right).
        """
        if not regions:
            return ""

        # Sort by vertical position (y), then horizontal (x)
        sorted_regions = sorted(regions, key=lambda r: (r.bbox[0][1], r.bbox[0][0]))

        # Group into lines based on vertical overlap
        lines: list[list[TextRegion]] = []
        current_line: list[TextRegion] = []
        current_y = sorted_regions[0].bbox[0][1] if sorted_regions else 0
        y_threshold = 20  # pixels threshold for same line

        for region in sorted_regions:
            region_y = region.bbox[0][1]
            if abs(region_y - current_y) < y_threshold:
                current_line.append(region)
            else:
                if current_line:
                    # Sort within line left-to-right
                    current_line.sort(key=lambda r: r.bbox[0][0])
                    lines.append(current_line)
                current_line = [region]
                current_y = region_y

        if current_line:
            current_line.sort(key=lambda r: r.bbox[0][0])
            lines.append(current_line)

        # Build text
        text_lines = []
        for line_regions in lines:
            line_text = " ".join(r.text for r in line_regions)
            text_lines.append(line_text)

        return "\n".join(text_lines)


def create_ocr_engine(use_gpu: bool = False, languages: list[str] | None = None) -> DocumentOCR:
    """Factory function for creating an OCR engine instance."""
    return DocumentOCR(use_gpu=use_gpu, languages=languages)
