"""Add Tab 다이얼로그 — 시리얼 번호 + Tip 이름(관리형 카탈로그 검색·선택)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.dialogs.tip_catalog_dialog import TipCatalogDialog


class AddTabDialog(QDialog):
    """탭 생성 입력: 고유 시리얼 + 카탈로그 Tip 이름.

    같은 Tip 이름이라도 시리얼이 다르면 새 탭을 만들 수 있다(중복 검사는 시리얼 기준).
    검색은 부분일치·대소문자 무시 자동완성으로 제공.
    """

    def __init__(
        self,
        catalog: list[str],
        existing_serials,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("탭 추가")
        self.setModal(True)
        self.resize(360, 150)

        self._catalog = list(catalog)
        self._existing_serials = set(existing_serials)
        self._catalog_changed = False
        self._serial = ""
        self._tip = ""

        outer = QVBoxLayout(self)
        form = QFormLayout()

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("예: P2601002")
        form.addRow("시리얼 번호:", self.serial_input)

        tip_row = QHBoxLayout()
        self.tip_combo = QComboBox()
        self.tip_combo.setEditable(True)
        self.tip_combo.setInsertPolicy(QComboBox.NoInsert)
        self.tip_combo.lineEdit().setPlaceholderText("Tip 이름 검색·선택")
        tip_row.addWidget(self.tip_combo, 1)

        self.btn_manage = QPushButton("관리…")
        self.btn_manage.setToolTip("Tip 카탈로그 추가/삭제")
        self.btn_manage.clicked.connect(self._open_manage)
        tip_row.addWidget(self.btn_manage)
        form.addRow("Tip 이름:", tip_row)

        # 측정 모드: 일반(Test) / 컨택(QR-only)
        mode_row = QHBoxLayout()
        self.radio_normal = QRadioButton("일반 (Test)")
        self.radio_normal.setChecked(True)
        self.radio_contact = QRadioButton("컨택 (QR-only)")
        self.radio_contact.setToolTip(
            "테스트 없이 QR만 작성 — 이미지·주파수·Q 입력 생략"
        )
        mode_row.addWidget(self.radio_normal)
        mode_row.addWidget(self.radio_contact)
        mode_row.addStretch()
        form.addRow("측정 모드:", mode_row)

        outer.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        outer.addWidget(self._buttons)

        self._populate_combo()
        self.serial_input.setFocus()

    def _populate_combo(self) -> None:
        current = self.tip_combo.currentText()
        self.tip_combo.clear()
        self.tip_combo.addItems(self._catalog)
        completer = self.tip_combo.completer()
        if completer is not None:
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
        self.tip_combo.setCurrentIndex(-1)
        self.tip_combo.setEditText(current)

    def _open_manage(self) -> None:
        dlg = TipCatalogDialog(self._catalog, self)
        if dlg.exec() == QDialog.Accepted:
            self._catalog = dlg.result_catalog()
            self._catalog_changed = True
            self._populate_combo()

    def _on_accept(self) -> None:
        serial = self.serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "입력 필요", "시리얼 번호를 입력하세요.")
            self.serial_input.setFocus()
            return
        if serial in self._existing_serials:
            QMessageBox.warning(
                self, "중복", f"시리얼 '{serial}' 탭이 이미 존재합니다."
            )
            self.serial_input.setFocus()
            self.serial_input.selectAll()
            return

        tip = self.tip_combo.currentText().strip()
        if not tip:
            QMessageBox.warning(self, "입력 필요", "Tip 이름을 선택하거나 입력하세요.")
            self.tip_combo.setFocus()
            return
        if tip not in self._catalog:
            reply = QMessageBox.question(
                self,
                "카탈로그에 없음",
                f"'{tip}' 은(는) 카탈로그에 없습니다. 추가할까요?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.tip_combo.setFocus()
                return
            self._catalog.append(tip)
            self._catalog_changed = True

        self._serial = serial
        self._tip = tip
        self.accept()

    # ── 결과 접근자 ──
    def result_serial(self) -> str:
        return self._serial

    def result_tip(self) -> str:
        return self._tip

    def result_contact_mode(self) -> bool:
        return self.radio_contact.isChecked()

    def result_catalog(self) -> list[str]:
        return list(self._catalog)

    def catalog_changed(self) -> bool:
        return self._catalog_changed
