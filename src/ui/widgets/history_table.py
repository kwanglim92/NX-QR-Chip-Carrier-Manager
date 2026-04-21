"""이력 목록 테이블 위젯 — 체크박스 다중 선택."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

from src.ui.theme import GREEN, ORANGE, RED, FG2

COLUMNS = ["", "Week", "Date", "PO Number", "Probe Type", "Mode", "Slots", "Upload"]
COL_CHECK = 0


class HistoryTable(QTableWidget):
    row_selected = Signal(int)        # measurement_set id (clicked row)
    selection_changed = Signal(int)   # count of checked rows

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ms_ids: list[int] = []

        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("QTableWidget { alternate-background-color: #24243a; }")

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)             # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Week
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # PO
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Probe
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Mode
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Slots
        header.setSectionResizeMode(7, QHeaderView.Stretch)           # Upload (나머지 공간)
        self.setColumnWidth(0, 32)

        self.itemChanged.connect(self._on_item_changed)
        self.itemSelectionChanged.connect(self._on_row_clicked)

    def load_data(self, records: list[dict]):
        """이력 데이터 로드."""
        self.blockSignals(True)
        self._ms_ids.clear()
        self.setRowCount(len(records))

        for row_idx, rec in enumerate(records):
            self._ms_ids.append(rec["id"])

            # 체크박스
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.setItem(row_idx, COL_CHECK, chk)

            data_items = [
                rec.get("iso_week", ""),
                rec.get("production_date", ""),
                rec.get("po_number", ""),
                rec.get("probe_type", ""),
                rec.get("mode", "").upper(),
                f"{rec.get('complete_slots', 0)}/{rec.get('total_slots', 0)}",
                self._upload_symbol(rec.get("upload_status", "pending")),
            ]

            for col_idx, text in enumerate(data_items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignCenter)

                if col_idx == 6:  # Upload
                    status = rec.get("upload_status", "pending")
                    if status == "uploaded":
                        item.setForeground(Qt.GlobalColor.green)
                    elif status == "failed":
                        item.setForeground(Qt.GlobalColor.red)

                self.setItem(row_idx, col_idx + 1, item)

        self.blockSignals(False)
        self.selection_changed.emit(0)

    def get_selected_ms_id(self) -> int | None:
        """클릭된 행의 measurement_set id (Load Record용)."""
        rows = self.selectionModel().selectedRows()
        if not rows:
            return None
        row_idx = rows[0].row()
        if 0 <= row_idx < len(self._ms_ids):
            return self._ms_ids[row_idx]
        return None

    def get_checked_ms_ids(self) -> list[int]:
        """체크된 모든 행의 measurement_set id."""
        ids = []
        for row in range(self.rowCount()):
            chk = self.item(row, COL_CHECK)
            if chk and chk.checkState() == Qt.Checked:
                if 0 <= row < len(self._ms_ids):
                    ids.append(self._ms_ids[row])
        return ids

    def get_checked_count(self) -> int:
        """체크된 행 수."""
        count = 0
        for row in range(self.rowCount()):
            chk = self.item(row, COL_CHECK)
            if chk and chk.checkState() == Qt.Checked:
                count += 1
        return count

    def check_all(self):
        """모든 행 체크."""
        self.blockSignals(True)
        for row in range(self.rowCount()):
            chk = self.item(row, COL_CHECK)
            if chk:
                chk.setCheckState(Qt.Checked)
        self.blockSignals(False)
        self.selection_changed.emit(self.get_checked_count())

    def uncheck_all(self):
        """모든 체크 해제."""
        self.blockSignals(True)
        for row in range(self.rowCount()):
            chk = self.item(row, COL_CHECK)
            if chk:
                chk.setCheckState(Qt.Unchecked)
        self.blockSignals(False)
        self.selection_changed.emit(0)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == COL_CHECK:
            self.selection_changed.emit(self.get_checked_count())

    def _on_row_clicked(self):
        ms_id = self.get_selected_ms_id()
        if ms_id is not None:
            self.row_selected.emit(ms_id)

    @staticmethod
    def _upload_symbol(status: str) -> str:
        if status == "uploaded":
            return "Done"
        elif status == "failed":
            return "Fail"
        return "-"
