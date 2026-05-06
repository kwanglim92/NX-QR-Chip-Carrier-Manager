"""메인 윈도우 — Mixin 조합 (SKILL 12 패턴)."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from src.core.models import MeasurementSet
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
        self._active_data_mode: str = "atx"
        self.measurement_sets: dict[str, MeasurementSet | None] = {
            "atx": None,
            "manual": None,
        }
        self.selected_slot_index: int = 0

    @property
    def measurement_set(self) -> MeasurementSet | None:
        """Return the active ATX/Manual measurement set for legacy mixins."""
        mode = (
            self.current_mode
            if self.current_mode in self.measurement_sets
            else self._active_data_mode
        )
        return self.measurement_sets.get(mode)

    @measurement_set.setter
    def measurement_set(self, value: MeasurementSet | None) -> None:
        if value is None:
            mode = (
                self.current_mode
                if self.current_mode in self.measurement_sets
                else self._active_data_mode
            )
            self.measurement_sets[mode] = None
            return

        mode = (
            value.mode
            if value.mode in self.measurement_sets
            else self._active_data_mode
        )
        self.measurement_sets[mode] = value

    def _auto_save_to_db(self, measurement_set: MeasurementSet | None = None) -> int | None:
        """현재 또는 지정한 measurement_set을 DB에 자동 저장."""
        target = measurement_set or self.measurement_set
        if not target:
            return None
        from src.core.database import save_measurement_set
        ms_id = save_measurement_set(self._db_conn, target)
        return ms_id

    def closeEvent(self, event):
        self._save_window_geometry()
        self._collect_settings_from_ui()
        self._save_settings()
        if hasattr(self, "_db_conn") and self._db_conn:
            self._db_conn.close()
        super().closeEvent(event)
