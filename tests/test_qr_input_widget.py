"""QR 스캔 입력창 영문 고정 — 시스템 IME 가 한글이어도 바코드 문자가 한글로 조합되지 않게 IME 를 끈다."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from src.core.models import SlotData
from src.ui.dialogs.slot_edit_dialog import SlotEditDialog
from src.ui.widgets.qr_input_widget import QRInputWidget, force_latin_input


def _is_latin_only(edit: QLineEdit) -> bool:
    return (not edit.testAttribute(Qt.WA_InputMethodEnabled)
            and bool(edit.inputMethodHints() & Qt.ImhLatinOnly))


def test_force_latin_input_disables_ime_and_sets_hints(qapp):
    edit = QLineEdit()
    assert edit.testAttribute(Qt.WA_InputMethodEnabled)   # 기본 QLineEdit 은 IME 사용
    force_latin_input(edit)
    assert _is_latin_only(edit)
    assert edit.inputMethodHints() & Qt.ImhNoPredictiveText


def test_bottom_bar_qr_input_is_latin_only_and_still_emits(qapp):
    w = QRInputWidget()
    assert _is_latin_only(w._input)
    got = []
    w.qr_scanned.connect(got.append)
    w._input.setText("  ABC123 ")
    w._input.returnPressed.emit()
    assert got == ["ABC123"] and w._input.text() == ""


def test_slot_edit_dialog_qr_field_is_latin_only(qapp):
    dlg = SlotEditDialog(SlotData(slot_index=0, slot_code="1101", qr_id="XYZ"))
    assert _is_latin_only(dlg.qr_input) and dlg.qr_input.text() == "XYZ"
    dlg.close()
