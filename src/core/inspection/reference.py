"""Reference Cantilever — 기준 슬롯 자동 선택 + 기준 대비 오프셋 계산.

스크린샷(ATX Classification) 판정식:
- A+B / A-B / C-D : ``ref ± offset`` 안이면 통과  → ``{item}_off = value - ref``
- X/Y Offset (um) : ``(ref_px - px) × um_per_pixel``  (RefX - X, RefY - Y)
- Angle Offset    : ``|angle - ref_angle| ≤ degree``  → ``angle_offset_deg = angle - ref_angle``
"""
from __future__ import annotations

from src.core.inspection.mtc_parser import MtcRun, MtcSlot

DEFAULT_REF_MIN_MATCH = 99.0
DEFAULT_UM_PER_PIXEL = 0.345   # 스크린샷 역산: 61.65 px → 21.269 um

OFFSET_KEYS = ("a_plus_b_off", "a_minus_b_off", "c_minus_d_off",
               "x_offset_um", "y_offset_um", "angle_offset_deg")


def is_reference_candidate(slot: MtcSlot, min_match: float = DEFAULT_REF_MIN_MATCH) -> bool:
    """sweep·PSPD·Vision·Angle 값이 모두 있고 Match Score 가 기준 이상인 슬롯."""
    return (
        slot.has_sweep and slot.has_vision
        and slot.a_plus_b is not None and slot.angle is not None
        and slot.match_score is not None and slot.match_score >= min_match
    )


def auto_reference(run: MtcRun, min_match: float = DEFAULT_REF_MIN_MATCH) -> MtcSlot | None:
    """(ATX, Port, Slot) 순서상 첫 후보. 없으면 기준을 완화해 sweep+vision 만 있는 첫 슬롯."""
    for s in run.slots:
        if is_reference_candidate(s, min_match):
            return s
    for s in run.slots:
        if s.has_sweep and s.has_vision:
            return s
    return None


def _diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def compute_offsets(slot: MtcSlot, ref: MtcSlot | None,
                    um_per_pixel: float = DEFAULT_UM_PER_PIXEL) -> dict[str, float | None]:
    """기준 대비 오프셋 6종. ref 가 없거나 한쪽 값이 없으면 None."""
    if ref is None:
        return {k: None for k in OFFSET_KEYS}
    dx = _diff(ref.tip_x, slot.tip_x)
    dy = _diff(ref.tip_y, slot.tip_y)
    return {
        "a_plus_b_off": _diff(slot.a_plus_b, ref.a_plus_b),
        "a_minus_b_off": _diff(slot.a_minus_b, ref.a_minus_b),
        "c_minus_d_off": _diff(slot.c_minus_d, ref.c_minus_d),
        "x_offset_um": None if dx is None else dx * um_per_pixel,
        "y_offset_um": None if dy is None else dy * um_per_pixel,
        "angle_offset_deg": _diff(slot.angle, ref.angle),
    }
