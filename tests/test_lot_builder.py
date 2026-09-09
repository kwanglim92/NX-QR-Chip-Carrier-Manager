"""로트 생성 테스트 — Unit No 증가, 폴더 형식, atx_parser 라운드트립, 리포트 CSV."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.core.atx_parser import load_atx_folder
from src.core.inspection.grading import grade_run
from src.core.inspection.lot_builder import (
    build_lots,
    default_batch,
    lot_folder_name,
    next_unit_no,
    plan_lot_sizes,
    validate_plan,
    write_lot_folder,
    write_report_csv,
)
from src.core.inspection.mtc_parser import load_mtc_run
from src.core.inspection.reference import auto_reference
from src.core.inspection.templates import default_template

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def run():
    return load_mtc_run(FIXTURE)


def test_next_unit_no():
    assert next_unit_no("P2401002") == "P2401003"
    assert next_unit_no("P2401099") == "P2401100"
    assert next_unit_no("P0009") == "P0010"
    assert next_unit_no("ABC") == "ABC_1"
    assert next_unit_no(" P1 ") == "P2"


def test_plan_and_validate():
    assert plan_lot_sizes({12: 2, 10: 1, 5: 3}) == [12, 12, 10, 5, 5, 5]
    assert plan_lot_sizes({12: 0, 10: 0, 5: 0}) == []
    assert validate_plan([], 10) == "로트 수량이 0 입니다"
    assert validate_plan([12], 11) == "필요 12개 > 통과 11개"
    assert validate_plan([5, 5], 10) is None


def test_names():
    assert lot_folder_name("P2401002", 12, "AC160") == "P2401002_12M_AC160"
    assert default_batch("AC160", "20260909") == "ac160(20260909)"


def test_write_lot_folder_roundtrip(run, tmp_path):
    slots = [run.find(1, 1, 1), run.find(1, 1, 2), run.find(1, 2, 4)]
    res = write_lot_folder(tmp_path, "P2401002", 5, "AC160", "ac160(20260909)", slots)
    folder = Path(res.folder)
    assert folder.name == "P2401002_5M_AC160"
    assert res.codes == ["1101", "1102", "1204"]

    rows = list(csv.reader((folder / "Summary.csv").open(encoding="utf-8")))
    assert rows[0][:4] == ["Batch", "ac160(20260909)_1101", "ac160(20260909)_1102", "ac160(20260909)_1204"]
    assert rows[1][:2] == ["Freq", "284.81"] and rows[2][:2] == ["Q", "422.81"]
    assert rows[0][-1] == ""      # 원본과 같은 후행 콤마

    assert (folder / "FreqSweep" / "1_ac160(20260909)_1101.jpg").exists()
    assert (folder / "FreqSweep" / "1_ac160(20260909)_1101_ZoomOut.jpg").exists()
    assert (folder / "FreqSweep" / "1_ac160(20260909)_1101.txt").exists()
    assert (folder / "Vision" / "1_ac160(20260909)_1101_pickUp.png").exists()
    assert (folder / "Vision" / "1_ac160(20260909)_1101_putBack.png").exists()
    assert (folder / "Vision" / "3_ac160(20260909)_1204_pickUp.png").exists()

    # 기존 ATX 모드 파서로 다시 읽힌다
    ms = load_atx_folder(str(folder))
    assert ms.po_number == "P2401002" and ms.quantity == 5 and ms.probe_type == "AC160"
    assert [s.slot_code for s in ms.slots] == ["1101", "1102", "1204"]
    assert ms.slots[0].frequency == 284 and ms.slots[0].q_factor == 422
    assert ms.slots[0].image_path.endswith("1_ac160(20260909)_1101.jpg")
    # write_lot_folder 가 돌려준 set 은 drive 까지 채워져 있다
    assert res.measurement_set.slots[0].drive == 1.87
    assert res.measurement_set.source_folder == str(folder)


def test_build_lots_increments_unit_no_and_returns_remaining(run, tmp_path):
    slots = [s for s in run.slots if s.has_sweep]          # 4개
    lots, remaining = build_lots(tmp_path, slots, [2, 1], "P2401002", "AC160", "b")
    assert [l.unit_no for l in lots] == ["P2401002", "P2401003"]
    assert [l.size for l in lots] == [2, 1]
    assert [Path(l.folder).name for l in lots] == ["P2401002_2M_AC160", "P2401003_1M_AC160"]
    assert lots[0].codes == ["1101", "1102"] and lots[1].codes == ["1204"]
    assert [s.code for s in remaining] == ["3212"]
    with pytest.raises(ValueError):
        build_lots(tmp_path, slots, [12], "P1", "AC160", "b")


def test_write_report_csv(run, tmp_path):
    ref = auto_reference(run)
    verdicts = grade_run(run, default_template("AC160"), ref)
    verdicts[0].override_grade = "research"
    path = tmp_path / "Inspection_20260909.csv"
    write_report_csv(path, run, verdicts, ref.code, "AC160")
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0].startswith("# run=20260909,reference=1101,template=AC160")
    rows = list(csv.reader(lines[1:]))
    header = rows[0]
    assert header[:7] == ["CantileverNo", "ATX", "Port", "Slot", "Grade", "Error", "Override"]
    assert len(rows) == 1 + len(run.slots)
    first = dict(zip(header, rows[1]))
    assert first["CantileverNo"] == "20260909_1101" and first["Grade"] == "연구용" and first["Override"] == "Y"
    no_sweep = dict(zip(header, rows[3]))
    assert no_sweep["CantileverNo"] == "20260909_1111" and no_sweep["Error"] == "No Sweep"
    assert no_sweep["Frequency (kHz)"] == ""
