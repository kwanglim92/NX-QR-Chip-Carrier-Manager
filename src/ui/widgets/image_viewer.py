"""FreqSweep 및 수동 측정 이미지 뷰어."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.ui.theme import BG2, BG3, FG2


class ImageViewer(QWidget):
    """Fixed viewport image preview.

    The original pixmap is kept untouched and rendered into the current widget
    bounds. This prevents large or unusual captures from resizing the app UI.
    """

    clicked = Signal()  # 좌클릭 — 호출자가 붙여넣기/불러오기 등에 연결
    double_clicked = Signal(str)  # 좌더블클릭 — 현재 이미지 경로("" 이면 없음)

    def __init__(self, parent=None, inset: int = 20):
        """``inset`` = 테두리 안쪽 여백(px). Inspection 처럼 이미지를 크게 보일 때는 작게."""
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._inset = max(0, int(inset))

        self._current_path: str | None = None
        self._pixmap = QPixmap()
        self._message = "Select an image"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._current_path or "")
        super().mouseDoubleClickEvent(event)

    def current_path(self) -> str | None:
        return self._current_path

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

        i = self._inset
        inner = rect.adjusted(i, i, -i, -i)
        if self._pixmap.isNull():
            painter.setPen(QColor(FG2))
            painter.drawText(inner, Qt.AlignCenter | Qt.TextWordWrap, self._message)
            return

        pix_size = self._pixmap.size()
        pix_size.scale(inner.size().toSize(), Qt.KeepAspectRatio)
        target = QRectF(0, 0, pix_size.width(), pix_size.height())
        target.moveCenter(inner.center())
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
