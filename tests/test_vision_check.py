"""Vision 파손 판정 테스트 — fixture pickUp png(800×600 축소본) + 합성 파손 이미지."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.inspection.mtc_parser import load_mtc_run
from src.core.inspection.vision_check import (
    MIN_LENGTH_RATIO,
    VisionCheck,
    check_vision,
    load_gray,
    measure_tip,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def run():
    return load_mtc_run(FIXTURE)


@pytest.fixture(scope="module")
def ref_measure(run):
    return measure_tip(run.find(1, 1, 1).pickup_image)


def test_measure_reference_tip(ref_measure):
    m = ref_measure
    assert m.image_height == 600 and m.image_width == 800
    assert 40 <= m.baseline_row <= 120          # 칩 몸체 하단
    assert m.band[0] > 250 and m.band[1] < 500  # 캔틸레버 열 밴드(중앙 부근)
    assert 150 <= m.length_px <= 260            # 팁 길이 ≈ 이미지 높이의 1/3
    assert m.area_px > 5000
    assert 0.25 < m.length_frac < 0.45


def test_all_fixture_tips_are_intact(run, ref_measure):
    for s in run.slots:
        if not s.pickup_image:
            continue
        vc = check_vision(s.pickup_image, s.match_score, ref_measure)
        assert vc.available and not vc.broken, s.code
        assert 0.9 < vc.length_ratio < 1.1


def test_shifted_cantilever_is_still_intact(run, ref_measure):
    """4_1_11: Tip X 891(기준 1209) 로 크게 이동했지만 팁은 온전 → 파손 아님."""
    s = run.find(4, 1, 11)
    m = measure_tip(s.pickup_image)
    assert m.band[1] < ref_measure.band[0]      # 밴드가 기준보다 왼쪽
    assert not check_vision(s.pickup_image, s.match_score, ref_measure).broken


def test_synthetic_broken_tip_detected(run, ref_measure):
    arr = load_gray(run.find(1, 1, 1).pickup_image).copy()
    m = ref_measure
    cut = m.baseline_row + int(m.length_px * 0.4)
    arr[cut:, :] = 235          # 팁 아래 60% 를 배경색으로 지움
    broken = measure_tip(arr)
    assert broken.length_px < m.length_px * MIN_LENGTH_RATIO
    # check_vision 은 경로를 받으므로 임시 파일로 저장
    from PIL import Image
    tmp = Path(str(FIXTURE)).parent / "_tmp_broken.png"
    try:
        Image.fromarray(arr).save(tmp)
        vc = check_vision(tmp, 99.0, m)
        assert vc.broken and vc.reasons and "tip length" in vc.reasons[0]
        assert vc.summary().startswith("BROKEN")
    finally:
        tmp.unlink(missing_ok=True)


def test_synthetic_area_loss_detected(run, ref_measure, tmp_path):
    """길이는 유지되지만 폭이 크게 깎인 팁(면적 60% 미만) → 파손."""
    arr = load_gray(run.find(1, 1, 1).pickup_image).copy()
    m = ref_measure
    c0, c1 = m.band
    mid = (c0 + c1) // 2
    # 밴드의 중앙 좁은 줄만 남기고 양옆을 지움
    arr[m.baseline_row + 1:, c0:mid - 4] = 235
    arr[m.baseline_row + 1:, mid + 4:c1 + 1] = 235
    from PIL import Image
    p = tmp_path / "thin.png"
    Image.fromarray(arr).save(p)
    vc = check_vision(p, 99.0, m)
    assert vc.broken and any("area" in r or "length" in r for r in vc.reasons)


def test_no_reference_uses_image_fraction(run):
    s = run.find(1, 1, 1)
    vc = check_vision(s.pickup_image, s.match_score, None)
    assert vc.available and not vc.broken and vc.length_ratio is None


def test_match_score_threshold(run, ref_measure):
    s = run.find(1, 1, 1)
    vc = check_vision(s.pickup_image, 97.0, ref_measure, min_match=99.0)
    assert vc.match_ok is False and "match 97.0%" in vc.reasons
    assert not vc.broken
    vc2 = check_vision(s.pickup_image, 99.5, ref_measure, min_match=99.0)
    assert vc2.match_ok is True


def test_missing_image_and_blank_image(tmp_path):
    vc = check_vision(None, 99.0, None)
    assert vc == VisionCheck(match_score=99.0, reasons=["no image"])
    assert vc.summary() == "vision 없음"
    blank = np.full((100, 100), 240, dtype=np.uint8)
    assert measure_tip(blank) is None
    from PIL import Image
    p = tmp_path / "blank.png"
    Image.fromarray(blank).save(p)
    assert "body not found" in check_vision(p, None, None).reasons
