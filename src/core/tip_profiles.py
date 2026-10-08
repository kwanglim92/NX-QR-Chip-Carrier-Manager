"""Tip 프로필 — ``app_settings`` 독립 키 ``tip_profiles`` (SKILL 14 패턴).

Word 체크시트에 들어가는 Tip 별 고정 정보: Type 표기명 · SEM 이미지 · 스펙 표.
``{tip_name: {"display_name", "sem_image", "spec_layout", "spec_rows"}}`` 로 저장한다.

- ``spec_layout``: ``min_typ_max``(Technical Data | Lever: min/typ/max, 값 3개) 또는
  ``nominal_range``(Technical Data | Nominal Value | Specified Range, 값 2개).
- ``spec_rows``: ``[[label, v1, v2(, v3)], ...]`` — 값 수는 레이아웃의 헤더 수에 맞춰 pad/truncate.
- SEM 이미지는 저장 시 ``{app_data}/tip_images/{tip}.png`` 로 복사(PNG 변환)해 원본 위치와 무관하게 유지.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from PIL import Image

from src.core.database import get_db_dir, load_setting, save_setting

TIP_PROFILES_KEY = "tip_profiles"

SPEC_LAYOUTS = ("min_typ_max", "nominal_range")
SPEC_LAYOUT_HEADERS: dict[str, tuple[str, ...]] = {
    "min_typ_max": ("min", "typ", "max"),
    "nominal_range": ("Nominal Value", "Specified Range"),
}
SPEC_LAYOUT_LABELS: dict[str, str] = {
    "min_typ_max": "Technical Data | Lever: min / typ / max",
    "nominal_range": "Technical Data | Nominal Value / Specified Range",
}
DEFAULT_SPEC_ROWS = (
    "Length (um)",
    "Width (um)",
    "Thickness (um)",
    "Resonance frequency, kHz",
    "Force constant, N/m",
)
_SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z._-]+")


def default_tip_profile(name: str) -> dict[str, Any]:
    return {
        "display_name": name,
        "sem_image": "",
        "spec_layout": "min_typ_max",
        "spec_rows": [[label, "", "", ""] for label in DEFAULT_SPEC_ROWS],
    }


def normalize_tip_profile(name: str, raw: Any) -> dict[str, Any]:
    """레이아웃 검증, 행의 값 수를 헤더 수에 맞춤, 빈 label 행 제거, 표기명 공백이면 Tip 이름."""
    raw = raw if isinstance(raw, dict) else {}
    out = default_tip_profile(name)
    layout = str(raw.get("spec_layout", out["spec_layout"]))
    out["spec_layout"] = layout if layout in SPEC_LAYOUTS else out["spec_layout"]
    n_values = len(SPEC_LAYOUT_HEADERS[out["spec_layout"]])

    display = str(raw.get("display_name", "") or "").strip()
    out["display_name"] = display or name
    out["sem_image"] = str(raw.get("sem_image", "") or "").strip()

    rows_raw = raw.get("spec_rows")
    if isinstance(rows_raw, list):
        rows: list[list[str]] = []
        for row in rows_raw:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            label = str(row[0] or "").strip()
            if not label:
                continue
            values = [str(v if v is not None else "").strip() for v in row[1:1 + n_values]]
            values += [""] * (n_values - len(values))
            rows.append([label, *values])
        out["spec_rows"] = rows
    else:
        out["spec_rows"] = [[label, *([""] * n_values)] for label in DEFAULT_SPEC_ROWS]
    return out


def normalize_tip_profiles(raw: Any) -> dict[str, dict[str, Any]]:
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for key, prof in raw.items():
        name = str(key or "").strip()
        if name:
            out[name] = normalize_tip_profile(name, prof)
    return out


def load_tip_profiles(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return normalize_tip_profiles(load_setting(conn, TIP_PROFILES_KEY, {}))


def save_tip_profiles(conn: sqlite3.Connection, profiles: dict) -> dict[str, dict[str, Any]]:
    clean = normalize_tip_profiles(profiles)
    save_setting(conn, TIP_PROFILES_KEY, clean)
    return clean


def profile_for(profiles: dict, probe_type: str | None) -> dict[str, Any] | None:
    """probe_type 과 같은 이름의 프로필 (정확 일치 → 대소문자 무시)."""
    key = str(probe_type or "").strip()
    if not key:
        return None
    if key in profiles:
        return profiles[key]
    lowered = key.lower()
    for name, prof in profiles.items():
        if name.lower() == lowered:
            return prof
    return None


def tip_images_dir() -> Path:
    d = get_db_dir() / "tip_images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_tip_image(name: str, src: str | Path, dest_dir: Path | None = None) -> str:
    """``src`` 이미지를 ``dest_dir/{safe name}.png`` 로 변환 복사하고 그 경로를 돌려준다."""
    dest_dir = dest_dir or tip_images_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = _SAFE_NAME_RE.sub("_", name.strip()).strip("_") or "tip"
    out = dest_dir / f"{safe}.png"
    with Image.open(src) as im:
        im.convert("RGB").save(out, "PNG")
    return str(out)


def import_tip_images(profiles: dict, dest_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """``sem_image`` 가 보관 폴더 밖을 가리키면 복사해 경로를 치환 (이미 안에 있으면 그대로 — 멱등)."""
    dest_dir = dest_dir or tip_images_dir()
    out = normalize_tip_profiles(profiles)
    for name, prof in out.items():
        src = prof.get("sem_image", "")
        if not src:
            continue
        p = Path(src)
        if p.exists() and p.is_file() and p.resolve().parent != dest_dir.resolve():
            prof["sem_image"] = store_tip_image(name, p, dest_dir)
    return out
