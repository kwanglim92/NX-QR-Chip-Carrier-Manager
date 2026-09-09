"""SR-X300W 결과 프레임 파서 (설계 문서 §3.1, 2026-09-09 확정).

프레임 형식 (고정 72개, 미판독은 ``ERROR`` 자리표시):

    <code1>,<code2>,...,<code72>:<scantime>ms<CR>

명령 응답(``OK,...`` / ``ER,<cmd>,<code>``)은 판독 결과가 아니므로 ``classify_line`` 으로 구분한다.
하드웨어·소켓과 무관한 순수 함수만 둔다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_EXPECTED_COUNT = 72
DEFAULT_NG_TOKEN = "ERROR"
FIELD_SEP = ","
EXTRA_SEP = ":"
FRAME_TERMINATOR = b"\r"

_SCAN_TIME_RE = re.compile(r"^(\d+)ms$")


class FrameError(ValueError):
    """프레임 폐기 사유 (개수 불일치, 빈 필드, 결과가 아닌 줄)."""


@dataclass(frozen=True)
class CellRead:
    cell: int            # 리더기 격자 번호 1~N
    code: str | None     # 디코드 문자열, 미판독(NG)은 None
    raw: str             # 원문 필드

    @property
    def is_ng(self) -> bool:
        return self.code is None


@dataclass(frozen=True)
class ParsedFrame:
    reads: tuple[CellRead, ...]
    scan_time_ms: int | None = None

    @property
    def codes(self) -> list[str | None]:
        return [r.code for r in self.reads]

    @property
    def ng_cells(self) -> list[int]:
        return [r.cell for r in self.reads if r.is_ng]


def split_frames(buffer: bytes, terminator: bytes = FRAME_TERMINATOR) -> tuple[list[bytes], bytes]:
    """수신 버퍼를 종단자 기준으로 완성 프레임 목록과 잔여 바이트로 나눈다."""
    frames: list[bytes] = []
    rest = buffer
    while True:
        idx = rest.find(terminator)
        if idx < 0:
            return frames, rest
        frames.append(rest[:idx])
        rest = rest[idx + len(terminator):]


def classify_line(line: str) -> str:
    """줄 종류: ``result`` / ``ok`` / ``error`` / ``empty``."""
    text = line.strip("\r\n")
    if text == "":
        return "empty"
    if text == "OK" or text.startswith("OK,"):
        return "ok"
    if text.startswith("ER,"):
        return "error"
    return "result"


def parse_frame(
    data: bytes | str,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
    ng_token: str = DEFAULT_NG_TOKEN,
) -> ParsedFrame:
    """결과 프레임 1개 → ``ParsedFrame``. 형식이 어긋나면 ``FrameError``."""
    text = data.decode("ascii", errors="replace") if isinstance(data, bytes) else data
    text = text.strip("\r\n")

    kind = classify_line(text)
    if kind != "result":
        raise FrameError(f"판독 결과가 아닌 줄({kind}): {text[:40]!r}")

    body, sep, tail = text.rpartition(EXTRA_SEP)
    scan_time_ms: int | None = None
    if sep and (m := _SCAN_TIME_RE.match(tail)):
        scan_time_ms = int(m.group(1))
    else:
        body = text

    fields = body.split(FIELD_SEP)
    if len(fields) != expected_count:
        raise FrameError(f"필드 수 불일치: {len(fields)} != {expected_count}")

    reads: list[CellRead] = []
    for i, field in enumerate(fields, start=1):
        if field == "":
            raise FrameError(f"빈 필드 (셀 {i})")
        code = None if field == ng_token else field
        reads.append(CellRead(cell=i, code=code, raw=field))

    return ParsedFrame(reads=tuple(reads), scan_time_ms=scan_time_ms)
