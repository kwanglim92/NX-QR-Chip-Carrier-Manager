"""probe-info.parksystems.com 서버 업로드 자동화.

Django 기반 웹 폼 자동화:
  1. 로그인 (CSRF + 세션 쿠키)
  2. CSV + 이미지 파일 업로드
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import urllib3

import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://probe-info.parksystems.com"
LOGIN_URL = f"{BASE_URL}/accounts/login/"
UPLOAD_URL = f"{BASE_URL}/chip/login/probe/update/file"


@dataclass
class UploadResult:
    success: bool
    message: str
    csv_uploaded: bool = False
    image_count: int = 0


class ServerUploader:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.logged_in = False
        self._username = ""

    def login(self, username: str, password: str) -> bool:
        """서버 로그인. 성공 시 True."""
        try:
            r = self.session.get(LOGIN_URL, timeout=10)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
            if not csrf_input:
                raise ValueError("CSRF 토큰을 찾을 수 없습니다")

            csrf = csrf_input["value"]

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

            # 로그인 성공 시 세션 쿠키에 sessionid 존재
            self.logged_in = "sessionid" in self.session.cookies
            if self.logged_in:
                self._username = username
            return self.logged_in

        except Exception:
            self.logged_in = False
            raise

    def upload(
        self,
        csv_path: str,
        image_paths: list[str] | None = None,
        mode: str = "upload",
    ) -> UploadResult:
        """CSV + 이미지를 서버에 업로드.

        Args:
            csv_path: CSV 파일 경로
            image_paths: 이미지 파일 경로 목록 (선택)
            mode: "upload" (신규) 또는 "update" (수정)
        """
        if not self.logged_in:
            return UploadResult(success=False, message="로그인이 필요합니다")

        csv_file = Path(csv_path)
        if not csv_file.exists():
            return UploadResult(success=False, message=f"CSV 파일 없음: {csv_path}")

        try:
            # CSRF 토큰 획득
            r = self.session.get(UPLOAD_URL, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
            if not csrf_input:
                raise ValueError("업로드 페이지 CSRF 토큰을 찾을 수 없습니다")
            csrf = csrf_input["value"]

            # 파일 준비
            files = [
                ("test_file", (csv_file.name, open(csv_file, "rb"), "text/csv")),
            ]

            image_count = 0
            image_file_handles = []
            if image_paths:
                for img_path in image_paths:
                    p = Path(img_path)
                    if p.exists():
                        fh = open(p, "rb")
                        image_file_handles.append(fh)
                        mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                        files.append(("image_files[]", (p.name, fh, mime)))
                        image_count += 1

            # POST 업로드
            data = {
                "csrfmiddlewaretoken": csrf,
                mode: "",  # upload 또는 update 버튼
            }

            r = self.session.post(
                UPLOAD_URL,
                data=data,
                files=files,
                headers={"Referer": UPLOAD_URL},
                timeout=60,
            )
            r.raise_for_status()

            # 파일 핸들 정리
            for fh in image_file_handles:
                fh.close()

            # 응답 파싱
            message = self._parse_response_message(r.text)

            # 에러 키워드 체크
            error_keywords = ["error", "fail", "오류", "실패"]
            has_error = any(kw in message.lower() for kw in error_keywords)

            return UploadResult(
                success=not has_error,
                message=message,
                csv_uploaded=True,
                image_count=image_count,
            )

        except Exception as e:
            return UploadResult(success=False, message=f"업로드 실패: {e}")

    def _parse_response_message(self, html: str) -> str:
        """업로드 응답에서 Message 영역 추출."""
        soup = BeautifulSoup(html, "html.parser")

        # Message: 다음 div 텍스트
        strong = soup.find("strong", string=lambda t: t and "Message" in t)
        if strong:
            msg_div = strong.parent.find_next_sibling("div")
            if msg_div:
                return msg_div.text.strip()

        # Encoding Data 테이블 (업로드 결과)
        tables = soup.find_all("table")
        if len(tables) > 1:
            rows = tables[-1].find_all("tr")
            if rows:
                return f"데이터 {len(rows) - 1}건 처리됨"

        return "응답 확인 불가"

    def logout(self):
        """세션 종료."""
        try:
            self.session.get(f"{BASE_URL}/accounts/logout/", timeout=5)
        except Exception:
            pass
        self.session.close()
        self.logged_in = False
        self._username = ""

    @property
    def username(self) -> str:
        return self._username
