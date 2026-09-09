"""등급 사다리 템플릿 — 항목 카탈로그, 기본값(AC160), 정규화, Spec Limits 동기화.

템플릿(JSON 직렬화 가능) 형식::

    {"tip_id": "AC160", "um_per_pixel": 0.345,
     "grades": [
        {"key": "industrial", "name": "산업용",
         "items": {"a_plus_b": {"enabled": true, "offset": 1.0},
                   "q":        {"enabled": true, "min": 200, "max": 700},
                   "sweep_shape": {"enabled": true, "min": 70}, ...}},
        {"key": "research", ...}, {"key": "recheck", ...}]}

사다리 순서 = ``GRADES`` 순서(산업용 → 연구용 → 재검사). 전부 실패 = ``reject``(불량,
임계값 없음). ``app_settings.inspection_templates`` 에 ``{tip_id: template}`` 로 저장.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from src.core.inspection.reference import DEFAULT_UM_PER_PIXEL

SETTINGS_KEY = "inspection_templates"

GRADES: tuple[tuple[str, str], ...] = (
    ("industrial", "산업용"),
    ("research", "연구용"),
    ("recheck", "재검사"),
)
REJECT_KEY = "reject"
REJECT_NAME = "불량"
GRADE_KEYS = tuple(k for k, _ in GRADES)
GRADE_NAMES: dict[str, str] = {**dict(GRADES), REJECT_KEY: REJECT_NAME}
ALL_GRADE_KEYS = GRADE_KEYS + (REJECT_KEY,)


@dataclass(frozen=True)
class ItemSpec:
    key: str
    label: str        # 폼 라벨
    short: str        # Error 열용 짧은 이름
    kind: str         # "offset" | "range" | "min"
    unit: str = ""


ITEM_CATALOG: tuple[ItemSpec, ...] = (
    ItemSpec("a_plus_b", "A+B (V)", "A+B", "offset", "V"),
    ItemSpec("a_minus_b", "A-B (V)", "A-B", "offset", "V"),
    ItemSpec("c_minus_d", "C-D (V)", "C-D", "offset", "V"),
    ItemSpec("drive", "Drive (%)", "Drive", "range", "%"),
    ItemSpec("q", "Q", "Q", "range", ""),
    ItemSpec("frequency", "Frequency (kHz)", "Frequency", "range", "kHz"),
    ItemSpec("x_offset_um", "X Offset (um)", "X Offset", "range", "um"),
    ItemSpec("y_offset_um", "Y Offset (um)", "Y Offset", "range", "um"),
    ItemSpec("angle_offset_deg", "Angle Offset (degree)", "Angle", "offset", "°"),
    ItemSpec("sweep_shape", "Sweep Shape (score)", "Sweep Shape", "min", ""),
    ItemSpec("vision_match", "Vision Match (%)", "Vision Match", "min", "%"),
)
ITEM_BY_KEY: dict[str, ItemSpec] = {i.key: i for i in ITEM_CATALOG}
ITEM_KEYS = tuple(i.key for i in ITEM_CATALOG)

# 등급별 기본값: (enabled, a, b) — offset: a=offset, range: (min, max), min: a=min
_DEFAULTS: dict[str, dict[str, tuple]] = {
    "industrial": {
        "a_plus_b": (True, 1.0, None), "a_minus_b": (False, 0.0, None),
        "c_minus_d": (False, 0.0, None), "drive": (False, 0.0, 80.0),
        "q": (True, 200.0, 700.0), "frequency": (True, 200.0, 400.0),
        "x_offset_um": (False, -10.0, 10.0), "y_offset_um": (False, -10.0, 10.0),
        "angle_offset_deg": (True, 3.0, None), "sweep_shape": (True, 70.0, None),
        "vision_match": (True, 95.0, None),
    },
    "research": {
        "a_plus_b": (True, 1.5, None), "a_minus_b": (False, 0.0, None),
        "c_minus_d": (False, 0.0, None), "drive": (False, 0.0, 80.0),
        "q": (True, 100.0, 800.0), "frequency": (True, 150.0, 450.0),
        "x_offset_um": (False, -10.0, 10.0), "y_offset_um": (False, -10.0, 10.0),
        "angle_offset_deg": (True, 5.0, None), "sweep_shape": (True, 50.0, None),
        "vision_match": (True, 90.0, None),
    },
    "recheck": {
        "a_plus_b": (True, 2.0, None), "a_minus_b": (False, 0.0, None),
        "c_minus_d": (False, 0.0, None), "drive": (False, 0.0, 80.0),
        "q": (True, 50.0, 1000.0), "frequency": (True, 100.0, 500.0),
        "x_offset_um": (False, -10.0, 10.0), "y_offset_um": (False, -10.0, 10.0),
        "angle_offset_deg": (True, 8.0, None), "sweep_shape": (True, 30.0, None),
        "vision_match": (True, 80.0, None),
    },
}


def _item_from_tuple(kind: str, t: tuple) -> dict:
    enabled, a, b = t
    if kind == "offset":
        return {"enabled": enabled, "offset": a}
    if kind == "range":
        return {"enabled": enabled, "min": a, "max": b}
    return {"enabled": enabled, "min": a}


def default_template(tip_id: str = "AC160") -> dict:
    grades = []
    for key, name in GRADES:
        items = {k: _item_from_tuple(ITEM_BY_KEY[k].kind, _DEFAULTS[key][k]) for k in ITEM_KEYS}
        grades.append({"key": key, "name": name, "items": items})
    return {"tip_id": tip_id, "um_per_pixel": DEFAULT_UM_PER_PIXEL, "grades": grades}


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_item(kind: str, raw) -> dict:
    """항목 dict 정규화 — 없는 키/잘못된 값은 비활성 + None."""
    raw = raw if isinstance(raw, dict) else {}
    enabled = bool(raw.get("enabled", False))
    if kind == "offset":
        off = _to_float(raw.get("offset"))
        return {"enabled": enabled and off is not None, "offset": off}
    if kind == "range":
        lo, hi = _to_float(raw.get("min")), _to_float(raw.get("max"))
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        return {"enabled": enabled and (lo is not None or hi is not None), "min": lo, "max": hi}
    mn = _to_float(raw.get("min"))
    return {"enabled": enabled and mn is not None, "min": mn}


def normalize_template(raw, tip_id: str | None = None) -> dict | None:
    """템플릿 dict 정규화. 등급/항목이 빠지면 기본값으로 채운다. 잘못된 입력은 None."""
    if not isinstance(raw, dict):
        return None
    tid = str(raw.get("tip_id") or tip_id or "").strip()
    if not tid:
        return None
    base = default_template(tid)
    upp = _to_float(raw.get("um_per_pixel"))
    base["um_per_pixel"] = upp if upp and upp > 0 else DEFAULT_UM_PER_PIXEL
    raw_grades = {g.get("key"): g for g in raw.get("grades", []) if isinstance(g, dict)}
    for grade in base["grades"]:
        rg = raw_grades.get(grade["key"])
        if not rg:
            continue
        if isinstance(rg.get("name"), str) and rg["name"].strip():
            grade["name"] = rg["name"].strip()
        r_items = rg.get("items") if isinstance(rg.get("items"), dict) else {}
        for k in ITEM_KEYS:
            if k in r_items:
                grade["items"][k] = normalize_item(ITEM_BY_KEY[k].kind, r_items[k])
    return base


def normalize_templates(raw) -> dict[str, dict]:
    """``{tip_id: template}`` 전체 정규화."""
    out: dict[str, dict] = {}
    if not isinstance(raw, dict):
        return out
    for tip_id, tpl in raw.items():
        t = normalize_template(tpl, tip_id=str(tip_id))
        if t is not None:
            out[t["tip_id"]] = t
    return out


def get_grade(template: dict, grade_key: str) -> dict | None:
    for g in template.get("grades", []):
        if g.get("key") == grade_key:
            return g
    return None


def get_item(template: dict, grade_key: str, item_key: str) -> dict | None:
    g = get_grade(template, grade_key)
    if g is None:
        return None
    return g.get("items", {}).get(item_key)


def industrial_spec_limits(template: dict) -> dict | None:
    """산업용 등급의 Frequency/Q 범위 → ``{freq_min, freq_max, q_min, q_max}``.

    두 항목 모두 비활성이면 None(동기화할 것 없음).
    """
    f = get_item(template, "industrial", "frequency") or {}
    q = get_item(template, "industrial", "q") or {}
    spec = {
        "freq_min": f.get("min") if f.get("enabled") else None,
        "freq_max": f.get("max") if f.get("enabled") else None,
        "q_min": q.get("min") if q.get("enabled") else None,
        "q_max": q.get("max") if q.get("enabled") else None,
    }
    return spec if any(v is not None for v in spec.values()) else None


def clone_template(template: dict, new_tip_id: str) -> dict:
    t = copy.deepcopy(template)
    t["tip_id"] = new_tip_id
    return t
