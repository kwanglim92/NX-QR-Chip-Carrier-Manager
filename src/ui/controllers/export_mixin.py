"""CSV 미리보기 + 저장."""
from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.csv_exporter import generate_csv_rows, export_csv


class ExportMixin:
    def _refresh_csv_preview(self):
        if not self.measurement_set:
            self.logger.warn("내보낼 데이터가 없습니다")
            return

        # 생산일자 동기화
        self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")

        rows = generate_csv_rows(self.measurement_set)
        self.csv_preview.load_rows(rows)

        data_count = len(rows) - 1  # 헤더 제외
        self.logger.info(f"CSV 미리보기: {data_count}행")

        # 미완성 슬롯 경고
        incomplete = [s for s in self.measurement_set.slots if not s.is_complete]
        if incomplete:
            self.logger.warn(
                f"{len(incomplete)}개 슬롯이 미완성 (QR/Freq/Q/Drive 누락)"
            )

    def _export_csv(self):
        if not self.measurement_set:
            self.logger.warn("내보낼 데이터가 없습니다")
            return

        self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")

        # 완성도 체크
        incomplete = [s for s in self.measurement_set.slots if not s.is_complete]
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

        # 기본 파일명
        default_name = f"{self.measurement_set.po_number}_QR.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV 저장", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            export_csv(self.measurement_set, path)
            self.logger.ok(f"CSV 저장 완료: {path}")
            self._statusbar.showMessage(f"CSV 저장: {path}")
        except Exception as e:
            self.logger.error(f"CSV 저장 실패: {e}")

    def _on_date_changed(self):
        if self.measurement_set:
            self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")
