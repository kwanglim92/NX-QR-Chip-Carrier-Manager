"""Inspection 모드 페이지 — ATX Classification 도구 스크린샷의 3열 레이아웃(앱 테마).

뷰 전용: 위젯을 만들고 표/폼을 채우는 헬퍼만 제공한다. 이벤트·상태는
``InspectionMixin`` 이 담당한다.

좌열: Path/Open · 결과표(ATX·Port·Slot·Grade·Error·No) · 등급 필터 + Total/Save/Run ·
      Fail Item(s) 판정식 · Threshold(Tip ID, 등급 탭별 항목 폼, Save)
중열: Vision 이미지 · Reference Cantilever · Info · Grouping
우열: FreqSweep 이미지 · ZoomOut 이미지 · sweep 판정 차트(In/Out)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.inspection.lot_builder import LOT_SIZES
from src.core.inspection.templates import (
    GRADES,
    GRADE_KEYS,
    GRADE_NAMES,
    ITEM_BY_KEY,
    ITEM_CATALOG,
    ITEM_KEYS,
    REJECT_KEY,
)
from src.ui.theme import ACCENT, BG, FG2, GREEN, ORANGE, RED, TEAL
from src.ui.widgets.image_viewer import ImageViewer
from src.ui.widgets.sweep_verdict_chart import SweepVerdictChart

TABLE_COLUMNS = ["ATX", "Port", "Slot", "Grade", "Error", "No"]
GRADE_COLORS: dict[str, str] = {
    "industrial": GREEN, "research": TEAL, "recheck": ORANGE, REJECT_KEY: RED,
}
INFO_ROW1 = ["Tip X (pxl)", "Tip Y (pxl)", "RefX - X (um)", "RefY - Y (um)", "Freq (kHz)", "Sweep Score"]
INFO_ROW2 = ["Set Pt (nm)", "Drive (%)", "Q", "A+B (V)", "A-B (V)", "C-D (V)", "Angle (°)", "Match (%)"]


def _ro_edit(width: int = 90) -> QLineEdit:
    e = QLineEdit()
    e.setReadOnly(True)
    e.setAlignment(Qt.AlignRight)
    e.setFixedWidth(width)
    return e


def _spin(lo: float = -1e6, hi: float = 1e6, decimals: int = 2, width: int = 80) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setFixedWidth(width)
    s.setButtonSymbols(QDoubleSpinBox.NoButtons)
    return s


def _scroll(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QScrollArea.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


class InspectionPage(QWidget):
    row_selected = Signal(str)           # slot code
    context_requested = Signal(str, object)   # (code, QPoint global)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.item_widgets: dict[str, dict[str, dict]] = {}
        self._codes: list[str] = []
        self._build()

    # ─── 빌드 ───

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # 상단: Path + Open  ...  타이틀 + Run
        top = QHBoxLayout()
        top.addWidget(QLabel("Path"))
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("MTC 런 폴더(예: 20260909)를 선택하세요")
        top.addWidget(self.path_edit, 1)
        self.btn_open = QPushButton("Open...")
        top.addWidget(self.btn_open)
        top.addSpacing(16)
        title = QLabel("MTC Inspection")
        title.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 14px;")
        top.addWidget(title)
        self.btn_run_top = QPushButton("Run...")
        self.btn_run_top.setProperty("accent", "true")
        self.btn_run_top.setToolTip("현재 템플릿으로 전체 슬롯을 다시 판정합니다")
        top.addWidget(self.btn_run_top)
        root.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(_scroll(self._build_left()))
        split.addWidget(_scroll(self._build_middle()))
        split.addWidget(_scroll(self._build_right()))
        split.setSizes([500, 620, 620])
        root.addWidget(split, 1)

    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(6)

        # 결과표
        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.setMinimumHeight(260)
        hdr = self.table.horizontalHeader()
        for i in range(len(TABLE_COLUMNS) - 1):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(len(TABLE_COLUMNS) - 1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_table_selection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context)
        lay.addWidget(self.table, 1)

        # 필터 + Total/Save/Run
        filt = QHBoxLayout()
        self.chk_grade: dict[str, QCheckBox] = {}
        for key in GRADE_KEYS + (REJECT_KEY,):
            chk = QCheckBox(GRADE_NAMES[key])
            chk.setChecked(True)
            chk.setStyleSheet(f"QCheckBox {{ color: {GRADE_COLORS[key]}; }}")
            self.chk_grade[key] = chk
            filt.addWidget(chk)
        filt.addStretch()
        lay.addLayout(filt)

        row2 = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0")
        row2.addWidget(self.lbl_total)
        self.lbl_counts = QLabel("")
        self.lbl_counts.setStyleSheet(f"color: {FG2};")
        row2.addWidget(self.lbl_counts, 1)
        self.btn_save = QPushButton("Save")
        self.btn_save.setToolTip("검사 리포트 CSV 저장")
        row2.addWidget(self.btn_save)
        self.btn_run = QPushButton("Run")
        self.btn_run.setProperty("accent", "true")
        row2.addWidget(self.btn_run)
        lay.addLayout(row2)

        # Fail Item(s)
        fail_grp = QGroupBox("Fail Item(s)")
        fl = QHBoxLayout(fail_grp)
        self.fail_combo = QComboBox()
        self.fail_combo.setMinimumWidth(140)
        fl.addWidget(self.fail_combo)
        self.lbl_formula = QLabel("-")
        self.lbl_formula.setStyleSheet(f"color: {RED}; font-weight: bold;")
        fl.addWidget(self.lbl_formula, 1)
        lay.addWidget(fail_grp)

        # Threshold
        thr = QGroupBox("Threshold")
        tl = QVBoxLayout(thr)
        tip_row = QHBoxLayout()
        tip_row.addWidget(QLabel("Tip ID"))
        self.tip_combo = QComboBox()
        self.tip_combo.setMinimumWidth(140)
        tip_row.addWidget(self.tip_combo, 1)
        self.btn_new_tpl = QPushButton("New...")
        tip_row.addWidget(self.btn_new_tpl)
        self.btn_del_tpl = QPushButton("삭제")
        tip_row.addWidget(self.btn_del_tpl)
        tl.addLayout(tip_row)

        upp_row = QHBoxLayout()
        upp_row.addWidget(QLabel("um / pixel"))
        self.um_spin = _spin(0.0001, 100.0, 4, 90)
        upp_row.addWidget(self.um_spin)
        upp_row.addWidget(QLabel("(X/Y Offset 환산, 기본 0.345)"))
        upp_row.addStretch()
        tl.addLayout(upp_row)

        self.grade_tabs = QTabWidget()
        for key, name in GRADES:
            self.grade_tabs.addTab(self._build_grade_form(key), name)
        tl.addWidget(self.grade_tabs)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.btn_save_tpl = QPushButton("Save")
        self.btn_save_tpl.setToolTip("템플릿 저장 (산업용 Frequency/Q 는 Spec Limits 에 동기화)")
        save_row.addWidget(self.btn_save_tpl)
        tl.addLayout(save_row)
        lay.addWidget(thr)
        return w

    def _build_grade_form(self, grade_key: str) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.item_widgets[grade_key] = {}
        for row, spec in enumerate(ITEM_CATALOG):
            chk = QCheckBox(spec.label)
            grid.addWidget(chk, row, 0)
            rec = {"chk": chk, "a": None, "b": None}
            if spec.kind == "offset":
                lbl = "Degree" if spec.key == "angle_offset_deg" else "Offset"
                grid.addWidget(QLabel(lbl), row, 1, alignment=Qt.AlignRight)
                rec["a"] = _spin(0, 1e6, 3)
                grid.addWidget(rec["a"], row, 2)
            elif spec.kind == "range":
                grid.addWidget(QLabel("Min"), row, 1, alignment=Qt.AlignRight)
                rec["a"] = _spin(-1e6, 1e6, 2)
                grid.addWidget(rec["a"], row, 2)
                grid.addWidget(QLabel("Max"), row, 3, alignment=Qt.AlignRight)
                rec["b"] = _spin(-1e6, 1e6, 2)
                grid.addWidget(rec["b"], row, 4)
            else:
                grid.addWidget(QLabel("Min"), row, 1, alignment=Qt.AlignRight)
                rec["a"] = _spin(0, 1e6, 1)
                grid.addWidget(rec["a"], row, 2)
            self.item_widgets[grade_key][spec.key] = rec
        grid.setColumnStretch(5, 1)
        return w

    def _build_middle(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(6)

        self.vision_viewer = ImageViewer()
        self.vision_viewer.setMinimumHeight(240)
        lay.addWidget(self.vision_viewer, 2)
        vrow = QHBoxLayout()
        self.lbl_vision_path = QLabel("-")
        self.lbl_vision_path.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        self.lbl_vision_path.setWordWrap(True)
        vrow.addWidget(self.lbl_vision_path, 1)
        self.btn_vision_toggle = QPushButton("putBack")
        self.btn_vision_toggle.setCheckable(True)
        self.btn_vision_toggle.setToolTip("pickUp ↔ putBack 이미지 전환")
        vrow.addWidget(self.btn_vision_toggle)
        lay.addLayout(vrow)

        # Reference Cantilever
        self.ref_group = QGroupBox("Reference Cantilever (-)")
        rl = QGridLayout(self.ref_group)
        self.ref_fields: dict[str, QLineEdit] = {}
        labels = [("X (pxl)", "tip_x"), ("Y (pxl)", "tip_y"), ("Angle (degree)", "angle"),
                  ("A+B (V)", "a_plus_b"), ("A-B (V)", "a_minus_b"), ("C-D (V)", "c_minus_d")]
        for i, (lbl, key) in enumerate(labels):
            r, c = divmod(i, 3)
            rl.addWidget(QLabel(lbl), r, c * 2, alignment=Qt.AlignRight)
            e = _ro_edit(80)
            self.ref_fields[key] = e
            rl.addWidget(e, r, c * 2 + 1)
        self.btn_set_ref = QPushButton("현재 슬롯을 기준으로")
        rl.addWidget(self.btn_set_ref, 2, 0, 1, 6, alignment=Qt.AlignRight)
        lay.addWidget(self.ref_group)

        # Info
        info_grp = QGroupBox("Info")
        il = QVBoxLayout(info_grp)
        self.info_table1 = self._info_table(INFO_ROW1)
        self.info_table2 = self._info_table(INFO_ROW2)
        il.addWidget(self.info_table1)
        il.addWidget(self.info_table2)
        self.lbl_vision_verdict = QLabel("-")
        self.lbl_vision_verdict.setStyleSheet(f"color: {FG2};")
        il.addWidget(self.lbl_vision_verdict)
        lay.addWidget(info_grp)

        # Grouping
        grp = QGroupBox("Grouping")
        gl = QGridLayout(grp)
        gl.addWidget(QLabel("Path"), 0, 0)
        self.grp_path_edit = QLineEdit()
        self.grp_path_edit.setReadOnly(True)
        gl.addWidget(self.grp_path_edit, 0, 1, 1, 5)
        self.btn_grp_change = QPushButton("Change...")
        gl.addWidget(self.btn_grp_change, 0, 6)

        gl.addWidget(QLabel("Unit No"), 1, 0)
        self.grp_unit_edit = QLineEdit()
        self.grp_unit_edit.setPlaceholderText("P2401002")
        gl.addWidget(self.grp_unit_edit, 1, 1, 1, 2)
        gl.addWidget(QLabel("Batch"), 1, 3)
        self.grp_batch_edit = QLineEdit()
        gl.addWidget(self.grp_batch_edit, 1, 4, 1, 3)

        gl.addWidget(QLabel("등급"), 2, 0)
        self.grp_grade_combo = QComboBox()
        for key in ("industrial", "research"):
            self.grp_grade_combo.addItem(GRADE_NAMES[key], key)
        gl.addWidget(self.grp_grade_combo, 2, 1, 1, 2)
        gl.addWidget(QLabel("통과"), 2, 3)
        self.lbl_grp_available = QLabel("0")
        gl.addWidget(self.lbl_grp_available, 2, 4)

        gl.addWidget(QLabel("Quantity"), 3, 0)
        qrow = QHBoxLayout()
        self.grp_spin: dict[int, QSpinBox] = {}
        for size in LOT_SIZES:
            qrow.addWidget(QLabel(f"{size}M  x"))
            sp = QSpinBox()
            sp.setRange(0, 99)
            sp.setFixedWidth(56)
            self.grp_spin[size] = sp
            qrow.addWidget(sp)
            qrow.addSpacing(8)
        qrow.addStretch()
        gl.addLayout(qrow, 3, 1, 1, 6)

        gl.addWidget(QLabel("Remain"), 4, 0)
        self.lbl_remain = QLabel("0")
        gl.addWidget(self.lbl_remain, 4, 1)
        self.lbl_grp_status = QLabel("")
        self.lbl_grp_status.setAlignment(Qt.AlignCenter)
        self.lbl_grp_status.setMinimumWidth(90)
        gl.addWidget(self.lbl_grp_status, 4, 4, 1, 2)
        self.btn_grp_run = QPushButton("Run")
        self.btn_grp_run.setProperty("accent", "true")
        self.btn_grp_run.setToolTip("로트 폴더를 만들고 ATX 모드 탭으로 엽니다")
        gl.addWidget(self.btn_grp_run, 4, 6)
        lay.addWidget(grp)
        lay.addStretch()
        return w

    def _info_table(self, headers: list[str]) -> QTableWidget:
        t = QTableWidget(1, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setDefaultSectionSize(22)
        t.setFixedHeight(22 + t.horizontalHeader().height() + 4)
        for c in range(len(headers)):
            it = QTableWidgetItem("-")
            it.setTextAlignment(Qt.AlignCenter)
            t.setItem(0, c, it)
        return t

    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(6)

        self.sweep_viewer = ImageViewer()
        self.sweep_viewer.setMinimumHeight(200)
        lay.addWidget(self.sweep_viewer, 2)
        self.lbl_sweep_path = QLabel("-")
        self.lbl_sweep_path.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        self.lbl_sweep_path.setWordWrap(True)
        lay.addWidget(self.lbl_sweep_path)

        self.zoom_viewer = ImageViewer()
        self.zoom_viewer.setMinimumHeight(200)
        lay.addWidget(self.zoom_viewer, 2)
        self.lbl_zoom_path = QLabel("-")
        self.lbl_zoom_path.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        self.lbl_zoom_path.setWordWrap(True)
        lay.addWidget(self.lbl_zoom_path)

        chart_grp = QGroupBox("Sweep 판정 (수치 기반)")
        cl = QVBoxLayout(chart_grp)
        self.chart = SweepVerdictChart()
        cl.addWidget(self.chart, 1)
        zrow = QHBoxLayout()
        zrow.addWidget(QLabel("Zoom"))
        self.btn_zoom_in = QPushButton("In")
        self.btn_zoom_in.setCheckable(True)
        self.btn_zoom_in.setChecked(True)
        self.btn_zoom_out = QPushButton("Out")
        self.btn_zoom_out.setCheckable(True)
        zrow.addWidget(self.btn_zoom_in)
        zrow.addWidget(self.btn_zoom_out)
        zrow.addStretch()
        cl.addLayout(zrow)
        lay.addWidget(chart_grp, 3)
        return w

    # ─── 표 ───

    def _on_table_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        code = self.table.item(rows[0].row(), 0).data(Qt.UserRole)
        if code:
            self.row_selected.emit(code)

    def _on_table_context(self, pos):
        it = self.table.itemAt(pos)
        if it is None:
            return
        code = self.table.item(it.row(), 0).data(Qt.UserRole)
        if code:
            self.context_requested.emit(code, self.table.viewport().mapToGlobal(pos))

    def set_rows(self, rows: list[dict]) -> None:
        """rows: [{code, atx, port, slot, grade, grade_name, error, no, override}]."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        self._codes = []
        for r, rec in enumerate(rows):
            color = QColor(GRADE_COLORS.get(rec["grade"], FG2))
            tint = QColor(color)
            tint.setAlpha(40)
            values = [str(rec["atx"]), str(rec["port"]), str(rec["slot"]),
                      rec["grade_name"] + (" *" if rec.get("override") else ""),
                      rec["error"], rec["no"]]
            for c, text in enumerate(values):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignCenter if c < 4 else Qt.AlignLeft | Qt.AlignVCenter)
                it.setBackground(tint)
                if c == 3:
                    it.setForeground(color)
                    font = it.font()
                    font.setBold(True)
                    it.setFont(font)
                if c == 0:
                    it.setData(Qt.UserRole, rec["code"])
                self.table.setItem(r, c, it)
            self._codes.append(rec["code"])
        self.table.blockSignals(False)

    def select_code(self, code: str) -> None:
        if code in self._codes:
            self.table.selectRow(self._codes.index(code))

    def current_code(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole)

    def grade_filter(self) -> set[str]:
        return {k for k, chk in self.chk_grade.items() if chk.isChecked()}

    # ─── 상세 ───

    def set_info(self, row1: list[str], row2: list[str]) -> None:
        for c, v in enumerate(row1):
            self.info_table1.item(0, c).setText(v)
        for c, v in enumerate(row2):
            self.info_table2.item(0, c).setText(v)

    def clear_detail(self) -> None:
        self.set_info(["-"] * len(INFO_ROW1), ["-"] * len(INFO_ROW2))
        self.vision_viewer.clear()
        self.sweep_viewer.clear()
        self.zoom_viewer.clear()
        self.lbl_vision_path.setText("-")
        self.lbl_sweep_path.setText("-")
        self.lbl_zoom_path.setText("-")
        self.lbl_vision_verdict.setText("-")
        self.fail_combo.clear()
        self.lbl_formula.setText("-")
        self.chart.clear()

    def set_reference(self, cantilever_no: str | None, values: dict[str, float | None]) -> None:
        self.ref_group.setTitle(f"Reference Cantilever ({cantilever_no or '-'})")
        for key, e in self.ref_fields.items():
            v = values.get(key)
            e.setText("-" if v is None else f"{v:,.3f}".rstrip("0").rstrip("."))

    def set_path_label(self, label: QLabel, path: str | None, missing_text: str = "does not exist") -> None:
        if path:
            label.setText(path)
            label.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        else:
            label.setText(missing_text)
            label.setStyleSheet(f"color: {RED}; font-size: 11px;")

    # ─── 템플릿 폼 ───

    def set_template_names(self, names: list[str], current: str | None) -> None:
        self.tip_combo.blockSignals(True)
        self.tip_combo.clear()
        self.tip_combo.addItems(names)
        if current in names:
            self.tip_combo.setCurrentText(current)
        self.tip_combo.blockSignals(False)

    def template_to_form(self, template: dict) -> None:
        self.um_spin.setValue(float(template.get("um_per_pixel") or 0.345))
        for grade in template.get("grades", []):
            widgets = self.item_widgets.get(grade["key"], {})
            for key in ITEM_KEYS:
                rec = widgets.get(key)
                item = grade["items"].get(key, {})
                if rec is None:
                    continue
                rec["chk"].setChecked(bool(item.get("enabled")))
                kind = ITEM_BY_KEY[key].kind
                if kind == "offset":
                    rec["a"].setValue(float(item.get("offset") or 0))
                elif kind == "range":
                    rec["a"].setValue(float(item.get("min") if item.get("min") is not None else 0))
                    rec["b"].setValue(float(item.get("max") if item.get("max") is not None else 0))
                else:
                    rec["a"].setValue(float(item.get("min") or 0))

    def form_to_template(self, tip_id: str) -> dict:
        grades = []
        for key, name in GRADES:
            items = {}
            for ikey in ITEM_KEYS:
                rec = self.item_widgets[key][ikey]
                kind = ITEM_BY_KEY[ikey].kind
                if kind == "offset":
                    items[ikey] = {"enabled": rec["chk"].isChecked(), "offset": rec["a"].value()}
                elif kind == "range":
                    items[ikey] = {"enabled": rec["chk"].isChecked(),
                                   "min": rec["a"].value(), "max": rec["b"].value()}
                else:
                    items[ikey] = {"enabled": rec["chk"].isChecked(), "min": rec["a"].value()}
            grades.append({"key": key, "name": name, "items": items})
        return {"tip_id": tip_id, "um_per_pixel": self.um_spin.value(), "grades": grades}

    # ─── Grouping ───

    def lot_counts(self) -> dict[int, int]:
        return {size: sp.value() for size, sp in self.grp_spin.items()}

    def set_grouping_status(self, text: str, ok: bool | None) -> None:
        self.lbl_grp_status.setText(text)
        if ok is None:
            self.lbl_grp_status.setStyleSheet("")
        else:
            color = GREEN if ok else RED
            self.lbl_grp_status.setStyleSheet(
                f"background: {color}; color: {BG}; font-weight: bold; border-radius: 3px; padding: 2px 6px;")
