"""NX QR Chip Carrier Manager — Entry Point."""
import sys

from PySide6.QtWidgets import QApplication

from src.ui.theme import DARK_STYLE
from src.ui.main_window import ChipCarrierManagerApp


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    window = ChipCarrierManagerApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
