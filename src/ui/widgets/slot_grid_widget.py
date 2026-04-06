"""ATX 슬롯 그리드 위젯 — Port별 섹션 분리, 스크롤 지원."""
from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QVBoxLayout, QFrame,
    QScrollArea, QSizePolicy,
)

from src.core.models import MeasurementSet, SlotData
from src.core.slot_mapper import parse_slot_code, slot_to_grid, grid_to_slot
from src.ui.theme import FG2, ACCENT, BG, BG3, PURPLE
from src.ui.widgets.measurement_card import MeasurementCard


class SlotGridWidget(QWidget):
    slot_clicked = Signal(int)  # slot_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[int, MeasurementCard] = {}
        self._selected_index: int = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("ATX 슬롯 그리드")
        self._title.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 14px;")
        outer.addWidget(self._title)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG}; }}")
        outer.addWidget(scroll, 1)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        scroll.setWidget(self._content)

    def load_measurement_set(self, ms: MeasurementSet):
        self._clear()

        if not ms.slots:
            return

        # Port별 슬롯 그룹핑
        port_groups: dict[int, list[SlotData]] = defaultdict(list)
        atx_num = None
        for slot in ms.slots:
            try:
                info = parse_slot_code(slot.slot_code)
                atx_num = info["atx"]
                port_groups[info["port"]].append((info["slot"], slot))
            except (ValueError, IndexError):
                port_groups[0].append((slot.slot_index + 1, slot))

        ports_str = ", ".join(f"Port{p}" for p in sorted(port_groups) if p > 0)
        self._title.setText(f"ATX{atx_num} {ports_str} — {ms.po_number}")

        # Port별 섹션 생성
        for port_num in sorted(port_groups):
            self._add_port_section(port_num, port_groups[port_num])

        self._content_layout.addStretch()

    def _add_port_section(self, port_num: int, slots: list[tuple[int, SlotData]]):
        # Port 헤더
        header = QLabel(f"  Port {port_num}")
        header.setStyleSheet(
            f"color: {PURPLE}; font-weight: bold; font-size: 13px; "
            f"padding: 4px 0;"
        )
        self._content_layout.addWidget(header)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {BG3};")
        self._content_layout.addWidget(line)

        # 4×3 그리드
        grid = QGridLayout()
        grid.setSpacing(6)

        # 슬롯을 물리적 위치에 배치
        occupied = set()
        for slot_num, slot in slots:
            row, col = slot_to_grid(slot_num)
            occupied.add((row, col))

            card = MeasurementCard(slot.slot_index, slot.slot_code, self)
            card.update_data(
                frequency=slot.frequency,
                q_factor=slot.q_factor,
                drive=slot.drive,
                qr_id=slot.qr_id,
            )
            card.clicked.connect(self._on_card_clicked)
            grid.addWidget(card, row, col)
            self._cards[slot.slot_index] = card

        # 빈 셀 (사용하지 않는 슬롯) 플레이스홀더
        for r in range(3):
            for c in range(4):
                if (r, c) not in occupied:
                    slot_num = grid_to_slot(r, c)
                    ph = QLabel(f"Slot {slot_num}")
                    ph.setAlignment(Qt.AlignCenter)
                    ph.setFixedHeight(140)
                    ph.setMinimumWidth(170)
                    ph.setStyleSheet(
                        f"color: {FG2}; font-size: 15px; "
                        f"border: 1px dashed {BG3}; border-radius: 6px;"
                    )
                    grid.addWidget(ph, r, c)

        self._content_layout.addLayout(grid)

    def update_slot(self, slot: SlotData):
        card = self._cards.get(slot.slot_index)
        if card:
            card.update_data(
                frequency=slot.frequency,
                q_factor=slot.q_factor,
                drive=slot.drive,
                qr_id=slot.qr_id,
            )

    def select_slot(self, slot_index: int):
        if self._selected_index >= 0 and self._selected_index in self._cards:
            self._cards[self._selected_index].set_selected(False)
        self._selected_index = slot_index
        if slot_index in self._cards:
            self._cards[slot_index].set_selected(True)

    def _on_card_clicked(self, slot_index: int):
        self.select_slot(slot_index)
        self.slot_clicked.emit(slot_index)

    def _clear(self):
        self._cards.clear()
        self._selected_index = -1
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
