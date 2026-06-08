"""QThread download worker for installer updates."""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from src.updater.config import UPDATE_DOWNLOAD_TIMEOUT_SEC


class DownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal(bool, str)

    def __init__(self, url: str, dest: Path, expected_sha256: str):
        super().__init__()
        self._url = url
        self._dest = dest
        self._expected_sha256 = expected_sha256.lower()

    def run(self) -> None:
        try:
            self._download()
        except Exception as exc:
            self.done.emit(False, str(exc))
            return
        self.done.emit(True, "")

    def _download(self) -> None:
        self._dest.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256()
        received = 0
        with requests.get(
            self._url,
            stream=True,
            timeout=UPDATE_DOWNLOAD_TIMEOUT_SEC,
        ) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", "0") or 0)
            with open(self._dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    sha.update(chunk)
                    received += len(chunk)
                    self.progress.emit(received, total)

        digest = sha.hexdigest().lower()
        if digest != self._expected_sha256:
            raise ValueError(
                f"sha256 mismatch: expected {self._expected_sha256}, got {digest}"
            )
