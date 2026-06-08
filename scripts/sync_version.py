"""Sync build-time version files from VERSION."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
APP_VERSION_FILE = ROOT / "src" / "core" / "_app_version.py"
INNO_VERSION_FILE = ROOT / "version.iss"


def read_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("VERSION is empty")
    return version


def main() -> None:
    version = read_version()
    APP_VERSION_FILE.write_text(
        '"""Generated from VERSION by scripts/sync_version.py."""\n\n'
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    INNO_VERSION_FILE.write_text(
        f'#define MyAppVersion "{version}"\n',
        encoding="utf-8",
    )
    print(f"synced version {version}")


if __name__ == "__main__":
    main()
