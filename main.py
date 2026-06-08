"""MC QR Code Chip Carrier Manager — Entry Point."""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QApplication

from src.ui.theme import ACTIVE_PALETTE, ACTIVE_STYLE, THEME_APP, THEME_ORG
from src.ui.main_window import ChipCarrierManagerApp

APP_MUTEX_NAME = "McQrManager_AppMutex"
_APP_MUTEX = None
if sys.platform == "win32":
    try:
        _APP_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
    except Exception:
        _APP_MUTEX = None


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(THEME_ORG)
    app.setApplicationName(THEME_APP)
    app.setStyle("Fusion")
    app.setPalette(ACTIVE_PALETTE)
    app.setStyleSheet(ACTIVE_STYLE)

    from src.updater import check_and_apply
    if check_and_apply():
        sys.exit(0)

    window = ChipCarrierManagerApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
