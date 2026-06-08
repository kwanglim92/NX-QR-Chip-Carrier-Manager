"""Run a downloaded Inno Setup installer for auto-update."""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.core.logger import get_logger

log = get_logger(__name__)

_SE_ERR_THRESHOLD = 32
_SW_SHOWNORMAL = 1
_DEFAULT_SILENT_ARGS = (
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/NOCANCEL",
    "/RESTARTAPPLICATIONS",
)


def run_installer(
    setup_exe: Path,
    *,
    log_dir: Optional[Path] = None,
    silent_args: Optional[Sequence[str]] = None,
    elevate: bool = False,
) -> None:
    """Launch a downloaded Inno Setup installer.

    The caller must exit the app immediately after this returns so the installer
    can replace the running files and restart the app via Restart Manager.
    """
    if sys.platform != "win32":
        raise RuntimeError("installer apply step is Windows-only")
    if not setup_exe.exists():
        raise RuntimeError(f"installer not found: {setup_exe}")

    args = list(silent_args) if silent_args is not None else list(_DEFAULT_SILENT_ARGS)
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        args.append(f'/LOG={log_dir / "_apply_update_install.log"}')

    params = " ".join(args)
    verb = "runas" if elevate else "open"
    log.info("launching installer: %s %s (verb=%s)", setup_exe, params, verb)
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        verb,
        str(setup_exe),
        params,
        None,
        _SW_SHOWNORMAL,
    )
    if int(rc) <= _SE_ERR_THRESHOLD:
        raise RuntimeError(
            f"ShellExecuteW failed to launch installer (code={rc})"
        )
    log.info("installer launched (ShellExecuteW code=%s)", rc)
