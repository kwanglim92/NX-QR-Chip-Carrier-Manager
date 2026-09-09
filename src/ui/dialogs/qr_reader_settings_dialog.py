"""리더기 설정 다이얼로그 (설계 §4, 승인 목업 "리더기 설정").

연결(전송 방식·IP·포트·자동 접속) / 판독(LON·LOFF·판독 시간·기대 코드 수·NG 문자열) /
셀 → Port·Slot 재정의 표 / 하단 상태 + [연결 테스트][테스트 판독][취소][저장].

연결 테스트·테스트 판독은 폼의 현재 값으로 임시 ``KeyenceClient`` 를 만들어 수행하고 끝나면 닫는다.
저장 시 ``result_settings()`` 가 정규화된 dict 를 돌려준다. DB 저장은 호출자(QRReaderMixin) 책임.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.qr_reader.keyence_client import KeyenceClient
from src.core.qr_reader.settings import client_kwargs, normalize_qr_reader_settings
from src.core.qr_reader.slot_assigner import SLOTS_PER_PORT
from src.ui.theme import FG2, GREEN, RED, TEAL

_TRANSPORT_LABELS = [("lan", "LAN (TCP)"), ("serial", "Serial (USB 가상 COM)"), ("keyboard", "Keyboard (폴백)")]
_TEST_TIMEOUT_MS = 20_000


class _FormError(Exception):
    """폼 입력 검증 실패."""


class QRReaderSettingsDialog(QDialog):
    def __init__(self, settings: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("리더기 설정")
        self.setModal(True)
        self.resize(620, 640)
        s = normalize_qr_reader_settings(settings)
        self._test_client: KeyenceClient | None = None
        self._test_timer = QTimer(self)
        self._test_timer.setSingleShot(True)
        self._test_timer.timeout.connect(lambda: self._end_test("응답 없음 (타임아웃)", RED))

        outer = QVBoxLayout(self)

        # ── 연결 ──
        conn_box = QGroupBox("연결")
        conn_form = QFormLayout(conn_box)
        self.transport_combo = QComboBox()
        for key, label in _TRANSPORT_LABELS:
            self.transport_combo.addItem(label, key)
        self.transport_combo.setCurrentIndex(max(0, [k for k, _ in _TRANSPORT_LABELS].index(s["transport"])))
        conn_form.addRow("전송 방식", self.transport_combo)

        host_row = QHBoxLayout()
        self.host_input = QLineEdit(s["host"])
        self.host_input.setFixedWidth(180)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(s["port"])
        self.port_spin.setFixedWidth(90)
        host_row.addWidget(self.host_input)
        host_row.addWidget(QLabel("포트"))
        host_row.addWidget(self.port_spin)
        host_row.addStretch()
        conn_form.addRow("IP 주소", host_row)

        self.enabled_check = QCheckBox("앱 시작 시 자동 접속, 끊기면 자동 재접속")
        self.enabled_check.setChecked(s["enabled"])
        conn_form.addRow("연결 유지", self.enabled_check)
        outer.addWidget(conn_box)

        # ── 판독 ──
        read_box = QGroupBox("판독")
        read_form = QFormLayout(read_box)
        cmd_row = QHBoxLayout()
        self.trigger_input = QLineEdit(s["trigger_cmd"])
        self.trigger_input.setFixedWidth(100)
        self.stop_input = QLineEdit(s["stop_cmd"])
        self.stop_input.setFixedWidth(100)
        cmd_row.addWidget(self.trigger_input)
        cmd_row.addWidget(QLabel("종료"))
        cmd_row.addWidget(self.stop_input)
        hint = QLabel("종단자 CR")
        hint.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        cmd_row.addWidget(hint)
        cmd_row.addStretch()
        read_form.addRow("트리거 명령", cmd_row)

        sec_row = QHBoxLayout()
        self.read_spin = QDoubleSpinBox()
        self.read_spin.setRange(0.1, 60.0)
        self.read_spin.setDecimals(1)
        self.read_spin.setSingleStep(0.5)
        self.read_spin.setSuffix(" s")
        self.read_spin.setValue(s["read_seconds"])
        self.read_spin.setFixedWidth(90)
        sec_row.addWidget(self.read_spin)
        sec_hint = QLabel("LON 후 이 시간이 지나면 LOFF 로 결과 확정")
        sec_hint.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        sec_row.addWidget(sec_hint)
        sec_row.addStretch()
        read_form.addRow("판독 시간", sec_row)

        cnt_row = QHBoxLayout()
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 999)
        self.count_spin.setValue(s["expected_count"])
        self.count_spin.setFixedWidth(90)
        self.ng_input = QLineEdit(s["ng_token"])
        self.ng_input.setFixedWidth(100)
        cnt_row.addWidget(self.count_spin)
        cnt_row.addWidget(QLabel("NG 문자열"))
        cnt_row.addWidget(self.ng_input)
        cnt_hint = QLabel("개수 불일치 시 프레임 폐기")
        cnt_hint.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        cnt_row.addWidget(cnt_hint)
        cnt_row.addStretch()
        read_form.addRow("기대 코드 수", cnt_row)
        outer.addWidget(read_box)

        # ── 셀 → Port / Slot 재정의 ──
        ov_box = QGroupBox("셀 → Port / Slot 대응")
        ov_layout = QVBoxLayout(ov_box)
        formula = QLabel("기본 공식: Port = (셀−1)÷12+1, Slot = (셀−1)%12+1. 아래 표의 셀만 재정의됩니다.")
        formula.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        ov_layout.addWidget(formula)
        self.override_table = QTableWidget(0, 3)
        self.override_table.setHorizontalHeaderLabels(["셀", "Port", "Slot"])
        self.override_table.verticalHeader().setVisible(False)
        self.override_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for cell, (port, slot) in sorted(s["cell_override"].items()):
            self._append_override_row(cell, port, slot)
        ov_layout.addWidget(self.override_table, 1)
        ov_btns = QHBoxLayout()
        btn_add = QPushButton("행 추가")
        btn_add.clicked.connect(lambda: self._append_override_row())
        btn_del = QPushButton("선택 행 삭제")
        btn_del.clicked.connect(self._remove_selected_override_rows)
        ov_btns.addWidget(btn_add)
        ov_btns.addWidget(btn_del)
        ov_btns.addStretch()
        ov_layout.addLayout(ov_btns)
        outer.addWidget(ov_box, 1)

        # ── 상태 + 버튼 ──
        footer = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_label = QLabel("미확인")
        self._set_status("미확인", FG2)
        footer.addWidget(self.status_dot)
        footer.addWidget(self.status_label, 1)
        self.btn_test_conn = QPushButton("연결 테스트")
        self.btn_test_conn.clicked.connect(self._test_connection)
        self.btn_test_read = QPushButton("테스트 판독")
        self.btn_test_read.clicked.connect(self._test_read)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("저장")
        btn_save.setProperty("accent", "true")
        btn_save.clicked.connect(self._on_accept)
        for b in (self.btn_test_conn, self.btn_test_read, btn_cancel, btn_save):
            footer.addWidget(b)
        outer.addLayout(footer)

    # ─── override 표 ───

    def _append_override_row(self, cell: int | None = None, port: int | None = None, slot: int | None = None) -> None:
        row = self.override_table.rowCount()
        self.override_table.insertRow(row)
        for col, val in enumerate((cell, port, slot)):
            item = QTableWidgetItem("" if val is None else str(val))
            item.setTextAlignment(Qt.AlignCenter)
            self.override_table.setItem(row, col, item)

    def _remove_selected_override_rows(self) -> None:
        rows = sorted({i.row() for i in self.override_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.override_table.removeRow(r)

    # ─── 수집/검증 ───

    def _collect(self) -> dict:
        """폼 → 설정 dict. 잘못된 입력은 ``_FormError``."""
        host = self.host_input.text().strip()
        if not host:
            raise _FormError("IP 주소를 입력하세요.")
        ng = self.ng_input.text().strip()
        if not ng or ng in ("OK", "ER") or ng.startswith(("OK,", "ER,")):
            raise _FormError("NG 문자열은 비울 수 없고 OK/ER 로 시작할 수 없습니다.")
        trigger = self.trigger_input.text().strip()
        stop = self.stop_input.text().strip()
        if not trigger or not stop:
            raise _FormError("트리거/종료 명령을 입력하세요.")

        override: dict[int, tuple[int, int]] = {}
        targets: dict[tuple[int, int], int] = {}
        for r in range(self.override_table.rowCount()):
            texts = [(self.override_table.item(r, c).text().strip() if self.override_table.item(r, c) else "")
                     for c in range(3)]
            if not any(texts):
                continue
            try:
                cell, port, slot = (int(t) for t in texts)
            except ValueError:
                raise _FormError(f"재정의 표 {r + 1}행: 셀·Port·Slot 은 정수여야 합니다.") from None
            if cell < 1 or port < 1 or not 1 <= slot <= SLOTS_PER_PORT:
                raise _FormError(f"재정의 표 {r + 1}행: 셀≥1, Port≥1, Slot 1~{SLOTS_PER_PORT}.")
            if cell in override:
                raise _FormError(f"재정의 표: 셀 {cell} 이 두 번 있습니다.")
            if (port, slot) in targets:
                raise _FormError(f"재정의 표: Port {port} Slot {slot} 을 셀 {targets[(port, slot)]} 과 셀 {cell} 이 함께 가리킵니다.")
            override[cell] = (port, slot)
            targets[(port, slot)] = cell

        return normalize_qr_reader_settings({
            "enabled": self.enabled_check.isChecked(),
            "transport": self.transport_combo.currentData(),
            "host": host,
            "port": self.port_spin.value(),
            "read_seconds": self.read_spin.value(),
            "expected_count": self.count_spin.value(),
            "ng_token": ng,
            "trigger_cmd": trigger,
            "stop_cmd": stop,
            "cell_override": override,
        })

    def result_settings(self) -> dict:
        return self._collect()

    def _on_accept(self) -> None:
        try:
            self._collect()
        except _FormError as exc:
            QMessageBox.warning(self, "리더기 설정 오류", str(exc))
            return
        self.accept()

    # ─── 연결 테스트 / 테스트 판독 ───

    def _set_status(self, text: str, color: str) -> None:
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    def _start_test(self) -> KeyenceClient | None:
        if self._test_client is not None:
            return None
        try:
            settings = self._collect()
        except _FormError as exc:
            QMessageBox.warning(self, "리더기 설정 오류", str(exc))
            return None
        client = KeyenceClient(self)
        client.configure(auto_reconnect=False, **client_kwargs(settings))
        client.comm_error.connect(lambda m: self._end_test(m, RED))
        client.command_error.connect(lambda cmd, code: self._end_test(f"명령 오류 ER,{cmd},{code}", RED))
        self._test_client = client
        self.btn_test_conn.setEnabled(False)
        self.btn_test_read.setEnabled(False)
        self._set_status(f"{settings['host']}:{settings['port']} 접속 중…", TEAL)
        self._test_timer.start(_TEST_TIMEOUT_MS)
        return client

    def _end_test(self, text: str, color: str) -> None:
        self._test_timer.stop()
        client, self._test_client = self._test_client, None
        if client is not None:
            client.close()
            client.deleteLater()
        self._set_status(text, color)
        self.btn_test_conn.setEnabled(True)
        self.btn_test_read.setEnabled(True)

    def _test_connection(self) -> None:
        client = self._start_test()
        if client is None:
            return
        client.response_received.connect(lambda line: self._end_test(f"연결됨 · {line.removeprefix('OK,KEYENCE,')}", GREEN))
        self._once_connected(client, lambda: client.send_command("KEYENCE"))
        client.open()

    def _test_read(self) -> None:
        client = self._start_test()
        if client is None:
            return

        def on_frame(frame):
            n = len(frame.reads)
            ng = frame.ng_cells
            ms = f", {frame.scan_time_ms} ms" if frame.scan_time_ms is not None else ""
            ng_text = f", NG {len(ng)}칸 ({', '.join(map(str, ng[:8]))}{'…' if len(ng) > 8 else ''})" if ng else ""
            self._end_test(f"판독 {n - len(ng)}/{n}{ng_text}{ms}", GREEN)

        client.frame_received.connect(on_frame)
        client.frame_rejected.connect(lambda m: self._end_test(f"프레임 거부: {m}", RED))
        self._once_connected(client, lambda: (self._set_status("판독 중…", TEAL), client.trigger()))
        client.open()

    @staticmethod
    def _once_connected(client: KeyenceClient, action) -> None:
        """첫 'connected' 상태에서 한 번만 action 실행 (판독 종료 시 READING→CONNECTED 재발화 무시)."""
        def on_state(st: str) -> None:
            if st == "connected":
                client.state_changed.disconnect(on_state)
                action()
        client.state_changed.connect(on_state)

    def closeEvent(self, event) -> None:
        self._end_test("미확인", FG2)
        super().closeEvent(event)

    def reject(self) -> None:
        self._end_test("미확인", FG2)
        super().reject()
