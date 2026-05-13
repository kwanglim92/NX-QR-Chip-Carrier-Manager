from __future__ import annotations

from src.core.capture_files import (
    ZOOMIN_SUBDIR,
    ZOOMOUT_SUBDIR,
    ZOOMOUT_SUFFIX,
    derive_zoomout_path,
    final_capture_pair,
    final_capture_path,
    is_app_capture_path,
    is_pending_capture_path,
    is_zoomout_filename,
    next_pending_capture_pair,
    next_pending_capture_path,
    sanitize_capture_filename_part,
    zoom_dir,
    zoom_filename,
)


def test_next_pending_capture_path_uses_first_available_number(tmp_path):
    (tmp_path / "pending_0001.png").write_bytes(b"one")

    assert next_pending_capture_path(tmp_path) == tmp_path / "pending_0002.png"


def test_is_pending_capture_path_requires_app_root_and_pending_png(tmp_path):
    capture_root = tmp_path / "captures"
    capture_dir = capture_root / "20260513" / "AC160"
    capture_dir.mkdir(parents=True)
    pending = capture_dir / "pending_0001.png"
    pending.write_bytes(b"image")
    external = tmp_path / "pending_0001.png"
    external.write_bytes(b"image")

    assert is_pending_capture_path(pending, capture_root)
    assert is_app_capture_path(pending, capture_root)
    assert not is_pending_capture_path(external, capture_root)
    assert not is_pending_capture_path(capture_dir / "slot_01_QR.png", capture_root)
    assert is_app_capture_path(capture_dir / "slot_01_QR.png", capture_root)


def test_final_capture_path_uses_slot_and_sanitized_qr(tmp_path):
    pending = tmp_path / "pending_0001.png"
    pending.write_bytes(b"image")

    assert final_capture_path(pending, 0, ' QR:123/ABC* ') == (
        tmp_path / "slot_01_QR_123_ABC.png"
    )


def test_final_capture_path_adds_suffix_on_collision(tmp_path):
    pending = tmp_path / "pending_0001.png"
    pending.write_bytes(b"image")
    (tmp_path / "slot_02_QR001.png").write_bytes(b"existing")

    assert final_capture_path(pending, 1, "QR001") == tmp_path / "slot_02_QR001_1.png"


def test_final_capture_path_keeps_current_final_name(tmp_path):
    current = tmp_path / "slot_02_QR001.png"
    current.write_bytes(b"image")

    assert final_capture_path(current, 1, "QR001") == current


def test_sanitize_capture_filename_part_uses_fallback_for_empty_values():
    assert sanitize_capture_filename_part(" <>:/\\|?* ") == "capture"


# ─── Zoom-In / Zoom-Out helpers ───


def test_is_zoomout_filename_detects_backtick_suffix():
    assert is_zoomout_filename(f"pending_0001{ZOOMOUT_SUFFIX}.png")
    assert is_zoomout_filename(f"slot_01_ABC{ZOOMOUT_SUFFIX}.png")
    assert not is_zoomout_filename("pending_0001.png")
    assert not is_zoomout_filename("slot_01_ABC.png")


def test_zoom_filename_appends_suffix_only_for_zoomout():
    assert zoom_filename("pending_0001", ".png", "zoomin") == "pending_0001.png"
    assert zoom_filename("pending_0001", ".png", "zoomout") == (
        f"pending_0001{ZOOMOUT_SUFFIX}.png"
    )


def test_zoom_dir_creates_zoomin_and_zoomout_subdirs(tmp_path):
    base = tmp_path / "probe"
    zi = zoom_dir(base, "zoomin")
    zo = zoom_dir(base, "zoomout")
    assert zi == base / ZOOMIN_SUBDIR
    assert zo == base / ZOOMOUT_SUBDIR
    assert zi.is_dir()
    assert zo.is_dir()


def test_next_pending_capture_pair_advances_counter_for_both_paths(tmp_path):
    base = tmp_path / "probe"
    zi, zo = next_pending_capture_pair(base)
    assert zi.name == "pending_0001.png"
    assert zo.name == f"pending_0001{ZOOMOUT_SUFFIX}.png"
    assert zi.parent.name == ZOOMIN_SUBDIR
    assert zo.parent.name == ZOOMOUT_SUBDIR

    zi.touch()  # zoom-in slot 1 occupied
    zi2, zo2 = next_pending_capture_pair(base)
    assert zi2.name == "pending_0002.png"
    assert zo2.name == f"pending_0002{ZOOMOUT_SUFFIX}.png"


def test_derive_zoomout_path_for_app_owned_layout(tmp_path):
    base = tmp_path / "probe"
    zi, zo_expected = next_pending_capture_pair(base)
    assert derive_zoomout_path(zi) == zo_expected


def test_derive_zoomout_path_legacy_same_folder(tmp_path):
    legacy = tmp_path / "external" / "chip1.png"
    assert derive_zoomout_path(legacy) == (
        tmp_path / "external" / f"chip1{ZOOMOUT_SUFFIX}.png"
    )


def test_final_capture_pair_returns_both_paths(tmp_path):
    base = tmp_path / "probe"
    zi_pending, _ = next_pending_capture_pair(base)
    zi_final, zo_final = final_capture_pair(zi_pending, 0, "CHIP-001")

    assert zi_final.name == "slot_01_CHIP-001.png"
    assert zo_final.name == f"slot_01_CHIP-001{ZOOMOUT_SUFFIX}.png"
    assert zi_final.parent.name == ZOOMIN_SUBDIR
    assert zo_final.parent.name == ZOOMOUT_SUBDIR
