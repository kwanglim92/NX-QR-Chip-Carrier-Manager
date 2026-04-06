"""QR 바코드 스캔 + 슬롯 매칭."""
from __future__ import annotations

from src.core.slot_mapper import format_full_label


class QRMatchMixin:
    def _on_qr_scanned(self, qr_id: str):
        if not self.measurement_set:
            self.qr_input.show_error("먼저 폴더를 로드하세요")
            return

        # 중복 체크
        for slot in self.measurement_set.slots:
            if slot.qr_id == qr_id:
                try:
                    dup_label = format_full_label(slot.slot_code)
                except (ValueError, IndexError):
                    dup_label = f"#{slot.slot_index + 1}"
                self.qr_input.show_error(f"중복 QR: {qr_id} ({dup_label})")
                self.qr_input.focus_input()
                return

        # 현재 모드에 따라 매칭
        if self.current_mode == "atx":
            self._match_qr_atx(qr_id)
        elif self.current_mode == "manual":
            self._match_qr_manual(qr_id)

        self._update_progress()
        self.qr_input.focus_input()

    def _match_qr_atx(self, qr_id: str):
        slot = self.measurement_set.find_slot_by_index(self.selected_slot_index)
        if not slot:
            self.qr_input.show_error("슬롯을 선택하세요")
            return

        label = format_full_label(slot.slot_code)

        if slot.qr_id:
            self.qr_input.show_error(f"{label}에 이미 QR이 있습니다")
            return

        slot.qr_id = qr_id
        self.slot_grid.update_slot(slot)
        self.qr_input.show_success(f"{label} ← {qr_id}")
        self.logger.ok(f"QR 매칭: {label} = {qr_id}")

        # 다음 미매칭 슬롯으로 자동 이동
        unmatched = self.measurement_set.get_unmatched_slots()
        if unmatched:
            self._on_slot_selected(unmatched[0].slot_index)
        else:
            self.logger.ok("모든 슬롯 QR 매칭 완료!")

    def _match_qr_manual(self, qr_id: str):
        idx = self.selected_manual_index
        if idx < 0:
            self.qr_input.show_error("카드를 먼저 선택하세요")
            return

        slot = self.measurement_set.find_slot_by_index(idx)
        if not slot:
            return

        if slot.qr_id:
            self.qr_input.show_error(f"#{idx + 1}에 이미 QR이 있습니다")
            return

        slot.qr_id = qr_id

        # 카드 업데이트
        for grid in self._manual_grids.values():
            if idx in grid._cards:
                grid.update_card(
                    idx,
                    frequency=slot.frequency,
                    q_factor=slot.q_factor,
                    drive=slot.drive,
                    qr_id=qr_id,
                )
                break

        probe = slot.probe_type or "?"
        self.qr_input.show_success(f"#{idx + 1} ({probe}) ← {qr_id}")
        self.logger.ok(f"QR 매칭: #{idx + 1} ({probe}) = {qr_id}")

        self._refresh_overview()

        # 현재 탭 내 다음 미매칭 카드로 자동 이동
        current_tab_idx = self.manual_tabs.currentIndex()
        if current_tab_idx < self.manual_tabs.count() - 1:
            probe_type = self.manual_tabs.tabText(current_tab_idx)
            grid = self._manual_grids.get(probe_type)
            if grid:
                for s_idx in grid.get_slot_indices():
                    if s_idx == idx:
                        continue
                    s = self.measurement_set.find_slot_by_index(s_idx)
                    if s and s.qr_id is None:
                        self._on_manual_card_selected(s_idx)
                        return

                # 현재 탭 모두 매칭 완료
                self.logger.ok(f"'{probe_type}' 탭 QR 매칭 완료!")

    def _update_progress(self):
        if not self.measurement_set:
            self.progress_bar.setMaximum(0)
            self.progress_bar.setValue(0)
            return

        total = self.measurement_set.total_count
        matched = self.measurement_set.matched_count
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(matched)

        if matched == total and total > 0:
            self._statusbar.showMessage(f"모든 {total}개 슬롯 매칭 완료!")
        else:
            self._statusbar.showMessage(f"매칭 진행: {matched}/{total}")
