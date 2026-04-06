"""CSV 미리보기 + 저장 + 이미지 리네임 내보내기."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog

from src.core.csv_exporter import generate_csv_rows, export_csv, export_with_images


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
                f"{len(incomplete)}개 슬롯의 데이터��� 불완전합니다.\n"
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

    def _export_csv_with_images(self):
        """CSV + ZOOMIN 폴더 (이미지를 QR ID로 리네임) 내보내기."""
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

        # 저장 위치 선택
        parent_dir = QFileDialog.getExistingDirectory(self, "저장할 위치 선택")
        if not parent_dir:
            return

        # 폴더 이름 입력
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
            result = export_with_images(self.measurement_set, output_dir, csv_name)

            self.logger.ok(
                f"내보내기 완료: CSV + {result['image_count']}개 이미지\n"
                f"  CSV: {result['csv_path']}\n"
                f"  ZOOMIN: {result['zoomin_dir']}"
            )
            self._statusbar.showMessage(f"내보내기 완료: {output_dir}")
        except Exception as e:
            self.logger.error(f"내보내기 실패: {e}")

    def _on_date_changed(self):
        if self.measurement_set:
            self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")
