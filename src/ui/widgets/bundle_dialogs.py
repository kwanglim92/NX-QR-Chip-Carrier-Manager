"""DB Export/Import 번들 다이얼로그 (F-18)."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDateEdit, QCheckBox, QPushButton, QRadioButton, QButtonGroup,
    QFrame, QDialogButtonBox, QGroupBox,
)

from src.core.bundle import BundlePreview
from src.ui.theme import ACCENT, FG, FG2, BG2, BG3, GREEN, ORANGE, RED


class BundleExportDialog(QDialog):
    """번들 Export 옵션 다이얼로그.

    ``get_options()``로 (date_from, date_to, include_images) 반환.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Bundle")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(self._make_header("Export Measurement Bundle"))

        # ── 날짜 범위 ──
        group = QGroupBox("Date Range")
        form = QFormLayout(group)

        self._chk_all_dates = QCheckBox("Export all records")
        self._chk_all_dates.setChecked(True)
        self._chk_all_dates.stateChanged.connect(self._on_all_toggled)
        form.addRow(self._chk_all_dates)

        self._date_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("yyyyMMdd")
        form.addRow("From:", self._date_from)

        self._date_to = QDateEdit(QDate.currentDate())
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("yyyyMMdd")
        form.addRow("To:", self._date_to)

        layout.addWidget(group)

        # ── 이미지 포함 ──
        self._chk_include_images = QCheckBox("Include image files (larger ZIP)")
        self._chk_include_images.setChecked(True)
        layout.addWidget(self._chk_include_images)

        # 버튼
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._on_all_toggled()

    def _on_all_toggled(self):
        enabled = not self._chk_all_dates.isChecked()
        self._date_from.setEnabled(enabled)
        self._date_to.setEnabled(enabled)

    def _make_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 14px; font-weight: bold;"
        )
        return lbl

    def get_options(self) -> tuple[str | None, str | None, bool]:
        """(date_from, date_to, include_images). 전체 Export 시 (None, None, ...)."""
        if self._chk_all_dates.isChecked():
            return None, None, self._chk_include_images.isChecked()
        return (
            self._date_from.date().toString("yyyyMMdd"),
            self._date_to.date().toString("yyyyMMdd"),
            self._chk_include_images.isChecked(),
        )


class BundleImportDialog(QDialog):
    """번들 Import 미리보기 + 중복 정책 선택.

    ``BundlePreview``를 받아 정보 표시 후, ``get_policy()`` 또는 취소 반환.
    번들이 비호환이면 OK 버튼 비활성화 + 사유 표시.
    """

    def __init__(self, preview: BundlePreview, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Bundle")
        self.setMinimumWidth(420)
        self._preview = preview

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(self._make_header("Import Measurement Bundle"))

        # ── 미리보기 정보 ──
        info = QGroupBox("Bundle Info")
        info_form = QFormLayout(info)
        info_form.setLabelAlignment(Qt.AlignRight)

        sv_color = GREEN if preview.compatible else RED
        sv_text = f"v{preview.schema_version}"
        if not preview.compatible:
            sv_text += "  (incompatible)"
        info_form.addRow("Schema:", self._value_label(sv_text, sv_color))
        info_form.addRow("Records:", self._value_label(str(preview.record_count)))
        info_form.addRow("Slots count:",
                         self._value_label("(see data.jsonl)"))
        info_form.addRow("Exported at:", self._value_label(preview.exported_at or "-"))
        dr = (
            f"{preview.date_range[0]} ~ {preview.date_range[1]}"
            if preview.date_range else "-"
        )
        info_form.addRow("Date range:", self._value_label(dr))
        info_form.addRow("Images:",
                         self._value_label("Included" if preview.images_included else "Not included",
                                           GREEN if preview.images_included else FG2))

        if not preview.compatible and preview.incompatible_reason:
            reason = QLabel(f"⚠ {preview.incompatible_reason}")
            reason.setStyleSheet(f"color: {RED}; font-size: 12px;")
            reason.setWordWrap(True)
            info_form.addRow("Reason:", reason)

        layout.addWidget(info)

        # ── 중복 정책 ──
        policy_group = QGroupBox("Duplicate Handling")
        policy_layout = QVBoxLayout(policy_group)
        self._policy_group = QButtonGroup(self)

        self._rb_skip = QRadioButton(
            "Skip — keep existing records, ignore duplicates"
        )
        self._rb_overwrite = QRadioButton(
            "Overwrite — replace existing records with incoming data"
        )
        self._rb_merge = QRadioButton(
            "Merge — add new QR IDs only, preserve existing slots"
        )
        self._rb_skip.setChecked(True)

        for i, rb in enumerate((self._rb_skip, self._rb_overwrite, self._rb_merge)):
            self._policy_group.addButton(rb, i)
            policy_layout.addWidget(rb)

        layout.addWidget(policy_group)

        self._chk_extract_images = QCheckBox(
            "Extract bundled images to local storage"
        )
        self._chk_extract_images.setChecked(preview.images_included)
        self._chk_extract_images.setEnabled(preview.images_included)
        layout.addWidget(self._chk_extract_images)

        # 버튼
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self._ok_btn = btns.button(QDialogButtonBox.Ok)
        self._ok_btn.setText("Import")
        self._ok_btn.setEnabled(preview.compatible)
        layout.addWidget(btns)

    def _make_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 14px; font-weight: bold;"
        )
        return lbl

    def _value_label(self, text: str, color: str | None = None) -> QLabel:
        lbl = QLabel(text)
        c = color or FG
        lbl.setStyleSheet(f"color: {c}; font-size: 13px;")
        return lbl

    def get_policy(self) -> str:
        if self._rb_overwrite.isChecked():
            return "overwrite"
        if self._rb_merge.isChecked():
            return "merge"
        return "skip"

    def get_extract_images(self) -> bool:
        return self._chk_extract_images.isChecked()
