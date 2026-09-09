"""R4-b: 리더기 설정 다이얼로그 — 폼 ↔ 설정 dict, 검증, 연결 테스트/테스트 판독(인프로세스 가짜 리더기)."""
from __future__ import annotations

import pytest

from src.ui.dialogs.qr_reader_settings_dialog import SECTIONS, QRReaderSettingsDialog, _FormError
from tests.test_qr_reader_client import FakeReader, wait_until


@pytest.fixture
def dialog(qapp):
    dlg = QRReaderSettingsDialog({"host": "192.168.100.2", "port": 9004, "cell_override": {5: (2, 3)}})
    yield dlg
    dlg.close()


def test_form_is_populated_from_settings(dialog):
    assert dialog.host_input.text() == "192.168.100.2"
    assert dialog.port_spin.value() == 9004
    assert dialog.read_spin.value() == 6.0
    assert dialog.count_spin.value() == 72 and dialog.ng_input.text() == "ERROR"
    assert dialog.override_table.rowCount() == 1
    assert [dialog.override_table.item(0, c).text() for c in range(3)] == ["5", "2", "3"]


def test_result_settings_round_trip(dialog):
    dialog.host_input.setText(" 10.1.2.3 ")
    dialog.port_spin.setValue(9100)
    dialog.read_spin.setValue(3.5)
    dialog.enabled_check.setChecked(True)
    dialog._append_override_row(7, 1, 12)
    s = dialog.result_settings()
    assert s["host"] == "10.1.2.3" and s["port"] == 9100 and s["read_seconds"] == 3.5
    assert s["enabled"] is True and s["transport"] == "lan"
    assert s["cell_override"] == {5: (2, 3), 7: (1, 12)}


def test_blank_override_rows_are_ignored(dialog):
    dialog._append_override_row()
    assert dialog.result_settings()["cell_override"] == {5: (2, 3)}


@pytest.mark.parametrize("row,msg", [
    (("a", "1", "1"), "정수"),
    (("6", "0", "1"), "Slot 1~12"),
    (("6", "1", "13"), "Slot 1~12"),
    (("5", "1", "1"), "두 번"),
    (("9", "2", "3"), "함께 가리킵니다"),
])
def test_invalid_override_rows_raise(dialog, row, msg):
    dialog._append_override_row(*row)
    with pytest.raises(_FormError, match=msg):
        dialog._collect()


def test_invalid_ng_token_and_empty_host_raise(dialog):
    dialog.ng_input.setText("ER")
    with pytest.raises(_FormError, match="NG 문자열"):
        dialog._collect()
    dialog.ng_input.setText("ERROR")
    dialog.host_input.setText("  ")
    with pytest.raises(_FormError, match="IP 주소"):
        dialog._collect()


def test_remove_selected_rows(dialog):
    dialog._append_override_row(8, 1, 1)
    dialog.override_table.selectRow(0)
    dialog._remove_selected_override_rows()
    assert dialog.override_table.rowCount() == 1
    assert dialog.override_table.item(0, 0).text() == "8"


def test_connection_test_against_fake_reader(qapp):
    server = FakeReader()
    dlg = QRReaderSettingsDialog({"host": "127.0.0.1", "port": server.serverPort()})
    dlg._test_connection()
    assert not dlg.btn_test_conn.isEnabled()
    assert wait_until(lambda: "FAKE-SR-X300" in dlg.status_label.text())
    assert dlg.status_label.text().startswith("연결됨")
    assert dlg.btn_test_conn.isEnabled() and dlg._test_client is None
    assert wait_until(lambda: server.received == ["KEYENCE"])
    dlg.close()
    server.close()


def test_read_test_against_fake_reader(qapp):
    server = FakeReader()
    dlg = QRReaderSettingsDialog({"host": "127.0.0.1", "port": server.serverPort(), "read_seconds": 0.2})
    dlg._test_read()
    assert wait_until(lambda: dlg.status_label.text().startswith("판독 70/72"), 4000)
    assert "NG 2칸 (13, 14)" in dlg.status_label.text() and "6064 ms" in dlg.status_label.text()
    assert server.received == ["LON", "LOFF"]
    assert dlg._test_client is None
    dlg.close()
    server.close()


def test_read_test_reports_command_error(qapp):
    server = FakeReader(er23=True)
    dlg = QRReaderSettingsDialog({"host": "127.0.0.1", "port": server.serverPort(), "read_seconds": 0.2})
    dlg._test_read()
    assert wait_until(lambda: "ER,LON,23" in dlg.status_label.text())
    assert dlg._test_client is None
    dlg.close()
    server.close()


def test_accept_during_connection_test_cleans_up_client(qapp):
    server = FakeReader(silent=True)                 # 접속은 받되 응답 없음
    dlg = QRReaderSettingsDialog({"host": "127.0.0.1", "port": server.serverPort()})
    dlg._test_connection()
    assert wait_until(lambda: len(server.clients) == 1)
    assert dlg._test_client is not None and dlg._test_timer.isActive()
    dlg._on_accept()                                 # 저장
    assert dlg._test_client is None and not dlg._test_timer.isActive()
    assert dlg.result() == 1
    server.close()


def test_hidden_timeout_settings_survive_save(qapp):
    dlg = QRReaderSettingsDialog({"result_timeout_s": 42.0, "connect_timeout_s": 7.5})
    s = dlg.result_settings()
    assert s["result_timeout_s"] == 42.0 and s["connect_timeout_s"] == 7.5
    dlg.close()


def test_tests_refused_for_non_lan_transport(qapp, monkeypatch):
    dlg = QRReaderSettingsDialog({"transport": "keyboard"})
    shown = []
    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QMessageBox.information",
                        lambda *a, **k: shown.append(a[2]))
    dlg._test_connection()
    dlg._test_read()
    assert len(shown) == 2 and "LAN" in shown[0] and dlg._test_client is None
    dlg.close()


def test_test_is_refused_when_form_invalid(qapp, monkeypatch):
    dlg = QRReaderSettingsDialog({})
    dlg.host_input.setText("")
    shown = []
    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QMessageBox.warning",
                        lambda *a, **k: shown.append(a[2]))
    dlg._test_connection()
    assert shown and "IP 주소" in shown[0]
    assert dlg._test_client is None
    dlg.close()


# ─── TOC 사이드바 ↔ 본문 스크롤 ───

def test_sidebar_lists_sections_and_scrolls_to_them(qapp):
    dlg = QRReaderSettingsDialog({})
    dlg.show()
    qapp.processEvents()
    assert dlg.nav.count() == len(SECTIONS) == 4
    assert dlg.nav.title(0).startswith("1.  연결") and dlg.nav.title(3).startswith("4.  리더기 현재 값")
    assert dlg.nav.currentRow() == 0 and dlg.current_section() == "conn"

    dlg.go_to("params")
    qapp.processEvents()
    assert dlg.scroll.verticalScrollBar().value() > 0
    assert dlg.current_section() == "params" and dlg.nav.currentRow() == 3

    dlg.scroll.verticalScrollBar().setValue(0)      # 본문을 직접 스크롤하면 사이드바가 따라온다
    qapp.processEvents()
    assert dlg.nav.currentRow() == 0
    dlg.close()


def test_form_error_jumps_to_related_section(qapp, monkeypatch):
    dlg = QRReaderSettingsDialog({})
    dlg.show()
    qapp.processEvents()
    shown = []
    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QMessageBox.warning",
                        lambda *a, **k: shown.append(a[2]))
    dlg.ng_input.setText("ER")
    dlg._on_accept()
    assert dlg.result() == 0 and "NG 문자열" in shown[-1] and dlg.nav.currentRow() == 1

    dlg.ng_input.setText("ERROR")
    dlg._append_override_row("x", "1", "1")
    dlg._on_accept()
    assert "정수" in shown[-1] and dlg.nav.currentRow() == 2
    dlg.close()


def test_action_buttons_live_in_their_sections(qapp):
    dlg = QRReaderSettingsDialog({})
    assert dlg.btn_test_conn.parent() is dlg.sections["conn"]
    assert dlg.btn_test_read.parent() is dlg.sections["read"] and dlg.btn_preview.parent() is dlg.sections["read"]
    assert dlg.btn_read_params.parent() is dlg.sections["params"]
    dlg.close()
