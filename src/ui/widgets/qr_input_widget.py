"""QR 바코드 스캐너 입력 위젯."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel

from src.ui.theme import ACCENT, GREEN, RED, FG2, BG2, BG3


def force_latin_input(edit: QLineEdit) -> None:
    """QR 스캔 입력창을 영문 전용으로 고정 — 시스템 IME 가 한글이어도 바코드 문자가 한글로 조합되지 않게.

    WA_InputMethodEnabled 를 끄면 Qt Windows 백엔드가 포커스 시 창의 IME 컨텍스트를 해제하므로
    키 입력이 조합 없이 그대로 들어온다. 포커스가 다른 입력창으로 가면 IME 는 다시 켜진다.
    """
    edit.setAttribute(Qt.WA_InputMethodEnabled, False)
    edit.setInputMethodHints(Qt.ImhLatinOnly | Qt.ImhNoPredictiveText)


class QRInputWidget(QWidget):
    qr_scanned = Signal(str)  # QR ID

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("QR")
        icon.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {ACCENT};")
        layout.addWidget(icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Scan QR code...")
        self._input.setStyleSheet(
            f"font-size: 14px; padding: 8px 12px; "
            f"background: {BG2}; border: 2px solid {ACCENT}; border-radius: 6px;"
        )
        self._input.returnPressed.connect(self._on_submit)
        force_latin_input(self._input)
        self._input.setFixedWidth(360)     # 하단 바: 입력창 폭 고정 → 바로 옆에 다중 QR 스캔·판독 검토 버튼
        layout.addWidget(self._input)

        self._status = QLabel("")
        self._status.setMinimumWidth(200)
        self._status.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        layout.addWidget(self._status)

    def detach_status(self) -> QLabel:
        """상태 라벨을 이 위젯의 레이아웃에서 떼어 돌려준다 — 하단 바가 버튼 뒤에 따로 배치할 때 사용."""
        self.layout().removeWidget(self._status)
        return self._status

    def _on_submit(self):
        text = self._input.text().strip()
        if text:
            self.qr_scanned.emit(text)
            self._input.clear()

    def set_target_label(self, label: str):
        self._input.setPlaceholderText(f"QR Scan → {label}")

    def show_success(self, msg: str):
        self._status.setStyleSheet(f"color: {GREEN}; font-size: 12px;")
        self._status.setText(msg)

    def show_error(self, msg: str):
        self._status.setStyleSheet(f"color: {RED}; font-size: 12px;")
        self._status.setText(msg)

    def focus_input(self):
        self._input.setFocus()
        self._input.selectAll()
