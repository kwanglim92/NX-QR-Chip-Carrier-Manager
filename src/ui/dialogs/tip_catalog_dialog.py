"""Tip 카탈로그 관리 다이얼로그 — 관리형 Tip 모델 목록 CRUD."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TipCatalogDialog(QDialog):
    """Tip 이름 카탈로그를 추가/삭제로 관리. OK 시 편집된 목록을 보존."""

    def __init__(self, catalog: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tip 카탈로그 관리")
        self.setModal(True)
        self.resize(320, 400)

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel("등록된 Tip 모델 목록:"))

        self._list = QListWidget()
        for name in catalog:
            self._list.addItem(name)
        outer.addWidget(self._list, 1)

        # 추가 행
        add_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("새 Tip 이름 입력 후 추가")
        self._input.returnPressed.connect(self._add)
        add_row.addWidget(self._input, 1)
        btn_add = QPushButton("추가")
        btn_add.clicked.connect(self._add)
        add_row.addWidget(btn_add)
        outer.addLayout(add_row)

        # 삭제
        btn_remove = QPushButton("선택 삭제")
        btn_remove.clicked.connect(self._remove_selected)
        outer.addWidget(btn_remove)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _add(self) -> None:
        name = self._input.text().strip()
        if not name:
            return
        existing = {self._list.item(i).text() for i in range(self._list.count())}
        if name not in existing:
            self._list.addItem(name)
        self._input.clear()
        self._input.setFocus()

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    def result_catalog(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]
