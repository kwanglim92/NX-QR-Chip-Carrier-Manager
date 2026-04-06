"""CSV 미리보기 테이블 (Ctrl+C 복사 지원)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QApplication, QHeaderView


class CSVPreviewTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)

    def load_rows(self, rows: list[list[str]]):
        if not rows:
            self.clear()
            return

        header = rows[0]
        data = rows[1:]

        self.setColumnCount(len(header))
        self.setRowCount(len(data))
        self.setHorizontalHeaderLabels(header)

        for r, row in enumerate(data):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.setItem(r, c, item)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            selected = self.selectedRanges()
            if not selected:
                return
            sel = selected[0]
            text = ""
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                row_data = []
                for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                    item = self.item(row, col)
                    row_data.append(item.text() if item else "")
                text += "\t".join(row_data) + "\n"
            QApplication.clipboard().setText(text)
        else:
            super().keyPressEvent(event)
