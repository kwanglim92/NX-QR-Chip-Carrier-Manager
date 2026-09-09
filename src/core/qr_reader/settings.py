"""리더기 설정 — ``app_settings`` 독립 키 ``qr_reader`` (설계 문서 §4, SKILL 14 패턴).

JSON 으로 저장되므로 ``cell_override`` 의 키는 문자열로 돌아온다. ``normalize_qr_reader_settings`` 가
타입·범위를 정리해 항상 완전한 dict 를 돌려준다.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from src.core.database import load_setting, save_setting
from src.core.qr_reader.payload_parser import DEFAULT_EXPECTED_COUNT, DEFAULT_NG_TOKEN
from src.core.qr_reader.slot_assigner import SLOTS_PER_PORT

QR_READER_KEY = "qr_reader"

TRANSPORTS = ("lan", "serial", "keyboard")

DEFAULT_QR_READER_SETTINGS: dict[str, Any] = {
    "enabled": True,                # 앱 시작 시 자동 접속(기본 켜짐). 끄면 설정 창에서 저장할 때만 접속
    "transport": "lan",             # lan | serial | keyboard(폴백: 리더기 기능 비활성)
    "host": "192.168.100.2",
    "port": 9004,
    "read_seconds": 6.0,            # LON 후 LOFF 까지 대기
    "result_timeout_s": 10.0,       # LOFF 후 결과 대기
    "connect_timeout_s": 5.0,
    "expected_count": DEFAULT_EXPECTED_COUNT,
    "ng_token": DEFAULT_NG_TOKEN,
    "trigger_cmd": "LON",
    "stop_cmd": "LOFF",
    "cell_override": {},            # {cell(int): [port, slot]}
}

_RANGES = {
    "port": (1, 65535),
    "read_seconds": (0.1, 60.0),
    "result_timeout_s": (0.5, 120.0),
    "connect_timeout_s": (0.5, 60.0),
    "expected_count": (1, 999),
}


def _num(value, default, lo, hi, cast):
    try:
        v = cast(value)
    except (TypeError, ValueError):
        return default
    return default if v < lo or v > hi else v


def normalize_qr_reader_settings(raw: dict | None) -> dict[str, Any]:
    """저장값/사용자 입력을 기본값과 병합하고 타입·범위를 정리한다. 잘못된 값은 기본값으로."""
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = dict(DEFAULT_QR_READER_SETTINGS)
    out["cell_override"] = {}

    out["enabled"] = bool(raw.get("enabled", out["enabled"]))
    transport = str(raw.get("transport", out["transport"])).lower()
    out["transport"] = transport if transport in TRANSPORTS else out["transport"]
    host = str(raw.get("host", out["host"])).strip()
    out["host"] = host or out["host"]

    out["port"] = _num(raw.get("port"), out["port"], *_RANGES["port"], int)
    out["read_seconds"] = _num(raw.get("read_seconds"), out["read_seconds"], *_RANGES["read_seconds"], float)
    out["result_timeout_s"] = _num(raw.get("result_timeout_s"), out["result_timeout_s"], *_RANGES["result_timeout_s"], float)
    out["connect_timeout_s"] = _num(raw.get("connect_timeout_s"), out["connect_timeout_s"], *_RANGES["connect_timeout_s"], float)
    out["expected_count"] = _num(raw.get("expected_count"), out["expected_count"], *_RANGES["expected_count"], int)

    for key in ("ng_token", "trigger_cmd", "stop_cmd"):
        val = str(raw.get(key, out[key])).strip()
        out[key] = val or out[key]
    if out["ng_token"] in ("OK", "ER") or out["ng_token"].startswith(("OK,", "ER,")):
        out["ng_token"] = DEFAULT_NG_TOKEN

    override_raw = raw.get("cell_override") or {}
    if isinstance(override_raw, dict):
        for k, v in override_raw.items():
            try:
                cell = int(k)
                port, slot = int(v[0]), int(v[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if cell < 1 or port < 1 or not 1 <= slot <= SLOTS_PER_PORT:
                continue
            out["cell_override"][cell] = (port, slot)
    return out


def load_qr_reader_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    return normalize_qr_reader_settings(load_setting(conn, QR_READER_KEY, {}))


def save_qr_reader_settings(conn: sqlite3.Connection, settings: dict) -> dict[str, Any]:
    """정규화 후 저장. JSON 직렬화를 위해 override 키는 문자열, 값은 리스트로 기록한다."""
    clean = normalize_qr_reader_settings(settings)
    payload = dict(clean)
    payload["cell_override"] = {str(c): [p, s] for c, (p, s) in clean["cell_override"].items()}
    save_setting(conn, QR_READER_KEY, payload)
    return clean


def client_kwargs(settings: dict) -> dict[str, Any]:
    """``KeyenceClient.configure(**...)`` 에 그대로 넘길 인자."""
    s = normalize_qr_reader_settings(settings)
    return {
        "host": s["host"],
        "port": s["port"],
        "read_seconds": s["read_seconds"],
        "result_timeout_s": s["result_timeout_s"],
        "connect_timeout_s": s["connect_timeout_s"],
        "expected_count": s["expected_count"],
        "ng_token": s["ng_token"],
        "trigger_cmd": s["trigger_cmd"],
        "stop_cmd": s["stop_cmd"],
    }
