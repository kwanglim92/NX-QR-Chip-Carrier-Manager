"""Auto-update configuration."""
from __future__ import annotations

import os

UPDATE_SERVER_URL = os.getenv(
    "MCQR_UPDATE_SERVER",
    "http://10.4.1.141:8006",
).rstrip("/")

UPDATE_MANIFEST_PATH = "/manifest.json"

UPDATE_CHECK_TIMEOUT_SEC = float(os.getenv("MCQR_UPDATE_TIMEOUT", "3"))
UPDATE_DOWNLOAD_TIMEOUT_SEC = float(os.getenv("MCQR_UPDATE_DL_TIMEOUT", "120"))
UPDATE_ENABLED = os.getenv("MCQR_UPDATE_ENABLED", "1") == "1"

# Current installer is per-user (PrivilegesRequired=lowest), so elevation is off
# by default. Set MCQR_UPDATE_ELEVATE=1 if future installers require admin.
UPDATE_ELEVATE = os.getenv("MCQR_UPDATE_ELEVATE", "0") == "1"
