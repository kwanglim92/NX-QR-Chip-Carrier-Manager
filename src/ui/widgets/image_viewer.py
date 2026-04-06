"""FreqSweep 및 수동 측정 이미지 뷰어."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.ui.theme import BG2, BG3, FG2


class ImageViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("이미지를 선택하세요")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            f"background: {BG2}; color: {FG2}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 20px;"
        )
        self._label.setMinimumHeight(200)
        layout.addWidget(self._label)

        self._current_path: str | None = None

    def load_image(self, path: str | None):
        self._current_path = path
        if not path:
            self._label.setPixmap(QPixmap())
            self._label.setText("이미지 없음")
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._label.setText(f"이미지 로드 실패:\n{path}")
            return

        scaled = pixmap.scaled(
            self._label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._label.setPixmap(scaled)
        self._label.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_path:
            self.load_image(self._current_path)

    def clear(self):
        self._current_path = None
        self._label.setPixmap(QPixmap())
        self._label.setText("이미지를 선택하세요")
