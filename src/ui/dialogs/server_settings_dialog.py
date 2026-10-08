"""서버 설정 다이얼로그 — 리더기 설정 창과 같은 좌측 목록 + 우측 섹션 구조.

섹션: ① 로그인(ID · 비밀번호 · [로그인][로그아웃][세션 확인]) ② 서버 주소(읽기 전용).
푸터: 세션 상태 + [닫기]. 저장할 설정은 없다 — 서버 주소는 코드 상수이고, 로그인 ID 는 로그인 성공 시
호출자(UploadMixin)가 ``server_id`` 에 기록한다. 비밀번호는 시그널로 넘긴 직후 입력창을 비우고 어디에도 보관하지 않는다.

실제 로그인/로그아웃/세션 확인은 호출자가 시그널을 받아 수행하고 ``set_session_state`` 로 결과를 돌려준다.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.server_uploader import BASE_URL, BASE_URL_QR21, LOGIN_URL, UPLOAD_URL
from src.ui.dialogs.qr_reader_settings_dialog import _hint, _SectionNav
from src.ui.theme import BG2, BG3, FG2, GREEN, ORANGE, TEAL

SECTIONS: list[tuple[str, str, str]] = [
    ("login", "로그인", "서버 ID · 비밀번호 · 세션 확인"),
    ("server", "서버 주소", "업로드 대상 서버 (읽기 전용)"),
]
_SECTION_KEYS = [k for k, _, _ in SECTIONS]

# 세션 상태 → (색, 라벨). UploadMixin 의 상태 칩과 동일
SESSION_STATES: dict[str, tuple[str, str]] = {
    "logged_out": (FG2, "미로그인"),
    "logged_in": (GREEN, "로그인됨"),
    "expired": (ORANGE, "세션 만료"),
    "uploading": (TEAL, "업로드 중"),
}


class ServerSettingsDialog(QDialog):
    login_requested = Signal(str, str)   # (username, password) — 수신자는 즉시 사용 후 참조 해제
    logout_requested = Signal()
    session_check_requested = Signal()

    def __init__(self, saved_id: str = "", state: str = "logged_out", username: str = "",
                 parent: QWidget | None = None, section: str = "login", close_on_login: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("서버 설정")
        self.setModal(True)
        self.resize(760, 420)
        self._close_on_login = close_on_login
        self._state = "logged_out"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.nav = _SectionNav(sections=SECTIONS)
        body.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.sections: dict[str, QWidget] = {}
        self.pages: dict[str, QWidget] = {}
        for key, box in (
            ("login", self._build_login_section(saved_id)),
            ("server", self._build_server_section()),
        ):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(20, 16, 20, 16)
            page_layout.addWidget(box)
            page_layout.addStretch(1)
            self.pages[key] = page
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        footer_frame = QFrame()
        footer_frame.setObjectName("serverFooter")
        footer_frame.setStyleSheet(f"QFrame#serverFooter {{ background: {BG2}; border-top: 1px solid {BG3}; }}")
        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(16, 10, 16, 10)
        self.status_dot = QLabel("●")
        self.status_label = QLabel()
        footer.addWidget(self.status_dot)
        footer.addWidget(self.status_label, 1)
        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.reject)
        footer.addWidget(self.btn_close)
        outer.addWidget(footer_frame)

        self.set_session_state(state, username)
        self.go_to(section)
        (self.pw_input if saved_id else self.id_input).setFocus()

    # ─── 섹션 ───

    def _section(self, key: str, title: str) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox(f"{_SECTION_KEYS.index(key) + 1}. {title}")
        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        self.sections[key] = box
        return box, layout

    def _build_login_section(self, saved_id: str) -> QWidget:
        box, layout = self._section("login", "로그인")
        form = QFormLayout()
        self.id_input = QLineEdit(saved_id)
        self.id_input.setFixedWidth(220)
        form.addRow("서버 ID", self.id_input)
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setFixedWidth(220)
        self.pw_input.returnPressed.connect(self._on_login)
        form.addRow("비밀번호", self.pw_input)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.btn_login = QPushButton("로그인")
        self.btn_login.setProperty("accent", "true")
        self.btn_login.setToolTip("입력한 ID·비밀번호로 서버에 로그인합니다. 성공하면 ID 만 설정에 저장됩니다.")
        self.btn_login.clicked.connect(self._on_login)
        self.btn_logout = QPushButton("로그아웃")
        self.btn_logout.setToolTip("서버 세션을 종료합니다.")
        self.btn_logout.clicked.connect(self.logout_requested.emit)
        self.btn_check = QPushButton("세션 확인")
        self.btn_check.setToolTip("현재 로그인 세션이 아직 유효한지 서버에 확인합니다.")
        self.btn_check.clicked.connect(self.session_check_requested.emit)
        actions.addWidget(self.btn_login)
        actions.addWidget(self.btn_logout)
        actions.addWidget(self.btn_check)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(_hint("비밀번호는 저장되지 않습니다 (ID 만 설정에 저장). 업로드 메뉴를 누를 때 로그인이 안 돼 있으면 이 창이 열립니다.", wrap=True))
        return box

    def _build_server_section(self) -> QWidget:
        box, layout = self._section("server", "서버 주소")
        form = QFormLayout()
        self.url_fields: dict[str, QLineEdit] = {}
        for key, label, value in (
            ("qr20", "QR 2.0 (현재 업로드 대상)", BASE_URL),
            ("login", "로그인 URL", LOGIN_URL),
            ("upload", "업로드 URL", UPLOAD_URL),
            ("qr21", "QR 2.1 (추후 지원)", BASE_URL_QR21),
        ):
            edit = QLineEdit(value)
            edit.setReadOnly(True)
            edit.setMinimumWidth(380)
            edit.setStyleSheet(f"color: {FG2};")
            self.url_fields[key] = edit
            form.addRow(label, edit)
        layout.addLayout(form)
        layout.addWidget(_hint("주소는 프로그램에 고정되어 있어 바꿀 수 없습니다. QR ID 의 Encoding Minor 가 2.1 인 코드는 "
                               "현재 업로드할 수 없습니다 — 업로드 전 자동 차단됩니다.", wrap=True))
        return box

    # ─── 상태 ───

    def go_to(self, key: str) -> None:
        self.nav.setCurrentRow(_SECTION_KEYS.index(key) if key in _SECTION_KEYS else 0)

    def current_section(self) -> str:
        return _SECTION_KEYS[self.nav.currentRow()]

    def set_session_state(self, state: str, username: str = "") -> None:
        self._state = state
        color, label = SESSION_STATES.get(state, (FG2, state))
        text = f"{label} ({username})" if state == "logged_in" and username else label
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")
        logged_in = state == "logged_in"
        self.btn_login.setEnabled(state != "uploading" and not logged_in)
        self.btn_logout.setEnabled(logged_in)
        self.btn_check.setEnabled(logged_in or state == "expired")
        if logged_in and self._close_on_login:
            self.accept()

    def result_server_id(self) -> str:
        return self.id_input.text().strip()

    def _on_login(self) -> None:
        username = self.id_input.text().strip()
        password = self.pw_input.text()
        if not username or not password:
            QMessageBox.warning(self, "서버 로그인", "서버 ID 와 비밀번호를 모두 입력하세요.")
            return
        self.pw_input.clear()
        self.login_requested.emit(username, password)
        del password
