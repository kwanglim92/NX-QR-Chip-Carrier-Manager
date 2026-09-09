"""기준 슬롯·템플릿·등급 사다리 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.inspection.grading import (
    SlotVerdict,
    evaluate_item,
    formula_text,
    grade_counts,
    grade_run,
    grade_slot,
    ladder_grade,
    regrade,
)
from src.core.inspection.mtc_parser import MtcRun, MtcSlot, load_mtc_run
from src.core.inspection.reference import auto_reference, compute_offsets, is_reference_candidate
from src.core.inspection.templates import (
    GRADE_KEYS,
    ITEM_KEYS,
    REJECT_KEY,
    clone_template,
    default_template,
    get_item,
    industrial_spec_limits,
    normalize_item,
    normalize_template,
    normalize_templates,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture(scope="module")
def run():
    return load_mtc_run(FIXTURE)


@pytest.fixture
def template():
    return default_template("AC160")


# ─── reference ───

def test_auto_reference_picks_first_clean_slot(run):
    ref = auto_reference(run)
    assert ref.code == "1101"
    assert is_reference_candidate(ref)
    # 1_1_11 은 sweep 이 없어 후보가 아니다
    assert not is_reference_candidate(run.find(1, 1, 11))


def test_auto_reference_fallback_when_match_too_strict():
    r = MtcRun("x", "x", [MtcSlot(1, 1, 1, frequency=280, tip_x=1, tip_y=1, match_score=90.0)])
    assert auto_reference(r, min_match=99.0).code == "1101"   # 완화 폴백
    assert auto_reference(MtcRun("x", "x", [])) is None


def test_compute_offsets_match_screenshot(run):
    """스크린샷: 3112 기준 1101 → RefX-X 21.269 um, RefY-Y 20.306 um, A+B 0.46."""
    ref = run.find(1, 1, 1)
    s = MtcSlot(3, 1, 12, tip_x=1147.77, tip_y=491.879, a_plus_b=0.46, angle=89.252)
    off = compute_offsets(s, ref, 0.345)
    assert off["x_offset_um"] == pytest.approx(21.269, abs=0.01)
    assert off["y_offset_um"] == pytest.approx(20.306, abs=0.01)
    assert off["a_plus_b_off"] == pytest.approx(0.46 - 2.91, abs=1e-9)
    assert off["angle_offset_deg"] == pytest.approx(89.252 - 89.408, abs=1e-9)
    assert off["a_minus_b_off"] is None          # 슬롯에 A-B 없음
    assert all(v is None for v in compute_offsets(s, None).values())


# ─── templates ───

def test_default_template_shape(template):
    assert template["tip_id"] == "AC160" and template["um_per_pixel"] == 0.345
    assert [g["key"] for g in template["grades"]] == list(GRADE_KEYS)
    for g in template["grades"]:
        assert set(g["items"]) == set(ITEM_KEYS)
    ind = get_item(template, "industrial", "q")
    assert ind == {"enabled": True, "min": 200.0, "max": 700.0}
    assert get_item(template, "industrial", "a_plus_b") == {"enabled": True, "offset": 1.0}
    assert get_item(template, "industrial", "sweep_shape") == {"enabled": True, "min": 70.0}
    assert get_item(template, "recheck", "sweep_shape")["min"] < get_item(template, "research", "sweep_shape")["min"]


def test_normalize_item_rules():
    assert normalize_item("range", {"enabled": True, "min": "300", "max": "100"}) == \
        {"enabled": True, "min": 100.0, "max": 300.0}
    assert normalize_item("range", {"enabled": True}) == {"enabled": False, "min": None, "max": None}
    assert normalize_item("offset", {"enabled": True, "offset": "x"}) == {"enabled": False, "offset": None}
    assert normalize_item("min", {"enabled": True, "min": 50}) == {"enabled": True, "min": 50.0}
    assert normalize_item("min", None) == {"enabled": False, "min": None}


def test_normalize_template_fills_defaults_and_overrides():
    raw = {"tip_id": " PPP-NCHR ", "um_per_pixel": "0.5",
           "grades": [{"key": "industrial", "name": "Industrial",
                       "items": {"q": {"enabled": True, "min": 250, "max": 600}}}]}
    t = normalize_template(raw)
    assert t["tip_id"] == "PPP-NCHR" and t["um_per_pixel"] == 0.5
    assert get_item(t, "industrial", "q") == {"enabled": True, "min": 250.0, "max": 600.0}
    assert t["grades"][0]["name"] == "Industrial"
    # 나머지 항목/등급은 기본값
    assert get_item(t, "industrial", "frequency") == {"enabled": True, "min": 200.0, "max": 400.0}
    assert get_item(t, "research", "q") == {"enabled": True, "min": 100.0, "max": 800.0}
    assert normalize_template("nope") is None
    assert normalize_template({}) is None
    assert normalize_template({"um_per_pixel": -1}, tip_id="X")["um_per_pixel"] == 0.345


def test_normalize_templates_dict():
    out = normalize_templates({"AC160": {}, "": {}, "B": "junk"})
    assert set(out) == {"AC160"}
    assert normalize_templates(None) == {}


def test_industrial_spec_limits_sync(template):
    assert industrial_spec_limits(template) == \
        {"freq_min": 200.0, "freq_max": 400.0, "q_min": 200.0, "q_max": 700.0}
    get_item(template, "industrial", "q")["enabled"] = False
    assert industrial_spec_limits(template)["q_min"] is None
    get_item(template, "industrial", "frequency")["enabled"] = False
    assert industrial_spec_limits(template) is None


def test_clone_template(template):
    c = clone_template(template, "AC240")
    assert c["tip_id"] == "AC240" and template["tip_id"] == "AC160"
    c["grades"][0]["items"]["q"]["min"] = 1
    assert get_item(template, "industrial", "q")["min"] == 200.0


# ─── evaluate_item / formula ───

def test_evaluate_item_kinds():
    m = {"a_plus_b": 0.46, "ref_a_plus_b": 2.91, "q": 150.0, "sweep_shape": 72.0, "angle": None}
    ok, v, b = evaluate_item("a_plus_b", {"enabled": True, "offset": 1.0}, m)
    assert not ok and v == 0.46 and b == "1.91 ~ 3.91"
    assert evaluate_item("a_plus_b", {"enabled": True, "offset": 3.0}, m)[0]
    assert evaluate_item("q", {"enabled": True, "min": 200, "max": 700}, m) == (False, 150.0, "200 ~ 700")
    assert evaluate_item("q", {"enabled": True, "min": None, "max": 700}, m)[0]
    assert evaluate_item("sweep_shape", {"enabled": True, "min": 70}, m) == (True, 72.0, "≥ 70")
    assert evaluate_item("sweep_shape", {"enabled": False, "min": 99}, m)[0]      # 비활성 → 통과
    assert evaluate_item("angle_offset_deg", {"enabled": True, "offset": 3}, m) == (False, None, "N/A")
    assert evaluate_item("frequency", {"enabled": True, "min": 200, "max": 400}, m) == (False, None, "200 ~ 400")


def test_formula_text_matches_screenshot():
    m = {"a_plus_b": 0.46, "ref_a_plus_b": 2.91, "q": 422.81}
    assert formula_text("a_plus_b", {"enabled": True, "offset": 1.0}, m) == "2.91 - 1 < 0.46 < 2.91 + 1"
    assert formula_text("q", {"enabled": True, "min": 200, "max": 700}, m) == "200 < 422.81 < 700"
    assert formula_text("sweep_shape", {"enabled": True, "min": 70}, {"sweep_shape": 86.2}) == "86.2 ≥ 70"
    assert formula_text("q", None, m) == ""


# ─── ladder ───

def _metrics(**over):
    base = {"a_plus_b": 2.9, "ref_a_plus_b": 2.91, "a_minus_b": 0, "ref_a_minus_b": 0,
            "c_minus_d": 0, "ref_c_minus_d": 0, "drive": 5.0, "q": 400.0, "frequency": 280.0,
            "x_offset_um": 0.0, "y_offset_um": 0.0, "angle": 89.5, "ref_angle": 89.4,
            "sweep_shape": 90.0, "vision_match": 99.9}
    base.update(over)
    return base


def test_ladder_first_passing_grade_wins(template):
    assert ladder_grade(_metrics(), template)[0] == "industrial"
    assert ladder_grade(_metrics(q=150.0), template)[0] == "research"       # 100~800
    assert ladder_grade(_metrics(q=60.0), template)[0] == "recheck"         # 50~1000
    assert ladder_grade(_metrics(q=10.0), template)[0] == REJECT_KEY
    g, failed = ladder_grade(_metrics(sweep_shape=55.0, a_plus_b=1.5), template)
    assert g == "research"
    assert {f.item for f in failed["industrial"]} == {"a_plus_b", "sweep_shape"}
    assert failed["research"] == []


def test_ladder_records_failures_for_every_grade(template):
    _, failed = ladder_grade(_metrics(frequency=None), template)
    assert all("frequency" in {f.item for f in failed[g]} for g in GRADE_KEYS)


def test_grade_run_on_fixture(run, template):
    vs = grade_run(run, template, auto_reference(run))
    by = {v.code: v for v in vs}
    assert by["1101"].grade == "industrial" and by["1101"].error_label == ""
    assert by["1111"].grade == REJECT_KEY and by["1111"].error_label == "No Sweep"
    assert by["3212"].grade == REJECT_KEY
    assert {"Q", "Sweep Shape"} <= set(by["3212"].error_label.split(", "))
    assert by["1102"].grade == REJECT_KEY                     # Q 141 + 잡음 sweep
    assert by["1204"].grade in ("recheck", REJECT_KEY)        # Q 79, 부피크
    counts = grade_counts(vs)
    assert sum(counts.values()) == len(run.slots)
    assert counts["industrial"] >= 1


def test_overrides_and_broken(run, template):
    v = grade_slot(run.find(1, 1, 1), template, run.find(1, 1, 1))
    assert v.grade == "industrial" and not v.broken and not v.is_override
    v.override_broken = True
    assert v.broken and v.grade == REJECT_KEY and v.error_label == "Broken"
    v.override_grade = "research"
    assert v.grade == "research" and v.grade_name == "연구용" and v.is_override
    v.override_broken = None
    v.override_grade = None
    assert v.grade == "industrial"


def test_regrade_keeps_overrides_and_reuses_sweep(run, template):
    ref = auto_reference(run)
    vs = grade_run(run, template, ref)
    vs[0].override_grade = "recheck"
    get_item(template, "industrial", "q")["max"] = 300.0
    new = regrade(vs, template, ref)
    assert new[0].override_grade == "recheck" and new[0].grade == "recheck"
    assert new[0].sweep is vs[0].sweep
    assert isinstance(new[0], SlotVerdict)
