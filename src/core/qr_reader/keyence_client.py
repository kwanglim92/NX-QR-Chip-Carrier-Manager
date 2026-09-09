"""SR-X300W TCP 클라이언트 (설계 문서 §3.2, §4).

메인 스레드에서 ``QTcpSocket`` 시그널로만 동작한다(스레드 없음, DB 접근 없음).

트리거 시퀀스(레벨 방식):
    trigger() → ``LON<CR>`` 전송 → ``read_seconds`` 후 ``LOFF<CR>`` 전송 → 결과 프레임 대기
    (전 코드가 일찍 판독되어 프레임이 먼저 오면 LOFF 를 즉시 보내고 판독을 끝낸다)

수신 처리:
    버퍼 → ``split_frames`` → ``classify_line`` →
      result → ``parse_frame`` → ``frame_received(ParsedFrame)`` / 형식 오류 → ``frame_rejected(str)``
      ER,…   → ``command_error(cmd, code)`` (판독 중이면 판독 중단)
      OK,…   → ``response_received(str)``
"""
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from src.core.qr_reader.payload_parser import (
    DEFAULT_EXPECTED_COUNT,
    DEFAULT_NG_TOKEN,
    FRAME_TERMINATOR,
    FrameError,
    ParsedFrame,
    classify_line,
    parse_frame,
    split_frames,
)


MAX_BUFFER_BYTES = 64 * 1024   # 72코드 프레임(~800B) 대비 충분. 종단자 없이 쌓이면 폐기.


class ReaderState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READING = "reading"
    RECONNECTING = "reconnecting"


class KeyenceClient(QObject):
    state_changed = Signal(str)          # ReaderState.value
    frame_received = Signal(object)      # ParsedFrame
    frame_rejected = Signal(str)         # FrameError 사유
    command_error = Signal(str, str)     # (cmd, code)  예: ("LON", "23")
    response_received = Signal(str)      # "OK,..." 줄
    comm_error = Signal(str)             # 소켓 오류·타임아웃 메시지

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._host = "192.168.100.2"
        self._port = 9004
        self._read_seconds = 6.0
        self._result_timeout_s = 10.0
        self._expected_count = DEFAULT_EXPECTED_COUNT
        self._ng_token = DEFAULT_NG_TOKEN
        self._trigger_cmd = "LON"
        self._stop_cmd = "LOFF"
        self._reconnect_s = 3.0
        self._auto_reconnect = True

        self._state = ReaderState.DISCONNECTED
        self._buffer = b""
        self._explicit_close = False

        self._socket = QTcpSocket(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.errorOccurred.connect(self._on_socket_error)
        self._socket.readyRead.connect(self._on_ready_read)

        self._loff_timer = QTimer(self)
        self._loff_timer.setSingleShot(True)
        self._loff_timer.timeout.connect(self._send_stop)

        self._result_timer = QTimer(self)
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._on_result_timeout)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)

    # ─── 설정/상태 ───

    def configure(
        self,
        host: str | None = None,
        port: int | None = None,
        read_seconds: float | None = None,
        result_timeout_s: float | None = None,
        expected_count: int | None = None,
        ng_token: str | None = None,
        trigger_cmd: str | None = None,
        stop_cmd: str | None = None,
        reconnect_s: float | None = None,
        auto_reconnect: bool | None = None,
    ) -> None:
        if host is not None:
            self._host = host
        if port is not None:
            self._port = int(port)
        if read_seconds is not None:
            self._read_seconds = float(read_seconds)
        if result_timeout_s is not None:
            self._result_timeout_s = float(result_timeout_s)
        if expected_count is not None:
            self._expected_count = int(expected_count)
        if ng_token is not None:
            self._ng_token = ng_token
        if trigger_cmd is not None:
            self._trigger_cmd = trigger_cmd
        if stop_cmd is not None:
            self._stop_cmd = stop_cmd
        if reconnect_s is not None:
            self._reconnect_s = float(reconnect_s)
        if auto_reconnect is not None:
            self._auto_reconnect = bool(auto_reconnect)

    @property
    def state(self) -> ReaderState:
        return self._state

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def is_connected(self) -> bool:
        return self._socket.state() == QAbstractSocket.SocketState.ConnectedState

    def is_reading(self) -> bool:
        return self._state is ReaderState.READING

    # ─── 연결 ───

    def open(self) -> None:
        self._explicit_close = False
        self._reconnect_timer.stop()
        if self.is_connected():
            return
        self._set_state(ReaderState.CONNECTING)
        self._socket.connectToHost(self._host, self._port)

    def close(self) -> None:
        self._explicit_close = True
        self._reconnect_timer.stop()
        self._cancel_read()
        if self._socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self._socket.abort()
        self._buffer = b""
        self._set_state(ReaderState.DISCONNECTED)

    # ─── 명령 ───

    def send_command(self, cmd: str) -> bool:
        """``cmd`` + CR 전송. 연결 안 됐으면 comm_error 후 False."""
        if not self.is_connected():
            self.comm_error.emit("리더기가 연결되지 않았습니다")
            return False
        self._socket.write(cmd.encode("ascii") + FRAME_TERMINATOR)
        return True

    def trigger(self) -> bool:
        """LON 전송 후 read_seconds 뒤 LOFF. 판독 중이면 무시."""
        if self.is_reading():
            self.comm_error.emit("이미 판독 중입니다")
            return False
        if not self.send_command(self._trigger_cmd):
            return False
        self._set_state(ReaderState.READING)
        self._loff_timer.start(int(self._read_seconds * 1000))
        self._result_timer.start(int((self._read_seconds + self._result_timeout_s) * 1000))
        return True

    def _send_stop(self) -> None:
        if self.is_connected():
            self._socket.write(self._stop_cmd.encode("ascii") + FRAME_TERMINATOR)

    def _cancel_read(self) -> None:
        self._loff_timer.stop()
        self._result_timer.stop()

    def _finish_read(self) -> None:
        """결과(또는 오류) 수신으로 판독 종료. LOFF 가 아직이면 즉시 보낸다."""
        if self._loff_timer.isActive():
            self._loff_timer.stop()
            self._send_stop()
        self._result_timer.stop()
        if self._state is ReaderState.READING:
            self._set_state(ReaderState.CONNECTED)

    def _on_result_timeout(self) -> None:
        if self._state is ReaderState.READING:
            self._set_state(ReaderState.CONNECTED)
        self.comm_error.emit("판독 결과 타임아웃")

    # ─── 수신 ───

    def _on_ready_read(self) -> None:
        self._buffer += bytes(self._socket.readAll())
        frames, self._buffer = split_frames(self._buffer)
        if len(self._buffer) > MAX_BUFFER_BYTES:
            self._buffer = b""
            self.frame_rejected.emit(f"종단자 없는 수신 데이터 {MAX_BUFFER_BYTES} 바이트 초과 — 버퍼 폐기")
        for raw in frames:
            self._handle_line(raw.decode("ascii", errors="replace"))

    def _handle_line(self, line: str) -> None:
        kind = classify_line(line)
        if kind == "empty":
            return
        if kind == "error":
            parts = line.strip().split(",")
            cmd = parts[1] if len(parts) > 1 else ""
            code = parts[2] if len(parts) > 2 else ""
            if self.is_reading():
                # 트리거 자체가 거부됨(예: Navigator 연결 중 23) — LOFF 를 보낼 이유가 없다
                self._cancel_read()
                self._set_state(ReaderState.CONNECTED)
            self.command_error.emit(cmd, code)
            return
        if kind == "ok":
            self.response_received.emit(line.strip())
            return
        # result
        was_reading = self.is_reading()
        if was_reading:
            self._finish_read()
        try:
            frame = parse_frame(line, expected_count=self._expected_count, ng_token=self._ng_token)
        except FrameError as e:
            self.frame_rejected.emit(str(e))
            return
        self.frame_received.emit(frame)

    # ─── 소켓 이벤트 ───

    def _on_connected(self) -> None:
        self._buffer = b""
        self._socket.setSocketOption(QAbstractSocket.SocketOption.KeepAliveOption, 1)
        self._set_state(ReaderState.CONNECTED)

    def _on_disconnected(self) -> None:
        self._cancel_read()
        self._buffer = b""
        if self._explicit_close:
            return
        self._schedule_reconnect()

    def _on_socket_error(self, _err: QAbstractSocket.SocketError) -> None:
        if self._explicit_close:
            return
        self.comm_error.emit(self._socket.errorString())
        if not self.is_connected():
            self._cancel_read()
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if not self._auto_reconnect:
            self._set_state(ReaderState.DISCONNECTED)
            return
        if self._reconnect_timer.isActive():
            return
        self._set_state(ReaderState.RECONNECTING)
        self._reconnect_timer.start(int(self._reconnect_s * 1000))

    def _attempt_reconnect(self) -> None:
        if self._explicit_close or self.is_connected():
            return
        self._socket.abort()
        self._socket.connectToHost(self._host, self._port)

    def _set_state(self, state: ReaderState) -> None:
        if state is self._state:
            return
        self._state = state
        self.state_changed.emit(state.value)
