"""Helpers for Manual Mode screen-capture file names."""
from __future__ import annotations

import re
from pathlib import Path

from src.core.database import get_db_dir


_WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def captures_root() -> Path:
    """Return the application-owned capture image root."""
    root = get_db_dir() / "captures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_capture_filename_part(value: str, fallback: str = "capture") -> str:
    """Return a Windows-safe filename component."""
    cleaned = _WINDOWS_FORBIDDEN.sub("_", value.strip())
    cleaned = cleaned.strip(" ._")
    return cleaned if cleaned and cleaned.strip("_") else fallback


def unique_path(path: Path) -> Path:
    """Return ``path`` or a suffixed sibling when it already exists."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def next_pending_capture_path(base_dir: Path) -> Path:
    """Return the next pending capture path in ``base_dir``."""
    base_dir.mkdir(parents=True, exist_ok=True)
    counter = 1
    while True:
        candidate = base_dir / f"pending_{counter:04d}.png"
        if not candidate.exists():
            return candidate
        counter += 1


def is_pending_capture_path(path: str | Path, root: Path | None = None) -> bool:
    """Return True when ``path`` is an app-owned pending capture PNG."""
    capture_path = Path(path)
    if capture_path.suffix.lower() != ".png":
        return False
    if not capture_path.name.lower().startswith("pending_"):
        return False

    return is_app_capture_path(capture_path, root)


def is_app_capture_path(path: str | Path, root: Path | None = None) -> bool:
    """Return True when ``path`` lives under the app-owned capture root."""
    capture_path = Path(path)
    capture_root = root or captures_root()
    try:
        capture_path.resolve().relative_to(capture_root.resolve())
    except (OSError, ValueError):
        return False
    return True


def final_capture_path(pending_path: str | Path, slot_index: int, qr_id: str) -> Path:
    """Return the final QR-based filename for a pending capture."""
    pending = Path(pending_path)
    safe_qr = sanitize_capture_filename_part(qr_id, fallback="qr")
    candidate = pending.with_name(f"slot_{slot_index + 1:02d}_{safe_qr}.png")
    try:
        if pending.resolve() == candidate.resolve():
            return candidate
    except OSError:
        pass
    return unique_path(candidate)
