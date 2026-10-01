"""
Accessible camera capture guidance (Phase 7).

Analyses a live camera frame and produces spoken guidance for blind and
low-vision users so they can position a document and capture it without
seeing the screen.

This module is the reference implementation of the guidance logic that the
Android app ports to Kotlin. Keeping it in Python makes it unit-testable
without an emulator, and the algorithms are identical.

Guidance vocabulary (fixed strings — the Android TTS layer speaks these):
    "Document not fully visible."
    "Move phone left."
    "Move phone right."
    "Move phone upward."
    "Move phone downward."
    "Move closer."
    "Move further away."
    "Too dark."
    "Too bright."
    "Hold steady."
    "Document captured."

All processing is local. No frames leave the device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np


class Guidance(Enum):
    """Fixed guidance messages spoken to the user."""
    DOCUMENT_NOT_VISIBLE = "Document not fully visible."
    MOVE_LEFT = "Move phone left."
    MOVE_RIGHT = "Move phone right."
    MOVE_UP = "Move phone upward."
    MOVE_DOWN = "Move phone downward."
    MOVE_CLOSER = "Move closer."
    MOVE_FURTHER = "Move further away."
    TOO_DARK = "Too dark."
    TOO_BRIGHT = "Too bright."
    HOLD_STEADY = "Hold steady."
    READY = "Document captured."


@dataclass
class FrameAssessment:
    """Assessment of a single camera frame for capture guidance."""
    brightness: float            # 0..1
    blur: float                  # 0..1 (1 = sharp)
    contrast: float              # 0..1
    document_detected: bool
    all_corners_visible: bool
    fill_ratio: float            # fraction of frame occupied by the document
    center_offset: tuple[float, float]  # (-1..1, -1..1) document centre vs frame centre
    orientation_degrees: float   # estimated rotation of the document
    guidance: list[Guidance] = field(default_factory=list)
    ready_to_capture: bool = False


class CaptureGuide:
    """
    Produces spoken guidance for positioning a document in the camera frame.

    Prioritises the single most important action so the user hears one clear
    instruction at a time (important for screen-reader usability).

    Thresholds are expressed as fractions of the frame so behaviour is
    resolution-independent and matches the Kotlin port.
    """

    # Document should fill between these fractions of the frame
    MIN_FILL: float = 0.35
    MAX_FILL: float = 0.98
    TARGET_FILL: float = 0.70

    # Corner must be at least this far from the frame edge to count as "visible"
    EDGE_MARGIN: float = 0.03

    # Centring tolerance
    CENTER_TOLERANCE: float = 0.12

    def assess_frame(self, frame: np.ndarray, is_document_candidate: bool = True) -> FrameAssessment:
        """
        Assess a single BGR or grayscale frame.

        Args:
            frame: Camera frame (BGR or grayscale uint8).
            is_document_candidate: Hint from the caller; when False the frame
                is treated as not containing a document.

        Returns:
            FrameAssessment with a prioritised guidance list.
        """
        if frame is None or frame.size == 0:
            return FrameAssessment(
                brightness=0.0, blur=0.0, contrast=0.0,
                document_detected=False, all_corners_visible=False,
                fill_ratio=0.0, center_offset=(0.0, 0.0),
                orientation_degrees=0.0,
                guidance=[Guidance.DOCUMENT_NOT_VISIBLE],
            )

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        h, w = gray.shape[:2]

        brightness = self._brightness(gray)
        blur = self._blur(gray)
        contrast = self._contrast(gray)

        corners, fill_ratio, center_offset, orientation = self._detect_document(gray)
        document_detected = is_document_candidate and corners is not None
        all_corners_visible = self._corners_visible(corners, h, w) if corners is not None else False

        guidance = self._prioritise(
            brightness=brightness,
            blur=blur,
            document_detected=document_detected,
            all_corners_visible=all_corners_visible,
            fill_ratio=fill_ratio,
            center_offset=center_offset,
            orientation=orientation,
        )

        ready = (
            document_detected
            and all_corners_visible
            and 0.25 < brightness < 0.9
            and blur > 0.35
            and self.MIN_FILL <= fill_ratio <= self.MAX_FILL
            and abs(center_offset[0]) <= self.CENTER_TOLERANCE
            and abs(center_offset[1]) <= self.CENTER_TOLERANCE
        )

        return FrameAssessment(
            brightness=brightness,
            blur=blur,
            contrast=contrast,
            document_detected=document_detected,
            all_corners_visible=all_corners_visible,
            fill_ratio=fill_ratio,
            center_offset=center_offset,
            orientation_degrees=orientation,
            guidance=[Guidance.READY] if ready else guidance,
            ready_to_capture=ready,
        )

    # ── metrics ───────────────────────────────────────────────

    @staticmethod
    def _brightness(gray: np.ndarray) -> float:
        return float(np.mean(gray)) / 255.0

    @staticmethod
    def _blur(gray: np.ndarray) -> float:
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return float(min(lap_var / 500.0, 1.0))

    @staticmethod
    def _contrast(gray: np.ndarray) -> float:
        return float(min(np.std(gray) / 80.0, 1.0))

    def _detect_document(
        self, gray: np.ndarray
    ) -> tuple[Optional[np.ndarray], float, tuple[float, float], float]:
        """Detect the document quadrilateral. Returns (corners, fill, offset, orientation)."""
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, 0.0, (0.0, 0.0), 0.0

        h, w = gray.shape[:2]
        frame_area = float(h * w)

        largest = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(largest))
        fill_ratio = area / frame_area if frame_area else 0.0

        if fill_ratio < 0.05:
            return None, fill_ratio, (0.0, 0.0), 0.0

        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
        if len(approx) >= 4:
            corners = approx.reshape(-1, 2).astype(np.float32)
            if len(corners) != 4:
                box = cv2.boxPoints(cv2.minAreaRect(corners))
                corners = box.astype(np.float32)
        else:
            return None, fill_ratio, (0.0, 0.0), 0.0

        cx = float(np.mean(corners[:, 0]))
        cy = float(np.mean(corners[:, 1]))
        offset_x = (cx / w - 0.5) * 2.0
        offset_y = (cy / h - 0.5) * 2.0

        orientation = self._orientation(corners)

        return corners, fill_ratio, (offset_x, offset_y), orientation

    @staticmethod
    def _orientation(corners: np.ndarray) -> float:
        """Estimate document rotation in degrees from the top edge."""
        pts = corners.reshape(-1, 2)
        # Order points: tl, tr, br, bl
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).reshape(-1)
        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(d)]
        bl = pts[np.argmax(d)]
        top = tr - tl
        angle = float(np.degrees(np.arctan2(top[1], top[0])))
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90
        return angle

    def _corners_visible(self, corners: Optional[np.ndarray], h: int, w: int) -> bool:
        if corners is None:
            return False
        mx = w * self.EDGE_MARGIN
        my = h * self.EDGE_MARGIN
        for x, y in corners.reshape(-1, 2):
            if x < mx or x > w - mx or y < my or y > h - my:
                return False
        return True

    # ── guidance ──────────────────────────────────────────────

    def _prioritise(
        self,
        brightness: float,
        blur: float,
        document_detected: bool,
        all_corners_visible: bool,
        fill_ratio: float,
        center_offset: tuple[float, float],
        orientation: float,
    ) -> list[Guidance]:
        """
        Return guidance ordered most-important-first.

        Order of priority:
        1. Lighting / up-front blockers
        2. Document presence
        3. Framing (corners, distance, position)
        4. Stability
        """
        out: list[Guidance] = []

        if brightness < 0.25:
            out.append(Guidance.TOO_DARK)
        elif brightness > 0.92:
            out.append(Guidance.TOO_BRIGHT)

        if not document_detected:
            out.append(Guidance.DOCUMENT_NOT_VISIBLE)
            return out

        if not all_corners_visible:
            out.append(Guidance.DOCUMENT_NOT_VISIBLE)

        if fill_ratio < self.MIN_FILL:
            out.append(Guidance.MOVE_CLOSER)
        elif fill_ratio > self.MAX_FILL:
            out.append(Guidance.MOVE_FURTHER)

        ox, oy = center_offset
        if ox < -self.CENTER_TOLERANCE:
            out.append(Guidance.MOVE_LEFT)
        elif ox > self.CENTER_TOLERANCE:
            out.append(Guidance.MOVE_RIGHT)
        if oy < -self.CENTER_TOLERANCE:
            out.append(Guidance.MOVE_UP)
        elif oy > self.CENTER_TOLERANCE:
            out.append(Guidance.MOVE_DOWN)

        if blur < 0.35:
            out.append(Guidance.HOLD_STEADY)

        return out

    @staticmethod
    def primary_guidance(assessment: FrameAssessment) -> Optional[str]:
        """Return the single most important spoken instruction, or None."""
        if assessment.ready_to_capture:
            return Guidance.READY.value
        if assessment.guidance:
            return assessment.guidance[0].value
        return None


def create_capture_guide() -> CaptureGuide:
    """Factory function for creating a capture guide."""
    return CaptureGuide()
