"""머지 내보내기 다이얼로그 — 여러 파트(시리얼)를 하나의 박스로 묶어 출력.

선택한 시리얼들의 슬롯을 모아 박스 시리얼 번호 이름의 단일 폴더/CSV로 내보내거나
업로드한다(박스 시리얼은 출력 폴더/파일명으로만 사용, 각 행 데이터는 그대로 유지).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class MergeExportDialog(QDialog):
    """파트(시리얼) 다중 선택 + 박스 시리얼 입력."""

    def __init__(self, parts: list[tuple[str, str, int]], parent=None):
        """parts: (serial, tip_name, card_count) 목록."""
        super().__init__(parent)
        self.setWindowTitle("머지 내보내기")
        self.setModal(True)
        self.resize(380, 420)

        self._checks: dict[str, QCheckBox] = {}
        self._box_serial = ""

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel("하나의 박스로 묶을 파트를 선택하세요:"))

        # 체크박스 목록 (스크롤)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        list_layout = QVBoxLayout(content)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(2)
        for serial, tip, count in parts:
            label = f"{tip} ({serial})  —  {count}장" if serial else f"{tip} (시리얼 없음)  —  {count}장"
            cb = QCheckBox(label)
            cb.setChecked(True)
            list_layout.addWidget(cb)
            self._checks[serial] = cb
        list_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        form = QFormLayout()
        self.box_input = QLineEdit()
        self.box_input.setPlaceholderText("예: BOX-20260530-01")
        form.addRow("박스 시리얼 번호:", self.box_input)
        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_accept(self):
        selected = [s for s, cb in self._checks.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "선택 필요", "묶을 파트를 하나 이상 선택하세요.")
            return
        box = self.box_input.text().strip()
        if not box:
            QMessageBox.warning(self, "입력 필요", "박스 시리얼 번호를 입력하세요.")
            self.box_input.setFocus()
            return
        self._box_serial = box
        self.accept()

    def selected_serials(self) -> set[str]:
        return {s for s, cb in self._checks.items() if cb.isChecked()}

    def box_serial(self) -> str:
        return self._box_serial
