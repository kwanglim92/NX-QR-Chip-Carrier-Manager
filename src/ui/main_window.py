"""메인 윈도우 — Mixin 조합 (SKILL 12 패턴)."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from src.ui.controllers.ui_builder_mixin import UIBuilderMixin
from src.ui.controllers.atx_import_mixin import ATXImportMixin
from src.ui.controllers.manual_import_mixin import ManualImportMixin
from src.ui.controllers.qr_match_mixin import QRMatchMixin
from src.ui.controllers.export_mixin import ExportMixin


class ChipCarrierManagerApp(
    UIBuilderMixin,
    ATXImportMixin,
    ManualImportMixin,
    QRMatchMixin,
    ExportMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self._init_shared_state()
        self._build_ui()
        self._init_manual_state()

    def _init_shared_state(self):
        self.current_mode: str = "atx"
        self.measurement_set = None
        self.selected_slot_index: int = 0
