"""OCR 관련 사용자 설정 — 해상도별 ROI 프로파일 저장/조회 (F-14 + Phase 7A).

저장 포맷 v2
-----------
``app_settings.ocr_roi`` 에 JSON으로 저장::

    {
      "version": 2,
      "profiles": {
        "722x479":  {"frequency": [595, 95, 120, 30], "q_factor": [595, 175, 120, 30]},
        "1024x768": {"frequency": [...],               "q_factor": [...]}
      }
    }

해상도별로 독립된 ROI set을 보관한다. 이미지 드롭 시 ``load_roi_for(conn, W, H)``
로 맞는 프로파일을 조회하고, 없으면 None 반환 → 호출자가 코드 기본값으로 fallback.

v1 → v2 마이그레이션
-------------------
기존 v1 포맷 ``{"frequency": [...], "q_factor": [...]}`` 는 load 시 자동으로
v2로 승격되며, 해상도를 알 수 없으므로 ``"legacy"`` 키로 보존된다. 사용자가
Calibrator에서 실제 해상도 이미지로 저장하면 해당 해상도 키로 새 프로파일이
생성된다. ``"legacy"`` 엔트리는 ``load_roi()`` (구 API) 호출 시 fallback으로 사용.

이전 Phase 6B API (``load_roi`` / ``save_roi``) 는 하위 호환을 위해 남아 있으며,
내부적으로 legacy 프로파일에 대응한다.
"""
from __future__ import annotations

import sqlite3

from src.core.database import load_setting, save_setting

SETTING_KEY = "ocr_roi"
SCHEMA_VERSION = 2

RoiDict = dict[str, tuple[int, int, int, int]]


# ─── 키 / 유효성 ───


def resolution_key(width: int, height: int) -> str:
    """(W, H) → ``"WxH"`` 문자열 키."""
    return f"{int(width)}x{int(height)}"


def parse_resolution_key(key: str) -> tuple[int, int] | None:
    """``"WxH"`` → (W, H). 파싱 실패 시 None."""
    try:
        w_str, h_str = key.split("x", 1)
        return (int(w_str), int(h_str))
    except (ValueError, AttributeError):
        return None


def _validate_single_roi(value) -> RoiDict | None:
    """단일 프로파일(dict) 유효성 검증. 손상 시 None."""
    if not isinstance(value, dict):
        return None
    try:
        result: RoiDict = {}
        for k, vv in value.items():
            if not isinstance(k, str) or len(vv) != 4:
                return None
            result[k] = tuple(int(x) for x in vv)  # type: ignore[assignment]
        return result or None
    except (TypeError, ValueError):
        return None


# ─── 내부: 마이그레이션 ───


def _load_normalized(conn: sqlite3.Connection) -> dict:
    """DB에서 원시 값을 읽고 v2 포맷 dict 반환. 저장은 하지 않음.

    - v2 포맷이면 그대로 통과
    - v1 포맷 (최상위에 frequency/q_factor) 이면 ``profiles["legacy"]`` 로 승격
    - 없거나 손상되면 빈 profiles
    """
    raw = load_setting(conn, SETTING_KEY, default=None)
    if not isinstance(raw, dict):
        return {"version": SCHEMA_VERSION, "profiles": {}}

    # v2 감지
    if raw.get("version") == SCHEMA_VERSION and isinstance(raw.get("profiles"), dict):
        # profiles 각각 검증 (손상된 엔트리는 제외)
        clean_profiles: dict = {}
        for k, v in raw["profiles"].items():
            validated = _validate_single_roi(v)
            if validated:
                clean_profiles[k] = v  # 원본 형태(list)를 그대로 보존
        return {"version": SCHEMA_VERSION, "profiles": clean_profiles}

    # v1 감지 (legacy 승격)
    if "frequency" in raw or "q_factor" in raw:
        legacy = _validate_single_roi(raw)
        if legacy:
            return {
                "version": SCHEMA_VERSION,
                "profiles": {
                    "legacy": {k: [int(x) for x in v] for k, v in legacy.items()},
                },
            }

    return {"version": SCHEMA_VERSION, "profiles": {}}


# ─── 해상도별 API (Phase 7A 신규) ───


def load_roi_for(
    conn: sqlite3.Connection, width: int, height: int
) -> RoiDict | None:
    """특정 해상도의 ROI 프로파일 조회.

    Lookup 순서:
    1. 정확한 해상도 키 매칭 (``"WxH"``)
    2. ``"legacy"`` 프로파일 (v1 업그레이드 시 생성된 폴백)
    3. None (→ 호출자는 ``image_parser.ROI`` 코드 기본값 사용)
    """
    data = _load_normalized(conn)
    profiles = data.get("profiles") or {}

    key = resolution_key(width, height)
    if key in profiles:
        return _validate_single_roi(profiles[key])

    if "legacy" in profiles:
        return _validate_single_roi(profiles["legacy"])

    return None


def save_roi_for(
    conn: sqlite3.Connection, width: int, height: int, roi: RoiDict
) -> None:
    """특정 해상도에 ROI 저장. 기존 다른 프로파일은 보존."""
    data = _load_normalized(conn)
    profiles = dict(data.get("profiles") or {})
    key = resolution_key(width, height)
    profiles[key] = {k: [int(x) for x in v] for k, v in roi.items()}
    payload = {"version": SCHEMA_VERSION, "profiles": profiles}
    save_setting(conn, SETTING_KEY, payload)


def list_profiles(conn: sqlite3.Connection) -> list[tuple[str, RoiDict]]:
    """저장된 모든 (해상도 키, ROI) 쌍 목록. Calibrator UI 표시용."""
    data = _load_normalized(conn)
    profiles = data.get("profiles") or {}
    result: list[tuple[str, RoiDict]] = []
    for key, value in profiles.items():
        roi = _validate_single_roi(value)
        if roi:
            result.append((key, roi))
    return result


def delete_profile(conn: sqlite3.Connection, width: int, height: int) -> bool:
    """특정 해상도 프로파일 제거. 제거되면 True, 없었으면 False."""
    data = _load_normalized(conn)
    profiles = dict(data.get("profiles") or {})
    key = resolution_key(width, height)
    if key not in profiles:
        return False
    profiles.pop(key)
    save_setting(conn, SETTING_KEY, {"version": SCHEMA_VERSION, "profiles": profiles})
    return True


# ─── 구 API (Phase 6B 호환) ───


def load_roi(conn: sqlite3.Connection) -> RoiDict | None:
    """[Deprecated since 7A] 해상도를 모르는 호출 경로용 — ``load_roi_for`` 권장.

    legacy 프로파일 우선, 없고 프로파일이 정확히 1개면 그것을, 여러 개면 None.
    """
    data = _load_normalized(conn)
    profiles = data.get("profiles") or {}
    if "legacy" in profiles:
        return _validate_single_roi(profiles["legacy"])
    if len(profiles) == 1:
        (sole_value,) = profiles.values()
        return _validate_single_roi(sole_value)
    return None


def save_roi(conn: sqlite3.Connection, roi: RoiDict) -> None:
    """[Deprecated since 7A] legacy 프로파일에 저장 — ``save_roi_for`` 권장."""
    data = _load_normalized(conn)
    profiles = dict(data.get("profiles") or {})
    profiles["legacy"] = {k: [int(x) for x in v] for k, v in roi.items()}
    save_setting(conn, SETTING_KEY, {"version": SCHEMA_VERSION, "profiles": profiles})
