"""Pass Pool 상단 폴더 칩 스트립.

로드된 폴더를 색 범례(칩)로 보여주고, 칩을 드래그해 순서를 바꿀 수 있다. 순서가 바뀌면
``order_changed(new_keys)`` 를 emit 해 컨트롤러가 폴더 탭 · Pass Pool 스택을 함께 재정렬한다.
Pass Pool 을 보는 중에도 폴더 탭을 벗어나지 않고 재정렬하기 위한 진입점이다.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QListView, QAbstractItemView,
)

from src.ui.theme import BADGE_FG, BG


class PoolFolderStrip(QListWidget):
    order_changed = Signal(list)   # 재정렬 후 폴더 key 리스트(시각 순서)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(False)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(38)
        self.setSpacing(6)
        # 주의: ``QListWidget::item {…}`` 규칙을 두면 Qt 가 item 의 setBackground/setForeground
        # 역할을 무시한다. 칩 색을 역할로 칠하려면 프레임 규칙만 남긴다.
        self.setStyleSheet(f"QListWidget {{ border: none; background: {BG}; }}")
        self.setToolTip("드래그하여 폴더 순서를 바꾸면 Pass Pool 이 즉시 재정렬됩니다.")

    def set_folders(self, folders: list[dict]):
        """folders: [{'key':..., 'po':..., 'color':..., 'number':...}] — 시그널 억제하고 칩 재구성."""
        bold = QFont()
        bold.setBold(True)
        self._suppress = True
        try:
            self.clear()
            for f in folders:
                num = f.get("number", "")
                item = QListWidgetItem(f"{num} {f['po']}".strip())
                item.setData(Qt.UserRole, f["key"])
                item.setBackground(QColor(f["color"]))
                item.setForeground(QColor(BADGE_FG))
                item.setFont(bold)
                item.setToolTip(f["po"])
                self.addItem(item)
        finally:
            self._suppress = False

    def current_keys(self) -> list:
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]

    def dropEvent(self, event):
        super().dropEvent(event)
        if not self._suppress:
            # 드롭 이벤트가 끝난 뒤(리스트 재구성 안전) 다음 틱에 통지
            QTimer.singleShot(0, lambda: self.order_changed.emit(self.current_keys()))
