"""Phase 7C 회귀 테스트 — OcrRunnable + QThreadPool 비동기 파이프라인."""
from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QElapsedTimer, QThreadPool

from src.core.image_parser import MeasurementReading
from src.core.ocr_worker import OcrRunnable, OcrSignals
from tests.conftest import SAMPLE_FREQ_EXPECTED, SAMPLE_Q_EXPECTED


def _wait_for(qapp, condition, timeout_ms: int = 30000) -> bool:
    """이벤트 루프를 돌리며 조건이 True가 될 때까지 대기."""
    timer = QElapsedTimer()
    timer.start()
    while not condition() and timer.elapsed() < timeout_ms:
        qapp.processEvents()
        time.sleep(0.02)
    return condition()


class TestOcrRunnableBasic:
    def test_runnable_signals_is_qobject(self):
        sig = OcrSignals()
        assert hasattr(sig, "finished")

    def test_runnable_attributes(self):
        r = OcrRunnable(slot_index=3, image_path="x.png", roi=None, batch_id="b1")
        assert r.slot_index == 3
        assert r.image_path == "x.png"
        assert r.roi is None
        assert r.batch_id == "b1"
        assert r.autoDelete() is True

    def test_runnable_fallback_on_missing_image(self, qapp):
        """잘못된 경로 → MeasurementReading(None, None) emit."""
        results = []
        r = OcrRunnable(slot_index=0, image_path="/nonexistent.png",
                         roi=None, batch_id="b")
        r.signals.finished.connect(
            lambda idx, reading, bid: results.append((idx, reading, bid))
        )
        pool = QThreadPool()
        pool.start(r)
        assert _wait_for(qapp, lambda: len(results) == 1, timeout_ms=5000)
        idx, reading, bid = results[0]
        assert idx == 0 and bid == "b"
        assert isinstance(reading, MeasurementReading)
        assert reading.frequency is None
        assert reading.q_factor is None


@pytest.mark.ocr
class TestOcrRunnableActual:
    """실제 Tesseract + 샘플 이미지가 있는 환경에서만 실행."""

    def test_single_runnable_extracts_values(
        self, qapp, sample_afm_image, require_ocr,
    ):
        results = []
        r = OcrRunnable(slot_index=0, image_path=sample_afm_image,
                         roi=None, batch_id="t1")
        r.signals.finished.connect(
            lambda idx, reading, bid: results.append((idx, reading, bid))
        )
        pool = QThreadPool()
        pool.start(r)
        assert _wait_for(qapp, lambda: len(results) == 1, timeout_ms=15000)

        idx, reading, bid = results[0]
        assert idx == 0 and bid == "t1"
        assert reading.frequency == SAMPLE_FREQ_EXPECTED
        assert reading.q_factor == SAMPLE_Q_EXPECTED

    @pytest.mark.slow
    def test_parallel_under_4_threads(
        self, qapp, sample_afm_image, require_ocr,
    ):
        """여러 장을 4 스레드로 병렬 처리 — 스모크/회귀 수준."""
        N = 5  # 실사용 증명은 _phase7c_smoke_test.py 에서 20장 검증 완료
        results = {}
        # runnable 시그널 객체를 함수 스코프에 유지 (autoDelete 타이밍 방어)
        runnables = []

        pool = QThreadPool()
        pool.setMaxThreadCount(4)
        assert pool.maxThreadCount() == 4

        timer = QElapsedTimer()
        timer.start()

        for i in range(N):
            r = OcrRunnable(slot_index=i, image_path=sample_afm_image,
                             roi=None, batch_id="batch-parallel")
            r.signals.finished.connect(
                lambda idx, reading, bid, store=results: store.__setitem__(idx, reading)
            )
            runnables.append(r)
            pool.start(r)

        assert _wait_for(qapp, lambda: len(results) == N, timeout_ms=120000), \
            f"only {len(results)}/{N} results after 120s"

        elapsed_ms = timer.elapsed()
        for i in range(N):
            assert results[i].frequency == SAMPLE_FREQ_EXPECTED
            assert results[i].q_factor == SAMPLE_Q_EXPECTED

        # 병렬이라는 사실을 과하게 주장하지 않고, 합리적인 상한만 둠
        assert elapsed_ms < 120000
