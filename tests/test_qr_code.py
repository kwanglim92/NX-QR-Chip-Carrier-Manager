"""QR ID 디코더 — 현장 판독값(2.0)과 인코딩 예시(2.1)로 비트 배치 검증."""
from __future__ import annotations

import pytest

from src.core.qr_code import UPLOAD_QR_VERSION, decode_qr_id, qr_version, summarize_qr_versions


def test_decode_field_fixture_is_qr20():
    info = decode_qr_id("2680002971")   # tests/fixtures/qr_reader 실제 판독값
    assert info is not None
    assert (info.major, info.year, info.minor) == (2, 26, 0)
    assert info.probe_code == 0 and info.serial == 0x2971
    assert info.version == "2.0" == UPLOAD_QR_VERSION


def test_decode_spec_example_is_qr21():
    info = decode_qr_id(" 2684080d7c ")   # 인코딩 예시: 2.1 / PPP_NCHR(2) / 2026 / S/N 3452
    assert info is not None
    assert info.code == "2684080D7C"
    assert (info.major, info.year, info.minor, info.probe_code, info.serial) == (2, 26, 1, 2, 3452)
    assert info.version == "2.1"


@pytest.mark.parametrize("bad", ["QR-001", "", None, "268000297", "26800029711", "268000297G"])
def test_non_hex_or_wrong_length_returns_none(bad):
    assert decode_qr_id(bad) is None
    assert qr_version(bad) is None


def test_summarize_counts_versions_and_undecodable():
    counts, undecodable = summarize_qr_versions(["2680002971", "2684080D7C", "QR-001", None, "2680086CB6"])
    assert counts == {"2.0": 2, "2.1": 1}
    assert undecodable == 2
