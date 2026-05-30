"""품질 규격(Spec) 한계 편집 다이얼로그 — Probe Type별 Freq/Q min·max."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_COLS = ["Probe Type", "Freq Min", "Freq Max", "Q Min", "Q Max"]
_FIELD_BY_COL = {1: "freq_min", 2: "freq_max", 3: "q_min", 4: "q_max"}


class _SpecError(Exception):
    """규격 입력 검증 실패."""


def _fmt(value) -> str:
    """저장값을 셀 텍스트로. 정수면 소수점 제거."""
    f = float(value)
    return str(int(f)) if f == int(f) else str(f)


class SpecLimitsDialog(QDialog):
    """Probe Type별 Frequency / Q 규격 상·하한 편집.

    빈 칸은 '제한 없음'(None)으로 처리된다. OK 시 ``result_spec_limits()`` 로
    ``{probe_type: {freq_min, freq_max, q_min, q_max}}`` 를 반환한다(경계가 하나도
    없는 probe 는 제외).
    """

    def __init__(self, probe_types: list[str], spec_limits: dict,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("품질 규격(Spec) 설정")
        self.setModal(True)
        self.resize(540, 420)

        spec_limits = spec_limits or {}
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(
            "Probe Type별 Frequency / Q 규격 상·하한을 입력하세요.\n"
            "빈 칸은 '제한 없음'으로 처리됩니다."
        ))

        self._table = QTableWidget(len(probe_types), len(_COLS))
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.verticalHeader().setVisible(False)
        for row, pt in enumerate(probe_types):
            pt_item = QTableWidgetItem(pt)
            pt_item.setFlags(pt_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 0, pt_item)
            spec = spec_limits.get(pt) or {}
            for col, field in _FIELD_BY_COL.items():
                val = spec.get(field)
                text = "" if val is None else _fmt(val)
                self._table.setItem(row, col, QTableWidgetItem(text))
        self._table.resizeColumnsToContents()
        outer.addWidget(self._table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_accept(self) -> None:
        try:
            self._parse(validate=True)
        except _SpecError as exc:
            QMessageBox.warning(self, "규격 입력 오류", str(exc))
            return
        self.accept()

    def _parse(self, validate: bool) -> dict:
        result: dict = {}
        for row in range(self._table.rowCount()):
            pt_item = self._table.item(row, 0)
            if pt_item is None:
                continue
            pt = pt_item.text().strip()
            if not pt:
                continue
            entry: dict = {}
            has_bound = False
            for col, field in _FIELD_BY_COL.items():
                cell = self._table.item(row, col)
                text = cell.text().strip() if cell else ""
                if not text:
                    entry[field] = None
                    continue
                try:
                    entry[field] = float(text)
                    has_bound = True
                except ValueError:
                    raise _SpecError(
                        f"'{pt}' 행의 '{_COLS[col]}' 값이 숫자가 아닙니다: {text!r}"
                    )
            if validate:
                if (entry["freq_min"] is not None and entry["freq_max"] is not None
                        and entry["freq_min"] > entry["freq_max"]):
                    raise _SpecError(f"'{pt}': Freq Min 이 Freq Max 보다 큽니다.")
                if (entry["q_min"] is not None and entry["q_max"] is not None
                        and entry["q_min"] > entry["q_max"]):
                    raise _SpecError(f"'{pt}': Q Min 이 Q Max 보다 큽니다.")
            if has_bound:
                result[pt] = entry
        return result

    def result_spec_limits(self) -> dict:
        return self._parse(validate=False)
