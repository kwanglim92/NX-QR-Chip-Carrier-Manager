"""Inspection 레이아웃 보기 창 테스트 (offscreen)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.inspection.grading import grade_run
from src.core.inspection.mtc_parser import load_mtc_run
from src.core.inspection.reference import auto_reference
from src.core.inspection.templates import default_template
from src.core.slot_mapper import slot_to_grid

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def graded():
    run = load_mtc_run(FIXTURE)
    ref = auto_reference(run)
    return run, ref, grade_run(run, default_template("AC160"), ref)


def test_cells_cover_4_atx_2_port_12_slots(qapp):
    from src.ui.widgets.inspection_layout_window import InspectionLayoutWindow, ATX_POSITIONS
    w = InspectionLayoutWindow()
    assert len(w.cells) == 4 * 2 * 12
    assert set(w.cells) >= {"1101", "1212", "3201", "4112"}
    assert ATX_POSITIONS == {1: (0, 0), 2: (0, 1), 3: (1, 0), 4: (1, 1)}
    # Slot 1 = 좌하단 (ATX Mode 그리드 규칙)
    assert slot_to_grid(1) == (2, 0) and slot_to_grid(12) == (0, 3)
    w.close()


def test_update_view_grade_mode(qapp, graded):
    from src.ui.widgets.inspection_layout_window import InspectionLayoutWindow, GRADE_COLORS
    from PySide6.QtGui import QColor
    run, ref, verdicts = graded
    w = InspectionLayoutWindow()
    w.update_view(run, verdicts, ref.code, {"1102": "P2401002"}, None)
    assert "20260909" in w.lbl_title.text() and "7 슬롯" in w.lbl_title.text()
    c = w.cells["1101"]
    assert c.code == "1101" and c._is_ref and c._bg == QColor(GRADE_COLORS["industrial"])
    assert w.cells["1102"].badge.text() == "→ P2401002"
    assert w.cells["3212"]._bg == QColor(GRADE_COLORS["reject"])
    assert w.cells["2101"].code is None and w.cells["2101"].toolTip() == "빈 슬롯"
    assert "산업용" in w.cells["1101"].toolTip() and "Sweep score" in w.cells["1101"].toolTip()
    # 필터 밖 등급은 흐리게(알파)
    w.update_view(run, verdicts, ref.code, {}, {"industrial"})
    assert w.cells["3212"]._bg.alpha() < 255 and w.cells["1101"]._bg.alpha() == 255
    w.close()


def test_color_modes_and_selection(qapp, graded):
    from src.ui.widgets.inspection_layout_window import InspectionLayoutWindow
    run, ref, verdicts = graded
    w = InspectionLayoutWindow()
    w.mode_combo.setCurrentIndex(1)                 # Sweep 점수
    w.update_view(run, verdicts, ref.code, {}, None)
    assert w.cells["1101"].lbl.text().startswith("1\n")
    assert "Sweep" in w.legend.text()
    w.mode_combo.setCurrentIndex(2)                 # Frequency
    w.update_view(run, verdicts, ref.code, {}, None)
    assert "Frequency" in w.legend.text()
    assert w.cells["1111"].lbl.text() == "11\n-"    # sweep 없음
    # 선택 표시
    w.select("3212")
    assert w.cells["3212"]._selected
    w.select("1101")
    assert not w.cells["3212"]._selected and w.cells["1101"]._selected
    # 클릭 시그널
    got = []
    w.cell_clicked.connect(got.append)
    w.cells["1101"].clicked.emit("1101")
    assert got == ["1101"]
    w.close()
