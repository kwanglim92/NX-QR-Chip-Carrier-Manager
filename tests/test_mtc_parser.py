"""MTC 런 폴더 파서 테스트 — 실제 런(20260909) 발췌 fixture 기반."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.inspection.mtc_parser import (
    MtcSlot,
    is_mtc_run_folder,
    load_mtc_run,
    normalize_header,
    read_table,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def run():
    return load_mtc_run(FIXTURE)


def test_normalize_header():
    assert normalize_header("A+B (V)") == "a_plus_b"
    assert normalize_header("A-B (V)") == "a_minus_b"
    assert normalize_header("Tip X (pxl)") == "tip_x"
    assert normalize_header("Frequency (KHz)") == "frequency"
    assert normalize_header("Set Point (nm)") == "set_point"
    assert normalize_header("Tip Exchanger") == "tip_exchanger"
    assert normalize_header("Match Score (%)") == "match_score"
    assert normalize_header("CantileverNo") == "cantileverno"


def test_read_table_handles_trailing_tab_and_space_rows():
    sweep = read_table(FIXTURE / "FreqSweep.txt")
    assert sweep[0]["frequency"] == "284.81"
    assert sweep[0]["q"] == "422.81"
    angle = read_table(FIXTURE / "Angle.txt")   # 행이 공백 구분
    assert angle[0] == {"cantileverno": "20260909_1101", "angle": "89.408"}


def test_is_mtc_run_folder(tmp_path):
    assert is_mtc_run_folder(FIXTURE)
    assert not is_mtc_run_folder(tmp_path)
    (tmp_path / "PSPD.txt").write_text("Repeat\tTip Exchanger\tPort\tSlot\tA+B (V)\n")
    assert is_mtc_run_folder(tmp_path)


def test_run_id_and_slot_order(run):
    assert run.run_id == "20260909"
    assert [s.key for s in run.slots] == [
        (1, 1, 1), (1, 1, 2), (1, 1, 11), (1, 2, 4), (1, 2, 6), (3, 2, 12), (4, 1, 11),
    ]
    assert run.slots[0].code == "1101"
    assert run.cantilever_no(run.slots[0]) == "20260909_1101"
    assert run.find_code("3212").key == (3, 2, 12)


def test_reference_slot_values(run):
    s = run.find(1, 1, 1)
    assert s.a_plus_b == 2.91 and s.a_minus_b == -0.43 and s.c_minus_d == 10.0
    assert s.frequency == 284.81 and s.set_point == 4.99 and s.amplitude == 9.99
    assert s.drive == 1.87 and s.q == 422.81
    assert s.zoom_frequency == 285.60 and s.zoom_q == 137.56
    assert s.tip_focus == 5272.38 and s.tip_x == 1209.42 and s.tip_y == 550.737
    assert s.match_score == 99.93
    assert s.angle == 89.408
    assert s.delta_z == 0.0
    assert s.has_sweep and s.has_vision


def test_file_paths_attached(run):
    s = run.find(1, 1, 1)
    assert Path(s.sweep_image).name == "Port1_1.jpg"
    assert Path(s.sweep_txt).name == "Port1_1.txt"
    assert Path(s.zoom_image).name == "Port1_1_ZoomOut.jpg"
    assert Path(s.zoom_txt).name == "Port1_1_ZoomOut.txt"
    assert Path(s.pickup_image).name == "Port1_1_pickUp.png"
    assert Path(s.putback_image).name == "Port1_1_putBack.png"
    assert "TipExchanger1" in s.sweep_image
    # 4_1_11 은 putBack 이미지를 fixture 에 두지 않았다 → None
    assert run.find(4, 1, 11).putback_image is None


def test_slot_without_zoomin_sweep(run):
    """1_1_11: ZoomOut/PSPD/Vision 에는 있으나 FreqSweep.txt 에 없음 → frequency None."""
    s = run.find(1, 1, 11)
    assert s.frequency is None and s.q is None
    assert s.zoom_frequency == 258.93
    assert s.sweep_image is None and s.zoom_image is not None
    assert not s.has_sweep


def test_exchange_does_not_define_slots(run):
    # Exchange.txt 는 fixture 에 7개 슬롯 행만 있지만, 원본은 빈 슬롯도 전부 나열한다.
    # 정의 파일에 없는 슬롯은 만들어지지 않아야 한다.
    assert run.find(2, 1, 1) is None


def test_double_peak_slot_values(run):
    s = run.find(3, 2, 12)
    assert s.frequency == 364.23 and s.q == 47.87
    assert s.angle == 88.957


def test_missing_files_give_empty_run(tmp_path):
    run = load_mtc_run(tmp_path)
    assert run.slots == [] and run.run_id == tmp_path.name


def test_mtcslot_defaults():
    s = MtcSlot(atx=2, port=1, slot=3)
    assert s.code == "2103" and s.repeat == 1
    assert not s.has_sweep and not s.has_vision
