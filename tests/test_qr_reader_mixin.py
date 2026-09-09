"""R4-c: QRReaderMixin — 스텁 호스트(로거·버튼·in-memory DB)로 상태 칩, 스캔, 설정 저장 검증."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QPushButton

from src.core.qr_reader.settings import load_qr_reader_settings, save_qr_reader_settings
from src.ui.controllers.qr_reader_mixin import QRReaderMixin
from tests.test_qr_reader_client import FakeReader, wait_until


class _Logger:
    def __init__(self):
        self.lines: list[tuple[str, str]] = []

    def info(self, m): self.lines.append(("info", m))
    def ok(self, m): self.lines.append(("ok", m))
    def warn(self, m): self.lines.append(("warn", m))
    def error(self, m): self.lines.append(("error", m))


class _Host(QRReaderMixin, QObject):
    """메인 윈도 대신 믹스인이 필요로 하는 것만 갖춘 호스트."""

    def __init__(self, db_conn):
        super().__init__()
        self._db_conn = db_conn
        self.logger = _Logger()
        self.btn_reader_status = QPushButton()
        self.btn_cassette_scan = QPushButton()
        self.btn_cassette_scan.setEnabled(False)


@pytest.fixture
def host(qapp, db_conn):
    h = _Host(db_conn)
    yield h
    h._shutdown_qr_reader()


def test_init_without_enabled_stays_disconnected(host):
    host._init_qr_reader()
    assert host._reader.state.value == "disconnected"
    assert not host.btn_cassette_scan.isEnabled()
    assert "미연결" in host.btn_reader_status.text()
    assert host._last_frame is None


def test_enabled_lan_connects_and_scan_records_frame(host, db_conn):
    server = FakeReader()
    save_qr_reader_settings(db_conn, {"enabled": True, "host": "127.0.0.1", "port": server.serverPort(), "read_seconds": 0.2})
    host._init_qr_reader()
    assert wait_until(host._reader.is_connected)
    assert host.btn_cassette_scan.isEnabled()
    assert "연결됨" in host.btn_reader_status.text()

    host._scan_cassette()
    assert "판독 중" in host.btn_reader_status.text() or host._reader.is_reading()
    assert wait_until(lambda: host._last_frame is not None)
    assert len(host._last_frame.reads) == 72 and host._last_frame.ng_cells == [13, 14]
    assert any(k == "ok" and "70 판독" in m for k, m in host.logger.lines)
    assert host.btn_cassette_scan.isEnabled()
    server.close()


def test_scan_refused_when_not_connected(host):
    host._init_qr_reader()
    host._scan_cassette()
    assert host.logger.lines[-1][0] == "warn" and "연결되지" in host.logger.lines[-1][1]


def test_scan_refused_for_non_lan_transport(host, db_conn):
    save_qr_reader_settings(db_conn, {"transport": "keyboard", "enabled": True})
    host._init_qr_reader()
    assert host._reader.state.value == "disconnected"   # keyboard 폴백은 접속하지 않음
    host._scan_cassette()
    assert "LAN" in host.logger.lines[-1][1]


def test_command_error_23_is_explained(host):
    host._init_qr_reader()
    host._on_reader_command_error("LON", "23")
    assert "Navigator" in host.logger.lines[-1][1]


def test_settings_dialog_save_reapplies_client(host, db_conn, monkeypatch):
    server = FakeReader()
    host._init_qr_reader()
    assert host._reader.state.value == "disconnected"

    new = {"enabled": True, "host": "127.0.0.1", "port": server.serverPort(), "read_seconds": 1.5}

    class _Dlg:
        def __init__(self, *a, **k): pass
        def exec(self): return 1          # QDialog.Accepted
        def deleteLater(self): pass
        def result_settings(self): return new

    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QRReaderSettingsDialog", _Dlg)
    host._open_qr_reader_settings()
    assert load_qr_reader_settings(db_conn)["port"] == server.serverPort()
    assert host._reader.port == server.serverPort() and host._reader._read_seconds == 1.5
    assert wait_until(host._reader.is_connected)
    assert any(m.startswith("리더기 설정이 저장") for _, m in host.logger.lines)
    server.close()


def test_saving_lan_settings_connects_even_without_autoconnect(host, db_conn, monkeypatch):
    server = FakeReader()
    host._init_qr_reader()
    new = {"enabled": False, "host": "127.0.0.1", "port": server.serverPort()}

    class _Dlg:
        def __init__(self, *a, **k): pass
        def exec(self): return 1
        def deleteLater(self): pass
        def result_settings(self): return new

    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QRReaderSettingsDialog", _Dlg)
    host._open_qr_reader_settings()
    assert wait_until(host._reader.is_connected)        # 저장 = 즉시 접속
    assert load_qr_reader_settings(db_conn)["enabled"] is False   # 다음 앱 시작에는 자동 접속 안 함
    server.close()


def test_shutdown_closes_reader(host, db_conn):
    server = FakeReader()
    save_qr_reader_settings(db_conn, {"enabled": True, "host": "127.0.0.1", "port": server.serverPort()})
    host._init_qr_reader()
    assert wait_until(host._reader.is_connected)
    host._shutdown_qr_reader()
    assert host._reader.state.value == "disconnected"
    server.close()
