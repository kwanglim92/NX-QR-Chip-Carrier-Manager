"""수동 측정 이미지 스텝핑 워크플로우."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from src.core.models import MeasurementSet, SlotData


class ManualImportMixin:
    def _init_manual_state(self):
        self.manual_images: list[Path] = []
        self.manual_current_idx: int = 0

    def _browse_manual_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "수동 측정 폴더 선택")
        if not folder:
            return

        self.manual_folder_input.setText(folder)
        self._init_manual_state()

        folder_path = Path(folder)

        # 숫자.jpg 패턴만 수집 (백틱 제외)
        images = []
        for f in folder_path.iterdir():
            if f.suffix.lower() in (".jpg", ".png") and re.match(r"^\d+\.", f.name):
                if "`" not in f.name:
                    images.append(f)

        images.sort(key=lambda p: int(re.match(r"(\d+)", p.name).group(1)))
        self.manual_images = images

        # MeasurementSet 생성
        probe_type = self.manual_probe_input.text().strip()
        ms = MeasurementSet(
            po_number=folder_path.name,
            quantity=len(images),
            probe_type=probe_type,
            production_date=self.date_edit.date().toString("yyyyMMdd"),
            source_folder=str(folder_path),
            mode="manual",
        )

        for i, img in enumerate(images):
            slot = SlotData(
                slot_index=i,
                slot_code=str(i + 1),
                image_path=str(img),
                source="manual_entry",
            )
            ms.slots.append(slot)

        self.measurement_set = ms
        self.manual_current_idx = 0

        self.lbl_manual_count.setText(f"{len(images)}개")
        self._update_progress()
        self._show_manual_image()

        self.logger.section("수동 측정 폴더 로드")
        self.logger.ok(f"{len(images)}개 이미지 발견")

    def _show_manual_image(self):
        if not self.manual_images:
            return

        idx = self.manual_current_idx
        total = len(self.manual_images)
        self.lbl_img_index.setText(f"{idx + 1} / {total}")

        img_path = str(self.manual_images[idx])
        self.manual_image_viewer.load_image(img_path)

        # 기존 입력값 복원
        if self.measurement_set:
            slot = self.measurement_set.find_slot_by_index(idx)
            if slot:
                if slot.frequency:
                    self.manual_freq_input.setValue(slot.frequency)
                else:
                    self.manual_freq_input.setValue(0)
                if slot.drive:
                    self.manual_drive_input.setValue(slot.drive)
                else:
                    self.manual_drive_input.setValue(0)
                if slot.q_factor:
                    self.manual_q_input.setValue(slot.q_factor)
                else:
                    self.manual_q_input.setValue(0)

        self.qr_input.set_target_label(f"이미지 {idx + 1}")
        self.btn_prev_img.setEnabled(idx > 0)
        self.btn_next_img.setEnabled(idx < total - 1)

    def _prev_manual_image(self):
        if self.manual_current_idx > 0:
            self.manual_current_idx -= 1
            self._show_manual_image()

    def _next_manual_image(self):
        if self.manual_current_idx < len(self.manual_images) - 1:
            self.manual_current_idx += 1
            self._show_manual_image()

    def _confirm_manual_entry(self):
        if not self.measurement_set:
            return

        idx = self.manual_current_idx
        slot = self.measurement_set.find_slot_by_index(idx)
        if not slot:
            return

        freq = self.manual_freq_input.value()
        drive = self.manual_drive_input.value()
        q = self.manual_q_input.value()

        if freq <= 0 or q <= 0:
            self.logger.warn(f"이미지 {idx + 1}: Frequency와 Q 값을 입력하세요")
            return

        slot.frequency = freq
        slot.drive = drive if drive > 0 else None
        slot.q_factor = q

        # Probe Type 업데이트
        probe_type = self.manual_probe_input.text().strip()
        if probe_type:
            self.measurement_set.probe_type = probe_type

        self.logger.ok(
            f"이미지 {idx + 1}: Freq={round(freq)} KHz, "
            f"Drive={round(drive, 1)}%, Q={round(q)}"
        )

        self._update_progress()

        # 다음 이미지로
        if idx < len(self.manual_images) - 1:
            self.manual_current_idx += 1
            self._show_manual_image()
            self.qr_input.focus_input()
