"""슬롯 상세 리스트 테이블 위젯."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

from src.ui.theme import BG2, GREEN, ORANGE


class SlotDetailTable(QTableWidget):
    slot_selected = Signal(int)  # slot_index

    def __init__(self, parent=None, show_serial: bool = False, name_header: str = "Probe Type"):
        super().__init__(parent)
        self._slot_indices: list[int] = []
        self._show_serial = show_serial

        # 컬럼 구성: 옵션 시 Serial 추가, 이름 헤더는 모드별("Probe Type"/"Tip Name")
        cols = ["#"]
        if show_serial:
            cols.append("Serial")
        cols += [name_header, "Freq", "Q", "QR ID", "Status"]
        self._columns = cols
        self._name_col = cols.index(name_header)
        self._qr_col = cols.index("QR ID")
        self._status_col = len(cols) - 1

        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(cols)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(f"QTableWidget {{ alternate-background-color: {BG2}; }}")

        header = self.horizontalHeader()
        for i in range(len(cols)):
            if i in (self._name_col, self._qr_col):
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.currentCellChanged.connect(self._on_current_changed)

    def load_slots(self, slots, default_probe: str = ""):
        """모든 슬롯 데이터 로드 (QR 미매칭 포함). show_serial 이면 시리얼 기준 정렬·그룹."""
        self._slot_indices.clear()

        rows = list(slots)
        if self._show_serial:
            rows.sort(key=lambda s: ((s.serial_number or ""), s.slot_index))

        self.setRowCount(len(rows))

        for row_idx, slot in enumerate(rows):
            self._slot_indices.append(slot.slot_index)
            probe = slot.probe_type or default_probe or "-"

            # 누락 항목 계산 (컨택 모드는 freq/Q 불필요)
            missing = []
            if not getattr(slot, "contact_mode", False):
                if slot.frequency is None:
                    missing.append("Freq")
                if slot.q_factor is None:
                    missing.append("Q")
            if slot.qr_id is None:
                missing.append("QR")

            is_complete = slot.is_complete
            status_text = "Complete" if is_complete else ",".join(missing)
            color = GREEN if is_complete else ORANGE

            cells = [str(slot.slot_index + 1)]
            if self._show_serial:
                cells.append(slot.serial_number or "-")
            cells += [
                probe,
                slot.format_frequency(),
                slot.format_q(),
                slot.qr_id or "-",
                status_text,
            ]

            for col_idx, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(Qt.GlobalColor.white)
                if col_idx == self._status_col:
                    item.setForeground(QColor(color))
                self.setItem(row_idx, col_idx, item)

    def _on_current_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int):
        if 0 <= row < len(self._slot_indices):
            self.slot_selected.emit(self._slot_indices[row])
