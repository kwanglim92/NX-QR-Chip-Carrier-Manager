"""R5: 카세트 판독 검토 다이얼로그 — 요약·패널·차단 규칙·덮어쓰기·필터·결과."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.models import MeasurementSet, SlotData
from src.core.qr_reader.payload_parser import CellRead, ParsedFrame, parse_frame
from src.core.qr_reader.slot_assigner import AssignStatus, build_plan
from PySide6.QtWidgets import QGroupBox, QLabel

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
    titles = [b.title() for b in dlg.findChildren(QGroupBox)]
    assert any(t.startswith("Port 1 · ① P1") for t in titles)
    assert any(t == "Port 6 · 폴더 미로드" for t in titles)


def test_ng_and_excluded_cards_render(fixture_dialog):
    dlg, *_ = fixture_dialog
    assert dlg._cards[13]._code.text() == "미판독" and dlg._cards[13]._badge.text() == "NG"
    assert dlg._cards[61]._badge.text() == "제외"
    assert not dlg._cards[61].parent().isEnabled()      # 미로드 패널은 비활성(흐림)


def test_no_record_warns_but_does_not_block(qapp):
    sets = [_set(1, "P1", slots=range(1, 12))]           # Slot 12 레코드 없음
    codes = [f"C{i}" for i in range(12)]
    plan = build_plan(_frame(codes), sets)
    dlg = BatchReadReviewDialog(plan, sets)
    assert plan.counts()[AssignStatus.NO_RECORD] == 1
    assert dlg.btn_apply.isEnabled() and dlg.btn_apply.text() == "적용 (11)"
    assert "레코드 없음 1칸" in dlg._block_label.text() and "Port 1 · S12" in dlg._block_label.text()
    assert len(dlg.selected_items()) == 11
    dlg.close()


def test_panels_and_cells_follow_boat_layout(fixture_dialog):
    """패널은 보트 모양(2열×3행), 칸은 카세트 모양(4열×3행) — 판독 미리보기와 같은 배치(기본 270°, 개략)."""
    dlg, *_ = fixture_dialog
    assert dlg._panel_pos == {1: (0, 0), 2: (0, 1), 3: (1, 0), 4: (1, 1), 5: (2, 0), 6: (2, 1)}
    assert [dlg._cell_pos[c] for c in (1, 2, 3, 4)] == [(2, 0), (2, 1), (2, 2), (2, 3)]     # 셀 1~4 = 맨 아랫줄
    assert [dlg._cell_pos[c] for c in (9, 10, 11, 12)] == [(0, 0), (0, 1), (0, 2), (0, 3)]  # 셀 9~12 = 맨 윗줄
    assert dlg._cell_pos[13] == (2, 0)                                                   # 카세트마다 같은 상대 위치
    assert "회전 270°" in [w.text() for w in dlg.findChildren(QLabel) if "실물 배치" in w.text()][0]


def test_explicit_layout_with_real_regions_and_rotation(qapp):
    from src.core.qr_reader.boat_layout import build_layout, schematic_regions
    sets = [_set(p, f"P{p}") for p in range(1, 7)]
    plan = build_plan(_frame(["X"] * 72), sets)
    layout = build_layout(schematic_regions(72), 0, None, 72)     # 리더기 화상 그대로: 카세트 3열×2행, 셀 3열×4행
    dlg = BatchReadReviewDialog(plan, sets, layout=layout)
    assert not layout.schematic
    assert max(c for _r, c in dlg._panel_pos.values()) == 2 and max(r for r, _c in dlg._panel_pos.values()) == 1
    assert max(c for _r, c in dlg._cell_pos.values()) == 2 and max(r for r, _c in dlg._cell_pos.values()) == 3
    assert "리더기 서치 영역" in [w.text() for w in dlg.findChildren(QLabel) if "실물 배치" in w.text()][0]
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


def test_issues_only_filter_dims_normal_cells_without_hiding(fixture_dialog):
    dlg, *_ = fixture_dialog
    dlg.show()
    dlg.chk_issues_only.setChecked(True)
    assert dlg._cards[1].dimmed and not dlg._cards[1].isHidden()   # APPLY → 흐림(격자 위치 유지)
    assert dlg._cards[61].dimmed                                   # EXCLUDED → 흐림
    assert not dlg._cards[13].dimmed and dlg._cards[13]._badge.text() == "NG"   # NG → 강조 유지
    dlg.chk_issues_only.setChecked(False)
    assert not dlg._cards[1].dimmed and dlg._cards[1]._badge.text() == "적용"


def test_port_with_only_no_record_is_titled_loaded_not_missing(qapp):
    sets = [_set(1, "P1", slots=range(1, 2))]      # Slot 1 만 레코드
    plan = build_plan(_frame(["A"]), sets, override={1: (1, 5)})   # 셀 1 → Slot 5 (레코드 없음)
    dlg = BatchReadReviewDialog(plan, sets)
    titles = [b.title() for b in dlg.findChildren(QGroupBox)]
    assert titles == ["Port 1 · 레코드 없음"]
    assert dlg._cards[1].parent().isEnabled()
    dlg.close()


def test_read_count_excludes_unread_cells_in_unloaded_ports(qapp):
    sets = [_set(1, "P1")]
    codes = ["A"] * 12 + [None] * 3 + ["B"] * 9      # Port 2 미로드, 그중 3칸 미판독
    plan = build_plan(_frame(codes), sets)
    dlg = BatchReadReviewDialog(plan, sets)
    assert dlg._chip_labels["read"].text() == "21 / 24"
    assert dlg._cards[24]._badge.text() == "제외"
    assert "A" in dlg._cards[1].toolTip()
    dlg.close()


def test_rescan_signal(fixture_dialog):
    dlg, *_ = fixture_dialog
    fired = []
    dlg.rescan_requested.connect(lambda: fired.append(1))
    dlg.btn_rescan.click()
    assert fired == [1]
