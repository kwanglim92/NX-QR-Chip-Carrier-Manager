"""R1: SR-X300W 결과 프레임 파서 — 실제 캡처 fixture + 합성 케이스."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.qr_reader.payload_parser import (
    CellRead,
    FrameError,
    ParsedFrame,
    classify_line,
    parse_frame,
    split_frames,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "qr_reader"
FULL_RAW = FIXTURE_DIR / "20260909_132804_full.raw"


def _frame(n: int, ng: set[int] = frozenset(), extra: str = ":100ms") -> str:
    fields = ["ERROR" if i in ng else f"QR{i:03d}" for i in range(1, n + 1)]
    return ",".join(fields) + extra + "\r"


# ─── 실제 fixture ───

def test_full_fixture_parses_72_cells_with_two_ng():
    frame = parse_frame(FULL_RAW.read_bytes())
    assert len(frame.reads) == 72
    assert frame.ng_cells == [13, 14]
    assert frame.scan_time_ms == 6064
    assert frame.reads[0] == CellRead(cell=1, code="2680002971", raw="2680002971")
    assert frame.reads[12] == CellRead(cell=13, code=None, raw="ERROR")
    assert frame.reads[71].code == "2680086CBC"
    assert all(len(c) == 10 for c in frame.codes if c is not None)


def test_full_fixture_raw_ends_with_single_cr():
    raw = FULL_RAW.read_bytes()
    assert raw.endswith(b"\r") and not raw.endswith(b"\r\n")
    frames, rest = split_frames(raw)
    assert len(frames) == 1 and rest == b""


# ─── parse_frame 합성 케이스 ───

def test_parse_str_and_bytes_equivalent():
    text = _frame(72)
    assert parse_frame(text) == parse_frame(text.encode())


def test_parse_without_scan_time():
    frame = parse_frame(_frame(72, extra=""))
    assert frame.scan_time_ms is None
    assert frame.reads[71].code == "QR072"


def test_parse_without_terminator():
    frame = parse_frame(_frame(72).rstrip("\r"))
    assert len(frame.reads) == 72 and frame.scan_time_ms == 100


def test_colon_tail_not_ms_is_part_of_last_code():
    frame = parse_frame("A,B:xyz", expected_count=2)
    assert frame.scan_time_ms is None
    assert frame.reads[1].code == "B:xyz"


def test_custom_ng_token_and_count():
    frame = parse_frame("X,NG,Y:5ms", expected_count=3, ng_token="NG")
    assert frame.codes == ["X", None, "Y"]
    assert frame.scan_time_ms == 5


@pytest.mark.parametrize("n", [71, 73])
def test_count_mismatch_raises(n):
    with pytest.raises(FrameError, match="필드 수 불일치"):
        parse_frame(_frame(n))


def test_empty_field_raises():
    with pytest.raises(FrameError, match="빈 필드"):
        parse_frame("A,,C", expected_count=3)


@pytest.mark.parametrize("line", ["OK,KEYENCE,SR-X300,1.73,7.244\r", "ER,LON,23\r", "", "\r"])
def test_non_result_lines_raise(line):
    with pytest.raises(FrameError):
        parse_frame(line, expected_count=1)


def test_all_ng_frame_is_valid():
    frame = parse_frame(_frame(72, ng=set(range(1, 73))))
    assert frame.ng_cells == list(range(1, 73))
    assert isinstance(frame, ParsedFrame)


# ─── classify_line ───

@pytest.mark.parametrize("line,kind", [
    ("OK,KEYENCE,SR-X300,1.73,7.244", "ok"),
    ("OK", "ok"),
    ("ER,KEYENCE,23", "error"),
    ("", "empty"),
    ("\r\n", "empty"),
    ("2680002971,ERROR:6064ms", "result"),
    ("OKAY", "result"),
])
def test_classify_line(line, kind):
    assert classify_line(line) == kind


# ─── split_frames ───

def test_split_frames_partial_buffer():
    frames, rest = split_frames(b"A,B:1ms\rC,D:2ms\rE,F")
    assert frames == [b"A,B:1ms", b"C,D:2ms"]
    assert rest == b"E,F"


def test_split_frames_empty_and_no_terminator():
    assert split_frames(b"") == ([], b"")
    assert split_frames(b"abc") == ([], b"abc")


def test_split_frames_consecutive_terminators_yield_empty_frames():
    frames, rest = split_frames(b"\r\rX\r")
    assert frames == [b"", b"", b"X"] and rest == b""
