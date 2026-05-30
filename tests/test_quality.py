"""quality.py 순수 함수 + spec 설정 라운드트립/정규화 테스트."""
from __future__ import annotations

from src.core.quality import compute_yield, evaluate_slot, spec_bounds_for


def _spec(fmin=None, fmax=None, qmin=None, qmax=None):
    return {"freq_min": fmin, "freq_max": fmax, "q_min": qmin, "q_max": qmax}


# ─── evaluate_slot ───

def test_evaluate_slot_empty_spec_passes():
    assert evaluate_slot(100, 500, None) is True
    assert evaluate_slot(100, 500, {}) is True
    assert evaluate_slot(100, 500, _spec()) is True  # 모든 경계 None


def test_evaluate_slot_within_and_out():
    spec = _spec(fmin=100, fmax=200, qmin=400, qmax=800)
    assert evaluate_slot(150, 600, spec) is True
    assert evaluate_slot(90, 600, spec) is False    # freq < min
    assert evaluate_slot(210, 600, spec) is False   # freq > max
    assert evaluate_slot(150, 390, spec) is False    # q < min
    assert evaluate_slot(150, 810, spec) is False    # q > max


def test_evaluate_slot_open_bounds():
    assert evaluate_slot(1000, 1, _spec(fmin=100)) is True   # 상한 없음
    assert evaluate_slot(50, 1, _spec(fmin=100)) is False
    assert evaluate_slot(1, 1, _spec(fmax=100)) is True      # 하한 없음


def test_evaluate_slot_none_value_skips_dimension():
    spec = _spec(fmin=100, fmax=200, qmin=400, qmax=800)
    assert evaluate_slot(None, 600, spec) is True   # freq 미측정 → 검사 skip
    assert evaluate_slot(150, None, spec) is True


# ─── compute_yield ───

def test_compute_yield_empty():
    r = compute_yield([], {})
    assert r["overall"]["measured"] == 0
    assert r["overall"]["yield_pct"] is None
    assert r["has_any_spec"] is False
    assert r["per_probe"] == {}


def test_compute_yield_mixed_probes():
    slot_values = [
        {"frequency": 150, "q_factor": 600, "probe_type": "A"},   # in
        {"frequency": 250, "q_factor": 600, "probe_type": "A"},   # freq out
        {"frequency": 150, "q_factor": 600, "probe_type": "B"},   # B 규격 없음 → in
    ]
    spec = {"A": _spec(fmin=100, fmax=200, qmin=400, qmax=800)}
    r = compute_yield(slot_values, spec)
    assert r["overall"]["measured"] == 3
    assert r["overall"]["in_spec"] == 2
    assert r["overall"]["out_of_spec"] == 1
    assert r["overall"]["yield_pct"] == round(2 / 3 * 100, 1)
    assert r["per_probe"]["A"]["measured"] == 2
    assert r["per_probe"]["A"]["out_of_spec"] == 1
    assert r["per_probe"]["B"]["in_spec"] == 1
    assert "B" in r["unspecced"]
    assert r["has_any_spec"] is True


def test_compute_yield_per_probe_sums_to_overall():
    slot_values = [
        {"frequency": 150, "q_factor": 600, "probe_type": "A"},
        {"frequency": 250, "q_factor": 600, "probe_type": "A"},
        {"frequency": 150, "q_factor": 900, "probe_type": "B"},
    ]
    spec = {"A": _spec(fmin=100, fmax=200), "B": _spec(qmin=400, qmax=800)}
    r = compute_yield(slot_values, spec)
    assert sum(b["measured"] for b in r["per_probe"].values()) == r["overall"]["measured"]
    assert sum(b["in_spec"] for b in r["per_probe"].values()) == r["overall"]["in_spec"]
    assert sum(b["out_of_spec"] for b in r["per_probe"].values()) == r["overall"]["out_of_spec"]


# ─── spec_bounds_for ───

def test_spec_bounds_for():
    spec = {"A": _spec(fmin=100, fmax=200, qmin=400, qmax=800)}
    assert spec_bounds_for(spec, "A") == (100.0, 200.0, 400.0, 800.0)
    assert spec_bounds_for(spec, "B") is None          # 없는 probe
    assert spec_bounds_for(spec, None) is None
    assert spec_bounds_for({"C": _spec()}, "C") is None  # 경계 전무
    assert spec_bounds_for({}, "A") is None


# ─── 설정 저장/로드 + 정규화 ───

def test_spec_settings_roundtrip(db_conn):
    from src.core.database import load_setting, save_setting
    from src.ui.controllers.settings_mixin import SPEC_LIMITS_KEY, SettingsMixin

    normalized = SettingsMixin._normalize_spec_limits(
        {"A": _spec(fmin=100, fmax=200, qmin=400, qmax=800)}
    )
    save_setting(db_conn, SPEC_LIMITS_KEY, normalized)
    loaded = load_setting(db_conn, SPEC_LIMITS_KEY, {})
    assert loaded["A"]["freq_min"] == 100
    assert loaded["A"]["q_max"] == 800


def test_normalize_spec_limits_drops_bad():
    from src.ui.controllers.settings_mixin import SettingsMixin

    raw = {
        "A": {"freq_min": "100", "freq_max": "", "q_min": "abc", "q_max": None},
        "B": {"freq_min": None, "freq_max": None, "q_min": None, "q_max": None},  # 경계 전무
        "": {"freq_min": 1},        # 빈 이름
        "C": "notadict",            # 잘못된 형식
    }
    out = SettingsMixin._normalize_spec_limits(raw)
    assert out["A"]["freq_min"] == 100.0
    assert out["A"]["freq_max"] is None
    assert out["A"]["q_min"] is None    # "abc" → None
    assert "B" not in out               # 경계 전무 제외
    assert "" not in out
    assert "C" not in out


# ─── 대시보드 스모크 (offscreen) ───

def test_dashboard_load_and_report_smoke(qapp, tmp_path):
    """load_stats(yield/spec) 무예외 + export_report_pdf 파일 생성 (offscreen)."""
    from src.ui.widgets.stats_dashboard import StatsDashboard

    dash = StatsDashboard()
    dash.set_probe_types(["A", "B"])

    stats = [
        {"period_label": "2026-W18", "probe_type": "A", "set_count": 1,
         "slot_count": 4, "complete_slots": 4},
        {"period_label": "2026-W19", "probe_type": "A", "set_count": 1,
         "slot_count": 4, "complete_slots": 3},
    ]
    summary = {"total_sets": 2, "total_slots": 8, "complete_slots": 7,
               "completion_rate": 87.5}
    today = {"total_sets": 1, "total_slots": 4, "complete_slots": 4,
             "completion_rate": 100.0}
    period_totals = [
        {"period_label": "2026-W18", "total_slots": 4, "complete_slots": 4},
        {"period_label": "2026-W19", "total_slots": 4, "complete_slots": 3},
    ]
    quality_stats = [
        {"period_label": "2026-W18", "freq_mean": 150.0, "freq_std": 5.0,
         "q_mean": 600.0, "q_std": 20.0, "sample_count": 4},
        {"period_label": "2026-W19", "freq_mean": 250.0, "freq_std": 6.0,
         "q_mean": 600.0, "q_std": 22.0, "sample_count": 3},
    ]
    slot_values = [
        {"frequency": 150, "q_factor": 600, "probe_type": "A"},
        {"frequency": 250, "q_factor": 600, "probe_type": "A"},   # freq out-of-spec
    ]
    spec = {"A": _spec(fmin=100, fmax=200, qmin=400, qmax=800)}
    yr = compute_yield(slot_values, spec)
    spec_lines = {"freq": (100.0, 200.0), "q": (400.0, 800.0)}

    # 규격선/수율 포함 — 무예외로 렌더링되어야 함
    dash.load_stats(stats, summary, period_totals, quality_stats, slot_values,
                    today=today, yield_result=yr, spec_lines=spec_lines)
    # 하위호환: 신규 인자 없이도 동작
    dash.load_stats(stats, summary, period_totals, quality_stats, slot_values,
                    today=today)

    out = tmp_path / "report.pdf"
    dash.export_report_pdf(
        str(out),
        {"period": "Weekly", "probe": "A", "generated": "2026-05-30 12:00"},
    )
    assert out.exists() and out.stat().st_size > 0
