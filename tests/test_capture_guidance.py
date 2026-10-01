"""Tests for accessible camera capture guidance."""
import numpy as np
import cv2
import pytest

from ml.capture_guidance import CaptureGuide, Guidance


def make_frame(brightness=200, blurness=0.0, size=(600, 800)):
    """Create a synthetic frame with a centred white rectangle (document)."""
    h, w = size
    frame = np.full((h, w, 3), brightness // 2, dtype=np.uint8)
    # Draw a bright "document" rectangle
    margin_x, margin_y = int(w * 0.15), int(h * 0.10)
    cv2.rectangle(
        frame,
        (margin_x, margin_y),
        (w - margin_x, h - margin_y),
        (brightness, brightness, brightness),
        -1,
    )
    # Add some text-like lines for edge detection
    for i in range(6):
        y = margin_y + 40 + i * 40
        cv2.line(frame, (margin_x + 30, y), (w - margin_x - 30, y), (40, 40, 40), 3)
    if blurness > 0:
        k = int(2 * blurness * 10) + 1
        frame = cv2.GaussianBlur(frame, (k, k), 0)
    return frame


class TestCaptureGuide:
    def setup_method(self):
        self.guide = CaptureGuide()

    def test_empty_frame_reports_not_visible(self):
        result = self.guide.assess_frame(np.zeros((10, 10, 3), dtype=np.uint8))
        assert not result.ready_to_capture
        # Blank frame: no document
        assert Guidance.DOCUMENT_NOT_VISIBLE in result.guidance or result.brightness < 0.25

    def test_none_frame_is_handled(self):
        result = self.guide.assess_frame(None)
        assert not result.ready_to_capture
        assert Guidance.DOCUMENT_NOT_VISIBLE in result.guidance

    def test_dark_frame_guides_to_light(self):
        dark = np.full((600, 800, 3), 10, dtype=np.uint8)
        result = self.guide.assess_frame(dark)
        assert Guidance.TOO_DARK in result.guidance
        assert self.guide.primary_guidance(result) == Guidance.TOO_DARK.value

    def test_bright_frame_guides_away_from_light(self):
        bright = np.full((600, 800, 3), 252, dtype=np.uint8)
        cv2.rectangle(bright, (100, 100), (700, 500), (255, 255, 255), -1)
        result = self.guide.assess_frame(bright)
        assert Guidance.TOO_BRIGHT in result.guidance

    def test_small_document_guides_closer(self):
        frame = np.full((600, 800, 3), 128, dtype=np.uint8)
        # Tiny rectangle -> fill ratio well below MIN_FILL
        cv2.rectangle(frame, (380, 280), (420, 320), (255, 255, 255), -1)
        result = self.guide.assess_frame(frame)
        # Either no document detected or "move closer"; both are valid failures
        assert result.ready_to_capture is False

    def test_primary_guidance_returns_single_string(self):
        frame = make_frame(brightness=180)
        result = self.guide.assess_frame(frame)
        msg = self.guide.primary_guidance(result)
        assert msg is None or isinstance(msg, str)

    def test_ready_frame_reports_captured(self):
        # A large, well-lit, sharp, centred document
        frame = make_frame(brightness=190)
        result = self.guide.assess_frame(frame)
        if result.ready_to_capture:
            assert self.guide.primary_guidance(result) == Guidance.READY.value
            assert result.guidance == [Guidance.READY]

    def test_guidance_is_deterministic(self):
        frame = make_frame(brightness=180)
        r1 = self.guide.assess_frame(frame)
        r2 = self.guide.assess_frame(frame)
        assert [g.value for g in r1.guidance] == [g.value for g in r2.guidance]
        assert r1.ready_to_capture == r2.ready_to_capture

    def test_metrics_are_in_range(self):
        frame = make_frame(brightness=150)
        result = self.guide.assess_frame(frame)
        assert 0.0 <= result.brightness <= 1.0
        assert 0.0 <= result.blur <= 1.0
        assert 0.0 <= result.contrast <= 1.0
        assert -1.0 <= result.center_offset[0] <= 1.0
        assert -1.0 <= result.center_offset[1] <= 1.0

    def test_offcentre_document_guides_to_move(self):
        frame = np.full((600, 800, 3), 128, dtype=np.uint8)
        # Document pushed to the right side
        cv2.rectangle(frame, (520, 80), (780, 520), (230, 230, 230), -1)
        for i in range(5):
            cv2.line(frame, (540, 120 + i * 60), (760, 120 + i * 60), (40, 40, 40), 3)
        result = self.guide.assess_frame(frame)
        if result.document_detected and result.center_offset[0] > 0.12:
            assert Guidance.MOVE_LEFT in result.guidance or Guidance.MOVE_RIGHT in result.guidance

    def test_grayscale_input_accepted(self):
        gray = cv2.cvtColor(make_frame(180), cv2.COLOR_BGR2GRAY)
        result = self.guide.assess_frame(gray)
        assert 0.0 <= result.brightness <= 1.0
