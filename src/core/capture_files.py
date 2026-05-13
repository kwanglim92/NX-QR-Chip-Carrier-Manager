"""Helpers for Manual Mode screen-capture file names."""
from __future__ import annotations

import re
from pathlib import Path

from src.core.database import get_db_dir


_WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

ZOOMIN_SUBDIR = "zoomin"
ZOOMOUT_SUBDIR = "zoomout"
ZOOMOUT_SUFFIX = "`"
_ZOOM_LEVELS = ("zoomin", "zoomout")


def captures_root() -> Path:
    """Return the application-owned capture image root."""
    root = get_db_dir() / "captures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def zoom_dir(base_dir: Path, level: str) -> Path:
    """Return the zoomin/ or zoomout/ subdirectory beneath ``base_dir``."""
    if level not in _ZOOM_LEVELS:
        raise ValueError(f"invalid zoom level: {level!r}")
    sub = ZOOMIN_SUBDIR if level == "zoomin" else ZOOMOUT_SUBDIR
    path = base_dir / sub
    path.mkdir(parents=True, exist_ok=True)
    return path


def zoom_filename(stem: str, ext: str, level: str) -> str:
    """Compose a zoom-aware filename.

    Zoom-in uses ``{stem}{ext}``. Zoom-out appends ``ZOOMOUT_SUFFIX`` to the stem.
    """
    if level not in _ZOOM_LEVELS:
        raise ValueError(f"invalid zoom level: {level!r}")
    suffix = ZOOMOUT_SUFFIX if level == "zoomout" else ""
    return f"{stem}{suffix}{ext}"


def is_zoomout_filename(name: str) -> bool:
    """Return True when the filename stem ends with the zoom-out suffix."""
    stem = Path(name).stem
    return bool(stem) and stem.endswith(ZOOMOUT_SUFFIX)


def derive_zoomout_path(zoomin_path: str | Path) -> Path:
    """Derive the zoom-out sibling for a given zoom-in image path.

    Two layouts are supported:

    1. App-owned captures: ``<base>/zoomin/<name>`` → ``<base>/zoomout/<stem>`<ext>``.
    2. Legacy / external paths: same directory, with backtick appended to the stem.
    """
    src = Path(zoomin_path)
    stem = src.stem
    ext = src.suffix
    out_name = f"{stem}{ZOOMOUT_SUFFIX}{ext}"

    parent = src.parent
    if parent.name.lower() == ZOOMIN_SUBDIR:
        return parent.parent / ZOOMOUT_SUBDIR / out_name
    return parent / out_name


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


def next_pending_capture_pair(base_dir: Path) -> tuple[Path, Path]:
    """Return a (zoomin, zoomout) pending capture pair under ``base_dir``.

    Both paths share the same counter; the counter is advanced until neither
    sibling exists. The zoom-in goes into ``zoomin/pending_NNNN.png`` and the
    zoom-out into ``zoomout/pending_NNNN`.png``.
    """
    zi_dir = zoom_dir(base_dir, "zoomin")
    zo_dir = zoom_dir(base_dir, "zoomout")
    counter = 1
    while True:
        zi = zi_dir / f"pending_{counter:04d}.png"
        zo = zo_dir / f"pending_{counter:04d}{ZOOMOUT_SUFFIX}.png"
        if not zi.exists() and not zo.exists():
            return zi, zo
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


def final_capture_pair(
    zoomin_pending: str | Path, slot_index: int, qr_id: str
) -> tuple[Path, Path]:
    """Return final (zoomin, zoomout) paths for a captured pair.

    Both share the same QR-based stem; the zoom-out variant appends
    ``ZOOMOUT_SUFFIX`` and lives in the sibling ``zoomout/`` directory when the
    pending path is app-owned.
    """
    zi_final = final_capture_path(zoomin_pending, slot_index, qr_id)
    zo_dir = zi_final.parent
    if zo_dir.name.lower() == ZOOMIN_SUBDIR:
        zo_dir = zo_dir.parent / ZOOMOUT_SUBDIR
        zo_dir.mkdir(parents=True, exist_ok=True)
    zo_candidate = zo_dir / f"{zi_final.stem}{ZOOMOUT_SUFFIX}{zi_final.suffix}"
    return zi_final, unique_path(zo_candidate)
