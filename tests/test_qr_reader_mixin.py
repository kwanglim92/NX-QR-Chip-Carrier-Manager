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
    # 자동 접속이 기본 켜짐이므로, 테스트가 실기기 IP 로 나가지 않도록 기본은 꺼 둔다(필요한 테스트는 다시 저장)
    save_qr_reader_settings(db_conn, {"enabled": False})
    h = _Host(db_conn)
    yield h
    h._shutdown_qr_reader()


def test_init_with_auto_connect_off_shows_not_in_use(host):
    host._init_qr_reader()
    assert host._reader.state.value == "disconnected"
    assert not host._reader_in_use
    assert not host.btn_cassette_scan.isEnabled()
    assert "사용 안함" in host.btn_reader_status.text()
    assert "미연결" not in host.btn_reader_status.text()
    assert host._last_frame is None


def test_init_default_auto_connects(host, db_conn):
    """저장된 설정에 enabled 가 없어도(기본값) 앱 시작 시 접속을 시도한다."""
    server = FakeReader()
    save_qr_reader_settings(db_conn, {"host": "127.0.0.1", "port": server.serverPort()})
    assert load_qr_reader_settings(db_conn)["enabled"] is True
    host._init_qr_reader()
    assert host._reader.state.value != "disconnected"
    assert wait_until(host._reader.is_connected)
    assert host.btn_cassette_scan.isEnabled()
    server.close()


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


class _NoSig:
    def connect(self, *_): pass


def _dialog_stub(new: dict):
    """실제 다이얼로그 대신 저장(Accepted)만 흉내 — 믹스인이 연결하는 시그널 3종을 더미로 제공."""
    class _Dlg:
        def __init__(self, *a, **k):
            assert "reader_in_use" in k           # 믹스인은 현재 사용 여부를 창에 넘긴다
            self.rotation_applied = _NoSig()
            self.disconnect_requested = _NoSig()
            self.connect_requested = _NoSig()
        def exec(self): return 1          # QDialog.Accepted
        def deleteLater(self): pass
        def result_settings(self): return new
    return _Dlg


def test_settings_dialog_save_reapplies_client_while_in_use(host, db_conn, monkeypatch):
    """사용 중(접속됨) 에 저장 → 새 설정(포트·판독 시간)으로 재접속."""
    first, second = FakeReader(), FakeReader()
    save_qr_reader_settings(db_conn, {"enabled": True, "host": "127.0.0.1", "port": first.serverPort()})
    host._init_qr_reader()
    assert wait_until(host._reader.is_connected) and host._reader_in_use

    new = {"enabled": True, "host": "127.0.0.1", "port": second.serverPort(), "read_seconds": 1.5}
    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QRReaderSettingsDialog", _dialog_stub(new))
    host._open_qr_reader_settings()
    assert load_qr_reader_settings(db_conn)["port"] == second.serverPort()
    assert host._reader.port == second.serverPort() and host._reader._read_seconds == 1.5
    assert wait_until(host._reader.is_connected)
    assert wait_until(lambda: len(second.clients) == 1)
    assert ("ok", "리더기 설정이 저장되었습니다") in host.logger.lines   # 사용 중이므로 접미 문구 없음
    first.close(); second.close()


def test_saving_while_not_in_use_does_not_connect(host, db_conn, monkeypatch):
    """사용 안함(자동 접속 꺼짐으로 시작) 상태에서 저장 → 설정만 저장, 접속하지 않음."""
    server = FakeReader()
    host._init_qr_reader()
    assert not host._reader_in_use
    new = {"enabled": False, "host": "127.0.0.1", "port": server.serverPort()}

    monkeypatch.setattr("src.ui.dialogs.qr_reader_settings_dialog.QRReaderSettingsDialog", _dialog_stub(new))
    host._open_qr_reader_settings()
    assert load_qr_reader_settings(db_conn)["port"] == server.serverPort()
    assert host._reader.state.value == "disconnected" and not host._reader_in_use
    assert not wait_until(lambda: len(server.clients) > 0, 500)   # 접속 시도 없음
    assert "사용 안함" in host.btn_reader_status.text()
    assert host.logger.lines[-1][0] == "ok" and "사용 안함" in host.logger.lines[-1][1]
    server.close()


def test_disconnect_stops_reconnect_and_shows_not_in_use(host, db_conn):
    server = FakeReader()
    save_qr_reader_settings(db_conn, {"enabled": True, "host": "127.0.0.1", "port": server.serverPort()})
    host._init_qr_reader()
    assert wait_until(host._reader.is_connected) and host._reader_in_use

    host._disconnect_reader()
    assert not host._reader_in_use
    assert host._reader.state.value == "disconnected"
    assert "사용 안함" in host.btn_reader_status.text()
    assert not host.btn_cassette_scan.isEnabled()
    assert host.logger.lines[-1] == ("info", "리더기 연결 해제 — 사용 안함 (재접속하지 않음)")
    # 서버가 살아 있어도 재접속하지 않는다
    assert not wait_until(lambda: host._reader.state.value != "disconnected", 700)
    server.close()


def test_connect_requested_saves_and_connects(host, db_conn):
    server = FakeReader()
    host._init_qr_reader()
    assert not host._reader_in_use

    host._connect_reader({"enabled": False, "host": "127.0.0.1", "port": server.serverPort(), "read_seconds": 2.0})
    assert host._reader_in_use
    loaded = load_qr_reader_settings(db_conn)
    assert loaded["port"] == server.serverPort() and loaded["read_seconds"] == 2.0 and loaded["enabled"] is False
    assert wait_until(host._reader.is_connected)
    assert "연결됨" in host.btn_reader_status.text() and host.btn_cassette_scan.isEnabled()
    assert any(k == "info" and m.startswith("리더기 연결 — 127.0.0.1:") for k, m in host.logger.lines)
    server.close()


def test_connect_requested_with_non_lan_transport_warns(host):
    host._init_qr_reader()
    host._connect_reader({"transport": "keyboard"})
    assert not host._reader_in_use and host._reader.state.value == "disconnected"
    assert host.logger.lines[-1][0] == "warn" and "LAN" in host.logger.lines[-1][1]
    assert "사용 안함" in host.btn_reader_status.text()


def test_connect_loads_reader_regions_for_review_layout(host, db_conn):
    server = FakeReader()
    save_qr_reader_settings(db_conn, {"enabled": True, "host": "127.0.0.1", "port": server.serverPort()})
    host._init_qr_reader()
    assert wait_until(lambda: len(host._reader_regions) == 72, 5000)
    assert server.received[:2] == ["RD,001", "RD,002"]
    layout = host._boat_layout()
    assert not layout.schematic and layout.rotation == 270
    assert layout.port_positions[1] == (0, 0) and layout.port_positions[2] == (0, 1) and layout.port_positions[6] == (2, 1)
    assert any("서치 영역 72개" in m for _, m in host.logger.lines)
    server.close()


def test_save_preview_rotation_persists_only_rotation(host, db_conn):
    save_qr_reader_settings(db_conn, {"enabled": False, "host": "10.0.0.7", "read_seconds": 2.5})
    host._init_qr_reader()
    host._save_preview_rotation(90)
    loaded = load_qr_reader_settings(db_conn)
    assert loaded["preview_rotation"] == 90 and loaded["host"] == "10.0.0.7" and loaded["read_seconds"] == 2.5
    assert host._qr_reader_settings["preview_rotation"] == 90 and host._boat_layout().rotation == 90
    assert host.logger.lines[-1][0] == "ok" and "90°" in host.logger.lines[-1][1]


def test_shutdown_closes_reader(host, db_conn):
    server = FakeReader()
    save_qr_reader_settings(db_conn, {"enabled": True, "host": "127.0.0.1", "port": server.serverPort()})
    host._init_qr_reader()
    assert wait_until(host._reader.is_connected)
    host._shutdown_qr_reader()
    assert host._reader.state.value == "disconnected"
    server.close()
