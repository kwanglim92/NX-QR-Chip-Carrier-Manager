"""probe-info.parksystems.com 서버 업로드 자동화.

Django 기반 웹 폼 자동화:
  1. 로그인 (CSRF + 세션 쿠키)
  2. CSV + 이미지 파일 업로드 (신규 ``upload`` / 수정 ``update``)

보안 원칙:
  - TLS 인증서 검증을 끄지 않는다 (서버 인증서 유효 확인됨).
  - 자격증명(비밀번호)은 어떤 로그·예외 메시지·반환값에도 포함하지 않는다.
  - 서버 응답 HTML 을 디스크에 남기지 않는다 (메시지 텍스트만 반환).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://probe-info.parksystems.com"
LOGIN_URL = f"{BASE_URL}/accounts/login/"
LOGOUT_URL = f"{BASE_URL}/accounts/logout/"
UPLOAD_URL = f"{BASE_URL}/chip/login/probe/update/file"

UPLOAD_MODES = ("upload", "update")

# 세션이 없거나 만료되면 서버는 로그인 페이지 또는 ``/chip/?next=...`` 로 리다이렉트한다.
_LOGIN_REDIRECT_MARKERS = ("/accounts/login", "?next=")
_LOGIN_FORM_MARKER = 'id="id_username"'


@dataclass
class UploadResult:
    success: bool
    message: str
    csv_uploaded: bool = False
    image_count: int = 0
    mode: str = "upload"


def _looks_like_login_page(url: str, html: str) -> bool:
    """응답이 로그인/리다이렉트 페이지인지 판정 (세션 만료 감지)."""
    if any(marker in (url or "") for marker in _LOGIN_REDIRECT_MARKERS):
        return True
    return _LOGIN_FORM_MARKER in (html or "")


def _extract_csrf(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if not csrf_input:
        return None
    return csrf_input.get("value")


def upload_timeout_for(image_count: int) -> int:
    """이미지 수에 비례하는 POST 타임아웃(초). 60 + 10/장, 최대 600."""
    return min(600, 60 + 10 * max(0, image_count))


class ServerUploader:
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False
        self._username = ""

    # ─── 인증 ───

    def login(self, username: str, password: str) -> bool:
        """서버 로그인. 성공 시 True.

        성공 판정: ``sessionid`` 쿠키가 발급되고, 응답이 로그인 폼이 아니어야 한다
        (실패 시 Django 는 200 으로 로그인 폼을 다시 그린다).
        """
        try:
            r = self.session.get(LOGIN_URL, timeout=10)
            r.raise_for_status()

            csrf = _extract_csrf(r.text)
            if not csrf:
                raise ValueError("CSRF 토큰을 찾을 수 없습니다")

            r = self.session.post(
                LOGIN_URL,
                data={
                    "csrfmiddlewaretoken": csrf,
                    "username": username,
                    "password": password,
                },
                headers={"Referer": LOGIN_URL},
                timeout=10,
            )
            r.raise_for_status()

            has_session = "sessionid" in self.session.cookies
            still_login_form = _LOGIN_FORM_MARKER in (r.text or "")
            self.logged_in = has_session and not still_login_form
            self._username = username if self.logged_in else ""
            return self.logged_in

        except Exception:
            self.logged_in = False
            self._username = ""
            raise

    def is_session_alive(self) -> bool:
        """서버 세션 유효성 확인.

        업로드 페이지를 리다이렉트 없이 GET — 200 이면 유효, 302(로그인 유도)면 만료.
        만료/오류 시 ``logged_in`` 을 False 로 되돌린다.
        """
        if not self.logged_in:
            return False
        try:
            r = self.session.get(UPLOAD_URL, timeout=10, allow_redirects=False)
        except Exception:
            self.logged_in = False
            return False
        alive = r.status_code == 200 and not _looks_like_login_page(
            getattr(r, "url", ""), r.text
        )
        if not alive:
            self.logged_in = False
        return alive

    def logout(self):
        """세션 종료 (서버 로그아웃 + 로컬 쿠키 폐기)."""
        try:
            self.session.get(LOGOUT_URL, timeout=5)
        except Exception:
            pass
        try:
            self.session.cookies.clear()
        except Exception:
            pass
        self.session.close()
        self.logged_in = False
        self._username = ""

    @property
    def username(self) -> str:
        return self._username

    # ─── 업로드 ───

    def upload(
        self,
        csv_path: str,
        image_files: list[tuple[str, str]] | None = None,
        mode: str = "upload",
    ) -> UploadResult:
        """CSV + 이미지를 서버에 업로드.

        Args:
            csv_path: CSV 파일 경로
            image_files: ``(로컬 경로, 전송 파일명)`` 목록 (선택). 전송 파일명은
                호출자가 결정한다 (앱 규격: ``{QR ID}{확장자}``).
            mode: ``"upload"`` (신규) 또는 ``"update"`` (수정) — 서버 폼의 submit 버튼명.
        """
        if mode not in UPLOAD_MODES:
            raise ValueError(f"지원하지 않는 업로드 모드: {mode!r}")

        if not self.logged_in:
            return UploadResult(success=False, message="로그인이 필요합니다", mode=mode)

        csv_file = Path(csv_path)
        if not csv_file.exists():
            return UploadResult(
                success=False, message=f"CSV 파일 없음: {csv_path}", mode=mode
            )

        if not self.is_session_alive():
            return UploadResult(
                success=False, message="세션 만료 — 다시 로그인하세요", mode=mode
            )

        try:
            # CSRF 토큰 획득 (업로드 페이지 자체에서)
            r = self.session.get(UPLOAD_URL, timeout=10)
            r.raise_for_status()
            if _looks_like_login_page(r.url, r.text):
                self.logged_in = False
                return UploadResult(
                    success=False, message="세션 만료 — 다시 로그인하세요", mode=mode
                )
            csrf = _extract_csrf(r.text)
            if not csrf:
                raise ValueError("업로드 페이지 CSRF 토큰을 찾을 수 없습니다")

            # 파일 준비 + 업로드 — 성공·실패(예외) 모두 핸들을 정리해야
            # Windows 에서 임시 CSV 가 잠겨 삭제되지 않는 문제를 막는다.
            opened_files: list = []
            image_count = 0
            try:
                csv_fh = open(csv_file, "rb")
                opened_files.append(csv_fh)
                files = [
                    ("test_file", (csv_file.name, csv_fh, "text/csv")),
                ]

                for local_path, send_name in image_files or []:
                    p = Path(local_path)
                    if not p.exists():
                        continue
                    fh = open(p, "rb")
                    opened_files.append(fh)
                    mime = (
                        "image/jpeg"
                        if p.suffix.lower() in (".jpg", ".jpeg")
                        else "image/png"
                    )
                    files.append(("image_files[]", (send_name, fh, mime)))
                    image_count += 1

                data = {
                    "csrfmiddlewaretoken": csrf,
                    mode: "",  # 서버 폼의 submit 버튼명 (upload / update)
                }

                r = self.session.post(
                    UPLOAD_URL,
                    data=data,
                    files=files,
                    headers={"Referer": UPLOAD_URL},
                    timeout=upload_timeout_for(image_count),
                )
                r.raise_for_status()
            finally:
                for fh in opened_files:
                    try:
                        fh.close()
                    except Exception:
                        pass

            if _looks_like_login_page(r.url, r.text):
                self.logged_in = False
                return UploadResult(
                    success=False,
                    message="세션 만료 — 업로드가 서버에 전달되지 않았습니다",
                    mode=mode,
                )

            message = self._parse_response_message(r.text)
            if message is None:
                return UploadResult(
                    success=False,
                    message="응답 형식 불일치 — 서버 Message 영역을 찾을 수 없습니다",
                    mode=mode,
                )

            error_keywords = ["error", "fail", "오류", "실패"]
            has_error = any(kw in message.lower() for kw in error_keywords)

            return UploadResult(
                success=not has_error,
                message=message,
                csv_uploaded=True,
                image_count=image_count,
                mode=mode,
            )

        except Exception as e:
            return UploadResult(success=False, message=f"업로드 실패: {e}", mode=mode)

    @staticmethod
    def _parse_response_message(html: str) -> str | None:
        """업로드 응답에서 ``Message :`` 영역 텍스트 추출. 없으면 None.

        서버 마크업::

            <div><strong> Message :  </strong></div>
            <div>메시지 텍스트</div>
        """
        soup = BeautifulSoup(html, "html.parser")
        strong = soup.find("strong", string=lambda t: t and "Message" in t)
        if not strong or strong.parent is None:
            return None
        msg_div = strong.parent.find_next_sibling("div")
        if msg_div is None:
            return None
        return msg_div.get_text(strip=True)
