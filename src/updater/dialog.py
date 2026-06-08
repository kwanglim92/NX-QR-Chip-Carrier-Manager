"""Modal progress dialog for auto-updates."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class UpdateDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        version: str,
        release_notes: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("업데이트 다운로드")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.resize(460, 170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self._title = QLabel(f"새 버전 {version}을 다운로드하는 중입니다.")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._notes = QLabel(release_notes or "업데이트 파일을 준비하고 있습니다.")
        self._notes.setWordWrap(True)
        layout.addWidget(self._notes)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)

        self._status = QLabel("0 KB")
        layout.addWidget(self._status)

    def on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(received)
            self._status.setText(
                f"{received / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB"
            )
            return

        self._progress.setRange(0, 0)
        self._status.setText(f"{received / 1024 / 1024:.1f} MB")
