"""R3: KeyenceClient ↔ 인프로세스 QTcpServer (실제 네트워크 접속 0건, localhost 만)."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from src.core.qr_reader.keyence_client import KeyenceClient, ReaderState
from src.core.qr_reader.payload_parser import ParsedFrame

FULL_RAW = Path(__file__).parent / "fixtures" / "qr_reader" / "20260909_132804_full.raw"
FULL_FRAME = FULL_RAW.read_bytes()


def wait_until(cond, timeout_ms: int = 3000) -> bool:
    """이벤트 루프를 돌리며 cond() 가 참이 될 때까지 대기."""
    loop = QEventLoop()
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll = QTimer()
    poll.setInterval(5)
    poll.timeout.connect(lambda: loop.quit() if cond() else None)
    deadline.start(timeout_ms)
    poll.start()
    while not cond() and deadline.isActive():
        loop.exec()
    poll.stop()
    return bool(cond())


class FakeReader(QTcpServer):
    """레벨 트리거를 흉내 내는 최소 서버. LON 대기 → LOFF 시 프레임 전송."""

    def __init__(self, frame: bytes = FULL_FRAME, fragment: bool = False, er23: bool = False,
                 immediate: bool = False, silent: bool = False):
        super().__init__()
        self.frame = frame
        self.fragment = fragment
        self.er23 = er23
        self.immediate = immediate
        self.silent = silent
        self.received: list[str] = []
        self.clients: list[QTcpSocket] = []
        self._buf: dict[QTcpSocket, bytes] = {}
        self._armed: dict[QTcpSocket, bool] = {}
        self.newConnection.connect(self._accept)
        assert self.listen(QHostAddress.SpecialAddress.LocalHost, 0)

    def _accept(self):
        while self.hasPendingConnections():
            s = self.nextPendingConnection()
            self.clients.append(s)
            self._buf[s] = b""
            self._armed[s] = False
            s.readyRead.connect(lambda s=s: self._read(s))

    def _read(self, s: QTcpSocket):
        self._buf[s] += bytes(s.readAll())
        while b"\r" in self._buf[s]:
            line, self._buf[s] = self._buf[s].split(b"\r", 1)
            cmd = line.decode()
            self.received.append(cmd)
            if self.silent:
                continue
            if self.er23:
                s.write(f"ER,{cmd},23\r".encode())
            elif cmd == "LON":
                if self.immediate:
                    self._send(s)
                else:
                    self._armed[s] = True
            elif cmd == "LOFF":
                if self._armed[s]:
                    self._armed[s] = False
                    self._send(s)
            elif cmd == "KEYENCE":
                s.write(b"OK,KEYENCE,FAKE-SR-X300,1.73,7.244\r")
            else:
                s.write(f"ER,{cmd},00\r".encode())

    def _send(self, s: QTcpSocket):
        if not self.fragment:
            s.write(self.frame)
            return
        third = len(self.frame) // 3
        parts = [self.frame[:third], self.frame[third:third * 2], self.frame[third * 2:]]
        s.write(parts[0])
        QTimer.singleShot(20, lambda: s.write(parts[1]))
        QTimer.singleShot(40, lambda: s.write(parts[2]))

    def drop_all(self):
        for s in self.clients:
            s.abort()


@pytest.fixture
def server(qapp):
    srv = FakeReader()
    yield srv
    srv.close()


def make_client(srv: QTcpServer, **cfg) -> tuple[KeyenceClient, dict]:
    client = KeyenceClient()
    settings = dict(host="127.0.0.1", port=srv.serverPort(), read_seconds=0.2, result_timeout_s=1.0,
                    reconnect_s=0.2)
    settings.update(cfg)
    client.configure(**settings)
    log = {"states": [], "frames": [], "rejected": [], "errors": [], "responses": [], "comm": []}
    client.state_changed.connect(log["states"].append)
    client.frame_received.connect(log["frames"].append)
    client.frame_rejected.connect(log["rejected"].append)
    client.command_error.connect(lambda c, e: log["errors"].append((c, e)))
    client.response_received.connect(log["responses"].append)
    client.comm_error.connect(log["comm"].append)
    return client, log


def test_connect_trigger_and_receive_full_frame(server):
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    assert log["states"] == ["connecting", "connected"]

    assert client.trigger()
    assert client.state is ReaderState.READING
    assert wait_until(lambda: len(log["frames"]) == 1)
    frame: ParsedFrame = log["frames"][0]
    assert len(frame.reads) == 72 and frame.ng_cells == [13, 14] and frame.scan_time_ms == 6064
    assert server.received == ["LON", "LOFF"]
    assert client.state is ReaderState.CONNECTED
    assert log["rejected"] == [] and log["comm"] == []
    client.close()
    assert client.state is ReaderState.DISCONNECTED


def test_fragmented_frame_is_reassembled(qapp):
    server = FakeReader(fragment=True)
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    client.trigger()
    assert wait_until(lambda: len(log["frames"]) == 1)
    assert len(log["frames"][0].reads) == 72
    client.close()
    server.close()


def test_early_result_before_loff_still_sends_loff(qapp):
    server = FakeReader(immediate=True)
    client, log = make_client(server, read_seconds=5.0)
    client.open()
    assert wait_until(client.is_connected)
    client.trigger()
    assert wait_until(lambda: len(log["frames"]) == 1)
    assert wait_until(lambda: server.received == ["LON", "LOFF"])
    assert client.state is ReaderState.CONNECTED
    client.close()
    server.close()


def test_er23_aborts_read_and_reports_command_error(qapp):
    server = FakeReader(er23=True)
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    client.trigger()
    assert wait_until(lambda: log["errors"] == [("LON", "23")])
    assert client.state is ReaderState.CONNECTED
    assert log["frames"] == []
    client.close()
    server.close()


def test_count_mismatch_frame_is_rejected(qapp):
    bad = b",".join(b"X%03d" % i for i in range(1, 72)) + b":10ms\r"   # 71개
    server = FakeReader(frame=bad)
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    client.trigger()
    assert wait_until(lambda: len(log["rejected"]) == 1)
    assert "71" in log["rejected"][0] and log["frames"] == []
    assert client.state is ReaderState.CONNECTED
    client.close()
    server.close()


def test_send_command_keyence_response(server):
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    assert client.send_command("KEYENCE")
    assert wait_until(lambda: log["responses"] == ["OK,KEYENCE,FAKE-SR-X300,1.73,7.244"])
    client.close()


def test_result_timeout_emits_comm_error(qapp):
    server = FakeReader(silent=True)
    client, log = make_client(server, read_seconds=0.1, result_timeout_s=0.2)
    client.open()
    assert wait_until(client.is_connected)
    client.trigger()
    assert wait_until(lambda: "판독 결과 타임아웃" in log["comm"], 2000)
    assert client.state is ReaderState.CONNECTED
    client.close()
    server.close()


def test_trigger_while_reading_is_refused(server):
    client, log = make_client(server, read_seconds=1.0)
    client.open()
    assert wait_until(client.is_connected)
    assert client.trigger()
    assert not client.trigger()
    assert "이미 판독 중" in log["comm"][-1]
    client.close()


def test_trigger_without_connection_is_refused(server):
    client, log = make_client(server)
    assert not client.trigger()
    assert "연결되지 않았습니다" in log["comm"][-1]


def test_reconnects_after_server_drop(server):
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    server.drop_all()
    assert wait_until(lambda: "reconnecting" in log["states"])
    assert wait_until(lambda: len(server.clients) == 2 and client.is_connected(), 3000)
    assert log["states"][-1] == "connected"
    client.trigger()
    assert wait_until(lambda: len(log["frames"]) == 1)
    client.close()


def test_explicit_close_does_not_reconnect(server):
    client, log = make_client(server)
    client.open()
    assert wait_until(client.is_connected)
    client.close()
    assert not wait_until(lambda: "reconnecting" in log["states"], 500)
    assert client.state is ReaderState.DISCONNECTED
