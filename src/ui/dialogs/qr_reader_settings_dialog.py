"""리더기 설정 다이얼로그 (설계 §4, 승인 목업 "리더기 설정").

좌측 **목록 사이드바** + 우측 **선택한 섹션만 단독 표시**(``QStackedWidget``) 구조.
사이드바 항목을 고르면 우측에 그 섹션 페이지만 보인다(스크롤 없음). 검증 오류는 해당 섹션 페이지로 이동한다.

섹션: ① 연결(전송 방식·IP·포트·자동 접속, [연결 테스트]) ② 판독(LON·LOFF·판독 시간·기대 코드 수·NG 문자열,
[테스트 판독][판독 미리보기]) ③ 셀 → Port·Slot 재정의 표 ④ 리더기 현재 값(읽기 전용 RB/RP, [리더기 값 읽기]).
하단 푸터: 상태 + [취소][저장].

연결 테스트·테스트 판독·값 읽기는 폼의 현재 값으로 임시 ``KeyenceClient`` 를 만들어 수행하고 끝나면 닫는다.
저장 시 ``result_settings()`` 가 정규화된 dict 를 돌려준다. DB 저장은 호출자(QRReaderMixin) 책임.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.qr_reader.keyence_client import KeyenceClient
from src.core.qr_reader.settings import client_kwargs, normalize_qr_reader_settings
from src.core.qr_reader.slot_assigner import SLOTS_PER_PORT
from src.ui.theme import ACCENT, BG2, BG3, FG, FG2, GREEN, RED, TEAL

_TRANSPORT_LABELS = [("lan", "LAN (TCP)"), ("serial", "Serial (USB 가상 COM)"), ("keyboard", "Keyboard (폴백)")]
_ROTATION_LABELS = [(0, "리더기 화상 그대로 (가로)"), (90, "시계 방향 90° (세로)"), (180, "180°"), (270, "반시계 방향 90° (세로, 기본)")]
_TEST_TIMEOUT_MS = 20_000

# TOC 사이드바 항목: (키, 제목, 한 줄 설명) — 본문 섹션 순서와 동일
SECTIONS: list[tuple[str, str, str]] = [
    ("conn", "연결", "전송 방식 · IP · 포트 · 자동 접속"),
    ("read", "판독", "트리거 명령 · 판독 시간 · 기대 코드 수"),
    ("map", "셀 → Port / Slot", "기본 공식과 재정의 표"),
    ("params", "리더기 현재 값", "노출 · 게인 · 조명 · 트리거 (읽기 전용)"),
]
_SECTION_KEYS = [k for k, _, _ in SECTIONS]


def _hex_ascii(payload: str) -> str:
    try:
        return bytes.fromhex(payload).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return payload


def _enum(mapping: dict[str, str]):
    return lambda v: mapping.get(v.lstrip("0") or "0", v)


# 실기기(SR-X300W, 2026-09-09)로 확인한 읽기 전용 조회 항목: (명령, 표시명, 값 포맷)
# RB 는 "RB,<뱅크 2자리><번호 3자리>", RP 는 "RP,<번호>" (매뉴얼 14-3, p.104~)
READER_PARAMS: list[tuple[str, str, object]] = [
    ("RP,101", "트리거 방식", _enum({"0": "레벨 (LON~LOFF)", "1": "원샷"})),
    ("RP,103", "트리거 ON 문자열", _hex_ascii),
    ("RP,104", "트리거 OFF 문자열", _hex_ascii),
    ("RP,205", "판독 에러 문자열", _hex_ascii),
    ("RP,290", "다중 코드 출력 형식", _enum({"0": "표준", "1": "뱅크별", "2": "영역별 (고정 개수)"})),
    ("RB,01100", "노출 시간 (뱅크 1)", lambda v: f"{int(v)} µs" if v.isdigit() else v),
    ("RB,01101", "게인 (뱅크 1)", lambda v: v.lstrip("0") or "0"),
    ("RB,01010", "내부 조명 종류 (뱅크 1)", _enum({"0": "직접광", "1": "편광", "2": "확산광"})),
    ("RB,01108", "콘트라스트 (뱅크 1)", _enum({"0": "표준", "1": "HDR", "2": "HDR2", "3": "콘트라스트 줌"})),
]


class _FormError(Exception):
    """폼 입력 검증 실패."""


def _hint(text: str, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(f"color: {FG2}; font-size: 12px; background: transparent;")
    return lbl


class _SectionNav(QListWidget):
    """좌측 TOC 사이드바. 항목마다 '번호. 제목'(굵게) + 설명(작게) 두 줄, 현재 섹션은 좌측 액센트 바 + 액센트 제목."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSpacing(2)
        self.setStyleSheet(f"""
            QListWidget {{ background: {BG2}; border: none; border-right: 1px solid {BG3}; padding: 10px 6px; outline: 0; }}
            QListWidget::item {{ border-radius: 6px; border-left: 3px solid transparent; }}
            QListWidget::item:hover {{ background: {BG3}; }}
            QListWidget::item:selected {{ background: {BG3}; border-left: 3px solid {ACCENT}; }}
        """)
        self._titles: list[QLabel] = []
        for i, (_key, title, desc) in enumerate(SECTIONS, 1):
            item = QListWidgetItem()
            item.setToolTip(f"{title} — {desc}")
            self.addItem(item)
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            v = QVBoxLayout(w)
            v.setContentsMargins(10, 7, 8, 7)
            v.setSpacing(2)
            t = QLabel(f"{i}.  {title}")
            d = QLabel(desc)
            d.setStyleSheet(f"color: {FG2}; font-size: 12px; background: transparent;")
            d.setWordWrap(True)
            v.addWidget(t)
            v.addWidget(d)
            item.setSizeHint(w.sizeHint())
            self.setItemWidget(item, w)
            self._titles.append(t)
        self.currentRowChanged.connect(self._restyle)
        self._restyle(-1)

    def title(self, row: int) -> str:
        return self._titles[row].text()

    def _restyle(self, current: int) -> None:
        for i, t in enumerate(self._titles):
            color, weight = (ACCENT, "bold") if i == current else (FG, "normal")
            t.setStyleSheet(f"color: {color}; font-weight: {weight}; font-size: 14px; background: transparent;")


class QRReaderSettingsDialog(QDialog):
    rotation_applied = Signal(int)   # 미리보기 창 [적용] → 호출자가 즉시 저장

    def __init__(self, settings: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("리더기 설정")
        self.setModal(True)
        self.resize(900, 600)
        s = normalize_qr_reader_settings(settings)
        self._base = s   # 폼에 노출하지 않는 키(result_timeout_s, connect_timeout_s)는 저장 시 그대로 유지
        self._test_client: KeyenceClient | None = None
        self._test_timer = QTimer(self)
        self._test_timer.setSingleShot(True)
        self._test_timer.timeout.connect(lambda: self._end_test("응답 없음 (타임아웃)", RED))
        self._last_frame = None
        self._preview = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 좌: 목록 사이드바 / 우: 선택한 섹션 페이지만 표시 ──
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.nav = _SectionNav()
        body.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.sections: dict[str, QWidget] = {}   # key → 섹션 QGroupBox
        self.pages: dict[str, QWidget] = {}      # key → 스택 페이지
        for key, box in (
            ("conn", self._build_conn_section(s)),
            ("read", self._build_read_section(s)),
            ("map", self._build_map_section(s)),
            ("params", self._build_params_section()),
        ):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(20, 16, 20, 16)
            if key == "map":
                page_layout.addWidget(box, 1)          # 재정의 표가 남는 높이를 차지
            else:
                page_layout.addWidget(box)
                page_layout.addStretch(1)
            self.pages[key] = page
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.nav.setCurrentRow(0)

        # ── 푸터: 상태 + 취소/저장 ──
        footer_frame = QFrame()
        footer_frame.setObjectName("readerFooter")
        footer_frame.setStyleSheet(f"QFrame#readerFooter {{ background: {BG2}; border-top: 1px solid {BG3}; }}")
        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(16, 10, 16, 10)
        self.status_dot = QLabel("●")
        self.status_label = QLabel("미확인")
        self._set_status("미확인", FG2)
        footer.addWidget(self.status_dot)
        footer.addWidget(self.status_label, 1)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("저장")
        btn_save.setProperty("accent", "true")
        btn_save.setToolTip("설정을 저장하고 (LAN 이면) 지금 바로 리더기에 접속합니다.")
        btn_save.clicked.connect(self._on_accept)
        footer.addWidget(btn_cancel)
        footer.addWidget(btn_save)
        outer.addWidget(footer_frame)

    # ─── 섹션 빌더 ───

    def _section(self, key: str, title: str) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox(f"{_SECTION_KEYS.index(key) + 1}. {title}")
        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        self.sections[key] = box
        return box, layout

    def _build_conn_section(self, s: dict) -> QWidget:
        box, layout = self._section("conn", "연결")
        form = QFormLayout()
        self.transport_combo = QComboBox()
        for key, label in _TRANSPORT_LABELS:
            self.transport_combo.addItem(label, key)
        self.transport_combo.setCurrentIndex(max(0, [k for k, _ in _TRANSPORT_LABELS].index(s["transport"])))
        form.addRow("전송 방식", self.transport_combo)

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
        form.addRow("IP 주소", host_row)

        self.enabled_check = QCheckBox("앱 시작 시 자동 접속 (기본 켜짐)")
        self.enabled_check.setChecked(s["enabled"])
        self.enabled_check.setToolTip("켜면 앱을 실행할 때 이 리더기에 자동으로 접속하고, 끊기면 재접속합니다.\n저장 버튼은 이 설정과 무관하게 즉시 접속을 시도합니다.")
        form.addRow("자동 접속", self.enabled_check)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.btn_test_conn = QPushButton("연결 테스트")
        self.btn_test_conn.setToolTip("현재 입력한 IP·포트로 접속해 KEYENCE 명령 응답(모델·펌웨어)을 확인합니다.")
        self.btn_test_conn.clicked.connect(self._test_connection)
        actions.addWidget(self.btn_test_conn)
        actions.addWidget(_hint("리더기가 AutoID Network Navigator 에 연결돼 있으면 ER,…,23 이 납니다. Navigator 에서 연결을 끊으세요.", wrap=True), 1)
        layout.addLayout(actions)
        return box

    def _build_read_section(self, s: dict) -> QWidget:
        box, layout = self._section("read", "판독")
        form = QFormLayout()
        cmd_row = QHBoxLayout()
        self.trigger_input = QLineEdit(s["trigger_cmd"])
        self.trigger_input.setFixedWidth(100)
        self.stop_input = QLineEdit(s["stop_cmd"])
        self.stop_input.setFixedWidth(100)
        cmd_row.addWidget(self.trigger_input)
        cmd_row.addWidget(QLabel("종료"))
        cmd_row.addWidget(self.stop_input)
        cmd_row.addWidget(_hint("종단자 CR"))
        cmd_row.addStretch()
        form.addRow("트리거 명령", cmd_row)

        sec_row = QHBoxLayout()
        self.read_spin = QDoubleSpinBox()
        self.read_spin.setRange(0.1, 60.0)
        self.read_spin.setDecimals(1)
        self.read_spin.setSingleStep(0.5)
        self.read_spin.setSuffix(" s")
        self.read_spin.setValue(s["read_seconds"])
        self.read_spin.setFixedWidth(90)
        sec_row.addWidget(self.read_spin)
        sec_row.addWidget(_hint("LON 후 이 시간이 지나면 LOFF 로 결과 확정"))
        sec_row.addStretch()
        form.addRow("판독 시간", sec_row)

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
        cnt_row.addWidget(_hint("개수 불일치 시 프레임 폐기"))
        cnt_row.addStretch()
        form.addRow("기대 코드 수", cnt_row)

        rot_row = QHBoxLayout()
        self.rotation_combo = QComboBox()
        for deg, label in _ROTATION_LABELS:
            self.rotation_combo.addItem(label, deg)
        self.rotation_combo.setCurrentIndex([d for d, _ in _ROTATION_LABELS].index(s["preview_rotation"]))
        self.rotation_combo.setFixedWidth(220)
        rot_row.addWidget(self.rotation_combo)
        rot_row.addWidget(_hint("리더기 화상은 보트가 눕혀져(카세트 3×2) 보이므로 실물(2×3)처럼 세워서 표시"))
        rot_row.addStretch()
        form.addRow("미리보기 회전", rot_row)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.btn_test_read = QPushButton("테스트 판독")
        self.btn_test_read.setToolTip("LON → 판독 시간 대기 → LOFF 로 한 번 판독하고 결과를 하단 상태와 판독 미리보기 창에 표시합니다.")
        self.btn_test_read.clicked.connect(self._test_read)
        self.btn_preview = QPushButton("판독 미리보기")
        self.btn_preview.setToolTip("리더기 서치 영역을 실제 좌표대로 그리고 판독 결과를 칸에 표시합니다 (Navigator 불필요)")
        self.btn_preview.clicked.connect(lambda: self._open_preview(self._last_frame))
        actions.addWidget(self.btn_test_read)
        actions.addWidget(self.btn_preview)
        actions.addStretch()
        layout.addLayout(actions)
        return box

    def _build_map_section(self, s: dict) -> QWidget:
        box, layout = self._section("map", "셀 → Port / Slot 대응")
        layout.addWidget(_hint("기본 공식: Port = (셀−1)÷12+1, Slot = (셀−1)%12+1  (셀 1~12 = Port 1). 아래 표에 적은 셀만 재정의됩니다.", wrap=True))
        self.override_table = QTableWidget(0, 3)
        self.override_table.setHorizontalHeaderLabels(["셀", "Port", "Slot"])
        self.override_table.verticalHeader().setVisible(False)
        self.override_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.override_table.setMinimumHeight(180)
        for cell, (port, slot) in sorted(s["cell_override"].items()):
            self._append_override_row(cell, port, slot)
        layout.addWidget(self.override_table)
        btns = QHBoxLayout()
        btn_add = QPushButton("행 추가")
        btn_add.clicked.connect(lambda: self._append_override_row())
        btn_del = QPushButton("선택 행 삭제")
        btn_del.clicked.connect(self._remove_selected_override_rows)
        btns.addWidget(btn_add)
        btns.addWidget(btn_del)
        btns.addStretch()
        layout.addLayout(btns)
        return box

    def _build_params_section(self) -> QWidget:
        box, layout = self._section("params", "리더기 현재 값 (읽기 전용)")
        self.param_table = QTableWidget(len(READER_PARAMS), 2)
        self.param_table.setHorizontalHeaderLabels(["항목", "리더기 값"])
        self.param_table.verticalHeader().setVisible(False)
        self.param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.param_table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, (_cmd, label, _fmt) in enumerate(READER_PARAMS):
            self.param_table.setItem(row, 0, QTableWidgetItem(label))
            self.param_table.setItem(row, 1, QTableWidgetItem("—"))
        # 전 행이 스크롤 없이 보이도록: 헤더 + 행 높이 합 (테마 글꼴 기준 실제 섹션 크기 사용)
        row_h = self.param_table.verticalHeader().defaultSectionSize()
        self.param_table.setFixedHeight(self.param_table.horizontalHeader().sizeHint().height() + row_h * len(READER_PARAMS) + 4)
        layout.addWidget(self.param_table)
        actions = QHBoxLayout()
        self.btn_read_params = QPushButton("리더기 값 읽기")
        self.btn_read_params.setToolTip("RB/RP 조회 명령으로 리더기의 현재 설정값을 읽어 표에 채웁니다. 값을 바꾸지는 않습니다.")
        self.btn_read_params.clicked.connect(self._read_params)
        actions.addWidget(self.btn_read_params)
        actions.addWidget(_hint("조명·노출·격자 등 설정 변경은 AutoID Network Navigator 에서 합니다. 여기서는 확인만 합니다.", wrap=True), 1)
        layout.addLayout(actions)
        return box

    # ─── 사이드바 → 페이지 전환 ───

    def _on_nav_changed(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def current_section(self) -> str:
        """우측에 표시 중인 섹션 키."""
        return _SECTION_KEYS[self.stack.currentIndex()]

    def go_to(self, key: str) -> None:
        """섹션 키로 이동 (검증 오류 안내·테스트용)."""
        self.nav.setCurrentRow(_SECTION_KEYS.index(key))

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
            "result_timeout_s": self._base["result_timeout_s"],
            "connect_timeout_s": self._base["connect_timeout_s"],
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
            "preview_rotation": self.rotation_combo.currentData(),
        })

    def result_settings(self) -> dict:
        return self._collect()

    def _on_accept(self) -> None:
        try:
            self._collect()
        except _FormError as exc:
            self._show_form_error(exc)
            return
        self.accept()

    @staticmethod
    def _section_for_error(msg: str) -> str:
        if msg.startswith("재정의 표"):
            return "map"
        if msg.startswith(("NG 문자열", "트리거")):
            return "read"
        return "conn"

    def _show_form_error(self, exc: _FormError) -> None:
        """검증 실패 시 해당 섹션으로 이동한 뒤 경고."""
        msg = str(exc)
        self.go_to(self._section_for_error(msg))
        QMessageBox.warning(self, "리더기 설정 오류", msg)

    # ─── 연결 테스트 / 테스트 판독 / 값 읽기 ───

    def _set_status(self, text: str, color: str) -> None:
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; background: transparent;")

    def _set_actions_enabled(self, enabled: bool) -> None:
        for b in (self.btn_test_conn, self.btn_test_read, self.btn_read_params):
            b.setEnabled(enabled)

    def _start_test(self) -> KeyenceClient | None:
        if self._test_client is not None:
            return None
        try:
            settings = self._collect()
        except _FormError as exc:
            self._show_form_error(exc)
            return None
        if settings["transport"] != "lan":
            QMessageBox.information(self, "리더기 테스트", "연결 테스트·테스트 판독은 전송 방식이 LAN (TCP) 일 때만 가능합니다.")
            return None
        client = KeyenceClient(self)
        client.configure(auto_reconnect=False, **client_kwargs(settings))
        client.comm_error.connect(lambda m: self._end_test(m, RED))
        client.command_error.connect(lambda cmd, code: self._end_test(f"명령 오류 ER,{cmd},{code}", RED))
        self._test_client = client
        self._set_actions_enabled(False)
        self._set_status(f"{settings['host']}:{settings['port']} 접속 중…", TEAL)
        self._test_timer.start(_TEST_TIMEOUT_MS)
        return client

    def _end_test(self, text: str, color: str) -> None:
        self._test_timer.stop()
        client, self._test_client = self._test_client, None
        if client is not None:
            client.close()          # 창의 자식이므로 창과 함께 파괴 (deleteLater 는 창 파괴 시 이중 삭제 위험)
        self._set_status(text, color)
        self._set_actions_enabled(True)

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
            self._last_frame = frame
            self._open_preview(frame)

        client.frame_received.connect(on_frame)
        client.frame_rejected.connect(lambda m: self._end_test(f"프레임 거부: {m}", RED))
        self._once_connected(client, lambda: (self._set_status("판독 중…", TEAL), client.trigger()))
        client.open()

    def _read_params(self) -> None:
        """RB/RP 로 확인된 파라미터를 순차 조회해 표에 채운다 (읽기 전용)."""
        client = self._start_test()
        if client is None:
            return
        remaining = [len(READER_PARAMS)]

        def fill(row: int, fmt, payload: str | None, reason: str) -> None:
            text = fmt(payload) if payload is not None else f"({reason})"
            self.param_table.item(row, 1).setText(text)
            remaining[0] -= 1
            if remaining[0] == 0:
                self._end_test("리더기 값 읽기 완료", GREEN)

        def start() -> None:
            self._set_status("리더기 값 읽는 중…", TEAL)
            for row, (cmd, _label, fmt) in enumerate(READER_PARAMS):
                client.query(cmd, lambda p, r, row=row, fmt=fmt: fill(row, fmt, p, r))

        self._once_connected(client, start)
        client.open()

    def _open_preview(self, frame) -> None:
        from src.ui.dialogs.frame_preview_dialog import FramePreviewDialog

        try:
            settings = self._collect()
        except _FormError as exc:
            self._show_form_error(exc)
            return
        if self._preview is not None:
            self._preview.close()
        self._preview = FramePreviewDialog(settings, frame, self)
        # 미리보기 창에서 회전을 바꾸면 폼에도 반영해 저장 시 함께 남기고, [적용] 이면 호출자에게 즉시 저장을 요청
        self._preview.rotation_changed.connect(self._set_rotation_combo)
        self._preview.rotation_applied.connect(self._on_rotation_applied)
        self._preview.show()

    def _set_rotation_combo(self, deg: int) -> None:
        self.rotation_combo.setCurrentIndex([d for d, _ in _ROTATION_LABELS].index(deg))

    def _on_rotation_applied(self, deg: int) -> None:
        self._set_rotation_combo(deg)
        self._base = dict(self._base, preview_rotation=deg)
        self._set_status(f"미리보기 회전 {deg}° 적용됨", GREEN)
        self.rotation_applied.emit(deg)

    @staticmethod
    def _once_connected(client: KeyenceClient, action) -> None:
        """첫 'connected' 상태에서 한 번만 action 실행 (판독 종료 시 READING→CONNECTED 재발화 무시)."""
        def on_state(st: str) -> None:
            if st == "connected":
                client.state_changed.disconnect(on_state)
                action()
        client.state_changed.connect(on_state)

    def done(self, result: int) -> None:
        """accept/reject/close 모두 여기를 지난다 — 진행 중인 테스트 클라이언트·타이머를 반드시 정리."""
        self._end_test("미확인", FG2)
        super().done(result)
