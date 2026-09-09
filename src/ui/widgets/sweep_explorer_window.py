"""Sweep Explorer — sweep 판정 차트 더블클릭 시 열리는 비모달 인터랙티브 창 (pyqtgraph, SKILL 03).

구성
----
- 위: ZoomOut(200~400 kHz) 광대역 — 부피크 위치, 공진 세로선
- 아래: 줌인 상세 — 측정 곡선·Lorentzian 피팅·피크 ▽·Set Point·공진 세로선 3종
  (MTC Frequency = 주황, 측정 최대 피크 = 빨강, 피팅 f0 = 청록)
- 두 플롯 모두 크로스헤어 + 최근접 점 좌표 라벨, 휠 확대·드래그 이동, 우클릭 메뉴(auto range)
- 오른쪽: 피크 목록 표(주파수·진폭·prominence·FWHM·Q 추정) — 행 클릭 → 그 피크로 확대·강조
- 옵션: 기준 슬롯 곡선 오버레이, 선택 슬롯 따라가기(메인 표 선택 시 갱신), Reset zoom

읽기 전용(판정 값은 바꾸지 않음). 여러 창을 동시에 열 수 있다.
"""
from __future__ import annotations

import bisect
import os

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

import pyqtgraph as pg  # noqa: E402
from PySide6.QtCore import Qt, Signal  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.inspection.sweep_shape import lorentzian_curve, peak_details, read_sweep_txt  # noqa: E402
from src.ui.theme import ACCENT, BG, BG2, BG3, FG, FG2, ORANGE, PURPLE, RED, TEAL  # noqa: E402

PEAK_COLUMNS = ["#", "Freq (kHz)", "Amp (nm)", "Prom (nm)", "FWHM (kHz)", "Q est."]


def _fmt(v, nd=2) -> str:
    return "-" if v is None else f"{v:.{nd}f}"


class _CrossHair:
    """플롯 하나에 붙는 크로스헤어 + 최근접 데이터 라벨."""

    def __init__(self, plot: pg.PlotItem):
        self.plot = plot
        self.xs: list[float] = []
        self.ys: list[float] = []
        pen = pg.mkPen(FG2, width=1, style=Qt.DashLine)
        self.v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self.h = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self.label = pg.TextItem(color=FG, anchor=(0, 1), fill=pg.mkBrush(BG2), border=pg.mkPen(BG3))
        for item in (self.v, self.h, self.label):
            item.setZValue(50)
            plot.addItem(item, ignoreBounds=True)
        self.set_visible(False)

    def set_data(self, xs: list[float], ys: list[float]):
        self.xs, self.ys = list(xs), list(ys)

    def set_visible(self, on: bool):
        for item in (self.v, self.h, self.label):
            item.setVisible(on)

    def move(self, scene_pos) -> bool:
        if not self.xs or not self.plot.sceneBoundingRect().contains(scene_pos):
            self.set_visible(False)
            return False
        p = self.plot.vb.mapSceneToView(scene_pos)
        i = bisect.bisect_left(self.xs, p.x())
        if i >= len(self.xs):
            i = len(self.xs) - 1
        if i > 0 and abs(self.xs[i - 1] - p.x()) < abs(self.xs[i] - p.x()):
            i -= 1
        x, y = self.xs[i], self.ys[i]
        self.v.setPos(x)
        self.h.setPos(y)
        self.label.setText(f"{x:.2f} kHz\n{y:.2f} nm")
        self.label.setPos(x, y)
        self.set_visible(True)
        return True


class SweepExplorerWindow(QWidget):
    closed = Signal(object)   # self

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Sweep Explorer")
        self.resize(1100, 720)
        self.slot_code: str | None = None
        self._peaks: list[dict] = []
        self._zoom_pts: tuple[list[float], list[float]] = ([], [])
        self._sweep_pts: tuple[list[float], list[float]] = ([], [])
        self._ref_items: list = []
        self._build()

    # ─── 빌드 ───

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.lbl_title = QLabel("-")
        self.lbl_title.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
        head.addWidget(self.lbl_title, 1)
        self.chk_follow = QCheckBox("선택 슬롯 따라가기")
        self.chk_follow.setChecked(True)
        head.addWidget(self.chk_follow)
        self.chk_ref = QCheckBox("기준 슬롯 오버레이")
        self.chk_ref.toggled.connect(self._apply_ref_visibility)
        head.addWidget(self.chk_ref)
        self.btn_reset = QPushButton("Reset zoom")
        self.btn_reset.clicked.connect(self.reset_zoom)
        head.addWidget(self.btn_reset)
        root.addLayout(head)

        self.lbl_summary = QLabel("-")
        self.lbl_summary.setStyleSheet(f"color: {FG2};")
        self.lbl_summary.setWordWrap(True)
        root.addWidget(self.lbl_summary)

        split = QSplitter(Qt.Horizontal)
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground(BG)
        self.p_top = self.glw.addPlot(row=0, col=0, title="ZoomOut (광대역)")
        self.p_bot = self.glw.addPlot(row=1, col=0, title="Zoom-in (상세)")
        self.glw.ci.layout.setRowStretchFactor(0, 2)
        self.glw.ci.layout.setRowStretchFactor(1, 3)
        for plot in (self.p_top, self.p_bot):
            self._style_plot(plot)
        self.legend_bot = self.p_bot.addLegend(offset=(10, 10), labelTextColor=FG, brush=pg.mkBrush(BG2))
        self.legend_top = self.p_top.addLegend(offset=(10, 10), labelTextColor=FG, brush=pg.mkBrush(BG2))
        self.cross_top = _CrossHair(self.p_top)
        self.cross_bot = _CrossHair(self.p_bot)
        self.glw.scene().sigMouseMoved.connect(self._on_mouse_moved)
        split.addWidget(self.glw)

        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("검출 피크 (행 클릭 → 확대)"))
        self.table = QTableWidget(0, len(PEAK_COLUMNS))
        self.table.setHorizontalHeaderLabels(PEAK_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_peak_selected)
        sl.addWidget(self.table, 1)
        self.lbl_lines = QLabel("")
        self.lbl_lines.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        self.lbl_lines.setWordWrap(True)
        sl.addWidget(self.lbl_lines)
        split.addWidget(side)
        side.setMinimumWidth(380)
        split.setSizes([700, 400])
        root.addWidget(split, 1)

    @staticmethod
    def _style_plot(plot: pg.PlotItem):
        plot.showGrid(x=True, y=True, alpha=0.25)
        for name in ("bottom", "left"):
            ax = plot.getAxis(name)
            ax.setPen(pg.mkPen(BG3))
            ax.setTextPen(pg.mkPen(FG2))
        plot.setLabel("bottom", "kHz", color=FG2)
        plot.setLabel("left", "nm", color=FG2)
        plot.titleLabel.setAttr("color", FG2)

    # ─── 데이터 ───

    def show_slot(self, verdict, run, ref_slot=None) -> None:
        """SlotVerdict 를 표시. run 은 CantileverNo 표기용, ref_slot 은 오버레이용(선택)."""
        s = verdict.slot
        self.slot_code = s.code
        self.setWindowTitle(f"Sweep Explorer — {run.cantilever_no(s)}")
        self.lbl_title.setText(
            f"{run.cantilever_no(s)}   ATX{s.atx} Port{s.port} Slot{s.slot}   등급 {verdict.grade_name}"
            f"{'  (' + verdict.error_label + ')' if verdict.error_label else ''}")
        shape = verdict.sweep
        self.lbl_summary.setText(
            f"Sweep {shape.summary()}   ·   MTC Frequency {_fmt(s.frequency)} kHz, Q {_fmt(s.q)}, "
            f"Drive {_fmt(s.drive)} %, Set Point {_fmt(s.set_point)} nm")

        self._sweep_pts = read_sweep_txt(s.sweep_txt)
        self._zoom_pts = read_sweep_txt(s.zoom_txt)
        ref_sweep = read_sweep_txt(ref_slot.sweep_txt) if ref_slot is not None else ([], [])
        ref_zoom = read_sweep_txt(ref_slot.zoom_txt) if ref_slot is not None else ([], [])

        for plot, legend in ((self.p_top, self.legend_top), (self.p_bot, self.legend_bot)):
            plot.clear()
            legend.clear()
        self._ref_items = []
        # clear() 가 크로스헤어도 지우므로 다시 생성
        self.cross_top = _CrossHair(self.p_top)
        self.cross_bot = _CrossHair(self.p_bot)

        # ── ZoomOut ──
        zf, za = self._zoom_pts
        self.cross_top.set_data(zf, za)
        if zf:
            if ref_zoom[0]:
                self._ref_items.append(self.p_top.plot(
                    ref_zoom[0], ref_zoom[1], pen=pg.mkPen(PURPLE, width=1), name="reference"))
            self.p_top.plot(zf, za, pen=pg.mkPen(ACCENT, width=1.5), name="ZoomOut")
            if shape.available and shape.side_peak_freq is not None and shape.side_peak_ratio is not None \
                    and shape.side_peak_ratio > 0.5:
                self.p_top.addItem(pg.InfiniteLine(
                    pos=shape.side_peak_freq, angle=90, pen=pg.mkPen(ORANGE, style=Qt.DotLine),
                    label=f"side {shape.side_peak_ratio:.2f}×", labelOpts={"color": ORANGE, "position": 0.9}))
        else:
            self.p_top.addItem(pg.TextItem("no ZoomOut data", color=FG2))

        # ── Zoom-in ──
        f, a = self._sweep_pts
        self.cross_bot.set_data(f, a)
        self._peaks = peak_details(f, a) if f else []
        if f:
            if ref_sweep[0]:
                self._ref_items.append(self.p_bot.plot(
                    ref_sweep[0], ref_sweep[1], pen=pg.mkPen(PURPLE, width=1), name="reference"))
            self.p_bot.plot(f, a, pen=pg.mkPen(ACCENT, width=2), name="measured")
            if shape.fit_params:
                self.p_bot.plot(f, lorentzian_curve(f, shape.fit_params),
                                pen=pg.mkPen(TEAL, width=1, style=Qt.DashLine),
                                name=f"Lorentz R²={shape.fit_r2:.2f}")
            if self._peaks:
                self.p_bot.addItem(pg.ScatterPlotItem(
                    [d["freq"] for d in self._peaks], [d["amp"] for d in self._peaks],
                    symbol="t", size=12, pen=pg.mkPen(RED, width=1.5), brush=pg.mkBrush(None), name="peaks"))
            self._highlight = pg.ScatterPlotItem([], [], symbol="o", size=18,
                                                 pen=pg.mkPen(ORANGE, width=2), brush=pg.mkBrush(None))
            self._highlight.setZValue(40)
            self.p_bot.addItem(self._highlight)
            if s.set_point is not None:
                self.p_bot.addItem(pg.InfiniteLine(pos=s.set_point, angle=0, pen=pg.mkPen(RED, width=1)))
        else:
            self.p_bot.addItem(pg.TextItem("no sweep data", color=FG2))

        # 공진 주파수 세로선 3종 (두 플롯 모두)
        lines = []
        if s.frequency is not None:
            lines.append((s.frequency, ORANGE, "MTC"))
        if shape.available and shape.peak_freq is not None:
            lines.append((shape.peak_freq, RED, "peak"))
        if shape.fit_params:
            lines.append((shape.fit_params["f0"], TEAL, "fit f0"))
        for i, (pos, color, name) in enumerate(lines):
            for plot in (self.p_top, self.p_bot):
                plot.addItem(pg.InfiniteLine(
                    pos=pos, angle=90, pen=pg.mkPen(color, width=1, style=Qt.DashLine),
                    label=f"{name} {pos:.2f}", labelOpts={"color": color, "position": 0.95 - 0.08 * i}))
        self.lbl_lines.setText("공진 세로선:  " + "   ".join(f"{n} = {p:.2f} kHz" for p, _c, n in lines))

        self._fill_peak_table()
        self._apply_ref_visibility(self.chk_ref.isChecked())
        self.reset_zoom()

    def _fill_peak_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._peaks))
        for r, d in enumerate(self._peaks):
            vals = [str(r + 1), _fmt(d["freq"]), _fmt(d["amp"]), _fmt(d["prominence"]),
                    _fmt(d["fwhm"], 3), _fmt(d["q_est"], 0)]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, it)
        self.table.blockSignals(False)

    def _apply_ref_visibility(self, on: bool):
        for item in self._ref_items:
            item.setVisible(bool(on))

    def reset_zoom(self):
        for plot in (self.p_top, self.p_bot):
            plot.enableAutoRange()
            plot.autoRange()
        if hasattr(self, "_highlight"):
            self._highlight.setData([], [])
        self.table.clearSelection()

    # ─── 이벤트 ───

    def _on_mouse_moved(self, pos):
        if not self.cross_bot.move(pos):
            self.cross_top.move(pos)
        else:
            self.cross_top.set_visible(False)

    def _on_peak_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows or not self._peaks:
            return
        d = self._peaks[rows[0].row()]
        span = max((d["fwhm"] or 0.0) * 3.0, 0.3)
        self.p_bot.setXRange(d["freq"] - span, d["freq"] + span, padding=0)
        f, a = self._sweep_pts
        lo = bisect.bisect_left(f, d["freq"] - span)
        hi = bisect.bisect_right(f, d["freq"] + span)
        seg = a[lo:hi] or a
        self.p_bot.setYRange(min(seg) * 0.9, max(seg) * 1.1, padding=0)
        self._highlight.setData([d["freq"]], [d["amp"]])

    def zoom_to_peak(self, row: int):
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)

    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)
