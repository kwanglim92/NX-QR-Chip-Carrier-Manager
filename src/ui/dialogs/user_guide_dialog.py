"""In-app user guide viewer."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover - depends on optional QtWebEngine runtime
    QWebEngineView = None


def project_root() -> Path:
    """Return the app root for both source and PyInstaller onedir runs."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def user_guide_path() -> Path:
    return project_root() / "docs" / "user-guide.html"


class UserGuideDialog(QDialog):
    """Display docs/user-guide.html inside the app."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("사용자 가이드")
        self.resize(1100, 760)
        self._guide_path = user_guide_path()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        if QWebEngineView is None:
            self.viewer = None
            self.status_label.setText(
                "내장 HTML 뷰어를 사용할 수 없습니다. 브라우저에서 열기를 사용하세요."
            )
            fallback = QLabel(
                "Qt WebEngine 런타임을 찾을 수 없어 앱 내부 표시를 건너뜁니다."
            )
            fallback.setWordWrap(True)
            fallback.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            root.addWidget(fallback, 1)
        else:
            self.viewer = QWebEngineView(self)
            self.viewer.loadFinished.connect(self._on_load_finished)
            root.addWidget(self.viewer, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()

        self.btn_open_browser = QPushButton("브라우저에서 열기")
        self.btn_open_browser.clicked.connect(self.open_in_browser)
        button_row.addWidget(self.btn_open_browser)

        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.accept)
        button_row.addWidget(self.btn_close)

        root.addLayout(button_row)
        self._load()

    def _load(self) -> None:
        if not self._guide_path.exists():
            self.status_label.setText(
                f"사용자 가이드 파일을 찾을 수 없습니다: {self._guide_path}"
            )
            QMessageBox.warning(
                self,
                "사용자 가이드 없음",
                "사용자 가이드 파일을 찾을 수 없습니다.\n"
                f"{self._guide_path}",
            )
            return

        url = QUrl.fromLocalFile(str(self._guide_path))
        self.status_label.setText(str(self._guide_path))
        if self.viewer is not None:
            self.viewer.load(url)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            self.status_label.setText("사용자 가이드가 로드되었습니다.")
            return

        self.status_label.setText(
            "앱 내부에서 사용자 가이드를 불러오지 못했습니다. 브라우저에서 열기를 사용하세요."
        )

    def open_in_browser(self) -> None:
        if not self._guide_path.exists():
            QMessageBox.warning(
                self,
                "사용자 가이드 없음",
                "사용자 가이드 파일을 찾을 수 없어 브라우저에서 열 수 없습니다.\n"
                f"{self._guide_path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._guide_path)))
