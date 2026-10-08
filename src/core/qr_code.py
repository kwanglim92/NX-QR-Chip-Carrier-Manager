"""QR ID 디코더 — 칩 캐리어 QR 코드(16진수 10자리 = 40비트)의 버전·연도·Probe Type·일련번호.

비트 배치(상위 → 하위):
    1~4   Encoding Major (2)
    5~10  칩 캐리어 생산연도 2자리 (예 26 → 2026)
    11~14 Encoding Minor  (0 → QR 2.0, 1 → QR 2.1)
    15~22 Probe Type 코드
    23~40 해당 연도 일련번호

예) 현장 판독 ``2680002971`` → 2.0 / 26년 / probe 0 / S/N 0x2971,
    ``2684080D7C`` → 2.1 / 26년 / probe 2(PPP_NCHR) / S/N 3452.

QR 2.0 은 probe-info.parksystems.com, QR 2.1 은 cantilever-info.parksystems.com 로 올라간다.
현재 앱은 2.0 서버만 지원하므로 업로드 전 ``summarize_qr_versions`` 로 섞임 여부를 검사한다.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

QR_ID_RE = re.compile(r"^[0-9A-Fa-f]{10}$")
UPLOAD_QR_VERSION = "2.0"   # probe-info.parksystems.com 가 받는 버전


@dataclass(frozen=True)
class QRCodeInfo:
    code: str
    major: int
    year: int
    minor: int
    probe_code: int
    serial: int

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}"


def decode_qr_id(code: str | None) -> QRCodeInfo | None:
    """10자리 16진수가 아니면(수동 입력 ``QR-001`` 등) None."""
    s = (code or "").strip()
    if not QR_ID_RE.match(s):
        return None
    v = int(s, 16)
    return QRCodeInfo(
        code=s.upper(),
        major=(v >> 36) & 0xF,
        year=(v >> 30) & 0x3F,
        minor=(v >> 26) & 0xF,
        probe_code=(v >> 18) & 0xFF,
        serial=v & 0x3FFFF,
    )


def qr_version(code: str | None) -> str | None:
    info = decode_qr_id(code)
    return info.version if info else None


def summarize_qr_versions(codes: Iterable[str | None]) -> tuple[Counter, int]:
    """(버전별 개수, 해독 불가 개수)."""
    counts: Counter = Counter()
    undecodable = 0
    for c in codes:
        v = qr_version(c)
        if v is None:
            undecodable += 1
        else:
            counts[v] += 1
    return counts, undecodable
