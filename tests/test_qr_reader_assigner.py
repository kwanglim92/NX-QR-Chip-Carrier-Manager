"""R2: 셀 → (port, slot) 공식/override + 적용 계획 상태 분류 (§5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.models import MeasurementSet, SlotData
from src.core.qr_reader.payload_parser import CellRead, ParsedFrame, parse_frame
from src.core.qr_reader.slot_assigner import (
    AssignError,
    AssignStatus,
    build_plan,
    cell_to_port_slot,
)

FULL_RAW = Path(__file__).parent / "fixtures" / "qr_reader" / "20260909_132804_full.raw"


def _set(port: int, atx: int = 1, slots: range = range(1, 13), po: str = "P1") -> MeasurementSet:
    ms = MeasurementSet(po_number=po, mode="atx")
    for i, s in enumerate(slots):
        ms.slots.append(SlotData(slot_index=i, slot_code=f"_{atx}{port}{s:02d}", frequency=396.0, q_factor=710.0))
    return ms


def _frame(codes: list[str | None]) -> ParsedFrame:
    return ParsedFrame(reads=tuple(
        CellRead(cell=i, code=c, raw=c or "ERROR") for i, c in enumerate(codes, start=1)
    ))


# ─── cell_to_port_slot ───

@pytest.mark.parametrize("cell,expected", [(1, (1, 1)), (12, (1, 12)), (13, (2, 1)), (24, (2, 12)), (72, (6, 12))])
def test_formula(cell, expected):
    assert cell_to_port_slot(cell) == expected


def test_override_takes_precedence():
    assert cell_to_port_slot(1, {1: (6, 12)}) == (6, 12)
    assert cell_to_port_slot(2, {1: (6, 12)}) == (1, 2)


def test_cell_below_one_rejected_even_with_override():
    with pytest.raises(ValueError):
        cell_to_port_slot(0)
    with pytest.raises(ValueError):
        cell_to_port_slot(0, {0: (1, 1)})


@pytest.mark.parametrize("target", [(0, 1), (1, 0), (1, 13), (-1, 5)])
def test_override_out_of_range_rejected(target):
    with pytest.raises(ValueError, match="override 범위"):
        cell_to_port_slot(5, {5: target})


def test_override_duplicate_target_rejected_in_build_plan():
    with pytest.raises(AssignError, match="override 대상 중복"):
        build_plan(_frame(["A", "B"]), [_set(1)], override={1: (1, 1), 2: (1, 1)})


def test_override_out_of_range_rejected_in_build_plan():
    with pytest.raises(AssignError, match="override 범위"):
        build_plan(_frame(["A"]), [_set(1)], override={1: (99, -3)})


# ─── build_plan 상태 분류 ───

def test_apply_when_record_exists_and_no_conflict():
    plan = build_plan(_frame(["A", "B"]), [_set(1)])
    assert [i.status for i in plan.items] == [AssignStatus.APPLY] * 2
    assert plan.items[0].target.slot_code == "_1101"
    assert plan.items[0].set_index == 0
    assert plan.can_apply and len(plan.applicable) == 2


def test_ng_keeps_slot_empty_and_does_not_block():
    plan = build_plan(_frame([None, "B"]), [_set(1)])
    assert plan.items[0].status is AssignStatus.NG
    assert plan.can_apply


def test_no_record_is_reported_but_does_not_block():
    plan = build_plan(_frame(["A", "B", "C"]), [_set(1, slots=range(1, 3))])  # Slot 3 레코드 없음
    assert plan.items[2].status is AssignStatus.NO_RECORD
    assert plan.can_apply                       # 현장 결정: 레코드 있는 칸은 그대로 적용
    assert len(plan.applicable) == 2


def test_ng_on_missing_record_is_ng_not_no_record():
    plan = build_plan(_frame(["A", None]), [_set(1, slots=range(1, 2))])
    assert plan.items[1].status is AssignStatus.NG
    assert plan.can_apply


def test_unloaded_port_is_excluded_even_with_codes():
    codes = ["A"] * 12 + ["B"] * 12
    plan = build_plan(_frame(codes), [_set(1)])
    assert all(i.status is AssignStatus.EXCLUDED for i in plan.items[12:])
    # 프레임 내 중복(A×12)은 로드된 포트에서 판정
    assert all(i.status is AssignStatus.DUP_FRAME for i in plan.items[:12])


def test_same_qr_already_matched():
    ms = _set(1)
    ms.slots[0].qr_id = "A"
    plan = build_plan(_frame(["A", "B"]), [ms])
    assert plan.items[0].status is AssignStatus.SAME
    assert plan.items[1].status is AssignStatus.APPLY


def test_conflict_with_existing_different_qr():
    ms = _set(1)
    ms.slots[0].qr_id = "OLD"
    plan = build_plan(_frame(["A"]), [ms])
    assert plan.items[0].status is AssignStatus.CONFLICT
    assert "OLD" in plan.items[0].note
    assert plan.applicable == []
    assert not plan.can_apply  # 적용할 칸이 0개


def test_dup_in_frame_marks_both_cells():
    plan = build_plan(_frame(["A", "A", "B"]), [_set(1)])
    assert plan.items[0].status is plan.items[1].status is AssignStatus.DUP_FRAME
    assert "2" in plan.items[0].note and "1" in plan.items[1].note
    assert plan.items[2].status is AssignStatus.APPLY


def test_dup_with_qr_loaded_elsewhere():
    ms = _set(1)
    ms.slots[5].qr_id = "A"  # Slot 6 에 이미 A
    plan = build_plan(_frame(["A"]), [ms])
    assert plan.items[0].status is AssignStatus.DUP_LOADED
    assert "_1106" in plan.items[0].note


def test_dup_loaded_lists_every_location_across_sets():
    s1, s2 = _set(1, po="P1"), _set(2, po="P2")
    s1.slots[5].qr_id = "A"
    s2.slots[2].qr_id = "A"
    plan = build_plan(_frame(["A"]), [s1, s2])
    assert plan.items[0].status is AssignStatus.DUP_LOADED
    assert "_1106" in plan.items[0].note and "_1203" in plan.items[0].note


def test_multiple_sets_map_by_port():
    plan = build_plan(_frame(["A"] * 12 + ["B"] * 12), [_set(1, po="P1"), _set(2, po="P2")])
    assert plan.items[0].set_index == 0 and plan.items[12].set_index == 1
    assert plan.items[12].target.slot_code == "_1201"


def test_atx_filter_resolves_ambiguity():
    sets = [_set(1, atx=1), _set(1, atx=2)]
    with pytest.raises(AssignError, match="set_for_port"):
        build_plan(_frame(["A"]), sets)
    plan = build_plan(_frame(["A"]), sets, atx=2)
    assert plan.items[0].target.slot_code == "_2101"


def test_same_atx_port_in_two_sets_needs_set_for_port():
    sets = [_set(1, po="P1"), _set(1, po="P2")]  # 다른 PO, 같은 ATX1 Port1
    with pytest.raises(AssignError, match="P1.*P2|P2.*P1"):
        build_plan(_frame(["A"]), sets, atx=1)
    plan = build_plan(_frame(["A"]), sets, set_for_port={1: 1})
    assert plan.items[0].set_index == 1
    assert plan.items[0].target is sets[1].slots[0]
    # 선택되지 않은 세트에 있는 QR 도 "로드된 폴더 전체" 중복 검사에 포함된다 (§5)
    sets[0].slots[3].qr_id = "A"
    plan = build_plan(_frame(["A"]), sets, set_for_port={1: 1})
    assert plan.items[0].status is AssignStatus.DUP_LOADED
    assert "_1104" in plan.items[0].note


def test_dup_loaded_sees_other_atx_when_atx_filtered():
    sets = [_set(1, atx=1, po="P1"), _set(1, atx=2, po="P2")]
    sets[1].slots[5].qr_id = "A"
    plan = build_plan(_frame(["A"]), sets, atx=1)
    assert plan.items[0].status is AssignStatus.DUP_LOADED and "_2106" in plan.items[0].note


def test_unparseable_slot_code_raises_assign_error():
    ms = _set(1)
    ms.slots[0].slot_code = "bad"
    with pytest.raises(AssignError, match="슬롯 코드"):
        build_plan(_frame(["A"]), [ms])


def test_empty_frame_cannot_apply():
    plan = build_plan(_frame([]), [_set(1)])
    assert plan.items == [] and not plan.can_apply


def test_override_routes_cell_to_other_slot():
    plan = build_plan(_frame(["A"]), [_set(1)], override={1: (1, 12)})
    assert (plan.items[0].port, plan.items[0].slot) == (1, 12)
    assert plan.items[0].target.slot_code == "_1112"


def test_counts_cover_all_statuses():
    plan = build_plan(_frame(["A", None]), [_set(1)])
    counts = plan.counts()
    assert set(counts) == set(AssignStatus)
    assert counts[AssignStatus.APPLY] == 1 and counts[AssignStatus.NG] == 1


# ─── 실제 fixture × 6포트 더미 세트 ───

def test_full_fixture_against_six_ports():
    frame = parse_frame(FULL_RAW.read_bytes())
    plan = build_plan(frame, [_set(p, po=f"P{p}") for p in range(1, 7)])
    counts = plan.counts()
    assert counts[AssignStatus.APPLY] == 70
    assert counts[AssignStatus.NG] == 2
    assert [i.cell for i in plan.items if i.status is AssignStatus.NG] == [13, 14]
    assert plan.can_apply
    assert plan.items[12].port == 2 and plan.items[12].slot == 1
    assert plan.items[71].target.slot_code == "_1612"


def test_full_fixture_with_port6_unloaded():
    frame = parse_frame(FULL_RAW.read_bytes())
    plan = build_plan(frame, [_set(p) for p in range(1, 6)])
    counts = plan.counts()
    assert counts[AssignStatus.EXCLUDED] == 12
    assert counts[AssignStatus.APPLY] == 58
    assert plan.can_apply
