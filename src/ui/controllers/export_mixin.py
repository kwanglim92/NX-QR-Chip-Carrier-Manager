"""CSV 내보내기 + Action-First Export 탭 로직."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog

from src.core.csv_exporter import export_csv, export_with_images


class ExportMixin:
    def _get_active_export_mode(self) -> str:
        if hasattr(self, "export_tabs") and self.export_tabs.currentIndex() == 1:
            return "manual"
        return "atx"

    def _get_export_measurement_set(self):
        mode = self._get_active_export_mode()
        return getattr(self, "measurement_sets", {}).get(mode)

    def _refresh_export_view(self):
        """Export 탭 진입 시 슬롯 테이블 + 액션 바 갱신."""
        atx_ms = getattr(self, "measurement_sets", {}).get("atx")
        manual_ms = getattr(self, "measurement_sets", {}).get("manual")

        self.export_atx_table.load_slots(
            atx_ms.slots if atx_ms else [],
            atx_ms.probe_type if atx_ms else "",
        )
        self.export_manual_table.load_slots(
            manual_ms.slots if manual_ms else [],
            manual_ms.probe_type if manual_ms else "",
        )
        self._refresh_export_status()

    def _export_csv(self):
        ms = self._get_export_measurement_set()
        if not ms or not ms.slots:
            self.logger.warn("내보낼 데이터가 없습니다")
            return

        ms.production_date = self.date_edit.date().toString("yyyyMMdd")

        # 완성도 체크
        incomplete = [s for s in ms.slots if not s.is_complete]
        if incomplete:
            reply = QMessageBox.question(
                self,
                "미완성 데이터",
                f"{len(incomplete)}개 슬롯의 데이터가 불완전합니다.\n"
                "QR ID가 있는 슬롯만 내보내시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        default_name = f"{ms.po_number}_QR.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV 저장", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            export_csv(ms, path)
            self.logger.ok(f"CSV 저장 완료: {path}")
            self._statusbar.showMessage(f"CSV 저장: {path}")
        except Exception as e:
            self.logger.error(f"CSV 저장 실패: {e}")

    def _export_csv_with_images(self):
        """CSV + ZOOMIN 폴더 (이미지를 QR ID로 리네임) 내보내기."""
        ms = self._get_export_measurement_set()
        if not ms or not ms.slots:
            self.logger.warn("내보낼 데이터가 없습니다")
            return

        ms.production_date = self.date_edit.date().toString("yyyyMMdd")

        incomplete = [s for s in ms.slots if not s.is_complete]
        if incomplete:
            reply = QMessageBox.question(
                self,
                "미완성 데이터",
                f"{len(incomplete)}개 슬롯의 데이터가 불완전합니다.\n"
                "QR ID가 있는 슬롯만 내보내시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        parent_dir = QFileDialog.getExistingDirectory(self, "저장할 위치 선택")
        if not parent_dir:
            return

        default_name = self.measurement_set.po_number or "export"
        folder_name, ok = QInputDialog.getText(
            self, "폴더 이름", "생성할 폴더 이름:", text=default_name
        )
        if not ok or not folder_name.strip():
            return

        folder_name = folder_name.strip()
        output_dir = str(Path(parent_dir) / folder_name)

        try:
            csv_name = f"{folder_name}_QR.csv"
            result = export_with_images(ms, output_dir, csv_name)

            self.logger.ok(
                f"내보내기 완료: CSV + {result['image_count']}개 이미지\n"
                f"  CSV: {result['csv_path']}\n"
                f"  ZOOMIN: {result['zoomin_dir']}"
            )
            self._statusbar.showMessage(f"내보내기 완료: {output_dir}")
        except Exception as e:
            self.logger.error(f"내보내기 실패: {e}")

    def _on_date_changed(self):
        if getattr(self, "current_mode", "") == "export":
            ms = self._get_export_measurement_set()
        else:
            ms = self.measurement_set

        if ms:
            ms.production_date = self.date_edit.date().toString("yyyyMMdd")
            self._auto_save_to_db(ms)
            if getattr(self, "current_mode", "") == "export":
                self._refresh_export_status()

    def _on_export_tab_changed(self, _idx: int):
        if hasattr(self, "export_image_viewer"):
            self.export_image_viewer.clear()
        self._refresh_export_status()

    def _refresh_export_status(self):
        if not hasattr(self, "lbl_export_status"):
            return

        mode = self._get_active_export_mode()
        ms = self._get_export_measurement_set()
        if not ms or not ms.slots:
            self.lbl_export_status.setText(f"No {mode.upper()} data")
            self.export_progress_bar.setValue(0)
            return

        total = len(ms.slots)
        complete = sum(1 for s in ms.slots if s.is_complete)
        pct = int(complete / total * 100) if total > 0 else 0
        self.lbl_export_status.setText(
            f"● {mode.upper()} {complete}/{total} Complete ({pct}%)"
        )
        self.export_progress_bar.setValue(pct)

    def _on_export_slot_detail_selected(self, slot_index: int):
        """슬롯 행 클릭 → 이미지 미리보기."""
        mode = self._get_active_export_mode()
        active_table = (
            self.export_manual_table if mode == "manual" else self.export_atx_table
        )
        sender = self.sender()
        if sender is not None and sender is not active_table:
            return

        ms = self._get_export_measurement_set()
        if not ms:
            return

        slot = ms.find_slot_by_index(slot_index)
        if not slot:
            return

        if slot.image_path:
            self.export_image_viewer.load_image(slot.image_path)
        else:
            self.export_image_viewer.clear()

    def _on_slot_detail_selected(self, slot_index: int):
        self._on_export_slot_detail_selected(slot_index)
