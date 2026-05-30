"""품질 규격(Spec) 평가 + In-Spec 수율 계산 — 순수 함수 (Qt/DB 무관).

수율(Yield) 정의
----------------
측정된 슬롯(frequency·q_factor 보유) 중 해당 probe 규격 내에 든 슬롯의 비율.
완료율(completion %, 입력 진척도)과는 **분모가 다른** 별개 지표다.

규격이 설정되지 않은 probe 의 측정 슬롯은 ``measured`` 에는 포함하되 ``in_spec``
으로 간주한다(미정의 규격으로는 불합 판정 불가). 그런 probe 는 ``unspecced`` 로
표시해 UI 가 "규격 미설정"을 안내할 수 있게 한다.

규격(probe 1개) 형식
---------------------
``{"freq_min": float|None, "freq_max": float|None,
   "q_min": float|None, "q_max": float|None}`` — 각 값이 None 이면 그 방향 무제한.
``spec_limits`` 는 ``{probe_type: 규격}`` 딕셔너리.
"""
from __future__ import annotations

SPEC_KEYS = ("freq_min", "freq_max", "q_min", "q_max")


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _within(value: float, lo, hi) -> bool:
    """``value`` 가 [lo, hi] 안인지. lo/hi None 이면 그 방향 무제한. value 는 not None."""
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


def _has_bound(spec) -> bool:
    """규격에 경계가 하나라도 정의돼 있으면 True."""
    return bool(spec) and any(_to_float(spec.get(k)) is not None for k in SPEC_KEYS)


def evaluate_slot(freq, q, spec) -> bool:
    """freq·q 가 모두 규격 내이면 True.

    규격이 비었거나(None/{}) 경계가 없으면 통과. freq/q 중 None(미측정)인 차원은
    검사하지 않는다.
    """
    if not spec:
        return True
    f = _to_float(freq)
    if f is not None and not _within(f, _to_float(spec.get("freq_min")), _to_float(spec.get("freq_max"))):
        return False
    qq = _to_float(q)
    if qq is not None and not _within(qq, _to_float(spec.get("q_min")), _to_float(spec.get("q_max"))):
        return False
    return True


def _blank_bucket() -> dict:
    return {"measured": 0, "in_spec": 0, "out_of_spec": 0, "yield_pct": None}


def _finalize(bucket: dict) -> dict:
    m = bucket["measured"]
    bucket["yield_pct"] = round(bucket["in_spec"] / m * 100, 1) if m else None
    return bucket


def compute_yield(slot_values, spec_limits) -> dict:
    """측정 슬롯들을 규격 대비 평가해 overall + per-probe 수율을 집계.

    Parameters
    ----------
    slot_values
        ``database.get_slot_values()`` 결과 형태:
        ``[{"frequency", "q_factor", "probe_type"}, ...]`` (이미 freq·q NOT NULL,
        contact-mode 제외).
    spec_limits
        ``{probe_type: {freq_min, freq_max, q_min, q_max}}``.

    Returns
    -------
    dict
        ``{"overall": bucket, "per_probe": {pt: bucket}, "has_any_spec": bool,
           "unspecced": set[str]}`` — bucket = ``{measured, in_spec, out_of_spec,
           yield_pct}`` (yield_pct 는 measured==0 이면 None).
    """
    spec_limits = spec_limits or {}
    overall = _blank_bucket()
    per_probe: dict[str, dict] = {}
    unspecced: set[str] = set()

    for row in slot_values:
        pt = row.get("probe_type") or ""
        spec = spec_limits.get(pt)
        bucket = per_probe.setdefault(pt, _blank_bucket())

        bucket["measured"] += 1
        overall["measured"] += 1

        if not _has_bound(spec):
            # 규격 미설정 → 불합 판정 불가, in_spec 으로 집계 + 플래그
            unspecced.add(pt)
            ok = True
        else:
            ok = evaluate_slot(row.get("frequency"), row.get("q_factor"), spec)

        if ok:
            bucket["in_spec"] += 1
            overall["in_spec"] += 1
        else:
            bucket["out_of_spec"] += 1
            overall["out_of_spec"] += 1

    for bucket in per_probe.values():
        _finalize(bucket)
    _finalize(overall)

    has_any_spec = any(_has_bound(s) for s in spec_limits.values())
    return {
        "overall": overall,
        "per_probe": per_probe,
        "has_any_spec": has_any_spec,
        "unspecced": unspecced,
    }


def spec_bounds_for(spec_limits, probe_type):
    """probe 의 ``(freq_lo, freq_hi, q_lo, q_hi)`` 반환. 경계가 없으면 None."""
    if not spec_limits or not probe_type:
        return None
    spec = spec_limits.get(probe_type)
    if not _has_bound(spec):
        return None
    return (
        _to_float(spec.get("freq_min")), _to_float(spec.get("freq_max")),
        _to_float(spec.get("q_min")), _to_float(spec.get("q_max")),
    )
