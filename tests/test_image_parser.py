"""Phase 5 + 7A 회귀 테스트 — image_parser.py extract_measurements + 범위 검증."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.core.image_parser import (
    ROI,
    MeasurementReading,
    _FREQ_RANGE,
    _Q_RANGE,
    _in_range,
    extract_measurements,
)
from tests.conftest import (
    SAMPLE_FREQ_EXPECTED,
    SAMPLE_Q_EXPECTED,
    SAMPLE_IMAGE_SIZE,
)


class TestDataclass:
    def test_default_values(self):
        r = MeasurementReading()
        assert r.frequency is None
        assert r.q_factor is None

    def test_explicit_values(self):
        r = MeasurementReading(frequency=150.25, q_factor=1234.5)
        assert r.frequency == 150.25
        assert r.q_factor == 1234.5


class TestRoiConstant:
    def test_roi_structure(self):
        assert isinstance(ROI, dict)
        assert set(ROI.keys()) == {"frequency", "q_factor"}
        for name, rect in ROI.items():
            assert len(rect) == 4
            assert all(isinstance(n, int) and n >= 0 for n in rect)


class TestRangeValidation:
    def test_range_constants(self):
        assert _FREQ_RANGE == (50.0, 5000.0)
        assert _Q_RANGE == (10.0, 10000.0)

    def test_in_range_valid(self):
        assert _in_range(100.0, 50.0, 5000.0) is True
        assert _in_range(50.0, 50.0, 5000.0) is True  # 경계 포함
        assert _in_range(5000.0, 50.0, 5000.0) is True

    def test_in_range_invalid(self):
        assert _in_range(49.9, 50.0, 5000.0) is False
        assert _in_range(5000.1, 50.0, 5000.0) is False
        assert _in_range(None, 0.0, 1.0) is False


class TestExtractFallback:
    """Tesseract/Pillow 부재 또는 잘못된 경로에서 조용한 fallback."""

    def test_nonexistent_path(self):
        r = extract_measurements("/nonexistent/path/to/image.png")
        assert r.frequency is None
        assert r.q_factor is None

    def test_invalid_format(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"not a real image")
            bad_path = f.name
        try:
            r = extract_measurements(bad_path)
            assert r.frequency is None
            assert r.q_factor is None
        finally:
            Path(bad_path).unlink()


@pytest.mark.ocr
class TestActualOcr:
    """실제 Tesseract + 실제 이미지가 필요한 테스트 — 없으면 skip."""

    def test_extract_default_roi(self, sample_afm_image, require_ocr):
        r = extract_measurements(sample_afm_image)
        assert r.frequency == SAMPLE_FREQ_EXPECTED
        assert r.q_factor == SAMPLE_Q_EXPECTED

    def test_extract_explicit_roi_equivalent(self, sample_afm_image, require_ocr):
        r = extract_measurements(sample_afm_image, roi=ROI)
        assert r.frequency == SAMPLE_FREQ_EXPECTED
        assert r.q_factor == SAMPLE_Q_EXPECTED

    def test_extract_out_of_bounds_roi(self, sample_afm_image, require_ocr):
        """이미지 범위 밖 ROI → MeasurementReading(None, None) + WARNING 로그."""
        bad_roi = {
            "frequency": (9000, 9000, 100, 20),
            "q_factor": (9000, 9000, 100, 20),
        }
        r = extract_measurements(sample_afm_image, roi=bad_roi)
        assert r.frequency is None
        assert r.q_factor is None

    def test_range_validation_clamps_bogus_values(self, sample_afm_image, require_ocr):
        """이미지 상단 전체를 ROI로 → 여러 수치 섞여 비상식 값 나올 수 있음. 범위 밖이면 폐기."""
        W, H = SAMPLE_IMAGE_SIZE
        # 상단 전폭 영역 — 여러 박스에 걸쳐 숫자가 합쳐질 가능성
        roi = {
            "frequency": (0, 0, W, 30),
            "q_factor": (0, 0, W, 30),
        }
        r = extract_measurements(sample_afm_image, roi=roi)
        # 범위 체크가 작동하면 freq가 None이거나 _FREQ_RANGE 안
        if r.frequency is not None:
            assert _in_range(r.frequency, *_FREQ_RANGE)
        if r.q_factor is not None:
            assert _in_range(r.q_factor, *_Q_RANGE)
