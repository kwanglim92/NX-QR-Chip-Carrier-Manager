"""이미지 확대 보기 다이얼로그 — Inspection 뷰어 더블클릭용 (화면의 90% 까지, 비율 유지)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from src.ui.widgets.image_viewer import ImageViewer


class ImagePopupDialog(QDialog):
    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(Path(path).name)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.viewer = ImageViewer(inset=2)
        self.viewer.load_image(path)
        lay.addWidget(self.viewer)

        pix = QPixmap(path)
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        if not pix.isNull() and avail is not None:
            w = min(pix.width(), int(avail.width() * 0.9))
            h = min(pix.height(), int(avail.height() * 0.9))
            size = pix.size()
            size.scale(w, h, Qt.KeepAspectRatio)
            self.resize(size.width() + 8, size.height() + 8)
        else:
            self.resize(900, 700)
        # 더블클릭으로 닫기
        self.viewer.double_clicked.connect(lambda _p: self.accept())
