"""R4-a: qr_reader 설정 정규화 + app_settings 영속화."""
from __future__ import annotations

from src.core.database import load_setting
from src.core.qr_reader.settings import (
    DEFAULT_QR_READER_SETTINGS,
    QR_READER_KEY,
    client_kwargs,
    load_qr_reader_settings,
    normalize_qr_reader_settings,
    save_qr_reader_settings,
)


def test_defaults_when_empty_or_invalid():
    for raw in (None, {}, "junk", []):
        s = normalize_qr_reader_settings(raw)
        assert s["host"] == "192.168.100.2" and s["port"] == 9004
        assert s["read_seconds"] == 6.0 and s["expected_count"] == 72
        assert s["ng_token"] == "ERROR" and s["cell_override"] == {}
        assert s["enabled"] is True and s["transport"] == "lan"   # 자동 접속 기본 켜짐
        assert s["preview_rotation"] == 270


def test_out_of_range_and_bad_types_fall_back():
    s = normalize_qr_reader_settings({
        "port": 70000, "read_seconds": "abc", "expected_count": 0,
        "transport": "usb", "host": "   ", "ng_token": "ER", "trigger_cmd": "",
    })
    assert s["port"] == 9004 and s["read_seconds"] == 6.0 and s["expected_count"] == 72
    assert s["transport"] == "lan" and s["host"] == "192.168.100.2"
    assert s["ng_token"] == "ERROR" and s["trigger_cmd"] == "LON"
    assert normalize_qr_reader_settings({"preview_rotation": 45})["preview_rotation"] == 270
    assert normalize_qr_reader_settings({"preview_rotation": "270"})["preview_rotation"] == 270


def test_valid_values_are_kept_and_cast():
    s = normalize_qr_reader_settings({"port": "9100", "read_seconds": "3", "enabled": 1, "host": " 10.0.0.5 "})
    assert s["port"] == 9100 and s["read_seconds"] == 3.0 and s["enabled"] is True and s["host"] == "10.0.0.5"


def test_override_keys_are_normalized_and_validated():
    s = normalize_qr_reader_settings({"cell_override": {
        "1": [6, 12], 2: (2, 3), "x": [1, 1], "3": [0, 1], "4": [1, 13], "5": "bad",
    }})
    assert s["cell_override"] == {1: (6, 12), 2: (2, 3)}


def test_save_and_load_round_trip(db_conn):
    saved = save_qr_reader_settings(db_conn, {"host": "192.168.100.9", "cell_override": {7: (1, 2)}, "port": 9005})
    assert saved["host"] == "192.168.100.9"
    stored = load_setting(db_conn, QR_READER_KEY)
    assert stored["cell_override"] == {"7": [1, 2]}          # JSON 친화 형태로 기록
    loaded = load_qr_reader_settings(db_conn)
    assert loaded["host"] == "192.168.100.9" and loaded["port"] == 9005
    assert loaded["cell_override"] == {7: (1, 2)}
    assert set(loaded) == set(DEFAULT_QR_READER_SETTINGS)


def test_load_without_saved_value_gives_defaults(db_conn):
    assert load_qr_reader_settings(db_conn) == normalize_qr_reader_settings({})


def test_client_kwargs_subset():
    kw = client_kwargs({"host": "1.2.3.4", "port": 9004, "read_seconds": 2.5})
    assert kw == {
        "host": "1.2.3.4", "port": 9004, "read_seconds": 2.5, "result_timeout_s": 10.0,
        "connect_timeout_s": 5.0, "expected_count": 72, "ng_token": "ERROR",
        "trigger_cmd": "LON", "stop_cmd": "LOFF",
    }
