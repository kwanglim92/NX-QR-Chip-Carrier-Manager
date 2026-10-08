"""UploadMixin — 상태 바 Server 칩, 서버 설정 창 연동 로그인, 세션 확인, 종료 로그아웃.

실서버에는 어떤 요청도 보내지 않는다: ``requests.Session`` 을 test_server_uploader 의 FakeSession 으로 대체.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QProgressBar, QPushButton

from src.core import server_uploader as su
from src.core.csv_exporter import CSV_EXPORT_QR_ONLY
from src.core.models import MeasurementSet, SlotData
from src.ui.controllers.upload_mixin import UploadMixin
from tests.test_server_uploader import (
    CHIP_SEARCH_HTML,
    LOGIN_FORM_HTML,
    UPLOAD_FORM_HTML,
    FakeResponse,
    FakeSession,
)
from tests.test_qr_reader_mixin import _Logger


class _StatusBar:
    def __init__(self):
        self.messages: list[str] = []

    def showMessage(self, m, *a):
        self.messages.append(m)


class _Host(UploadMixin, QObject):
    def __init__(self, db_conn):
        super().__init__()
        self._db_conn = db_conn
        self.logger = _Logger()
        self._settings = {"server_id": ""}
        self.btn_server_status = QPushButton()
        self.btn_upload = QPushButton()
        self.upload_progress = QProgressBar()
        self._statusbar = _StatusBar()
        self.current_mode = "atx"
        self.measurement_set = None
        self.opened: list[dict] = []

    def _choose_incomplete_export_policy(self, ms, a, b):
        return CSV_EXPORT_QR_ONLY


@pytest.fixture
def host(qapp, db_conn, monkeypatch):
    FakeSession.instances.clear()
    monkeypatch.setattr(su.requests, "Session", FakeSession)
    h = _Host(db_conn)
    h._init_upload_state()
    assert isinstance(h._uploader.session, FakeSession)
    return h


def _script_login_ok(sess: FakeSession):
    sess.expect("GET", FakeResponse(200, su.LOGIN_URL, LOGIN_FORM_HTML))
    sess.expect("POST", FakeResponse(200, f"{su.BASE_URL}/chip/login/", "<a>Log Out</a>"),
                set_cookies={"csrftoken": "c", "sessionid": "s"})


def _ms(*qr_ids: str | None) -> MeasurementSet:
    ms = MeasurementSet(po_number="P2601001", quantity=12, probe_type="AC160", production_date="20261008")
    for i, q in enumerate(qr_ids):
        ms.slots.append(SlotData(slot_index=i, slot_code=str(i + 1), frequency=300.0, drive=1.0, q_factor=500.0, qr_id=q))
    return ms


# ─── 칩 · 로그인 ───


def test_init_chip_logged_out(host):
    assert host.btn_server_status.text() == "● Server 미로그인"
    assert su.BASE_URL in host.btn_server_status.toolTip()


def test_login_requested_success_updates_chip_and_server_id(host):
    _script_login_ok(host._uploader.session)
    host._on_login_requested("tester", "pw-dummy")
    assert host._uploader.logged_in and host._settings["server_id"] == "tester"
    assert host.btn_server_status.text() == "● Server 로그인됨 (tester)"
    assert host.logger.lines[-1] == ("ok", "서버 로그인 성공: tester")
    assert not any("pw-dummy" in m for _, m in host.logger.lines)


def test_login_failure_logs_error_and_stays_logged_out(host):
    sess = host._uploader.session
    sess.expect("GET", FakeResponse(200, su.LOGIN_URL, LOGIN_FORM_HTML))
    sess.expect("POST", FakeResponse(200, su.LOGIN_URL, LOGIN_FORM_HTML))   # 로그인 폼이 다시 옴
    host._on_login_requested("tester", "pw-dummy")
    assert not host._uploader.logged_in and host._settings["server_id"] == ""
    assert host.btn_server_status.text() == "● Server 미로그인"
    assert host.logger.lines[-1][0] == "error"


def test_login_exception_is_logged_without_password(host):
    sess = host._uploader.session
    sess.expect("GET", FakeResponse(500, su.LOGIN_URL, ""))
    host._on_login_requested("tester", "pw-dummy")
    assert host.logger.lines[-1][0] == "error" and "pw-dummy" not in host.logger.lines[-1][1]
    assert host.btn_server_status.text() == "● Server 미로그인"


def test_session_check_expired_sets_orange_label(host):
    sess = host._uploader.session
    _script_login_ok(sess)
    host._on_login_requested("tester", "pw-dummy")
    sess.expect("GET", FakeResponse(302, f"{su.BASE_URL}/chip/?next=/chip/login/probe/update/file", CHIP_SEARCH_HTML))
    host._on_session_check_requested()
    assert host.btn_server_status.text() == "● Server 세션 만료"
    assert host.logger.lines[-1][0] == "warn"

    sess.expect("GET", FakeResponse(302, su.LOGIN_URL, ""))
    host._on_session_check_requested()          # 이미 로그아웃 상태에서 확인 → 미로그인
    assert host.btn_server_status.text() == "● Server 미로그인"


def test_session_check_alive_keeps_logged_in(host):
    sess = host._uploader.session
    _script_login_ok(sess)
    host._on_login_requested("tester", "pw-dummy")
    sess.expect("GET", FakeResponse(200, su.UPLOAD_URL, UPLOAD_FORM_HTML))
    host._on_session_check_requested()
    assert host.btn_server_status.text() == "● Server 로그인됨 (tester)"
    assert host.logger.lines[-1] == ("ok", "서버 세션 유효")


def test_logout_updates_chip(host):
    sess = host._uploader.session
    _script_login_ok(sess)
    host._on_login_requested("tester", "pw-dummy")
    sess.expect("GET", FakeResponse(200, su.LOGOUT_URL, ""))
    host._do_logout()
    assert not host._uploader.logged_in and host.btn_server_status.text() == "● Server 미로그인"


class _DialogStub:
    """ServerSettingsDialog 대신 — 생성 인자를 기록하고 exec 에서 바로 닫힌다."""
    created: list[dict] = []

    def __init__(self, saved_id, state, username, parent, section="login", close_on_login=False):
        _DialogStub.created.append({"saved_id": saved_id, "state": state, "username": username,
                                    "section": section, "close_on_login": close_on_login})
        self.login_requested = self.logout_requested = self.session_check_requested = _NoSig()

    def exec(self): return 0
    def deleteLater(self): pass
    def set_session_state(self, *a): pass


class _NoSig:
    def connect(self, *_): pass


def test_ensure_logged_in_opens_dialog_at_login_section(host, monkeypatch):
    _DialogStub.created.clear()
    monkeypatch.setattr("src.ui.dialogs.server_settings_dialog.ServerSettingsDialog", _DialogStub)
    host._settings["server_id"] = "tester"
    assert host._ensure_logged_in() is False
    assert _DialogStub.created == [{"saved_id": "tester", "state": "logged_out", "username": "",
                                    "section": "login", "close_on_login": True}]
    assert host._server_dialog is None


def test_ensure_logged_in_with_expired_session_marks_chip_then_opens_dialog(host, monkeypatch):
    _DialogStub.created.clear()
    monkeypatch.setattr("src.ui.dialogs.server_settings_dialog.ServerSettingsDialog", _DialogStub)
    sess = host._uploader.session
    _script_login_ok(sess)
    host._on_login_requested("tester", "pw-dummy")
    sess.expect("GET", FakeResponse(302, su.LOGIN_URL, ""))     # 세션 만료
    assert host._ensure_logged_in() is False
    assert host.btn_server_status.text() == "● Server 세션 만료"
    assert _DialogStub.created[0]["state"] == "logged_out"


def test_shutdown_upload_logs_out_and_closes_session(host):
    sess = host._uploader.session
    host._shutdown_upload()                      # 미로그인 → 요청 없음
    assert sess.calls == []
    _script_login_ok(sess)
    host._on_login_requested("tester", "pw-dummy")
    sess.expect("GET", FakeResponse(200, su.LOGOUT_URL, ""))
    host._shutdown_upload()
    assert not host._uploader.logged_in and sess.closed

