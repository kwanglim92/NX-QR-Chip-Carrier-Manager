"""sweep 형상 판정 테스트 — 실런 발췌 txt(정상/이중피크/부피크) + 합성 곡선."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.core.inspection.mtc_parser import load_mtc_run
from src.core.inspection.sweep_shape import (
    SweepShape,
    analyze_sweep,
    find_peaks,
    half_width_asymmetry,
    lorentzian_curve,
    lorentzian_fit,
    read_sweep_txt,
    side_peak_ratio,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def run():
    return load_mtc_run(FIXTURE)


def _lorentz_curve(f0=280.0, gamma=0.3, a0=10.0, base=1.0, span=1.7, n=100, center=280.0):
    freqs = [center - span / 2 + span * i / (n - 1) for i in range(n)]
    amps = [base + (a0 - base) / (1 + ((f - f0) / gamma) ** 2) for f in freqs]
    return freqs, amps


def test_read_sweep_txt(run):
    freqs, amps = read_sweep_txt(run.find(1, 1, 1).sweep_txt)
    assert len(freqs) == 100 and len(amps) == 100
    assert freqs[0] == 283.89 and amps[0] == 2.45
    assert read_sweep_txt(None) == ([], [])
    assert read_sweep_txt("Z:/nope.txt") == ([], [])


def test_find_peaks_single_and_double():
    _, single = _lorentz_curve()
    assert len(find_peaks(single)) == 1
    f, a1 = _lorentz_curve(f0=279.7, gamma=0.15)
    _, a2 = _lorentz_curve(f0=280.4, gamma=0.15, a0=8.0)
    double = [x + y for x, y in zip(a1, a2)]
    assert len(find_peaks(double)) == 2
    assert find_peaks([1.0, 1.0]) == []


def test_lorentzian_fit_recovers_synthetic():
    freqs, amps = _lorentz_curve(gamma=0.3)
    r2, gamma, params = lorentzian_fit(freqs, amps)
    assert r2 > 0.995
    assert 0.2 < gamma < 0.45
    assert params["f0"] == pytest.approx(280.0, abs=0.02) and params["a0"] == pytest.approx(10.0, abs=0.6)
    curve = lorentzian_curve(freqs, params)
    assert len(curve) == 100 and max(curve) == pytest.approx(10.0, abs=0.6)
    assert lorentzian_fit([1, 2], [1, 2]) == (None, None, None)
    assert lorentzian_fit([1, 2, 3, 4, 5], [1, 1, 1, 1, 1]) == (None, None, None)


def test_half_width_asymmetry_symmetric_and_skewed():
    freqs, amps = _lorentz_curve()
    assert half_width_asymmetry(freqs, amps) == pytest.approx(1.0, abs=0.1)
    # 오른쪽 꼬리를 늘린 왜곡 곡선
    skewed = [a * (1.0 + 2.0 * max(0.0, (f - 280.0))) for f, a in zip(freqs, amps)]
    assert half_width_asymmetry(freqs, skewed) > 1.3
    # 피크가 창 가장자리에 있어 한쪽 반높이를 못 찾으면 None
    edge = _lorentz_curve(f0=279.15)
    assert half_width_asymmetry(*edge) is None


def test_side_peak_ratio():
    freqs = [200 + i * 0.4 for i in range(500)]
    # 200 + 0.4·k 격자 위에 정확히 놓이는 중심(284.8, 240.0)
    amps = [1.0 + 15.0 * math.exp(-((f - 284.8) / 0.5) ** 2) + 12.0 * math.exp(-((f - 240) / 0.5) ** 2)
            for f in freqs]
    ratio, at = side_peak_ratio(freqs, amps, 284.8)
    assert ratio == pytest.approx(13.0 / 16.0, abs=0.02)
    assert at == pytest.approx(240.0, abs=0.5)
    assert side_peak_ratio([], [], 285.0) == (None, None)


def test_analyze_reference_slot_is_clean(run):
    s = run.find(1, 1, 1)
    sh = analyze_sweep(s.sweep_txt, s.zoom_txt)
    assert sh.available and sh.n_peaks == 1
    assert sh.fit_r2 > 0.95
    assert sh.side_peak_ratio < 0.5
    assert sh.score >= 80
    assert sh.peak_freq == pytest.approx(284.7, abs=0.2)
    assert "score" in sh.summary()


def test_analyze_double_peak_slot_is_flagged(run):
    """ATX3 Port2 Slot12: 어깨 왜곡 + ZoomOut 288 kHz 부피크(주피크보다 큼)."""
    s = run.find(3, 2, 12)
    sh = analyze_sweep(s.sweep_txt, s.zoom_txt)
    assert sh.available
    assert sh.fit_r2 < 0.92
    assert sh.side_peak_ratio > 1.0
    assert sh.side_peak_freq == pytest.approx(288, abs=2)
    assert sh.score < 30
    assert any(r.startswith("side peak") for r in sh.reasons)


def test_analyze_freq364_slot_side_peak(run):
    """ATX1 Port2 Slot4: 줌인은 단봉이나 ZoomOut 246 kHz 에 주피크급 부피크."""
    s = run.find(1, 2, 4)
    sh = analyze_sweep(s.sweep_txt, s.zoom_txt)
    assert sh.n_peaks == 1 and sh.side_peak_ratio > 1.0
    assert 40 <= sh.score < 70


def test_analyze_without_zoomin(run):
    s = run.find(1, 1, 11)
    sh = analyze_sweep(s.sweep_txt, s.zoom_txt)
    assert sh == SweepShape()
    assert sh.summary() == "sweep 없음"


def test_analyze_low_q_noisy_slot(run):
    s = run.find(1, 1, 2)   # Q 141, 다중 피크 잡음
    sh = analyze_sweep(s.sweep_txt, s.zoom_txt)
    assert sh.n_peaks >= 2 and sh.score < 30
