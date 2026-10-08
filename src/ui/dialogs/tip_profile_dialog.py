"""Tip 관리 다이얼로그 — Tip 별 Type 표기명 · SEM 이미지 · 스펙 표 (Word 체크시트용).

좌측: Tip 목록(카탈로그 ∪ 저장된 프로필 ∪ 현재 로드된 probe_type) + 추가/삭제.
우측: 선택한 Tip 의 표기명, SEM 이미지(찾아보기 + 썸네일), 스펙 레이아웃 콤보, 스펙 표(행 추가/삭제/위/아래).
[저장] 시 ``result_profiles()`` 가 정규화된 ``{tip: profile}`` 을, ``result_catalog()`` 가 Tip 이름 목록을 돌려준다.
SEM 이미지는 여기서 원본 경로만 보관하고, 보관 폴더로의 복사는 호출자(ExportMixin)가 저장할 때 한다.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.tip_profiles import (
    SPEC_LAYOUT_HEADERS,
    SPEC_LAYOUT_LABELS,
    SPEC_LAYOUTS,
    default_tip_profile,
    normalize_tip_profile,
    normalize_tip_profiles,
)
from src.ui.theme import BG2, BG3, FG2

_THUMB_W, _THUMB_H = 160, 124
_IMAGE_FILTER = "이미지 (*.png *.jpg *.jpeg *.bmp)"


class TipProfileDialog(QDialog):
    def __init__(self, catalog: list[str], profiles: dict, loaded_types: tuple[str, ...] | list[str] = (),
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tip 관리")
        self.setModal(True)
        self.resize(880, 640)
        self._profiles: dict[str, dict] = normalize_tip_profiles(profiles)
        self._current: str | None = None

        names: list[str] = []
        for n in list(catalog) + list(self._profiles) + list(loaded_types):
            n = str(n or "").strip()
            if n and n not in names:
                names.append(n)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 8)
        body.setSpacing(12)

        # ── 좌: Tip 목록 ──
        left = QVBoxLayout()
        left.addWidget(QLabel("Tip 목록"))
        self.list = QListWidget()
        self.list.setFixedWidth(220)
        for n in names:
            self.list.addItem(n)
        left.addWidget(self.list, 1)
        add_row = QHBoxLayout()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("새 Tip 이름 (폴더 probe_type 과 동일)")
        self.new_name.returnPressed.connect(self._add_tip)
        self.btn_add = QPushButton("추가")
        self.btn_add.clicked.connect(self._add_tip)
        add_row.addWidget(self.new_name, 1)
        add_row.addWidget(self.btn_add)
        left.addLayout(add_row)
        self.btn_remove = QPushButton("선택 삭제")
        self.btn_remove.clicked.connect(self._remove_tip)
        left.addWidget(self.btn_remove)
        body.addLayout(left)

        # ── 우: 프로필 편집 ──
        self.form_box = QGroupBox("프로필")
        form_layout = QVBoxLayout(self.form_box)
        form = QFormLayout()
        self.display_name = QLineEdit()
        self.display_name.setToolTip("체크시트 'Type :' 에 찍히는 정식 모델명 (예 AC160TS). 비우면 Tip 이름.")
        form.addRow("Type 표기명", self.display_name)

        img_row = QHBoxLayout()
        self.sem_path = QLineEdit()
        self.sem_path.setReadOnly(True)
        self.sem_path.setStyleSheet(f"color: {FG2};")
        self.btn_browse = QPushButton("찾아보기…")
        self.btn_browse.clicked.connect(self._browse_image)
        self.btn_clear_image = QPushButton("지움")
        self.btn_clear_image.clicked.connect(lambda: self._set_image(""))
        img_row.addWidget(self.sem_path, 1)
        img_row.addWidget(self.btn_browse)
        img_row.addWidget(self.btn_clear_image)
        form.addRow("SEM 이미지", img_row)
        self.thumb = QLabel("미리보기 없음")
        self.thumb.setFixedSize(_THUMB_W, _THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet(f"border: 1px solid {BG3}; color: {FG2};")
        form.addRow("", self.thumb)

        self.layout_combo = QComboBox()
        for key in SPEC_LAYOUTS:
            self.layout_combo.addItem(SPEC_LAYOUT_LABELS[key], key)
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        form.addRow("스펙 표 양식", self.layout_combo)
        form_layout.addLayout(form)

        self.table = QTableWidget(0, 4)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        form_layout.addWidget(self.table, 1)
        row_btns = QHBoxLayout()
        self.btn_row_add = QPushButton("행 추가")
        self.btn_row_del = QPushButton("행 삭제")
        self.btn_row_up = QPushButton("위")
        self.btn_row_down = QPushButton("아래")
        self.btn_row_add.clicked.connect(self._row_add)
        self.btn_row_del.clicked.connect(self._row_del)
        self.btn_row_up.clicked.connect(lambda: self._row_move(-1))
        self.btn_row_down.clicked.connect(lambda: self._row_move(+1))
        for b in (self.btn_row_add, self.btn_row_del, self.btn_row_up, self.btn_row_down):
            row_btns.addWidget(b)
        row_btns.addStretch(1)
        form_layout.addLayout(row_btns)
        body.addWidget(self.form_box, 1)
        outer.addLayout(body, 1)

        # ── 푸터 ──
        footer_frame = QFrame()
        footer_frame.setObjectName("tipFooter")
        footer_frame.setStyleSheet(f"QFrame#tipFooter {{ background: {BG2}; border-top: 1px solid {BG3}; }}")
        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(16, 10, 16, 10)
        hint = QLabel("Tip 이름은 ATX 폴더의 probe_type(예 P2601001_12M_AC160 → AC160)과 같아야 Word 체크시트가 생성됩니다.")
        hint.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        hint.setWordWrap(True)
        footer.addWidget(hint, 1)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("저장")
        self.btn_save.setProperty("accent", "true")
        self.btn_save.clicked.connect(self._on_accept)
        footer.addWidget(btn_cancel)
        footer.addWidget(self.btn_save)
        outer.addWidget(footer_frame)

        self.list.currentRowChanged.connect(self._on_row_changed)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.form_box.setEnabled(False)

    # ─── 목록 ───

    def tip_names(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]

    def _add_tip(self) -> None:
        name = self.new_name.text().strip()
        if not name:
            return
        if name in self.tip_names():
            QMessageBox.information(self, "Tip 관리", f"'{name}' 은 이미 목록에 있습니다.")
            return
        self.list.addItem(name)
        self.new_name.clear()
        self.list.setCurrentRow(self.list.count() - 1)

    def _remove_tip(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        name = self.list.item(row).text()
        self._current = None                      # 삭제되는 항목은 커밋하지 않음
        self._profiles.pop(name, None)
        self.list.takeItem(row)
        if not self.list.count():
            self.form_box.setEnabled(False)

    def _on_row_changed(self, row: int) -> None:
        self._commit_form()
        if row < 0:
            self._current = None
            self.form_box.setEnabled(False)
            return
        self.form_box.setEnabled(True)
        self._load_form(self.list.item(row).text())

    # ─── 폼 ↔ 프로필 ───

    def _load_form(self, name: str) -> None:
        self._current = None
        prof = self._profiles.get(name) or default_tip_profile(name)
        self.display_name.setText(prof["display_name"])
        self._set_image(prof["sem_image"])
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(SPEC_LAYOUTS.index(prof["spec_layout"]))
        self.layout_combo.blockSignals(False)
        self._fill_table(prof["spec_layout"], prof["spec_rows"])
        self._current = name

    def _commit_form(self) -> None:
        if self._current is None:
            return
        self._profiles[self._current] = normalize_tip_profile(self._current, {
            "display_name": self.display_name.text(),
            "sem_image": self.sem_path.text(),
            "spec_layout": self.layout_combo.currentData(),
            "spec_rows": self._table_rows(),
        })

    def _set_image(self, path: str) -> None:
        self.sem_path.setText(path)
        pix = QPixmap(path) if path and Path(path).is_file() else QPixmap()
        if pix.isNull():
            self.thumb.setPixmap(QPixmap())
            self.thumb.setText("미리보기 없음" if not path else "이미지를 열 수 없음")
        else:
            self.thumb.setText("")
            self.thumb.setPixmap(pix.scaled(_THUMB_W - 2, _THUMB_H - 2, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "SEM 이미지 선택", "", _IMAGE_FILTER)
        if path:
            self._set_image(path)

    def _fill_table(self, layout: str, rows: list[list[str]]) -> None:
        headers = SPEC_LAYOUT_HEADERS[layout]
        self.table.setRowCount(0)
        self.table.setColumnCount(1 + len(headers))
        self.table.setHorizontalHeaderLabels(["Technical Data", *headers])
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, text in enumerate(row[:1 + len(headers)]):
                self.table.setItem(r, c, QTableWidgetItem(text))

    def _table_rows(self) -> list[list[str]]:
        rows = []
        for r in range(self.table.rowCount()):
            cells = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                cells.append(item.text() if item else "")
            rows.append(cells)
        return rows

    def _on_layout_changed(self, _idx: int) -> None:
        layout = self.layout_combo.currentData()
        rows = normalize_tip_profile(self._current or "", {"spec_layout": layout, "spec_rows": self._table_rows()})["spec_rows"]
        self._fill_table(layout, rows)

    def _row_add(self) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(""))
        self.table.setCurrentCell(r, 0)
        self.table.editItem(self.table.item(r, 0))

    def _row_del(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _row_move(self, delta: int) -> None:
        r = self.table.currentRow()
        t = r + delta
        if r < 0 or t < 0 or t >= self.table.rowCount():
            return
        for c in range(self.table.columnCount()):
            a, b = self.table.takeItem(r, c), self.table.takeItem(t, c)
            self.table.setItem(t, c, a if a else QTableWidgetItem(""))
            self.table.setItem(r, c, b if b else QTableWidgetItem(""))
        self.table.setCurrentCell(t, 0)

    # ─── 결과 ───

    def _on_accept(self) -> None:
        self._commit_form()
        self.accept()

    def result_profiles(self) -> dict:
        self._commit_form()
        names = self.tip_names()
        return normalize_tip_profiles({n: self._profiles.get(n) or default_tip_profile(n) for n in names})

    def result_catalog(self) -> list[str]:
        return self.tip_names()
