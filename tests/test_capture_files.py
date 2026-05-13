from __future__ import annotations

from src.core.capture_files import (
    final_capture_path,
    is_app_capture_path,
    is_pending_capture_path,
    next_pending_capture_path,
    sanitize_capture_filename_part,
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
