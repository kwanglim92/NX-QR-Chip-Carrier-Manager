"""QR 바코드 스캐너 입력 위젯."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel

from src.ui.theme import ACCENT, GREEN, RED, FG2, BG2, BG3


class QRInputWidget(QWidget):
    qr_scanned = Signal(str)  # QR ID

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("📱")
        icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("QR 코드를 스캔하세요...")
        self._input.setStyleSheet(
            f"font-size: 14px; padding: 8px 12px; "
            f"background: {BG2}; border: 2px solid {ACCENT}; border-radius: 6px;"
        )
        self._input.returnPressed.connect(self._on_submit)
        layout.addWidget(self._input)

        self._status = QLabel("")
        self._status.setFixedWidth(200)
        self._status.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        layout.addWidget(self._status)

    def _on_submit(self):
        text = self._input.text().strip()
        if text:
            self.qr_scanned.emit(text)
            self._input.clear()

    def set_target_label(self, label: str):
        self._input.setPlaceholderText(f"QR 스캔 → {label}")

    def show_success(self, msg: str):
        self._status.setStyleSheet(f"color: {GREEN}; font-size: 12px;")
        self._status.setText(msg)

    def show_error(self, msg: str):
        self._status.setStyleSheet(f"color: {RED}; font-size: 12px;")
        self._status.setText(msg)

    def focus_input(self):
        self._input.setFocus()
        self._input.selectAll()
