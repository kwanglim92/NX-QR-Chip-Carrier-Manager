"""Installer-based update orchestration."""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from src.core._app_version import __version__
from src.core.database import get_db_dir
from src.core.logger import get_logger
from src.updater.config import (
    UPDATE_CHECK_TIMEOUT_SEC,
    UPDATE_ELEVATE,
    UPDATE_ENABLED,
    UPDATE_MANIFEST_PATH,
    UPDATE_SERVER_URL,
)

log = get_logger(__name__)

_VERSION_RE = re.compile(r"^\d+(\.\d+){1,3}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_APP_STEM = "McQrManager"


@dataclass(frozen=True)
class UpdateCandidate:
    latest_version: str
    download_url: str
    sha256: str
    release_notes: str


def check_and_apply(parent=None) -> bool:
    """Download and launch a newer installer when available.

    Returns True only after the installer has been launched. The caller must exit
    immediately on True.
    """
    if not getattr(sys, "frozen", False):
        return False
    if not UPDATE_ENABLED:
        return False

    if not UPDATE_SERVER_URL.lower().startswith("https://"):
        log.warning(
            "update server is not HTTPS (%s); SHA-256 provides integrity only",
            UPDATE_SERVER_URL,
        )

    try:
        manifest = _fetch_manifest()
    except Exception as exc:
        log.warning("update check failed: %s", exc)
        return False

    candidate = _candidate_from_manifest(manifest, __version__)
    if candidate is None:
        return False

    work_dir = get_db_dir() / "updates"
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = work_dir / f"{_APP_STEM}-Setup-{candidate.latest_version}.exe.tmp"
    setup_path = work_dir / f"{_APP_STEM}-Setup-{candidate.latest_version}.exe"

    if tmp_path.resolve().parent != work_dir.resolve():
        log.error("staged update path escaped work_dir: %s", tmp_path)
        return False

    result = {"ok": False, "error": ""}
    try:
        from src.updater.dialog import UpdateDialog
        from src.updater.download_worker import DownloadWorker

        dlg = UpdateDialog(parent, candidate.latest_version, candidate.release_notes)
        worker = DownloadWorker(candidate.download_url, tmp_path, candidate.sha256)

        def _on_done(ok: bool, error: str) -> None:
            result["ok"] = ok
            result["error"] = error
            dlg.accept()

        worker.progress.connect(dlg.on_progress)
        worker.done.connect(_on_done)
        worker.start()
        dlg.exec()
        worker.wait()
    except Exception as exc:
        log.exception("update download/dialog failed: %s", exc)
        _safe_unlink(tmp_path)
        return False

    if not result["ok"]:
        log.warning("update download failed: %s", result["error"])
        _safe_unlink(tmp_path)
        return False

    if not _file_sha256_matches(tmp_path, candidate.sha256):
        log.error("downloaded installer SHA-256 verification failed: %s", tmp_path)
        _safe_unlink(tmp_path)
        return False

    try:
        if setup_path.exists():
            setup_path.unlink()
        tmp_path.rename(setup_path)
    except OSError as exc:
        log.exception("rename .tmp -> installer failed: %s", exc)
        _safe_unlink(tmp_path)
        return False

    try:
        from src.updater.installer_applier import run_installer

        run_installer(setup_path, log_dir=work_dir, elevate=UPDATE_ELEVATE)
    except Exception as exc:
        log.exception("installer launch failed: %s", exc)
        _safe_unlink(setup_path)
        return False

    return True


def _candidate_from_manifest(
    manifest: Optional[dict],
    current_version: str,
) -> Optional[UpdateCandidate]:
    if not isinstance(manifest, dict):
        return None

    latest = str(manifest.get("latest_version", "")).strip()
    if not _is_valid_version(latest):
        log.error("manifest latest_version invalid: %r", latest)
        return None

    min_required = str(manifest.get("min_required_version", "")).strip()
    mandatory = (
        bool(min_required)
        and _is_valid_version(min_required)
        and _parse(current_version) < _parse(min_required)
    )
    if not _is_newer(latest, current_version) and not mandatory:
        return None
    if mandatory and not _is_newer(latest, current_version):
        log.error(
            "min_required_version %s not satisfiable by latest %s",
            min_required,
            latest,
        )
        return None

    download_url = str(manifest.get("download_url", "")).strip()
    expected_sha = str(manifest.get("sha256", "")).lower().strip()
    if not download_url or not _SHA256_RE.match(expected_sha):
        log.error("manifest missing/invalid download_url or sha256")
        return None

    return UpdateCandidate(
        latest_version=latest,
        download_url=download_url,
        sha256=expected_sha,
        release_notes=str(manifest.get("release_notes", "") or ""),
    )


def _fetch_manifest() -> Optional[dict]:
    import requests

    url = f"{UPDATE_SERVER_URL}{UPDATE_MANIFEST_PATH}"
    resp = requests.get(url, timeout=UPDATE_CHECK_TIMEOUT_SEC)
    if resp.status_code != 200:
        log.info("manifest http %s from %s", resp.status_code, url)
        return None
    return resp.json()


def _is_valid_version(version: str) -> bool:
    return bool(_VERSION_RE.match(version or ""))


def _is_newer(latest: str, current: str) -> bool:
    return _parse(latest) > _parse(current)


def _parse(version: str) -> Tuple[int, ...]:
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)


def _file_sha256_matches(path: Path, expected_sha256: str) -> bool:
    if not path.exists():
        return False
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            sha.update(chunk)
    return sha.hexdigest().lower() == expected_sha256.lower()


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
