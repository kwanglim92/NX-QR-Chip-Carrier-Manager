"""설정 저장/복원 컨트롤러 (SKILL 14 패턴, SQLite 통합)."""
from __future__ import annotations

from src.core.database import (
    load_all_settings,
    load_setting,
    save_all_settings,
    save_setting,
)

DEFAULT_SETTINGS = {
    "window_geometry": "",
    "last_mode": "atx",
    "server_id": "",
    "manual_columns": 4,
    "last_production_date": "",
    "recent_folders": [],
}

_RESET_ON_START_KEYS = {"last_production_date"}

# 관리형 Tip 카탈로그 — app_settings 에 독립 키로 즉시 영속화 (self._settings 와 분리)
TIP_CATALOG_KEY = "manual_tip_catalog"


class SettingsMixin:
    def _init_settings(self):
        """DB에서 설정 로드 → 기본값 머지 → 리셋 키 처리."""
        saved = load_all_settings(self._db_conn)

        self._settings = dict(DEFAULT_SETTINGS)
        for key, value in saved.items():
            if key in DEFAULT_SETTINGS and key not in _RESET_ON_START_KEYS:
                self._settings[key] = value

        # 리셋 키는 항상 기본값
        for key in _RESET_ON_START_KEYS:
            self._settings[key] = DEFAULT_SETTINGS[key]

    def _save_settings(self):
        """현재 설정을 DB에 저장."""
        if not hasattr(self, "_db_conn") or not self._db_conn:
            return
        save_all_settings(self._db_conn, self._settings)

    def _restore_window_geometry(self):
        """저장된 윈도우 크기/위치 복원."""
        geo = self._settings.get("window_geometry", "")
        if not geo:
            return
        try:
            parts = geo.split(",")
            if len(parts) == 4:
                x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                self.setGeometry(x, y, w, h)
        except (ValueError, TypeError):
            pass

    def _save_window_geometry(self):
        """현재 윈도우 크기/위치 저장."""
        geo = self.geometry()
        self._settings["window_geometry"] = (
            f"{geo.x()},{geo.y()},{geo.width()},{geo.height()}"
        )

    def _apply_settings_to_ui(self):
        """저장된 설정을 UI에 적용."""
        # 서버 ID는 _settings에 보관 (로그인 다이얼로그에서 사용)

        # 수동 모드 열 수
        cols = self._settings.get("manual_columns", 4)
        if hasattr(self, "manual_col_spin"):
            self.manual_col_spin.setValue(cols)

        # 마지막 모드
        last_mode = self._settings.get("last_mode", "atx")
        self._switch_mode(last_mode)

    def _collect_settings_from_ui(self):
        """현재 UI 상태를 설정에 수집."""
        if hasattr(self, "current_mode"):
            self._settings["last_mode"] = self.current_mode

        # server_id는 로그인 시 _settings에 직접 저장됨

        if hasattr(self, "manual_col_spin"):
            self._settings["manual_columns"] = self.manual_col_spin.value()

    def _add_recent_folder(self, folder_path: str):
        """최근 폴더 추가 (최대 5개, 중복 제거)."""
        recent = self._settings.get("recent_folders", [])
        if folder_path in recent:
            recent.remove(folder_path)
        recent.insert(0, folder_path)
        self._settings["recent_folders"] = recent[:5]

    # ─── Tip 카탈로그 (관리형) ───

    def _load_tip_catalog(self) -> list[str]:
        """저장된 Tip 카탈로그 목록 반환 (정규화된 문자열 리스트)."""
        cat = load_setting(self._db_conn, TIP_CATALOG_KEY, [])
        if not isinstance(cat, list):
            return []
        seen: set[str] = set()
        cleaned: list[str] = []
        for name in cat:
            n = str(name).strip()
            if n and n not in seen:
                seen.add(n)
                cleaned.append(n)
        return cleaned

    def _save_tip_catalog(self, catalog: list[str]) -> None:
        """Tip 카탈로그 저장 (공백/빈값/중복 제거, 순서 보존)."""
        seen: set[str] = set()
        cleaned: list[str] = []
        for name in catalog:
            n = str(name).strip()
            if n and n not in seen:
                seen.add(n)
                cleaned.append(n)
        save_setting(self._db_conn, TIP_CATALOG_KEY, cleaned)
