"""FreqSweep 및 수동 측정 이미지 뷰어."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.ui.theme import BG2, BG3, FG2


class ImageViewer(QWidget):
    """Fixed viewport image preview.

    The original pixmap is kept untouched and rendered into the current widget
    bounds. This prevents large or unusual captures from resizing the app UI.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._current_path: str | None = None
        self._pixmap = QPixmap()
        self._message = "Select an image"

    def load_image(self, path: str | None):
        self._current_path = path
        self._pixmap = QPixmap()

        if not path:
            self._message = "이미지 없음"
            self.update()
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._message = f"이미지 로드 실패:\n{path}"
            self.update()
            return

        self._pixmap = pixmap
        self._message = ""
        self.update()

    def clear(self):
        self._current_path = None
        self._pixmap = QPixmap()
        self._message = "이미지를 선택하세요"
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillRect(rect, QColor(BG2))
        painter.setPen(QPen(QColor(BG3), 1))
        painter.drawRoundedRect(rect, 6, 6)

        inner = rect.adjusted(20, 20, -20, -20)
        if self._pixmap.isNull():
            painter.setPen(QColor(FG2))
            painter.drawText(inner, Qt.AlignCenter | Qt.TextWordWrap, self._message)
            return

        pix_size = self._pixmap.size()
        pix_size.scale(inner.size().toSize(), Qt.KeepAspectRatio)
        target = QRectF(0, 0, pix_size.width(), pix_size.height())
        target.moveCenter(inner.center())
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
