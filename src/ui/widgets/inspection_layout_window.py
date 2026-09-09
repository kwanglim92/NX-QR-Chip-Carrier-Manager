"""Inspection 레이아웃 보기 — MTC 실물 배치(ATX 2×2 · Port 상하 · Slot 4열×3행)로 등급을 한눈에.

배치
----
- ATX1 좌상 · ATX2 우상 · ATX3 좌하 · ATX4 우하
- ATX 안: Port2 위, Port1 아래(상하 배치). 각 Port 는 ATX Mode 슬롯 그리드와 같은 규칙
  (``slot_mapper.slot_to_grid``: 아래 행 1~4, 중간 5~8, 위 9~12 — Slot 1 = 좌하단)
- 셀: 배경 = 색 기준(등급 / Sweep 점수 / Frequency / Q), 글자 = 슬롯 코드 ``{ATX}{Port}{SS}``(예 1101,
  2112 — 폴더·Summary.csv 의 코드와 동일). 빈 슬롯 = 점선 회색.
  기준 캔틸레버 = 굵은 테두리, 로트로 내보낸 슬롯 = ``→`` 배지, 수동 지정 = ``*``
- 상호작용은 결과표와 동일: 클릭 선택 / 우클릭 메뉴 / 더블클릭 Sweep Explorer / 호버 툴팁
- 범례 버튼(산업용/연구용/재검사/불량) 클릭 = 그 등급만 표시(나머지는 빈 슬롯처럼), 다시 클릭 = 전체

비모달 창. 메인 표 선택과 양방향 동기화는 ``InspectionMixin`` 이 담당한다.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.inspection.templates import ALL_GRADE_KEYS, GRADE_NAMES
from src.core.slot_mapper import slot_to_grid
from src.ui.theme import ACCENT, BG, BG2, BG3, FG, FG2, GREEN, ORANGE, RED, TEAL

GRADE_COLORS: dict[str, str] = {"industrial": GREEN, "research": TEAL, "recheck": ORANGE, "reject": RED}
ATX_POSITIONS = {1: (0, 0), 2: (0, 1), 3: (1, 0), 4: (1, 1)}
PORTS = (1, 2)
SLOTS_PER_PORT = 12
COLOR_MODES = (("grade", "등급"), ("sweep", "Sweep 점수"), ("frequency", "Frequency"), ("q", "Q"))


def _lerp(c1: str, c2: str, t: float) -> QColor:
    a, b = QColor(c1), QColor(c2)
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def gradient_color(t: float) -> QColor:
    """0(빨강) → 0.5(주황) → 1(초록)."""
    return _lerp(RED, ORANGE, t * 2) if t < 0.5 else _lerp(ORANGE, GREEN, (t - 0.5) * 2)


class LayoutCell(QFrame):
    clicked = Signal(str)
    double_clicked = Signal(str)
    context_requested = Signal(str, object)

    def __init__(self, slot_num: int, parent=None, slot_code: str = ""):
        super().__init__(parent)
        self.slot_num = slot_num
        self.slot_code = slot_code or str(slot_num)   # 표시용 코드(예 '1101')
        self.code: str | None = None
        self._bg = QColor(BG2)
        self._selected = False
        self._is_ref = False
        self._hidden = False
        self.setMinimumSize(56, 34)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 1, 2, 1)
        lay.setSpacing(0)
        self.lbl = QLabel(self.slot_code)
        self.lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl)
        self.badge = QLabel("")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet("font-size: 9px;")
        lay.addWidget(self.badge)
        self.set_empty()

    def set_empty(self):
        self.code = None
        self._bg = QColor(BG2)
        self._is_ref = False
        self.lbl.setText(self.slot_code)
        self.badge.setText("")
        self.setToolTip(f"{self.slot_code} 빈 슬롯")
        self._restyle(empty=True)

    def set_state(self, code: str, bg: QColor, text: str, badge: str, tooltip: str,
                  is_ref: bool, dimmed: bool, hidden: bool = False):
        """hidden=True 면 코드만 흐리게 남기고 빈 슬롯처럼 그린다(범례 필터)."""
        self.code = code
        self._bg = QColor(bg)
        if dimmed:
            self._bg.setAlpha(60)
        self._is_ref = is_ref
        self._hidden = hidden
        self.lbl.setText(text.split("\n")[0] if hidden else text)
        self.badge.setText("" if hidden else badge)
        self.setToolTip(tooltip)
        self._restyle(empty=hidden)

    def set_selected(self, on: bool):
        self._selected = on
        self._restyle(empty=self.code is None or self._hidden)

    def _restyle(self, empty: bool):
        if empty:
            border = f"3px solid {ACCENT}" if (self._selected and self.code) else f"1px dashed {BG3}"
            bg = BG2
            fg = FG2
        else:
            border = f"3px solid {ACCENT}" if self._selected else (
                f"2px solid {FG}" if self._is_ref else f"1px solid {BG3}")
            bg = self._bg.name(QColor.HexArgb) if self._bg.alpha() < 255 else self._bg.name()
            fg = BG if self._bg.alpha() == 255 else FG2
        self.setStyleSheet(
            f"LayoutCell {{ background: {bg}; border: {border}; border-radius: 4px; }}"
            f"QLabel {{ color: {fg}; font-weight: bold; background: transparent; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.code:
            self.clicked.emit(self.code)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.code:
            self.double_clicked.emit(self.code)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self.code:
            self.context_requested.emit(self.code, event.globalPos())


class InspectionLayoutWindow(QWidget):
    cell_clicked = Signal(str)
    cell_double_clicked = Signal(str)
    cell_context_requested = Signal(str, object)
    closed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Inspection 레이아웃 보기")
        self.resize(760, 900)
        self.cells: dict[str, LayoutCell] = {}   # code → cell
        self._selected: str | None = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        head = QHBoxLayout()
        self.lbl_title = QLabel("-")
        self.lbl_title.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
        head.addWidget(self.lbl_title, 1)
        head.addWidget(QLabel("색 기준"))
        self.mode_combo = QComboBox()
        for key, name in COLOR_MODES:
            self.mode_combo.addItem(name, key)
        head.addWidget(self.mode_combo)
        root.addLayout(head)

        legend_row = QHBoxLayout()
        self.legend_buttons: dict[str, QPushButton] = {}
        self.legend_filter: str | None = None
        for key in ALL_GRADE_KEYS:
            b = QPushButton(f"■ {GRADE_NAMES[key]}")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(f"{GRADE_NAMES[key]}만 표시 (다시 클릭하면 전체)")
            color = GRADE_COLORS[key]
            b.setStyleSheet(
                f"QPushButton {{ color: {color}; background: transparent; border: 1px solid {BG3};"
                f" border-radius: 3px; padding: 2px 8px; }}"
                f"QPushButton:checked {{ background: {color}; color: {BG}; font-weight: bold; }}")
            b.clicked.connect(lambda _c=False, k=key: self._on_legend_clicked(k))
            self.legend_buttons[key] = b
            legend_row.addWidget(b)
        self.legend = QLabel("")
        self.legend.setStyleSheet(f"color: {FG2};")
        legend_row.addWidget(self.legend, 1)
        root.addLayout(legend_row)

        grid = QGridLayout()
        grid.setSpacing(10)
        for atx, (r, c) in ATX_POSITIONS.items():
            grid.addWidget(self._build_atx(atx), r, c)
        root.addLayout(grid, 1)

    def _build_atx(self, atx: int) -> QGroupBox:
        box = QGroupBox(f"ATX {atx}")
        hl = QVBoxLayout(box)
        hl.setSpacing(8)
        for port in reversed(PORTS):   # Port2 위, Port1 아래
            pw = QWidget()
            pl = QVBoxLayout(pw)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.setSpacing(2)
            title = QLabel(f"Port {port}")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet(f"color: {FG2};")
            pl.addWidget(title)
            g = QGridLayout()
            g.setSpacing(3)
            for slot in range(1, SLOTS_PER_PORT + 1):
                row, col = slot_to_grid(slot)
                cell = LayoutCell(slot, slot_code=f"{atx}{port}{slot:02d}")
                cell.clicked.connect(self.cell_clicked)
                cell.double_clicked.connect(self.cell_double_clicked)
                cell.context_requested.connect(self.cell_context_requested)
                g.addWidget(cell, row, col)
                self.cells[f"{atx}{port}{slot:02d}"] = cell
            pl.addLayout(g, 1)
            hl.addWidget(pw, 1)
        return box

    # ─── 데이터 ───

    def mode(self) -> str:
        return self.mode_combo.currentData() or "grade"

    def update_view(self, run, verdicts, ref_code: str | None, grouped: dict[str, str],
                    allowed_grades: set[str] | None = None) -> None:
        """verdicts 로 셀을 채운다. allowed_grades 밖의 등급은 흐리게."""
        title = f"런 {run.run_id}  ·  {len(verdicts)} 슬롯" if run is not None else "-"
        self.lbl_title.setText(title)
        by_code = {v.code: v for v in verdicts}
        mode = self.mode()
        lo = hi = None
        if mode in ("frequency", "q"):
            vals = [getattr(v.slot, mode) for v in verdicts if getattr(v.slot, mode) is not None]
            if vals:
                lo, hi = min(vals), max(vals)
        self._last_view = (run, verdicts, ref_code, grouped, allowed_grades)
        for code, cell in self.cells.items():
            v = by_code.get(code)
            if v is None:
                cell.set_empty()
                continue
            hidden = self.legend_filter is not None and v.grade != self.legend_filter
            s = v.slot
            if mode == "grade":
                bg = QColor(GRADE_COLORS.get(v.grade, FG2))
                text = code
            elif mode == "sweep":
                score = v.metrics.get("sweep_shape")
                bg = gradient_color(score / 100.0) if score is not None else QColor(BG3)
                text = f"{code}\n{score:.0f}" if score is not None else f"{code}\n-"
            else:
                val = getattr(s, mode)
                if val is None or lo is None or hi is None or hi == lo:
                    bg = QColor(BG3)
                else:
                    bg = gradient_color((val - lo) / (hi - lo))
                text = f"{code}\n{val:.0f}" if val is not None else f"{code}\n-"
            badge = ""
            if code in grouped:
                badge = f"→ {grouped[code]}"
            elif v.is_override:
                badge = "*"
            tip = (f"{run.cantilever_no(s)}  {v.grade_name}"
                   f"{'  (' + v.error_label + ')' if v.error_label else ''}\n"
                   f"Freq {s.frequency if s.frequency is not None else '-'} kHz · Q {s.q if s.q is not None else '-'}"
                   f" · A+B {s.a_plus_b if s.a_plus_b is not None else '-'} V\n"
                   f"Sweep {v.sweep.summary()} · Vision {v.vision.summary()}")
            dimmed = allowed_grades is not None and v.grade not in allowed_grades
            cell.set_state(code, bg, text, badge, tip, code == ref_code, dimmed, hidden)
        self._update_legend(mode, lo, hi)
        if self._selected:
            self.select(self._selected)

    def _on_legend_clicked(self, key: str):
        """범례 버튼: 그 등급만 표시. 같은 버튼을 다시 누르면 전체 표시."""
        self.legend_filter = None if self.legend_filter == key else key
        for k, b in self.legend_buttons.items():
            b.setChecked(k == self.legend_filter)
        if getattr(self, "_last_view", None):
            self.update_view(*self._last_view)

    def _update_legend(self, mode: str, lo, hi):
        if mode == "grade":
            self.legend.setText("굵은 테두리 = 기준 캔틸레버, → = 로트로 내보냄, * = 수동 지정")
        elif mode == "sweep":
            self.legend.setText(f'<span style="color:{RED}">■</span> 0  →  <span style="color:{ORANGE}">■</span> 50  →  '
                                f'<span style="color:{GREEN}">■</span> 100  (Sweep 형상 점수)')
        else:
            name = "Frequency (kHz)" if mode == "frequency" else "Q"
            rng = f"{lo:.0f} ~ {hi:.0f}" if lo is not None and hi is not None else "-"
            self.legend.setText(f'<span style="color:{RED}">■</span> 낮음  →  <span style="color:{GREEN}">■</span> 높음   {name} {rng}')

    def select(self, code: str | None):
        if self._selected and self._selected in self.cells:
            self.cells[self._selected].set_selected(False)
        self._selected = code
        if code and code in self.cells:
            self.cells[code].set_selected(True)

    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)
