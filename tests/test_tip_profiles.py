"""Tip 프로필 설정 — 정규화·저장/복원·probe_type 매칭·SEM 이미지 보관."""
from __future__ import annotations

from PIL import Image

from src.core.tip_profiles import (
    DEFAULT_SPEC_ROWS,
    default_tip_profile,
    import_tip_images,
    load_tip_profiles,
    normalize_tip_profile,
    normalize_tip_profiles,
    profile_for,
    save_tip_profiles,
    store_tip_image,
)


def test_default_profile_has_five_rows_with_three_values():
    p = default_tip_profile("AC160")
    assert p["display_name"] == "AC160" and p["sem_image"] == "" and p["spec_layout"] == "min_typ_max"
    assert [r[0] for r in p["spec_rows"]] == list(DEFAULT_SPEC_ROWS)
    assert all(len(r) == 4 for r in p["spec_rows"])


def test_normalize_pads_truncates_and_drops_blank_rows():
    p = normalize_tip_profile("AC160", {
        "display_name": "  AC160TS ",
        "spec_layout": "min_typ_max",
        "spec_rows": [["Length (um)", 145, "160", "175", "extra"], ["Width", "38"], ["", "1", "2"], "junk"],
    })
    assert p["display_name"] == "AC160TS"
    assert p["spec_rows"] == [["Length (um)", "145", "160", "175"], ["Width", "38", "", ""]]


def test_normalize_nominal_range_keeps_two_values_and_bad_layout_falls_back():
    p = normalize_tip_profile("PPP-NCHR", {"spec_layout": "nominal_range",
                                           "spec_rows": [["Length / ㎛", "125", "115 ~ 135", "zzz"]]})
    assert p["spec_rows"] == [["Length / ㎛", "125", "115 ~ 135"]]
    bad = normalize_tip_profile("X", {"spec_layout": "weird", "display_name": "", "spec_rows": "no"})
    assert bad["spec_layout"] == "min_typ_max" and bad["display_name"] == "X"
    assert len(bad["spec_rows"]) == len(DEFAULT_SPEC_ROWS)


def test_normalize_profiles_strips_keys_and_drops_empty():
    out = normalize_tip_profiles({" AC160 ": {}, "": {"display_name": "nope"}, 7: None})
    assert list(out) == ["AC160", "7"] and out["AC160"]["display_name"] == "AC160"


def test_round_trip_through_db(db_conn):
    assert load_tip_profiles(db_conn) == {}
    saved = save_tip_profiles(db_conn, {"AC160": {"display_name": "AC160TS", "sem_image": "C:/x.png"}})
    assert load_tip_profiles(db_conn) == saved
    assert saved["AC160"]["sem_image"] == "C:/x.png"


def test_profile_for_exact_then_case_insensitive():
    profiles = normalize_tip_profiles({"AC160": {}, "ac160ts": {"display_name": "lower"}})
    assert profile_for(profiles, "AC160")["display_name"] == "AC160"
    assert profile_for(profiles, "AC160TS")["display_name"] == "lower"
    assert profile_for(profiles, "PPP-NCHR") is None and profile_for(profiles, "") is None


def test_store_tip_image_converts_to_png(tmp_path):
    src = tmp_path / "sem.jpg"
    Image.new("RGB", (40, 30), "gray").save(src, "JPEG")
    out = store_tip_image("AC 160/TS", src, tmp_path / "store")
    assert out.endswith("AC_160_TS.png")
    with Image.open(out) as im:
        assert im.format == "PNG" and im.size == (40, 30)


def test_import_tip_images_copies_outside_paths_only(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    src = tmp_path / "sem.png"
    Image.new("RGB", (10, 10), "white").save(src, "PNG")
    inside = store / "PPP.png"
    Image.new("RGB", (10, 10), "white").save(inside, "PNG")
    out = import_tip_images({
        "AC160": {"sem_image": str(src)},
        "PPP": {"sem_image": str(inside)},
        "NONE": {"sem_image": ""},
        "MISSING": {"sem_image": str(tmp_path / "gone.png")},
    }, store)
    assert out["AC160"]["sem_image"] == str(store / "AC160.png") and (store / "AC160.png").exists()
    assert out["PPP"]["sem_image"] == str(inside)               # 이미 보관 폴더 안 → 그대로
    assert out["NONE"]["sem_image"] == ""
    assert out["MISSING"]["sem_image"] == str(tmp_path / "gone.png")   # 없는 파일은 건드리지 않음
    assert import_tip_images(out, store) == out                   # 멱등
