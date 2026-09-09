"""등급 사다리 평가 — 슬롯 지표 × 템플릿 → SlotVerdict.

절차
----
1. ``slot_metrics``: 원시값 + 기준 대비 오프셋 + sweep 점수 + vision match 를 한 dict 로.
2. ``ladder_grade``: 산업용 → 연구용 → 재검사 순으로 활성 항목을 전부 검사해 첫 통과 등급.
   전부 실패 = ``reject``. 항목 값이 None(미측정)이면 그 항목은 실패(bound 'N/A').
3. 파손(``vision.broken`` 또는 수동 override)은 사다리와 무관하게 ``reject``.
4. Error 열 = Broken / No Sweep / 산업용 등급에서 실패한 항목 짧은 이름(콤마).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.core.inspection.mtc_parser import MtcRun, MtcSlot
from src.core.inspection.reference import compute_offsets
from src.core.inspection.sweep_shape import SweepShape, analyze_sweep
from src.core.inspection.templates import (
    GRADE_KEYS,
    GRADE_NAMES,
    ITEM_BY_KEY,
    ITEM_KEYS,
    REJECT_KEY,
    get_grade,
)
from src.core.inspection.vision_check import TipMeasure, VisionCheck, check_vision, measure_tip

# 항목 키 → (metrics 값 키, 기준값 키 | None)
_OFFSET_SOURCE = {
    "a_plus_b": ("a_plus_b", "ref_a_plus_b"),
    "a_minus_b": ("a_minus_b", "ref_a_minus_b"),
    "c_minus_d": ("c_minus_d", "ref_c_minus_d"),
    "angle_offset_deg": ("angle", "ref_angle"),
}


@dataclass
class FailedItem:
    item: str
    grade: str
    value: float | None
    bound: str

    @property
    def label(self) -> str:
        return ITEM_BY_KEY[self.item].short


@dataclass
class SlotVerdict:
    slot: MtcSlot
    ladder_grade: str
    failed_by_grade: dict[str, list[FailedItem]]
    metrics: dict
    sweep: SweepShape
    vision: VisionCheck
    override_grade: str | None = None
    override_broken: bool | None = None
    # 사용자 메모(선택)
    note: str = ""

    @property
    def code(self) -> str:
        return self.slot.code

    @property
    def broken(self) -> bool:
        if self.override_broken is not None:
            return self.override_broken
        return bool(self.vision and self.vision.broken)

    @property
    def grade(self) -> str:
        if self.override_grade:
            return self.override_grade
        if self.broken:
            return REJECT_KEY
        return self.ladder_grade

    @property
    def grade_name(self) -> str:
        return GRADE_NAMES.get(self.grade, self.grade)

    @property
    def is_override(self) -> bool:
        return self.override_grade is not None or self.override_broken is not None

    @property
    def error_label(self) -> str:
        if self.broken:
            return "Broken"
        if not self.slot.has_sweep:
            return "No Sweep"
        top = self.failed_by_grade.get(GRADE_KEYS[0], [])
        return ", ".join(f.label for f in top)

    def failed_items(self, grade_key: str) -> list[FailedItem]:
        return self.failed_by_grade.get(grade_key, [])


def slot_metrics(slot: MtcSlot, ref: MtcSlot | None, um_per_pixel: float,
                 sweep: SweepShape | None, vision: VisionCheck | None) -> dict:
    m: dict = {
        "a_plus_b": slot.a_plus_b, "a_minus_b": slot.a_minus_b, "c_minus_d": slot.c_minus_d,
        "frequency": slot.frequency, "set_point": slot.set_point, "amplitude": slot.amplitude,
        "drive": slot.drive, "q": slot.q,
        "tip_x": slot.tip_x, "tip_y": slot.tip_y, "tip_focus": slot.tip_focus,
        "angle": slot.angle, "match_score": slot.match_score,
        "ref_a_plus_b": ref.a_plus_b if ref else None,
        "ref_a_minus_b": ref.a_minus_b if ref else None,
        "ref_c_minus_d": ref.c_minus_d if ref else None,
        "ref_angle": ref.angle if ref else None,
        "ref_tip_x": ref.tip_x if ref else None,
        "ref_tip_y": ref.tip_y if ref else None,
        "sweep_shape": sweep.score if (sweep and sweep.available) else None,
        "vision_match": slot.match_score,
    }
    m.update(compute_offsets(slot, ref, um_per_pixel))
    return m


def _fmt(v: float | None, nd: int = 2) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"


def evaluate_item(item_key: str, spec: dict | None, metrics: dict) -> tuple[bool, float | None, str]:
    """(통과?, 표시 값, 경계 문자열). spec 비활성/없음 → 통과."""
    if not spec or not spec.get("enabled"):
        return True, metrics.get(item_key), ""
    kind = ITEM_BY_KEY[item_key].kind
    if kind == "offset":
        vkey, rkey = _OFFSET_SOURCE[item_key]
        value, ref = metrics.get(vkey), metrics.get(rkey)
        off = spec.get("offset")
        if value is None or ref is None or off is None:
            return False, value, "N/A"
        ok = abs(value - ref) <= off
        return ok, value, f"{_fmt(ref - off)} ~ {_fmt(ref + off)}"
    value = metrics.get(item_key)
    if kind == "range":
        lo, hi = spec.get("min"), spec.get("max")
        bound = f"{_fmt(lo)} ~ {_fmt(hi)}"
        if value is None:
            return False, None, bound
        if lo is not None and value < lo:
            return False, value, bound
        if hi is not None and value > hi:
            return False, value, bound
        return True, value, bound
    mn = spec.get("min")
    bound = f"≥ {_fmt(mn)}"
    if value is None or mn is None:
        return False, value, bound
    return value >= mn, value, bound


def formula_text(item_key: str, spec: dict | None, metrics: dict) -> str:
    """스크린샷식 판정식 문자열. 예: ``2.91 - 1.0 < 0.46 < 2.91 + 1.0``."""
    if not spec:
        return ""
    kind = ITEM_BY_KEY[item_key].kind
    if kind == "offset":
        vkey, rkey = _OFFSET_SOURCE[item_key]
        value, ref, off = metrics.get(vkey), metrics.get(rkey), spec.get("offset")
        return f"{_fmt(ref)} - {_fmt(off)} < {_fmt(value, 3)} < {_fmt(ref)} + {_fmt(off)}"
    value = metrics.get(item_key)
    if kind == "range":
        return f"{_fmt(spec.get('min'))} < {_fmt(value, 3)} < {_fmt(spec.get('max'))}"
    return f"{_fmt(value, 3)} ≥ {_fmt(spec.get('min'))}"


def ladder_grade(metrics: dict, template: dict) -> tuple[str, dict[str, list[FailedItem]]]:
    """사다리 평가. 반환: (등급 키, {등급: 실패 항목 리스트}) — 모든 등급의 실패를 기록한다."""
    failed_by_grade: dict[str, list[FailedItem]] = {}
    result = REJECT_KEY
    for gkey in GRADE_KEYS:
        grade = get_grade(template, gkey) or {"items": {}}
        fails: list[FailedItem] = []
        for ikey in ITEM_KEYS:
            ok, value, bound = evaluate_item(ikey, grade["items"].get(ikey), metrics)
            if not ok:
                fails.append(FailedItem(ikey, gkey, value, bound))
        failed_by_grade[gkey] = fails
        if not fails and result == REJECT_KEY:
            result = gkey
    return result, failed_by_grade


def grade_slot(slot: MtcSlot, template: dict, ref: MtcSlot | None,
               ref_tip: TipMeasure | None = None,
               sweep: SweepShape | None = None,
               vision: VisionCheck | None = None) -> SlotVerdict:
    """슬롯 1개 평가. sweep/vision 은 미리 계산한 것을 넘기면 재계산하지 않는다."""
    if sweep is None:
        sweep = analyze_sweep(slot.sweep_txt, slot.zoom_txt)
    if vision is None:
        vision = check_vision(slot.pickup_image, slot.match_score, ref_tip)
    upp = float(template.get("um_per_pixel") or 0) or 0.345
    metrics = slot_metrics(slot, ref, upp, sweep, vision)
    grade, failed = ladder_grade(metrics, template)
    return SlotVerdict(slot=slot, ladder_grade=grade, failed_by_grade=failed,
                       metrics=metrics, sweep=sweep, vision=vision)


def grade_run(run: MtcRun, template: dict, ref: MtcSlot | None,
              progress=None) -> list[SlotVerdict]:
    """런 전체 평가. ``progress(done, total)`` 콜백 선택."""
    ref_tip = measure_tip(ref.pickup_image) if (ref and ref.pickup_image) else None
    out: list[SlotVerdict] = []
    total = len(run.slots)
    for i, s in enumerate(run.slots, start=1):
        out.append(grade_slot(s, template, ref, ref_tip))
        if progress is not None:
            progress(i, total)
    return out


def regrade(verdicts: list[SlotVerdict], template: dict, ref: MtcSlot | None,
            ref_tip: TipMeasure | None = None) -> list[SlotVerdict]:
    """템플릿/기준만 바뀌었을 때 sweep·vision 결과를 재사용해 재평가(override 유지)."""
    out = []
    for v in verdicts:
        vision = v.vision
        if ref_tip is not None and vision.available:
            vision = check_vision(v.slot.pickup_image, v.slot.match_score, ref_tip)
        nv = grade_slot(v.slot, template, ref, ref_tip, sweep=v.sweep, vision=vision)
        nv.override_grade, nv.override_broken, nv.note = v.override_grade, v.override_broken, v.note
        out.append(nv)
    return out


def grade_counts(verdicts: list[SlotVerdict]) -> dict[str, int]:
    counts = {k: 0 for k in GRADE_KEYS + (REJECT_KEY,)}
    for v in verdicts:
        counts[v.grade] = counts.get(v.grade, 0) + 1
    return counts
