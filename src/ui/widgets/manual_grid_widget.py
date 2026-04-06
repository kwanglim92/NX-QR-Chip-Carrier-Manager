"""수동 모드 드래그&드롭 카드 그리드."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QSizePolicy,
)

from src.ui.theme import FG2, BG, BG3, ACCENT
from src.ui.widgets.manual_card import ManualCard, MANUAL_CARD_HEIGHT


class ManualGridWidget(QWidget):
    card_clicked = Signal(int)          # slot_index
    card_removed = Signal(int)          # slot_index
    images_dropped = Signal(list)       # list[str] 파일 경로

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[int, ManualCard] = {}
        self._selected_index: int = -1
        self._columns: int = 4

        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG}; }}")
        outer.addWidget(scroll, 1)

        self._content = QWidget()
        self._content.setAcceptDrops(True)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        scroll.setWidget(self._content)

        self._grid = QGridLayout()
        self._grid.setSpacing(6)
        self._content_layout.addLayout(self._grid)

        # 드롭 안내 플레이스홀더
        self._placeholder = QLabel("이미지를 여기에 드래그&드롭 하세요")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setMinimumHeight(80)
        self._placeholder.setStyleSheet(
            f"color: {FG2}; font-size: 14px; "
            f"border: 2px dashed {BG3}; border-radius: 8px; "
            f"padding: 20px; margin: 8px;"
        )
        self._content_layout.addWidget(self._placeholder)
        self._content_layout.addStretch()

    def set_columns(self, n: int):
        self._columns = max(1, n)
        self._rebuild_grid()

    def add_card(self, card: ManualCard):
        card.clicked.connect(self._on_card_clicked)
        card.removed.connect(self._on_card_removed)
        self._cards[card.slot_index] = card
        self._rebuild_grid()

    def remove_card(self, slot_index: int):
        card = self._cards.pop(slot_index, None)
        if card:
            card.deleteLater()
            if self._selected_index == slot_index:
                self._selected_index = -1
            self._rebuild_grid()

    def update_card(self, slot_index: int, **kwargs):
        card = self._cards.get(slot_index)
        if card:
            card.update_data(**kwargs)

    def select_card(self, slot_index: int):
        if self._selected_index >= 0 and self._selected_index in self._cards:
            self._cards[self._selected_index].set_selected(False)
        self._selected_index = slot_index
        if slot_index in self._cards:
            self._cards[slot_index].set_selected(True)

    def clear_all(self):
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()
        self._selected_index = -1
        self._rebuild_grid()

    def get_slot_indices(self) -> list[int]:
        return sorted(self._cards.keys())

    def _rebuild_grid(self):
        # 그리드에서 모든 위젯 제거 (삭제하지 않음)
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # 이전 열 stretch 초기화 + 현재 열 균등 분배
        for c in range(self._grid.columnCount()):
            self._grid.setColumnStretch(c, 0)
        for c in range(self._columns):
            self._grid.setColumnStretch(c, 1)

        # 카드 재배치
        sorted_indices = sorted(self._cards.keys())
        for i, idx in enumerate(sorted_indices):
            row = i // self._columns
            col = i % self._columns
            self._grid.addWidget(self._cards[idx], row, col)

        # 플레이스홀더 표시/숨김
        self._placeholder.setVisible(len(self._cards) == 0)

    def _on_card_clicked(self, slot_index: int):
        self.select_card(slot_index)
        self.card_clicked.emit(slot_index)

    def _on_card_removed(self, slot_index: int):
        self.card_removed.emit(slot_index)

    # ─── 드래그&드롭 ───

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # 이미지 파일이 하나라도 있으면 수락
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith((".jpg", ".jpeg", ".png", ".bmp")):
                    event.acceptProposedAction()
                    self._placeholder.setStyleSheet(
                        f"color: {ACCENT}; font-size: 14px; "
                        f"border: 2px dashed {ACCENT}; border-radius: 8px; "
                        f"padding: 20px; margin: 8px;"
                    )
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._placeholder.setStyleSheet(
            f"color: {FG2}; font-size: 14px; "
            f"border: 2px dashed {BG3}; border-radius: 8px; "
            f"padding: 20px; margin: 8px;"
        )

    def dropEvent(self, event):
        self._placeholder.setStyleSheet(
            f"color: {FG2}; font-size: 14px; "
            f"border: 2px dashed {BG3}; border-radius: 8px; "
            f"padding: 20px; margin: 8px;"
        )

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                paths.append(path)

        if paths:
            event.acceptProposedAction()
            self.images_dropped.emit(paths)
