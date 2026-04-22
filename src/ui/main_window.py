"""메인 윈도우 — Mixin 조합 (SKILL 12 패턴)."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from src.ui.controllers.ui_builder_mixin import UIBuilderMixin
from src.ui.controllers.atx_import_mixin import ATXImportMixin
from src.ui.controllers.manual_import_mixin import ManualImportMixin
from src.ui.controllers.qr_match_mixin import QRMatchMixin
from src.ui.controllers.export_mixin import ExportMixin
from src.ui.controllers.upload_mixin import UploadMixin
from src.ui.controllers.history_mixin import HistoryMixin
from src.ui.controllers.settings_mixin import SettingsMixin


class ChipCarrierManagerApp(
    UIBuilderMixin,
    ATXImportMixin,
    ManualImportMixin,
    QRMatchMixin,
    ExportMixin,
    UploadMixin,
    HistoryMixin,
    SettingsMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self._init_db()
        self._init_ocr()
        self._init_shared_state()
        self._init_settings()
        self._build_ui()
        self._init_manual_state()
        self._init_upload_state()
        self._init_history_state()
        self._restore_window_geometry()
        self._apply_settings_to_ui()

    def _init_db(self):
        from src.core.database import get_connection, init_db
        self._db_conn = get_connection()
        init_db(self._db_conn)

    def _init_ocr(self):
        """F-14: 포터블 Tesseract 바이너리 설정 (없으면 OCR 조용히 비활성화)."""
        from src.core.tesseract_setup import configure_tesseract
        self._ocr_available = configure_tesseract()

    def _init_shared_state(self):
        self.current_mode: str = "atx"
        self.measurement_set = None
        self.selected_slot_index: int = 0

    def _auto_save_to_db(self) -> int | None:
        """현재 measurement_set을 DB에 자동 저장."""
        if not self.measurement_set:
            return None
        from src.core.database import save_measurement_set
        ms_id = save_measurement_set(self._db_conn, self.measurement_set)
        return ms_id

    def closeEvent(self, event):
        self._save_window_geometry()
        self._collect_settings_from_ui()
        self._save_settings()
        if hasattr(self, "_db_conn") and self._db_conn:
            self._db_conn.close()
        super().closeEvent(event)
