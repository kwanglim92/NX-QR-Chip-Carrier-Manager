"""ATX 폴더 로드 워크플로우."""
from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from src.core.atx_parser import load_atx_folder
from src.core.slot_mapper import parse_slot_code, format_full_label


class ATXImportMixin:
    def _browse_atx_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "ATX 결과 폴더 선택")
        if not folder:
            return

        self.atx_folder_input.setText(folder)
        self.logger.section("ATX 폴더 로드")
        self.logger.info(f"폴더: {folder}")

        try:
            ms = load_atx_folder(folder)
            self.measurement_set = ms
            self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")

            # UI 업데이트
            self.lbl_po.setText(ms.po_number)
            self.lbl_probe_type.setText(ms.probe_type)
            self.lbl_quantity.setText(f"{ms.quantity}M ({len(ms.slots)}개 슬롯)")

            # 그리드 로드
            self.slot_grid.load_measurement_set(ms)

            # 진행률
            self._update_progress()

            self.logger.ok(f"{len(ms.slots)}개 슬롯 로드 완료")
            self.logger.info(f"PO: {ms.po_number} | Probe: {ms.probe_type}")

            # 첫 번째 슬롯 선택
            if ms.slots:
                self._on_slot_selected(0)

            self._statusbar.showMessage(f"ATX 폴더 로드 완료: {ms.po_number}")

        except Exception as e:
            self.logger.error(f"폴더 로드 실패: {e}")

    def _on_slot_selected(self, slot_index: int):
        self.selected_slot_index = slot_index
        self.slot_grid.select_slot(slot_index)

        if not self.measurement_set:
            return

        slot = self.measurement_set.find_slot_by_index(slot_index)
        if not slot:
            return

        # 이미지 표시
        self.atx_image_viewer.load_image(slot.image_path)

        # Drive 입력값 설정
        if slot.drive is not None:
            self.atx_drive_input.setValue(slot.drive)
        else:
            self.atx_drive_input.setValue(0)

        # ATX/Port/Slot 라벨
        label = format_full_label(slot.slot_code)
        self.qr_input.set_target_label(label)

        self.logger.info(
            f"{label} 선택 — Freq: {slot.format_frequency()}, Q: {slot.format_q()}"
        )

    def _apply_drive(self):
        if not self.measurement_set:
            return

        slot = self.measurement_set.find_slot_by_index(self.selected_slot_index)
        if not slot:
            return

        drive_val = self.atx_drive_input.value()
        if drive_val <= 0:
            return

        slot.drive = drive_val
        self.slot_grid.update_slot(slot)

        label = format_full_label(slot.slot_code)
        self.logger.ok(f"{label}: Drive = {drive_val:.2f}%")

        # 다음 Drive 미입력 슬롯으로 자동 이동
        for s in self.measurement_set.slots:
            if s.drive is None and s.slot_index != self.selected_slot_index:
                self._on_slot_selected(s.slot_index)
                break
