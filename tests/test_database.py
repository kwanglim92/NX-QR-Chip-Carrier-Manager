"""Phase 0 회귀 테스트 — database.py 의 PG 이관 친화성 리팩토링.

- app_settings UPSERT (ON CONFLICT DO UPDATE)
- measurement_sets created_at/updated_at 호출자 주입
- get_period_quality_stats: GROUP_CONCAT 제거 + Python statistics
- _period_expr: daily/weekly/monthly/quarterly/yearly 지원
"""
from __future__ import annotations

import statistics as st

from src.core import database as db
from src.core.models import MeasurementSet, SlotData


def _mk_ms(po: str, date: str, slots_spec: list[tuple]) -> MeasurementSet:
    """slots_spec = [(slot_index, freq, q, qr_id)]"""
    ms = MeasurementSet(
        po_number=po, quantity=len(slots_spec), probe_type="TypeA",
        production_date=date, source_folder=f"/data/{po}", mode="atx",
    )
    for idx, freq, q, qr in slots_spec:
        ms.slots.append(SlotData(
            slot_index=idx, slot_code=f"S{idx+1:02d}",
            frequency=freq, drive=1.0, q_factor=q,
            qr_id=qr, image_path=None, source="summary_csv",
            probe_type="TypeA",
        ))
    return ms


class TestAppSettingsUpsert:
    """Phase 0 H-1: INSERT OR REPLACE → ON CONFLICT DO UPDATE."""

    def test_save_setting_insert(self, db_conn):
        db.save_setting(db_conn, "theme", "dark")
        assert db.load_setting(db_conn, "theme") == "dark"

    def test_save_setting_update(self, db_conn):
        """동일 키 재저장 시 ON CONFLICT 경로로 UPDATE."""
        db.save_setting(db_conn, "theme", "dark")
        db.save_setting(db_conn, "theme", "light")
        assert db.load_setting(db_conn, "theme") == "light"

    def test_save_all_settings(self, db_conn):
        db.save_all_settings(db_conn, {"a": 1, "b": "text"})
        all_ = db.load_all_settings(db_conn)
        assert all_["a"] == 1
        assert all_["b"] == "text"


class TestTimestampDefault:
    """Phase 0 H-2: datetime() DEFAULT 제거 → 호출자 주입."""

    def test_created_at_populated_by_caller(self, db_conn):
        ms = _mk_ms("PO-1", "20260421", [(0, 150.0, 1200.0, "QR-1")])
        db.save_measurement_set(db_conn, ms)
        row = db_conn.execute(
            "SELECT created_at, updated_at FROM measurement_sets WHERE id=?",
            (ms.db_id,),
        ).fetchone()
        assert row["created_at"], "created_at 비어있음"
        assert row["updated_at"], "updated_at 비어있음"


class TestPeriodStats:
    """Phase 0 H-3/H-4: _period_expr(daily) + get_period_quality_stats Python 계산."""

    def test_daily_period_in_production_stats(self, db_conn):
        db.save_measurement_set(db_conn, _mk_ms("PO-1", "20260420", [
            (0, 150.1, 1200.0, "Q1"),
        ]))
        db.save_measurement_set(db_conn, _mk_ms("PO-2", "20260421", [
            (0, 151.0, 1210.0, "Q2"),
        ]))
        stats = db.get_production_stats(db_conn, period="daily")
        labels = {r["period_label"] for r in stats}
        assert "20260420" in labels
        assert "20260421" in labels

    def test_quality_stats_mean_stdev_accuracy(self, db_conn):
        """Python statistics 계산이 hand-calculated 값과 일치하는지."""
        # 동일 날짜에 3개 슬롯
        db.save_measurement_set(db_conn, _mk_ms("PO-1", "20260420", [
            (0, 150.1, 1200.0, "Q1"),
            (1, 150.2, 1210.0, "Q2"),
            (2, 150.3, 1220.0, "Q3"),
        ]))
        rows = db.get_period_quality_stats(db_conn, period="daily")
        by_label = {r["period_label"]: r for r in rows}
        r = by_label["20260420"]

        expected_freq_mean = round(st.mean([150.1, 150.2, 150.3]), 3)
        expected_freq_std = round(st.stdev([150.1, 150.2, 150.3]), 3)
        expected_q_mean = round(st.mean([1200.0, 1210.0, 1220.0]), 3)
        expected_q_std = round(st.stdev([1200.0, 1210.0, 1220.0]), 3)

        assert r["freq_mean"] == expected_freq_mean
        assert r["freq_std"] == expected_freq_std
        assert r["q_mean"] == expected_q_mean
        assert r["q_std"] == expected_q_std
        assert r["sample_count"] == 3

    def test_quality_stats_single_sample_stdev_zero(self, db_conn):
        """n=1 경계: stdev 호출 없이 0.0 반환."""
        db.save_measurement_set(db_conn, _mk_ms("PO-A", "20260421", [
            (0, 150.0, 1200.0, "Q1"),
        ]))
        rows = db.get_period_quality_stats(db_conn, period="daily")
        assert rows[0]["freq_std"] == 0.0
        assert rows[0]["q_std"] == 0.0
        assert rows[0]["sample_count"] == 1


class TestListMeasurementSetsFilters:
    """Phase 2: list_measurement_sets 확장 필터 (QR / probe / upload)."""

    def test_search_matches_qr_id(self, db_conn):
        db.save_measurement_set(db_conn, _mk_ms("PO-A", "20260421", [
            (0, 150.0, 1200.0, "ALPHA-001"),
        ]))
        db.save_measurement_set(db_conn, _mk_ms("PO-B", "20260421", [
            (0, 150.0, 1200.0, "BRAVO-001"),
        ]))
        results = db.list_measurement_sets(db_conn, search="BRAVO")
        assert len(results) == 1
        assert results[0]["po_number"] == "PO-B"

    def test_upload_status_filter(self, db_conn):
        ms = _mk_ms("PO-A", "20260421", [(0, 150.0, 1200.0, "Q1")])
        db.save_measurement_set(db_conn, ms)
        db.update_upload_status(db_conn, ms.db_id, "uploaded", "2026-04-21T10:00:00")

        pending = db.list_measurement_sets(db_conn, upload_status="pending")
        uploaded = db.list_measurement_sets(db_conn, upload_status="uploaded")
        assert len(pending) == 0
        assert len(uploaded) == 1

    def test_probe_type_filter(self, db_conn):
        db.save_measurement_set(db_conn, _mk_ms("PO-A", "20260421", [
            (0, 150.0, 1200.0, "Q1"),
        ]))
        results = db.list_measurement_sets(db_conn, probe_type="TypeA")
        assert len(results) == 1
        results = db.list_measurement_sets(db_conn, probe_type="TypeX")
        assert len(results) == 0


class TestTodayStats:
    """Phase 3: get_today_stats."""

    def test_today_stats_with_matching_date(self, db_conn):
        from datetime import datetime
        today = datetime.now().strftime("%Y%m%d")
        db.save_measurement_set(db_conn, _mk_ms("PO-T", today, [
            (0, 150.0, 1200.0, "Q1"),
            (1, 151.0, 1210.0, "Q2"),
        ]))
        stats = db.get_today_stats(db_conn)
        assert stats["production_date"] == today
        assert stats["total_sets"] == 1
        assert stats["total_slots"] == 2
        assert stats["complete_slots"] == 2
        assert stats["completion_rate"] == 100.0

    def test_today_stats_empty(self, db_conn):
        stats = db.get_today_stats(db_conn, today="19000101")
        assert stats["total_sets"] == 0
        assert stats["total_slots"] == 0
        assert stats["completion_rate"] == 0
