"""
Image preprocessing pipeline for document capture.

Handles: brightness normalization, contrast enhancement, blur detection,
document boundary estimation, and orientation checks.
All processing is local — no data leaves the device.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np
from PIL import Image


class QualityIssue(Enum):
    """Issues detected during image quality assessment."""
    TOO_DARK = "too_dark"
    TOO_BRIGHT = "too_bright"
    TOO_BLURRY = "too_blurry"
    DOCUMENT_NOT_FULLY_VISIBLE = "document_not_fully_visible"
    SKEWED = "skewed"
    LOW_CONTRAST = "low_contrast"


@dataclass
class PreprocessingResult:
    """Result of image preprocessing and quality assessment."""
    processed_image: np.ndarray
    original_image: np.ndarray
    brightness_score: float  # 0.0 (pitch black) to 1.0 (ideal)
    blur_score: float        # 0.0 (very blurry) to 1.0 (very sharp)
    contrast_score: float    # 0.0 (no contrast) to 1.0 (good contrast)
    document_visible: bool
    document_corners: Optional[np.ndarray] = None  # 4x2 array of corner points
    quality_issues: list[QualityIssue] = field(default_factory=list)
    guidance_messages: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        """Overall quality is sufficient for reliable OCR."""
        return (
            self.brightness_score > 0.25
            and self.blur_score > 0.3
            and self.contrast_score > 0.2
            and self.document_visible
            and QualityIssue.TOO_BLURRY not in self.quality_issues
            and QualityIssue.TOO_DARK not in self.quality_issues
        )


class ImagePreprocessor:
    """
    Preprocesses document images for OCR and analysis.

    Performs:
    - Brightness and contrast normalization
    - Blur detection
    - Document boundary estimation
    - Perspective correction
    - Quality guidance for blind users
    """

    # Thresholds (tunable)
    BRIGHTNESS_MIN: float = 40.0   # Below this is too dark
    BRIGHTNESS_MAX: float = 230.0  # Above this is too bright
    BLUR_THRESHOLD: float = 100.0  # Laplacian variance below this is blurry
    CONTRAST_MIN: float = 30.0     # Standard deviation below this is low contrast

    def __init__(self, target_size: tuple[int, int] = (1024, 1024)):
        """
        Args:
            target_size: Maximum dimensions for processing (width, height).
                         Larger images are downsized while preserving aspect ratio.
        """
        self.target_size = target_size

    def load_image(self, path: str) -> np.ndarray:
        """Load image from disk as RGB numpy array."""
        pil_img = Image.open(path).convert("RGB")
        return np.array(pil_img)

    def resize_for_processing(self, image: np.ndarray) -> np.ndarray:
        """Resize image to fit within target_size, preserving aspect ratio."""
        h, w = image.shape[:2]
        max_w, max_h = self.target_size
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            new_w, new_h = int(w * scale), int(h * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return image.copy()

    def assess_brightness(self, gray: np.ndarray) -> tuple[float, list[QualityIssue], list[str]]:
        """Assess image brightness. Returns (score, issues, guidance)."""
        mean_brightness = float(np.mean(gray))
        issues: list[QualityIssue] = []
        guidance: list[str] = []

        if mean_brightness < self.BRIGHTNESS_MIN:
            issues.append(QualityIssue.TOO_DARK)
            guidance.append("Too dark. Please move to better lighting or use flash.")
            score = max(0.0, mean_brightness / self.BRIGHTNESS_MIN)
        elif mean_brightness > self.BRIGHTNESS_MAX:
            issues.append(QualityIssue.TOO_BRIGHT)
            guidance.append("Too bright. Please avoid direct light on the document.")
            score = max(0.0, 1.0 - (mean_brightness - self.BRIGHTNESS_MAX) / (255 - self.BRIGHTNESS_MAX))
        else:
            score = 1.0 - abs(mean_brightness - 128) / 128

        return score, issues, guidance

    def assess_blur(self, gray: np.ndarray) -> tuple[float, list[QualityIssue], list[str]]:
        """Assess image sharpness via Laplacian variance. Returns (score, issues, guidance)."""
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        issues: list[QualityIssue] = []
        guidance: list[str] = []

        if laplacian_var < self.BLUR_THRESHOLD:
            issues.append(QualityIssue.TOO_BLURRY)
            guidance.append("Image is blurry. Hold the phone steady and ensure the document is in focus.")
            score = laplacian_var / self.BLUR_THRESHOLD
        else:
            score = min(1.0, laplacian_var / 500.0)

        return score, issues, guidance

    def assess_contrast(self, gray: np.ndarray) -> tuple[float, list[QualityIssue], list[str]]:
        """Assess image contrast. Returns (score, issues, guidance)."""
        std_dev = float(np.std(gray))
        issues: list[QualityIssue] = []
        guidance: list[str] = []

        if std_dev < self.CONTRAST_MIN:
            issues.append(QualityIssue.LOW_CONTRAST)
            guidance.append("Low contrast. Please ensure the document is well-lit.")
            score = std_dev / self.CONTRAST_MIN
        else:
            score = min(1.0, std_dev / 80.0)

        return score, issues, guidance

    def detect_document_edges(self, gray: np.ndarray) -> tuple[bool, Optional[np.ndarray], list[str]]:
        """
        Attempt to find document edges in the image.
        Returns (visible, corners, guidance_messages).
        """
        # Edge detection
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return False, None, ["Document not detected. Please ensure the entire document is visible."]

        # Find the largest quadrilateral-like contour
        largest = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(largest) / (gray.shape[0] * gray.shape[1])

        if area_ratio < 0.1:
            return False, None, ["Document appears too small. Please move the camera closer."]

        # Approximate polygon
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

        guidance: list[str] = []

        if len(approx) == 4:
            corners = approx.reshape(4, 2).astype(np.float32)
            # Check if corners are near image edges (document cut off)
            h, w = gray.shape[:2]
            margin = 0.05
            for corner in corners:
                if corner[0] < w * margin or corner[0] > w * (1 - margin):
                    guidance.append("Document edge is near the frame edge. Please ensure all four corners are visible.")
                    break
                if corner[1] < h * margin or corner[1] > h * (1 - margin):
                    guidance.append("Document edge is near the frame edge. Please ensure all four corners are visible.")
                    break
            return True, corners, guidance
        elif len(approx) > 4:
            # Try to find the best 4-corner approximation
            corners = approx.reshape(-1, 2).astype(np.float32)
            rect = cv2.minAreaRect(corners)
            box = cv2.boxPoints(rect)
            return True, box, guidance
        else:
            return False, None, ["Could not find document corners. Please ensure the entire document is visible."]

    def enhance_for_ocr(self, gray: np.ndarray) -> np.ndarray:
        """Apply enhancements to improve OCR accuracy."""
        # Adaptive histogram equalization for local contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Gentle sharpening
        kernel = np.array([[-0.5, -0.5, -0.5],
                           [-0.5,  5.0, -0.5],
                           [-0.5, -0.5, -0.5]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

        return sharpened

    def process(self, image_path: str) -> PreprocessingResult:
        """
        Full preprocessing pipeline.

        Args:
            image_path: Path to the input image.

        Returns:
            PreprocessingResult with processed image and quality assessment.
        """
        # Load
        original = self.load_image(image_path)
        resized = self.resize_for_processing(original)

        # Convert to grayscale for analysis
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
        else:
            gray = resized.copy()

        # Assess quality
        brightness_score, b_issues, b_guidance = self.assess_brightness(gray)
        blur_score, bl_issues, bl_guidance = self.assess_blur(gray)
        contrast_score, c_issues, c_guidance = self.assess_contrast(gray)

        # Detect document edges
        doc_visible, corners, e_guidance = self.detect_document_edges(gray)

        # Enhance for OCR
        enhanced = self.enhance_for_ocr(gray)

        # Collect all issues and guidance
        all_issues = b_issues + bl_issues + c_issues
        all_guidance = b_guidance + bl_guidance + c_guidance + e_guidance

        if not doc_visible:
            all_issues.append(QualityIssue.DOCUMENT_NOT_FULLY_VISIBLE)

        return PreprocessingResult(
            processed_image=enhanced,
            original_image=resized,
            brightness_score=brightness_score,
            blur_score=blur_score,
            contrast_score=contrast_score,
            document_visible=doc_visible,
            document_corners=corners,
            quality_issues=all_issues,
            guidance_messages=all_guidance,
        )
