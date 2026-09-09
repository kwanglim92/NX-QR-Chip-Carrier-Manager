"""Sweep Explorer 창 테스트 (offscreen, pyqtgraph 없으면 skip)."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyqtgraph")

from src.core.inspection.grading import grade_run  # noqa: E402
from src.core.inspection.mtc_parser import load_mtc_run  # noqa: E402
from src.core.inspection.reference import auto_reference  # noqa: E402
from src.core.inspection.templates import default_template  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def graded():
    run = load_mtc_run(FIXTURE)
    ref = auto_reference(run)
    return run, ref, {v.code: v for v in grade_run(run, default_template("AC160"), ref)}


def test_show_slot_fills_plots_and_table(qapp, graded):
    from src.ui.widgets.sweep_explorer_window import SweepExplorerWindow
    run, ref, by = graded
    w = SweepExplorerWindow()
    w.show_slot(by["1102"], run, ref)          # 잡음 다봉 슬롯
    assert w.slot_code == "1102"
    assert "20260909_1102" in w.windowTitle()
    assert w.table.rowCount() >= 2
    assert "MTC" in w.lbl_lines.text() and "peak" in w.lbl_lines.text() and "fit f0" in w.lbl_lines.text()
    assert len(w._ref_items) == 2 and not w._ref_items[0].isVisible()
    w.chk_ref.setChecked(True)
    assert w._ref_items[0].isVisible()
    # 피크 행 클릭 → X 범위가 그 피크 주변으로 좁아지고 강조 마커가 찍힌다
    before = w.p_bot.viewRange()[0]
    w.zoom_to_peak(0)
    after = w.p_bot.viewRange()[0]
    assert (after[1] - after[0]) < (before[1] - before[0])
    assert len(w._highlight.data) == 1
    w.reset_zoom()
    assert len(w._highlight.data) == 0
    w.close()


def test_show_slot_without_sweep(qapp, graded):
    from src.ui.widgets.sweep_explorer_window import SweepExplorerWindow
    run, ref, by = graded
    w = SweepExplorerWindow()
    w.show_slot(by["1111"], run, None)          # 줌인 sweep 없음, ZoomOut 만
    assert w.table.rowCount() == 0
    assert "peak" not in w.lbl_lines.text()
    assert w._ref_items == []
    closed = []
    w.closed.connect(closed.append)
    w.close()
    assert closed == [w]


def test_crosshair_snaps_to_nearest_point(qapp, graded):
    from src.ui.widgets.sweep_explorer_window import SweepExplorerWindow
    run, ref, by = graded
    w = SweepExplorerWindow()
    w.resize(900, 600)
    w.show()
    qapp.processEvents()
    w.show_slot(by["1101"], run, ref)
    qapp.processEvents()
    f, a = w._sweep_pts
    # 데이터 좌표 → 씬 좌표로 변환해 마우스 이동을 흉내
    scene_pos = w.p_bot.vb.mapViewToScene(pg_point(f[50] + 0.001, a[50]))
    assert w.cross_bot.move(scene_pos)
    assert w.cross_bot.v.value() == pytest.approx(f[50])
    assert f"{f[50]:.2f} kHz" in w.cross_bot.label.textItem.toPlainText()
    w.close()


def pg_point(x, y):
    from PySide6.QtCore import QPointF
    return QPointF(x, y)
