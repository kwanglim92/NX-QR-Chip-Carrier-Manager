"""ServerUploader 단위 테스트 — 실제 네트워크 없이 ``requests.Session`` 을 Fake 로 대체.

운영 서버(probe-info.parksystems.com)에는 어떤 요청도 보내지 않는다. 모든 케이스는
2026-09-07 사이트 분석에서 확인한 실제 마크업/리다이렉트 동작을 그대로 재현한 응답으로 검증한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core import server_uploader as su
from src.core.server_uploader import (
    LOGIN_URL,
    UPLOAD_URL,
    ServerUploader,
    UploadResult,
    upload_timeout_for,
)

# ─── 실제 서버 마크업 재현 ───

LOGIN_FORM_HTML = """
<form action="" method="post">
  <input type="hidden" name="csrfmiddlewaretoken" value="csrf-login-token">
  <input type="text" name="username" id="id_username" required>
  <input type="password" name="password" id="id_password" required>
  <button type="submit">Sign in</button>
</form>
"""

UPLOAD_FORM_HTML = """
<form action="" method="post" enctype="multipart/form-data">
  <input type="hidden" name="csrfmiddlewaretoken" value="csrf-upload-token">
  <input type="file" name="test_file">
  <input type="file" name="image_files[]" multiple>
  <button type="submit" name="upload">Upload</button>
  <button type="submit" name="update">Update</button>
</form>
<div style="margin-top: 10px;"><strong> Message :  </strong></div>
<div>
    Request isn't POST
</div>
<div></div>
"""

# 미로그인 시 /chip/?next=... 로 리다이렉트된 페이지 — 여기에도 CSRF 토큰이 있는 검색 폼이 존재
CHIP_SEARCH_HTML = """
<a href="/accounts/login/">Log In</a>
<form action="" method="post">
  <input type="hidden" name="csrfmiddlewaretoken" value="csrf-search-token">
  <input type="text" name="encoding_data" id="id_encoding_data" required>
  <button type="submit">Search</button>
</form>
"""


def _message_page(text: str) -> str:
    return (
        UPLOAD_FORM_HTML.split("<div style=")[0]
        + f'<div style="margin-top: 10px;"><strong> Message :  </strong></div>\n'
        f"<div>\n    {text}\n</div>\n<div></div>"
    )


# ─── Fake requests.Session ───


class _FakeCookies(dict):
    def clear(self):  # dict.clear 와 동일하지만 명시
        super().clear()


class FakeResponse:
    def __init__(self, status: int, url: str, text: str = ""):
        self.status_code = status
        self.url = url
        self.text = text
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise su.requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """스크립트된 응답 큐 + 호출 기록. 큐가 비면 테스트 실패."""

    instances: list["FakeSession"] = []

    def __init__(self):
        self.verify = True
        self.cookies = _FakeCookies()
        self.calls: list[dict] = []
        self._queue: list[tuple[str, FakeResponse, dict]] = []
        self.closed = False
        FakeSession.instances.append(self)

    # 스크립팅
    def expect(self, method: str, response: FakeResponse, set_cookies: dict | None = None):
        self._queue.append((method, response, set_cookies or {}))
        return self

    def _next(self, method: str, url: str, **kwargs) -> FakeResponse:
        if not self._queue:
            raise AssertionError(f"예상치 못한 요청: {method} {url}")
        exp_method, resp, set_cookies = self._queue.pop(0)
        assert exp_method == method, f"기대 {exp_method}, 실제 {method} {url}"
        self.calls.append({"method": method, "url": url, **kwargs})
        self.cookies.update(set_cookies)
        return resp

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_session(monkeypatch):
    FakeSession.instances.clear()
    monkeypatch.setattr(su.requests, "Session", FakeSession)
    up = ServerUploader()
    assert isinstance(up.session, FakeSession), "requests.Session 이 Fake 로 대체되어야 한다"
    return up, up.session


def _logged_in(up: ServerUploader, sess: FakeSession, username="mfg_probe"):
    sess.expect("GET", FakeResponse(200, LOGIN_URL, LOGIN_FORM_HTML))
    sess.expect(
        "POST",
        FakeResponse(200, "https://probe-info.parksystems.com/chip/login/", "<a>Log Out</a>"),
        set_cookies={"csrftoken": "c", "sessionid": "s"},
    )
    assert up.login(username, "secret-pw") is True
    return up


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    p = tmp_path / "upload.csv"
    p.write_text("QR ID,생산일자[YYYYMMDD],Frequency (KHz),Drive (%),Q,Probe Type\n1234567890,20260907,300,,600,AC160\n", encoding="utf-8-sig")
    return p


# ─── 보안 기본값 ───


def test_tls_verification_stays_enabled(fake_session):
    up, sess = fake_session
    assert sess.verify is True
    assert not hasattr(su, "urllib3"), "urllib3 경고 억제 코드가 남아 있으면 안 된다"


# ─── 로그인 ───


def test_login_success_sets_session(fake_session):
    up, sess = fake_session
    _logged_in(up, sess)
    assert up.logged_in is True
    assert up.username == "mfg_probe"
    post = sess.calls[1]
    assert post["url"] == LOGIN_URL
    assert post["data"]["csrfmiddlewaretoken"] == "csrf-login-token"
    assert post["data"]["username"] == "mfg_probe"
    assert post["headers"]["Referer"] == LOGIN_URL


def test_login_failure_when_form_redisplayed(fake_session):
    up, sess = fake_session
    sess.expect("GET", FakeResponse(200, LOGIN_URL, LOGIN_FORM_HTML))
    # Django 는 실패 시 200 으로 로그인 폼을 다시 그리고 sessionid 를 주지 않는다
    sess.expect("POST", FakeResponse(200, LOGIN_URL, LOGIN_FORM_HTML), set_cookies={"csrftoken": "c"})
    assert up.login("mfg_probe", "wrong") is False
    assert up.logged_in is False
    assert up.username == ""


def test_login_failure_when_sessionid_but_still_login_form(fake_session):
    up, sess = fake_session
    sess.expect("GET", FakeResponse(200, LOGIN_URL, LOGIN_FORM_HTML))
    sess.expect("POST", FakeResponse(200, LOGIN_URL, LOGIN_FORM_HTML), set_cookies={"sessionid": "stale"})
    assert up.login("mfg_probe", "wrong") is False
    assert up.logged_in is False


def test_login_exception_never_leaks_password(fake_session):
    up, sess = fake_session
    sess.expect("GET", FakeResponse(200, LOGIN_URL, "<html>no csrf here</html>"))
    with pytest.raises(ValueError) as ei:
        up.login("mfg_probe", "Very$ecretPW!")
    assert "Very$ecretPW!" not in str(ei.value)
    assert up.logged_in is False


# ─── 세션 유효성 ───


def test_is_session_alive_false_when_not_logged_in(fake_session):
    up, sess = fake_session
    assert up.is_session_alive() is False
    assert sess.calls == [], "미로그인 상태에서는 네트워크 요청을 보내지 않는다"


def test_is_session_alive_true_on_200(fake_session):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    assert up.is_session_alive() is True
    assert sess.calls[-1]["allow_redirects"] is False
    assert up.logged_in is True


def test_is_session_alive_false_on_302_resets_flag(fake_session):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(302, UPLOAD_URL, ""))
    assert up.is_session_alive() is False
    assert up.logged_in is False


# ─── 업로드 ───


def test_upload_requires_login(fake_session, csv_file):
    up, sess = fake_session
    res = up.upload(str(csv_file))
    assert res.success is False
    assert "로그인" in res.message
    assert sess.calls == []


def test_upload_rejects_unknown_mode(fake_session, csv_file):
    up, sess = fake_session
    with pytest.raises(ValueError):
        up.upload(str(csv_file), mode="delete")


def test_upload_missing_csv(fake_session, tmp_path):
    up, sess = fake_session
    _logged_in(up, sess)
    res = up.upload(str(tmp_path / "nope.csv"))
    assert res.success is False and "CSV 파일 없음" in res.message


def test_upload_success_parses_message_and_sends_expected_fields(fake_session, csv_file, tmp_path):
    up, sess = fake_session
    _logged_in(up, sess)
    img1 = tmp_path / "slot_01_1234567890.png"
    img1.write_bytes(b"\x89PNG")
    img2 = tmp_path / "slot_02_2222222222.jpg"
    img2.write_bytes(b"\xff\xd8")

    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))  # is_session_alive
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))  # CSRF
    sess.expect("POST", FakeResponse(200, UPLOAD_URL, _message_page("2 rows saved")))

    res = up.upload(
        str(csv_file),
        [(str(img1), "1234567890.png"), (str(img2), "2222222222.jpg"), (str(tmp_path / "missing.png"), "x.png")],
        mode="upload",
    )
    assert res == UploadResult(True, "2 rows saved", csv_uploaded=True, image_count=2, mode="upload")

    post = sess.calls[-1]
    assert post["url"] == UPLOAD_URL
    assert post["data"] == {"csrfmiddlewaretoken": "csrf-upload-token", "upload": ""}
    assert post["headers"]["Referer"] == UPLOAD_URL
    files = post["files"]
    assert files[0][0] == "test_file" and files[0][1][0] == "upload.csv" and files[0][1][2] == "text/csv"
    image_parts = [f for f in files if f[0] == "image_files[]"]
    assert [f[1][0] for f in image_parts] == ["1234567890.png", "2222222222.jpg"]
    assert [f[1][2] for f in image_parts] == ["image/png", "image/jpeg"]
    # 파일 핸들은 모두 닫혀야 한다 (Windows 임시파일 잠김 방지)
    assert all(f[1][1].closed for f in files)
    assert post["timeout"] == upload_timeout_for(2)


def test_upload_update_mode_uses_update_button(fake_session, csv_file):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("POST", FakeResponse(200, UPLOAD_URL, _message_page("updated")))
    res = up.upload(str(csv_file), None, mode="update")
    assert res.success is True and res.mode == "update"
    assert sess.calls[-1]["data"] == {"csrfmiddlewaretoken": "csrf-upload-token", "update": ""}
    assert "upload" not in sess.calls[-1]["data"]


def test_upload_fails_on_error_keyword(fake_session, csv_file):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("POST", FakeResponse(200, UPLOAD_URL, _message_page("Upload Error: duplicated encoding data")))
    res = up.upload(str(csv_file))
    assert res.success is False
    assert res.message == "Upload Error: duplicated encoding data"
    assert res.csv_uploaded is True


def test_upload_fails_when_message_block_missing(fake_session, csv_file):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("POST", FakeResponse(200, UPLOAD_URL, "<html><body>unexpected page</body></html>"))
    res = up.upload(str(csv_file))
    assert res.success is False
    assert "응답 형식 불일치" in res.message


def test_upload_expired_session_never_posts(fake_session, csv_file):
    """세션 만료 시 (302) 업로드 POST 를 보내지 않고 실패로 보고 — 기존 false-success 버그 회귀 방지."""
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(302, UPLOAD_URL, ""))
    res = up.upload(str(csv_file))
    assert res.success is False
    assert "세션 만료" in res.message
    assert up.logged_in is False
    assert [c["method"] for c in sess.calls].count("POST") == 1, "로그인 POST 외 추가 POST 없음"


def test_upload_detects_redirect_to_login_after_post(fake_session, csv_file):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    # POST 직후 서버가 세션을 끊어 /chip/?next=... 로 보낸 경우 (requests 는 리다이렉트를 따라감)
    sess.expect("POST", FakeResponse(200, "https://probe-info.parksystems.com/chip/?next=/chip/login/probe/update/file", CHIP_SEARCH_HTML))
    res = up.upload(str(csv_file))
    assert res.success is False
    assert "세션 만료" in res.message
    assert up.logged_in is False


def test_upload_csrf_get_redirected_to_chip_page_is_failure(fake_session, csv_file):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("GET", FakeResponse(200, "https://probe-info.parksystems.com/chip/?next=/chip/login/probe/update/file", CHIP_SEARCH_HTML))
    res = up.upload(str(csv_file))
    assert res.success is False
    assert "세션 만료" in res.message
    assert [c["method"] for c in sess.calls].count("POST") == 1


def test_upload_http_error_is_reported_not_raised(fake_session, csv_file):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("GET", FakeResponse(200, UPLOAD_URL, UPLOAD_FORM_HTML))
    sess.expect("POST", FakeResponse(500, UPLOAD_URL, ""))
    res = up.upload(str(csv_file))
    assert res.success is False and "업로드 실패" in res.message


# ─── 로그아웃 / 기타 ───


def test_logout_clears_cookies_and_state(fake_session):
    up, sess = fake_session
    _logged_in(up, sess)
    sess.expect("GET", FakeResponse(200, su.LOGOUT_URL, ""))
    up.logout()
    assert up.logged_in is False
    assert up.username == ""
    assert dict(sess.cookies) == {}
    assert sess.closed is True


def test_parse_response_message_real_markup():
    html = '<div style="margin-top: 10px;">\n<strong> Message :  </strong>\n</div>\n<div>\n Request isn\'t POST\n</div>'
    assert ServerUploader._parse_response_message(html) == "Request isn't POST"
    assert ServerUploader._parse_response_message("<p>nothing</p>") is None


@pytest.mark.parametrize("n,expected", [(0, 60), (1, 70), (10, 160), (100, 600), (-5, 60)])
def test_upload_timeout_scales_with_images(n, expected):
    assert upload_timeout_for(n) == expected
