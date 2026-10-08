"""서버 설정 다이얼로그 — 섹션 구조, 읽기 전용 주소, 로그인 시그널·비밀번호 비움, 세션 상태 표시."""
from __future__ import annotations

import pytest

from src.core.server_uploader import BASE_URL, BASE_URL_QR21, LOGIN_URL, UPLOAD_URL
from src.ui.dialogs import server_settings_dialog as mod
from src.ui.dialogs.server_settings_dialog import ServerSettingsDialog


@pytest.fixture
def dlg(qapp):
    d = ServerSettingsDialog(saved_id="tester")
    yield d
    d.close()
    d.deleteLater()


def test_sections_and_default_section(dlg):
    assert list(dlg.sections) == ["login", "server"]
    assert dlg.current_section() == "login" and dlg.stack.currentIndex() == 0
    dlg.go_to("server")
    assert dlg.current_section() == "server" and dlg.stack.currentIndex() == 1
    assert dlg.sections["server"].title() == "2. 서버 주소"


def test_server_urls_are_read_only_constants(dlg):
    f = dlg.url_fields
    assert [k for k in f] == ["qr20", "login", "upload", "qr21"]
    assert all(e.isReadOnly() for e in f.values())
    assert f["qr20"].text() == BASE_URL and f["login"].text() == LOGIN_URL
    assert f["upload"].text() == UPLOAD_URL and f["qr21"].text() == BASE_URL_QR21
    assert "cantilever-info" in f["qr21"].text()


def test_login_emits_credentials_and_clears_password(dlg):
    got = []
    dlg.login_requested.connect(lambda u, p: got.append((u, p)))
    dlg.pw_input.setText("pw-dummy")
    dlg.btn_login.click()
    assert got == [("tester", "pw-dummy")]
    assert dlg.pw_input.text() == ""          # 시그널 직후 입력창을 비운다
    assert not any("pw-dummy" in str(v) for v in vars(dlg).values())


def test_empty_credentials_warn_and_do_not_emit(qapp, monkeypatch):
    warnings = []
    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))
    d = ServerSettingsDialog(saved_id="")
    got = []
    d.login_requested.connect(lambda u, p: got.append(u))
    d.btn_login.click()                       # ID·PW 모두 비어 있음
    d.id_input.setText("tester")
    d.pw_input.returnPressed.emit()           # PW 비어 있음
    assert got == [] and len(warnings) == 2 and "모두 입력" in warnings[0]
    d.close()


def test_logout_and_session_check_signals(dlg):
    seen = []
    dlg.logout_requested.connect(lambda: seen.append("logout"))
    dlg.session_check_requested.connect(lambda: seen.append("check"))
    dlg.set_session_state("logged_in", "tester")
    dlg.btn_logout.click()
    dlg.btn_check.click()
    assert seen == ["logout", "check"]


def test_set_session_state_toggles_buttons_and_footer(dlg):
    assert dlg.status_label.text() == "미로그인"
    assert dlg.btn_login.isEnabled() and not dlg.btn_logout.isEnabled() and not dlg.btn_check.isEnabled()

    dlg.set_session_state("logged_in", "tester")
    assert dlg.status_label.text() == "로그인됨 (tester)"
    assert not dlg.btn_login.isEnabled() and dlg.btn_logout.isEnabled() and dlg.btn_check.isEnabled()

    dlg.set_session_state("expired")
    assert dlg.status_label.text() == "세션 만료"
    assert dlg.btn_login.isEnabled() and not dlg.btn_logout.isEnabled() and dlg.btn_check.isEnabled()

    dlg.set_session_state("uploading", "tester")
    assert dlg.status_label.text() == "업로드 중" and not dlg.btn_login.isEnabled()


def test_close_on_login_accepts_dialog(qapp):
    d = ServerSettingsDialog(saved_id="tester", close_on_login=True)
    results = []
    d.finished.connect(results.append)
    d.set_session_state("logged_out")
    assert results == []
    d.set_session_state("logged_in", "tester")
    assert results == [int(ServerSettingsDialog.Accepted)]
    d.deleteLater()


def test_opens_at_requested_section(qapp):
    d = ServerSettingsDialog(saved_id="", section="server")
    assert d.current_section() == "server"
    d.close()
