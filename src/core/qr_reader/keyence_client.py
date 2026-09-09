"""SR-X300W TCP 클라이언트 (설계 문서 §3.2, §4).

메인 스레드에서 ``QTcpSocket`` 시그널로만 동작한다(스레드 없음, DB 접근 없음).

트리거 시퀀스(레벨 방식):
    trigger() → ``LON<CR>`` 전송 → ``read_seconds`` 후 ``LOFF<CR>`` 전송 → 결과 프레임 대기
    (전 코드가 일찍 판독되어 프레임이 먼저 오면 LOFF 를 즉시 보내고 판독을 끝낸다)
    판독 중 close() 또는 트리거 명령 거부(``ER,LON,…``)가 아닌 사유로 판독을 접을 때도 LOFF 를 보내
    리더기가 LON 상태로 남지 않게 한다.

수신 처리:
    버퍼 → ``split_frames`` → ``classify_line`` →
      result → 판독 중일 때만 ``parse_frame`` → ``frame_received(ParsedFrame)`` / 형식 오류 → ``frame_rejected(str)``
               판독 중이 아닐 때(타임아웃 이후 지연 도착, 리더기 버튼 트리거 등) → ``frame_rejected``
      ER,…   → ``command_error(cmd, code)`` (트리거 명령이 거부된 경우에만 판독 중단)
      OK,…   → ``response_received(str)``

연결:
    접속 시도에는 ``connect_timeout_s`` 가 걸리고, 끊기거나 실패하면 ``reconnect_s`` 부터 2배씩
    ``reconnect_max_s`` 까지 늘어나는 간격으로 재접속한다(접속 성공 시 초기화). close() 는 재접속하지 않는다.
"""
from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Callable

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
TUNING_RESULT_PREFIXES = ("Focus Tuning ", "Tuning ")   # FTUNE / TUNE 완료 통지 (매뉴얼 14-2, 실기기 확인 2026-09-09)


class ReaderState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READING = "reading"
    RECONNECTING = "reconnecting"


class KeyenceClient(QObject):
    state_changed = Signal(str)          # ReaderState.value
    frame_received = Signal(object)      # ParsedFrame
    frame_rejected = Signal(str)         # FrameError 사유 / 트리거 없이 도착한 프레임
    command_error = Signal(str, str)     # (cmd, code)  예: ("LON", "23")
    response_received = Signal(str)      # "OK,..." 줄
    comm_error = Signal(str)             # 소켓 오류·타임아웃 메시지
    tuning_result = Signal(str)          # "Focus Tuning SUCCEEDED/FAILED", "Tuning SUCCEEDED,…" (FTUNE/TUNE 완료 통지)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._host = "192.168.100.2"
        self._port = 9004
        self._read_seconds = 6.0
        self._result_timeout_s = 10.0
        self._connect_timeout_s = 5.0
        self._expected_count = DEFAULT_EXPECTED_COUNT
        self._ng_token = DEFAULT_NG_TOKEN
        self._trigger_cmd = "LON"
        self._stop_cmd = "LOFF"
        self._reconnect_s = 3.0
        self._reconnect_max_s = 30.0
        self._auto_reconnect = True

        self._state = ReaderState.DISCONNECTED
        self._buffer = b""
        self._explicit_close = False
        self._reconnect_delay_s = self._reconnect_s

        self._socket = QTcpSocket(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.errorOccurred.connect(self._on_socket_error)
        self._socket.readyRead.connect(self._on_ready_read)

        self._connect_timer = QTimer(self)
        self._connect_timer.setSingleShot(True)
        self._connect_timer.timeout.connect(self._on_connect_timeout)

        self._loff_timer = QTimer(self)
        self._loff_timer.setSingleShot(True)
        self._loff_timer.timeout.connect(self._send_stop)

        self._result_timer = QTimer(self)
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._on_result_timeout)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)

        # 순차 질의 큐: (응답 태그, 명령, 콜백, 타임아웃)
        self._queries: deque[tuple[str, str, Callable[[str | None, str], None], float]] = deque()
        self._query_inflight = False   # 큐 머리 질의를 이미 전송해 응답 대기 중인지 (콜백 안에서 새 질의를 넣어도 중복 전송 방지)
        self._query_timer = QTimer(self)
        self._query_timer.setSingleShot(True)
        self._query_timer.timeout.connect(self._on_query_timeout)

    # ─── 설정/상태 ───

    def configure(
        self,
        host: str | None = None,
        port: int | None = None,
        read_seconds: float | None = None,
        result_timeout_s: float | None = None,
        connect_timeout_s: float | None = None,
        expected_count: int | None = None,
        ng_token: str | None = None,
        trigger_cmd: str | None = None,
        stop_cmd: str | None = None,
        reconnect_s: float | None = None,
        reconnect_max_s: float | None = None,
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
        if connect_timeout_s is not None:
            self._connect_timeout_s = float(connect_timeout_s)
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
            self._reconnect_delay_s = self._reconnect_s
        if reconnect_max_s is not None:
            self._reconnect_max_s = float(reconnect_max_s)
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
        """접속 시작. 이미 접속 중/접속됨이면 아무것도 하지 않는다."""
        self._explicit_close = False
        self._reconnect_timer.stop()
        if self._socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            return
        self._reconnect_delay_s = self._reconnect_s
        self._set_state(ReaderState.CONNECTING)
        self._start_connect()

    def close(self) -> None:
        """명시적 종료. 판독 중이면 LOFF 를 먼저 보내 리더기를 LON 상태로 두지 않는다. 재접속 안 함."""
        self._explicit_close = True
        self._reconnect_timer.stop()
        self._connect_timer.stop()
        self._flush_queries("연결 종료")
        if self.is_reading() and self.is_connected():
            self._cancel_read()
            self._send_stop()
            self._socket.flush()
            self._socket.waitForBytesWritten(300)
        else:
            self._cancel_read()
        if self._socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self._socket.abort()
        self._buffer = b""
        self._set_state(ReaderState.DISCONNECTED)

    def _start_connect(self) -> None:
        self._connect_timer.start(int(self._connect_timeout_s * 1000))
        self._socket.connectToHost(self._host, self._port)

    def _on_connect_timeout(self) -> None:
        if self._explicit_close or self.is_connected():
            return
        self._socket.abort()
        self.comm_error.emit(f"접속 타임아웃 ({self._host}:{self._port}, {self._connect_timeout_s:g}s)")
        self._schedule_reconnect()

    # ─── 명령 ───

    def send_command(self, cmd: str) -> bool:
        """``cmd`` + CR 전송. 연결 안 됐거나 쓰기 실패면 comm_error 후 False."""
        if not self.is_connected():
            self.comm_error.emit("리더기가 연결되지 않았습니다")
            return False
        if self._socket.write(cmd.encode("ascii") + FRAME_TERMINATOR) < 0:
            self.comm_error.emit(f"전송 실패: {self._socket.errorString()}")
            return False
        return True

    def query(self, cmd: str, on_reply: Callable[[str | None, str], None], timeout_s: float = 3.0) -> bool:
        """응답이 있는 명령(RD/RB/RP/KEYENCE 등)을 순차 질의한다.

        응답 ``OK,<tag>,<payload>`` 가 오면 ``on_reply(payload, "")``, ``ER,<tag>,<code>``·타임아웃·연결 끊김이면
        ``on_reply(None, 사유)``. 질의는 FIFO 로 한 번에 하나만 전송한다(리더기 응답에 질의 식별자가 없으므로).
        """
        if not self.is_connected():
            on_reply(None, "리더기가 연결되지 않았습니다")
            return False
        tag = cmd.split(",", 1)[0].strip()
        self._queries.append((tag, cmd, on_reply, timeout_s))
        if len(self._queries) == 1:
            self._send_next_query()
        return True

    def _send_next_query(self) -> None:
        if self._query_inflight:
            return
        while self._queries:
            tag, cmd, on_reply, timeout_s = self._queries[0]
            if self._socket.write(cmd.encode("ascii") + FRAME_TERMINATOR) < 0:
                self._queries.popleft()
                on_reply(None, f"전송 실패: {self._socket.errorString()}")
                continue
            self._query_inflight = True
            self._query_timer.start(int(timeout_s * 1000))
            return

    def _finish_query(self, payload: str | None, reason: str) -> None:
        self._query_timer.stop()
        self._query_inflight = False
        _tag, _cmd, on_reply, _t = self._queries.popleft()
        try:
            on_reply(payload, reason)
        finally:
            self._send_next_query()

    def _on_query_timeout(self) -> None:
        if self._queries:
            self._finish_query(None, f"응답 없음 ({self._queries[0][1]})")

    def _flush_queries(self, reason: str) -> None:
        self._query_timer.stop()
        self._query_inflight = False
        pending, self._queries = list(self._queries), deque()
        for _tag, _cmd, on_reply, _t in pending:
            on_reply(None, reason)

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
        """결과 수신으로 판독 종료. LOFF 가 아직이면 즉시 보낸다."""
        if self._loff_timer.isActive():
            self._loff_timer.stop()
            self._send_stop()
        self._result_timer.stop()
        if self._state is ReaderState.READING:
            self._set_state(ReaderState.CONNECTED)

    def _on_result_timeout(self) -> None:
        self._cancel_read()
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
            if self._queries and self._queries[0][0] == cmd:
                self._finish_query(None, f"ER,{cmd},{code}")
                return
            if self.is_reading() and cmd == self._trigger_cmd:
                # 트리거 자체가 거부됨(예: Navigator 연결 중 23) — 리더기는 LON 상태가 아니므로 LOFF 불필요
                self._cancel_read()
                self._set_state(ReaderState.CONNECTED)
            self.command_error.emit(cmd, code)
            return
        if kind == "ok":
            text = line.strip()
            parts = text.split(",")
            if self._queries and len(parts) > 1 and parts[1] == self._queries[0][0]:
                self._finish_query(",".join(parts[2:]), "")
                return
            self.response_received.emit(text)
            return
        # 튜닝 완료 통지 (FTUNE → "Focus Tuning SUCCEEDED/FAILED", TUNE → "Tuning SUCCEEDED,tms,code") — 프레임이 아님
        if line.startswith(TUNING_RESULT_PREFIXES):
            self.tuning_result.emit(line.strip())
            return
        # result
        if not self.is_reading():
            self.frame_rejected.emit("트리거 없이(또는 타임아웃 이후) 도착한 프레임 — 무시")
            return
        self._finish_read()
        try:
            frame = parse_frame(line, expected_count=self._expected_count, ng_token=self._ng_token)
        except FrameError as e:
            self.frame_rejected.emit(str(e))
            return
        self.frame_received.emit(frame)

    # ─── 소켓 이벤트 ───

    def _on_connected(self) -> None:
        self._connect_timer.stop()
        self._buffer = b""
        self._reconnect_delay_s = self._reconnect_s
        self._socket.setSocketOption(QAbstractSocket.SocketOption.KeepAliveOption, 1)
        self._set_state(ReaderState.CONNECTED)

    def _on_disconnected(self) -> None:
        self._cancel_read()
        self._flush_queries("연결 끊김")
        self._buffer = b""
        if self._explicit_close:
            return
        self._schedule_reconnect()

    def _on_socket_error(self, err: QAbstractSocket.SocketError) -> None:
        if self._explicit_close:
            return
        if err == QAbstractSocket.SocketError.RemoteHostClosedError:
            return  # disconnected 시그널이 처리
        self.comm_error.emit(self._socket.errorString())
        if not self.is_connected():
            self._connect_timer.stop()
            self._cancel_read()
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if not self._auto_reconnect:
            self._set_state(ReaderState.DISCONNECTED)
            return
        if self._reconnect_timer.isActive():
            return
        self._set_state(ReaderState.RECONNECTING)
        self._reconnect_timer.start(int(self._reconnect_delay_s * 1000))
        self._reconnect_delay_s = min(self._reconnect_delay_s * 2, self._reconnect_max_s)

    def _attempt_reconnect(self) -> None:
        if self._explicit_close or self.is_connected():
            return
        self._socket.abort()
        self._start_connect()

    def _set_state(self, state: ReaderState) -> None:
        if state is self._state:
            return
        self._state = state
        self.state_changed.emit(state.value)
