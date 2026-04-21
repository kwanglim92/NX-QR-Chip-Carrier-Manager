"""슬롯 상세 리스트 테이블 위젯."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

from src.ui.theme import GREEN, ORANGE, FG2


COLUMNS = ["#", "Probe Type", "Freq", "Q", "QR ID", "Status"]


class SlotDetailTable(QTableWidget):
    slot_selected = Signal(int)  # slot_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slot_indices: list[int] = []

        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("QTableWidget { alternate-background-color: #24243a; }")

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # #
        header.setSectionResizeMode(1, QHeaderView.Stretch)            # Probe Type
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Freq
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # Q
        header.setSectionResizeMode(4, QHeaderView.Stretch)            # QR ID
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)   # Status

        self.currentCellChanged.connect(self._on_current_changed)

    def load_slots(self, slots, default_probe: str = ""):
        """모든 슬롯 데이터 로드 (QR 미매칭 포함)."""
        self._slot_indices.clear()
        self.setRowCount(len(slots))

        for row_idx, slot in enumerate(slots):
            self._slot_indices.append(slot.slot_index)
            probe = slot.probe_type or default_probe or "-"

            # 누락 항목 계산
            missing = []
            if slot.frequency is None:
                missing.append("Freq")
            if slot.q_factor is None:
                missing.append("Q")
            if slot.qr_id is None:
                missing.append("QR")

            is_complete = slot.is_complete
            status_text = "Complete" if is_complete else ",".join(missing)
            color = GREEN if is_complete else ORANGE

            items = [
                str(slot.slot_index + 1),
                probe,
                slot.format_frequency(),
                slot.format_q(),
                slot.qr_id or "-",
                status_text,
            ]

            for col_idx, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(Qt.GlobalColor.white if is_complete
                                   else Qt.GlobalColor.white)
                # Status 열 색상
                if col_idx == 5:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(color))
                self.setItem(row_idx, col_idx, item)

    def _on_current_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int):
        if 0 <= row < len(self._slot_indices):
            self.slot_selected.emit(self._slot_indices[row])
