"""Phase 6B + 7A 회귀 테스트 — ocr_settings.py 의 해상도별 프로파일 + 마이그레이션."""
from __future__ import annotations

from src.core import database as db
from src.core.ocr_settings import (
    SETTING_KEY,
    SCHEMA_VERSION,
    resolution_key,
    parse_resolution_key,
    load_roi_for,
    save_roi_for,
    list_profiles,
    delete_profile,
    load_roi,
    save_roi,
)


class TestResolutionKey:
    def test_roundtrip(self):
        assert resolution_key(722, 479) == "722x479"
        assert parse_resolution_key("722x479") == (722, 479)

    def test_parse_invalid(self):
        assert parse_resolution_key("invalid") is None
        assert parse_resolution_key("") is None
        assert parse_resolution_key("abcxdef") is None


class TestLoadSaveProfile:
    def test_empty_db_returns_none(self, db_conn):
        assert load_roi_for(db_conn, 722, 479) is None

    def test_save_and_load(self, db_conn):
        roi = {"frequency": (595, 95, 120, 30), "q_factor": (595, 175, 120, 30)}
        save_roi_for(db_conn, 722, 479, roi)
        assert load_roi_for(db_conn, 722, 479) == roi

    def test_multiple_resolutions_independent(self, db_conn):
        r722 = {"frequency": (595, 95, 120, 30), "q_factor": (595, 175, 120, 30)}
        r1024 = {"frequency": (800, 130, 160, 40), "q_factor": (800, 230, 160, 40)}
        save_roi_for(db_conn, 722, 479, r722)
        save_roi_for(db_conn, 1024, 768, r1024)
        assert load_roi_for(db_conn, 722, 479) == r722
        assert load_roi_for(db_conn, 1024, 768) == r1024

    def test_missing_resolution_returns_none(self, db_conn):
        save_roi_for(db_conn, 722, 479,
                     {"frequency": (1, 2, 3, 4), "q_factor": (5, 6, 7, 8)})
        assert load_roi_for(db_conn, 9999, 9999) is None


class TestListAndDelete:
    def test_list_profiles(self, db_conn):
        save_roi_for(db_conn, 722, 479,
                     {"frequency": (1, 2, 3, 4), "q_factor": (5, 6, 7, 8)})
        save_roi_for(db_conn, 1024, 768,
                     {"frequency": (1, 2, 3, 4), "q_factor": (5, 6, 7, 8)})
        keys = {k for k, _ in list_profiles(db_conn)}
        assert keys == {"722x479", "1024x768"}

    def test_delete_profile(self, db_conn):
        save_roi_for(db_conn, 722, 479,
                     {"frequency": (1, 2, 3, 4), "q_factor": (5, 6, 7, 8)})
        assert delete_profile(db_conn, 722, 479) is True
        assert load_roi_for(db_conn, 722, 479) is None
        assert delete_profile(db_conn, 999, 999) is False  # 없는 키


class TestMigrationV1toV2:
    def test_v1_schema_loads_as_legacy(self, db_conn):
        """v1 포맷(최상위 frequency/q_factor)을 직접 주입 후 load 시 legacy 승격."""
        db.save_setting(db_conn, SETTING_KEY, {
            "frequency": [100, 200, 80, 20],
            "q_factor": [100, 230, 80, 20],
        })
        # 해상도 키는 없지만 legacy fallback으로 반환
        result = load_roi_for(db_conn, 722, 479)
        assert result == {
            "frequency": (100, 200, 80, 20),
            "q_factor": (100, 230, 80, 20),
        }

    def test_v1_compat_load_roi(self, db_conn):
        """구 API load_roi 도 legacy 프로파일 반환."""
        db.save_setting(db_conn, SETTING_KEY, {
            "frequency": [1, 2, 3, 4], "q_factor": [5, 6, 7, 8],
        })
        assert load_roi(db_conn) == {
            "frequency": (1, 2, 3, 4), "q_factor": (5, 6, 7, 8),
        }


class TestSafetyFallback:
    def test_corrupted_value_returns_none(self, db_conn):
        db.save_setting(db_conn, SETTING_KEY, "garbage")
        assert load_roi_for(db_conn, 722, 479) is None

    def test_partial_v2_filters_invalid_entries(self, db_conn):
        """v2 프로파일 중 일부가 손상되면 해당 엔트리만 제외."""
        db.save_setting(db_conn, SETTING_KEY, {
            "version": 2,
            "profiles": {
                "722x479": {"frequency": [1, 2, 3, 4], "q_factor": [5, 6, 7, 8]},
                "bad": "not-a-dict",
            },
        })
        keys = {k for k, _ in list_profiles(db_conn)}
        assert keys == {"722x479"}
