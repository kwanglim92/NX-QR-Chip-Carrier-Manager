"""수동 측정 워크플로우 — Probe Type 탭 + 드래그&드롭 카드 그리드."""
from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog

from src.core.models import MeasurementSet, SlotData
from src.ui.widgets.manual_card import ManualCard
from src.ui.widgets.manual_grid_widget import ManualGridWidget


class ManualImportMixin:
    def _init_manual_state(self):
        self._manual_slot_counter: int = 0
        self._manual_grids: dict[str, ManualGridWidget] = {}  # probe_type -> grid
        self.selected_manual_index: int = -1

        # MeasurementSet 초기화 (수동 모드)
        if not hasattr(self, 'measurement_set') or self.measurement_set is None:
            self.measurement_set = MeasurementSet(mode="manual")

    # ─── 탭 관리 ───

    def _add_probe_tab(self):
        text, ok = QInputDialog.getText(
            self, "Probe Type 추가", "Probe Type 이름:"
        )
        if not ok or not text.strip():
            return

        probe_type = text.strip()
        if probe_type in self._manual_grids:
            self.logger.warn(f"'{probe_type}' 탭이 이미 존재합니다")
            return

        grid = ManualGridWidget()
        grid.set_columns(self.manual_col_spin.value())
        grid.card_clicked.connect(self._on_manual_card_selected)
        grid.card_removed.connect(self._on_manual_card_removed)
        grid.images_dropped.connect(
            lambda paths, pt=probe_type: self._on_images_dropped(pt, paths)
        )

        self._manual_grids[probe_type] = grid

        # 전체 현황 탭 앞에 삽입
        overview_idx = self.manual_tabs.count() - 1
        self.manual_tabs.insertTab(overview_idx, grid, probe_type)
        self.manual_tabs.setCurrentIndex(overview_idx)

        self.logger.ok(f"'{probe_type}' 탭 추가됨")
        self._refresh_overview()

    def _remove_current_probe_tab(self):
        idx = self.manual_tabs.currentIndex()
        # 전체 현황 탭은 삭제 불가
        if idx == self.manual_tabs.count() - 1:
            self.logger.warn("Overview 탭은 삭제할 수 없습니다")
            return

        probe_type = self.manual_tabs.tabText(idx)
        reply = QMessageBox.question(
            self,
            "탭 삭제",
            f"'{probe_type}' 탭과 모든 카드를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 해당 probe type의 SlotData 제거
        grid = self._manual_grids.pop(probe_type, None)
        if grid:
            indices = grid.get_slot_indices()
            self.measurement_set.slots = [
                s for s in self.measurement_set.slots
                if s.slot_index not in indices
            ]
            grid.deleteLater()

        self.manual_tabs.removeTab(idx)
        self.logger.info(f"'{probe_type}' 탭 삭제됨")
        self._refresh_overview()
        self._update_progress()

    # ─── 이미지 불러오기 (파일 다이얼로그) ───

    def _browse_manual_images(self):
        """현재 탭에 이미지를 파일 다이얼로그로 불러오기."""
        if not self._manual_grids:
            QMessageBox.warning(self, "Warning", "Probe Type 탭을 먼저 추가하세요.")
            return

        idx = self.manual_tabs.currentIndex()
        if idx >= self.manual_tabs.count() - 1:
            QMessageBox.warning(self, "Warning", "Probe Type 탭을 선택하세요.")
            return

        probe_type = self.manual_tabs.tabText(idx)

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "이미지 불러오기",
            "",
            "이미지 파일 (*.jpg *.jpeg *.png *.bmp);;모든 파일 (*)",
        )
        if paths:
            self._on_images_dropped(probe_type, paths)

    # ─── 이미지 드롭 처리 ───

    def _on_images_dropped(self, probe_type: str, paths: list[str]):
        if self.measurement_set.mode != "manual":
            self.measurement_set = MeasurementSet(mode="manual")

        self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")

        grid = self._manual_grids.get(probe_type)
        if not grid:
            return

        first_index = None
        for path in paths:
            idx = self._manual_slot_counter
            self._manual_slot_counter += 1

            slot = SlotData(
                slot_index=idx,
                slot_code=str(idx + 1),
                image_path=path,
                source="manual_entry",
                probe_type=probe_type,
            )
            self.measurement_set.slots.append(slot)

            card = ManualCard(idx, path)
            grid.add_card(card)

            if first_index is None:
                first_index = idx

        self.logger.ok(f"'{probe_type}' 탭에 {len(paths)}개 이미지 추가")
        self._refresh_overview()
        self._update_progress()

        if first_index is not None:
            self._on_manual_card_selected(first_index)

    # ─── 카드 선택/삭제 ───

    def _on_manual_card_selected(self, slot_index: int):
        # 이전 선택 해제
        for grid in self._manual_grids.values():
            if self.selected_manual_index in grid._cards:
                grid._cards[self.selected_manual_index].set_selected(False)

        self.selected_manual_index = slot_index

        # 새 선택 표시
        for grid in self._manual_grids.values():
            if slot_index in grid._cards:
                grid.select_card(slot_index)
                break

        slot = self.measurement_set.find_slot_by_index(slot_index)
        if not slot:
            return

        # 이미지 뷰어 업데이트
        self.manual_image_viewer.load_image(slot.image_path)

        # 입력값 복원
        if slot.frequency is not None:
            self.manual_freq_input.setValue(slot.frequency)
        else:
            self.manual_freq_input.setValue(0)

        if slot.drive is not None:
            self.manual_drive_input.setValue(slot.drive)
        else:
            self.manual_drive_input.setValue(0)

        if slot.q_factor is not None:
            self.manual_q_input.setValue(slot.q_factor)
        else:
            self.manual_q_input.setValue(0)

        # QR 입력 대상
        probe = slot.probe_type or "?"
        self.qr_input.set_target_label(f"#{slot_index + 1} ({probe})")

    def _on_manual_card_removed(self, slot_index: int):
        # SlotData 제거
        self.measurement_set.slots = [
            s for s in self.measurement_set.slots
            if s.slot_index != slot_index
        ]

        # 카드 제거
        for grid in self._manual_grids.values():
            if slot_index in grid._cards:
                grid.remove_card(slot_index)
                break

        if self.selected_manual_index == slot_index:
            self.selected_manual_index = -1
            self.manual_image_viewer.clear()

        self.logger.info(f"카드 #{slot_index + 1} 삭제됨")
        self._refresh_overview()
        self._update_progress()

    # ─── 데이터 입력 ───

    def _apply_manual_entry(self):
        if self.selected_manual_index < 0:
            self.logger.warn("카드를 먼저 선택하세요")
            return

        slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
        if not slot:
            return

        freq = self.manual_freq_input.value()
        drive = self.manual_drive_input.value()
        q = self.manual_q_input.value()

        if freq <= 0 or q <= 0:
            self.logger.warn("Frequency와 Q 값을 입력하세요")
            return

        slot.frequency = freq
        slot.drive = drive  # 0도 유효값
        slot.q_factor = q

        # 카드 업데이트
        for grid in self._manual_grids.values():
            if self.selected_manual_index in grid._cards:
                grid.update_card(
                    self.selected_manual_index,
                    frequency=freq, q_factor=q, drive=drive, qr_id=slot.qr_id,
                )
                break

        probe = slot.probe_type or "?"
        self.logger.ok(
            f"#{slot.slot_index + 1} ({probe}): "
            f"Freq={round(freq)} KHz, Drive={round(drive, 1)}%, Q={round(q)}"
        )

        self._refresh_overview()
        self._update_progress()

        # 현재 탭에서 다음 미입력 카드로 이동
        self._advance_to_next_empty()

    def _advance_to_next_empty(self):
        """현재 탭에서 다음 측정값 미입력 카드로 이동."""
        current_tab_idx = self.manual_tabs.currentIndex()
        if current_tab_idx >= self.manual_tabs.count() - 1:
            return  # 전체 현황 탭

        probe_type = self.manual_tabs.tabText(current_tab_idx)
        grid = self._manual_grids.get(probe_type)
        if not grid:
            return

        for idx in grid.get_slot_indices():
            if idx == self.selected_manual_index:
                continue
            slot = self.measurement_set.find_slot_by_index(idx)
            if slot and slot.frequency is None:
                self._on_manual_card_selected(idx)
                return

    # ─── 전체 현황 ───

    def _refresh_overview(self):
        if not hasattr(self, '_overview_layout'):
            return

        # 기존 내용 삭제
        while self._overview_layout.count():
            item = self._overview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total_all = 0
        complete_all = 0

        for probe_type, grid in self._manual_grids.items():
            indices = grid.get_slot_indices()
            total = len(indices)
            complete = 0
            for idx in indices:
                slot = self.measurement_set.find_slot_by_index(idx)
                if slot and slot.is_complete:
                    complete += 1

            total_all += total
            complete_all += complete

            from PySide6.QtWidgets import QLabel
            from src.ui.theme import GREEN, ORANGE, FG, ACCENT

            status = "Done" if complete == total and total > 0 else "In Progress"
            color = GREEN if status == "Done" else ORANGE
            lbl = QLabel(f"  {probe_type}: {complete}/{total} {status}")
            lbl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
            self._overview_layout.addWidget(lbl)

        # 전체 요약
        from PySide6.QtWidgets import QLabel, QFrame
        from src.ui.theme import BG3, ACCENT

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {BG3};")
        self._overview_layout.addWidget(line)

        pct = round(complete_all / total_all * 100) if total_all > 0 else 0
        summary = QLabel(f"  Total: {complete_all}/{total_all} ({pct}%)")
        summary.setStyleSheet(f"color: {ACCENT}; font-size: 15px; font-weight: bold;")
        self._overview_layout.addWidget(summary)
        self._overview_layout.addStretch()

    # ─── 초기화 ───

    def _reset_manual_all(self):
        """모든 탭/카드/데이터를 초기화."""
        if not self._manual_grids:
            return

        reply = QMessageBox.question(
            self,
            "초기화",
            "모든 탭과 데이터를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 모든 Probe Type 탭 제거 (전체 현황 탭 제외)
        for grid in self._manual_grids.values():
            grid.deleteLater()
        self._manual_grids.clear()

        while self.manual_tabs.count() > 1:
            self.manual_tabs.removeTab(0)

        # 상태 리셋
        self._manual_slot_counter = 0
        self.selected_manual_index = -1
        self.measurement_set = MeasurementSet(mode="manual")

        # UI 리셋
        self.manual_image_viewer.clear()
        self.manual_freq_input.setValue(0)
        self.manual_drive_input.setValue(0)
        self.manual_q_input.setValue(0)

        self._refresh_overview()
        self._update_progress()
        self.logger.section("수동 모드 초기화")
        self.logger.ok("모든 데이터가 초기화되었습니다")

    # ─── 열 수 변경 ───

    def _on_manual_columns_changed(self, n: int):
        for grid in self._manual_grids.values():
            grid.set_columns(n)
