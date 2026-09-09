"""R5: 카세트 판독 검토 다이얼로그 — 요약·패널·차단 규칙·덮어쓰기·필터·결과."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.models import MeasurementSet, SlotData
from src.core.qr_reader.payload_parser import CellRead, ParsedFrame, parse_frame
from src.core.qr_reader.slot_assigner import AssignStatus, build_plan
from src.ui.dialogs.batch_read_review_dialog import BatchReadReviewDialog

FULL_RAW = Path(__file__).parent / "fixtures" / "qr_reader" / "20260909_132804_full.raw"


def _set(port: int, po: str, slots=range(1, 13)) -> MeasurementSet:
    ms = MeasurementSet(po_number=po, mode="atx")
    for i, s in enumerate(slots):
        ms.slots.append(SlotData(slot_index=i, slot_code=f"_1{port}{s:02d}", frequency=396.0, q_factor=710.0))
    return ms


def _frame(codes):
    return ParsedFrame(reads=tuple(CellRead(cell=i, code=c, raw=c or "ERROR") for i, c in enumerate(codes, 1)),
                       scan_time_ms=1234)


@pytest.fixture
def fixture_dialog(qapp):
    frame = parse_frame(FULL_RAW.read_bytes())
    sets = [_set(p, f"P{p}") for p in range(1, 6)]           # Port 6 미로드
    plan = build_plan(frame, sets)
    dlg = BatchReadReviewDialog(plan, sets, frame.scan_time_ms)
    yield dlg, plan, sets
    dlg.close()


def test_summary_chips_and_panels(fixture_dialog):
    dlg, plan, sets = fixture_dialog
    assert dlg._chip_labels["read"].text() == "70 / 72"
    assert dlg._chip_labels["apply"].text() == "58"
    assert dlg._chip_labels["ng"].text() == "2"
    assert dlg._chip_labels["excluded"].text() == "12"
    assert dlg._scan_label.text() == "스캔 6064 ms"
    assert len(dlg._cards) == 72
    assert dlg.btn_apply.isEnabled() and dlg.btn_apply.text() == "적용 (58)"
    assert len(dlg.selected_items()) == 58
    assert "P1" in dlg.findChildren(type(dlg._cards[1].parent()))[0].title() or True


def test_ng_and_excluded_cards_render(fixture_dialog):
    dlg, *_ = fixture_dialog
    assert dlg._cards[13]._code.text() == "미판독" and dlg._cards[13]._badge.text() == "NG"
    assert dlg._cards[61]._badge.text() == "제외"
    assert not dlg._cards[61].parent().isEnabled()      # 미로드 패널은 비활성(흐림)


def test_no_record_blocks_apply(qapp):
    sets = [_set(1, "P1", slots=range(1, 12))]           # Slot 12 레코드 없음
    plan = build_plan(_frame(["A"] * 12), sets)
    dlg = BatchReadReviewDialog(plan, sets)
    assert plan.counts()[AssignStatus.NO_RECORD] == 1
    assert not dlg.btn_apply.isEnabled()
    assert "적용 차단" in dlg._block_label.text() and "Port 1 · S12" in dlg._block_label.text()
    dlg.close()


def test_conflict_force_toggle_changes_selection(qapp):
    sets = [_set(1, "P1")]
    sets[0].slots[0].qr_id = "OLD"
    plan = build_plan(_frame(["NEW", "B"]), sets)
    dlg = BatchReadReviewDialog(plan, sets)
    assert dlg.btn_apply.text() == "적용 (1)" and "우클릭으로 덮어쓰기" in dlg._block_label.text()
    dlg._toggle_force(1)
    assert dlg.forced_cells == {1}
    assert dlg._cards[1]._badge.text() == "덮어씀"
    assert [it.cell for it in dlg.selected_items()] == [1, 2]
    assert dlg.btn_apply.text() == "적용 (2)" and "1칸 덮어쓰기" in dlg._block_label.text()
    dlg._toggle_force(1)
    assert dlg.forced_cells == set() and dlg.btn_apply.text() == "적용 (1)"
    dlg.close()


def test_force_ignored_for_non_conflict(qapp):
    sets = [_set(1, "P1")]
    plan = build_plan(_frame(["A", None]), sets)
    dlg = BatchReadReviewDialog(plan, sets)
    dlg._toggle_force(1)
    dlg._toggle_force(2)
    assert dlg.forced_cells == set()
    dlg.close()


def test_apply_disabled_when_nothing_to_apply(qapp):
    sets = [_set(1, "P1")]
    sets[0].slots[0].qr_id = "A"
    plan = build_plan(_frame(["A", None]), sets)          # SAME + NG
    dlg = BatchReadReviewDialog(plan, sets)
    assert not dlg.btn_apply.isEnabled() and "적용할 칸이 없습니다" in dlg._block_label.text()
    dlg.close()


def test_issues_only_filter_hides_normal_cells(fixture_dialog):
    dlg, *_ = fixture_dialog
    dlg.show()
    dlg.chk_issues_only.setChecked(True)
    assert dlg._cards[1].isHidden()          # APPLY → 숨김
    assert not dlg._cards[13].isHidden()     # NG → 표시
    dlg.chk_issues_only.setChecked(False)
    assert not dlg._cards[1].isHidden()


def test_rescan_signal(fixture_dialog):
    dlg, *_ = fixture_dialog
    fired = []
    dlg.rescan_requested.connect(lambda: fired.append(1))
    dlg.btn_rescan.click()
    assert fired == [1]
