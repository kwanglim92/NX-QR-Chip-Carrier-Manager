"""Inspection 템플릿 새로 만들기 다이얼로그 — Tip ID 입력 + 복사 원본 선택."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_LABEL = "(기본값 AC160)"


class NewTemplateDialog(QDialog):
    """OK 시 ``result()`` 로 ``(tip_id, source_tip_id | None)`` 반환."""

    def __init__(self, existing: list[str], parent: QWidget | None = None,
                 tip_suggestions: list[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("새 검사 템플릿")
        self.setModal(True)
        self._existing = list(existing)
        self._result: tuple[str, str | None] | None = None

        outer = QVBoxLayout(self)
        form = QFormLayout()
        self._tip = QComboBox()
        self._tip.setEditable(True)
        for name in (tip_suggestions or []):
            if name not in existing:
                self._tip.addItem(name)
        self._tip.setCurrentText("")
        self._tip.lineEdit().setPlaceholderText("예: AC240")
        form.addRow("Tip ID:", self._tip)

        self._source = QComboBox()
        self._source.addItem(_DEFAULT_LABEL, None)
        for name in existing:
            self._source.addItem(name, name)
        form.addRow("복사 원본:", self._source)
        outer.addLayout(form)
        outer.addWidget(QLabel("복사 원본의 등급별 임계값을 새 Tip ID 로 복제합니다."))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_accept(self) -> None:
        tip = self._tip.currentText().strip()
        if not tip:
            QMessageBox.warning(self, "입력 오류", "Tip ID 를 입력하세요.")
            return
        if tip in self._existing:
            QMessageBox.warning(self, "입력 오류", f"'{tip}' 템플릿이 이미 있습니다.")
            return
        self._result = (tip, self._source.currentData())
        self.accept()

    def result_template(self) -> tuple[str, str | None] | None:
        return self._result
