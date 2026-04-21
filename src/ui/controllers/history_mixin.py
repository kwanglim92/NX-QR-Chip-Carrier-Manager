"""이력 조회/검색/로드/삭제 + 백업/복원 컨트롤러."""
from __future__ import annotations

from datetime import datetime

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.database import (
    list_measurement_sets, list_weeks, load_measurement_set,
    delete_measurement_set, export_db, import_db, get_connection, init_db,
    get_production_stats, get_overall_stats, get_period_totals,
    get_slot_values, get_period_quality_stats, get_probe_type_list,
)


class HistoryMixin:
    def _init_history_state(self):
        """이력 패널 초기화."""
        self._refresh_week_list()
        self.stats_dashboard.period_changed.connect(self._refresh_stats)
        self.stats_dashboard.probe_filter_changed.connect(self._refresh_stats)
        self._detail_ms = None  # 현재 상세 패널에 표시 중인 MeasurementSet

        # Probe Type 필터 초기화
        probe_types = get_probe_type_list(self._db_conn)
        self.stats_dashboard.set_probe_types(probe_types)

    # ─── 주차 목록 ───

    def _refresh_week_list(self):
        weeks = list_weeks(self._db_conn)
        self.history_week_combo.clear()
        self.history_week_combo.addItem("All")
        for w in weeks:
            self.history_week_combo.addItem(w)

    # ─── 이력 조회 ───

    def _refresh_history(self):
        week = self.history_week_combo.currentText()
        search = self.history_search_input.text().strip() or None

        records = list_measurement_sets(
            self._db_conn,
            week=week if week != "All" else None,
            search=search,
        )
        self.history_table.load_data(records)
        self._refresh_stats()

        # 주차 목록 갱신 (시그널 차단하여 재귀 방지)
        current_week = self.history_week_combo.currentText()
        self.history_week_combo.blockSignals(True)
        self._refresh_week_list()
        idx = self.history_week_combo.findText(current_week)
        if idx >= 0:
            self.history_week_combo.setCurrentIndex(idx)
        self.history_week_combo.blockSignals(False)

    def _refresh_stats(self):
        """통계 대시보드 갱신."""
        period = self.stats_dashboard.get_selected_period()
        probe_filter = self.stats_dashboard.get_selected_probe_type()

        stats = get_production_stats(self._db_conn, period=period)
        summary = get_overall_stats(self._db_conn)
        period_totals = get_period_totals(self._db_conn, period=period)
        quality_stats = get_period_quality_stats(
            self._db_conn, period=period, probe_type=probe_filter
        )
        slot_values = get_slot_values(self._db_conn, probe_type=probe_filter)

        self.stats_dashboard.load_stats(
            stats, summary, period_totals, quality_stats, slot_values
        )

        # Probe Type 목록 갱신
        probe_types = get_probe_type_list(self._db_conn)
        self.stats_dashboard.set_probe_types(probe_types)

    def _on_history_selection_changed(self, count: int):
        """체크 항목 수 표시."""
        if count > 0:
            self.lbl_selection_count.setText(f"{count} checked")
        else:
            self.lbl_selection_count.setText("")

    def _clear_detail_panel(self):
        """상세 패널 초기화."""
        self._detail_ms = None
        self.lbl_detail_info.setText("Select a record to view details")
        self.btn_open_folder.setEnabled(False)
        self.history_slot_table.setRowCount(0)
        self.history_image_viewer.clear()

    def _on_history_row_selected(self, ms_id: int):
        """PO 행 클릭 → 하단 상세 패널에 슬롯 표시."""
        ms = load_measurement_set(self._db_conn, ms_id)
        if not ms:
            return

        self._detail_ms = ms

        # 헤더 업데이트
        total = len(ms.slots)
        complete = sum(1 for s in ms.slots if s.is_complete)
        self.lbl_detail_info.setText(
            f"{ms.po_number}  |  {ms.probe_type}  |  "
            f"{ms.mode.upper()}  |  {complete}/{total} Slots"
        )

        # 폴더 열기 버튼 활성화
        has_folder = bool(ms.source_folder) or any(s.image_path for s in ms.slots)
        self.btn_open_folder.setEnabled(has_folder)

        # 슬롯 테이블 로드
        self.history_slot_table.load_slots(ms.slots, ms.probe_type)

        # 이미지 초기화
        self.history_image_viewer.clear()

    def _on_history_slot_selected(self, slot_index: int):
        """슬롯 행 클릭 → 이미지 미리보기."""
        if not self._detail_ms:
            return

        slot = self._detail_ms.find_slot_by_index(slot_index)
        if not slot:
            return

        if slot.image_path:
            self.history_image_viewer.load_image(slot.image_path)
        else:
            self.history_image_viewer.clear()

    def _on_open_source_folder(self):
        """소스 폴더 또는 이미지 폴더를 OS 탐색기로 열기."""
        if not self._detail_ms:
            return

        folder = None

        # ATX 모드: source_folder 우선
        if self._detail_ms.source_folder:
            p = Path(self._detail_ms.source_folder)
            if p.exists():
                folder = str(p)

        # source_folder 없으면 이미지 경로에서 폴더 추출
        if not folder:
            for slot in self._detail_ms.slots:
                if slot.image_path:
                    p = Path(slot.image_path).parent
                    if p.exists():
                        folder = str(p)
                        break

        if folder:
            os.startfile(folder)
        else:
            self.logger.warn("폴더를 찾을 수 없습니다")

    def _on_history_search(self):
        self._refresh_history()

    # ─── 레코드 로드 ───

    def _on_history_load(self):
        ms_id = self.history_table.get_selected_ms_id()
        if ms_id is None:
            self.logger.warn("이력에서 레코드를 선택하세요")
            return

        ms = load_measurement_set(self._db_conn, ms_id)
        if not ms:
            self.logger.error("레코드를 불러올 수 없습니다")
            return

        self.measurement_set = ms

        if ms.mode == "atx":
            self._load_atx_from_history(ms)
        else:
            self._load_manual_from_history(ms)

        self.logger.ok(f"이력 로드: {ms.po_number} ({ms.mode.upper()})")

    def _load_atx_from_history(self, ms):
        """ATX 이력 레코드를 UI에 로드."""
        self._switch_mode("atx")

        self.atx_folder_input.setText(ms.source_folder)
        self.lbl_po.setText(ms.po_number)
        self.lbl_probe_type.setText(ms.probe_type)
        self.lbl_quantity.setText(f"{ms.quantity}M ({len(ms.slots)}개 슬롯)")

        self.slot_grid.load_measurement_set(ms)
        self._update_progress()

        if ms.slots:
            self._on_slot_selected(0)

    def _load_manual_from_history(self, ms):
        """수동 이력 레코드를 UI에 로드."""
        self._switch_mode("manual")

        # 기존 탭 정리
        self._reset_manual_all_silent()

        # Probe Type별 그룹핑
        probe_groups: dict[str, list] = {}
        for slot in ms.slots:
            pt = slot.probe_type or "Unknown"
            if pt not in probe_groups:
                probe_groups[pt] = []
            probe_groups[pt].append(slot)

        # 탭 생성 + 카드 추가
        from src.ui.widgets.manual_card import ManualCard
        from src.ui.widgets.manual_grid_widget import ManualGridWidget

        self._manual_slot_counter = 0

        for probe_type, slots in probe_groups.items():
            grid = ManualGridWidget()
            grid.set_columns(self.manual_col_spin.value())
            grid.card_clicked.connect(self._on_manual_card_selected)
            grid.card_removed.connect(self._on_manual_card_removed)
            grid.images_dropped.connect(
                lambda paths, pt=probe_type: self._on_images_dropped(pt, paths)
            )

            self._manual_grids[probe_type] = grid

            overview_idx = self.manual_tabs.count() - 1
            self.manual_tabs.insertTab(overview_idx, grid, probe_type)

            for slot in slots:
                card = ManualCard(slot.slot_index, slot.image_path)
                card.update_data(
                    frequency=slot.frequency,
                    q_factor=slot.q_factor,
                    qr_id=slot.qr_id,
                )
                grid.add_card(card)

                if slot.slot_index >= self._manual_slot_counter:
                    self._manual_slot_counter = slot.slot_index + 1

        self._refresh_overview()
        self._update_progress()

        if ms.slots:
            self.manual_tabs.setCurrentIndex(0)
            self._on_manual_card_selected(ms.slots[0].slot_index)

    def _reset_manual_all_silent(self):
        """확인 다이얼로그 없이 수동 모드 리셋."""
        for grid in self._manual_grids.values():
            grid.deleteLater()
        self._manual_grids.clear()

        while self.manual_tabs.count() > 1:
            self.manual_tabs.removeTab(0)

        self._manual_slot_counter = 0
        self.selected_manual_index = -1

    # ─── 레코드 삭제 ───

    def _on_history_delete(self):
        ms_ids = self.history_table.get_checked_ms_ids()
        if not ms_ids:
            self.logger.warn("삭제할 레코드를 선택하세요")
            return

        count = len(ms_ids)
        msg = (f"선택한 {count}개 레코드를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."
               if count > 1
               else "선택한 레코드를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.")

        reply = QMessageBox.question(
            self,
            "Delete Record",
            msg,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for ms_id in ms_ids:
            delete_measurement_set(self._db_conn, ms_id)

            if self.measurement_set and self.measurement_set.db_id == ms_id:
                self.measurement_set.db_id = None

        self._refresh_history()
        self._clear_detail_panel()
        self.logger.info(f"{count}개 레코드 삭제됨")

    # ─── 백업 ───

    def _on_backup_db(self):
        default_name = f"chip_carrier_backup_{datetime.now().strftime('%Y%m%d')}.db"
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", default_name, "SQLite DB (*.db)"
        )
        if not path:
            return

        try:
            export_db(self._db_conn, path)
            self.logger.ok(f"DB 백업 완료: {path}")
        except Exception as e:
            self.logger.error(f"백업 실패: {e}")

    # ─── 복원 ───

    def _on_restore_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Restore Database", "", "SQLite DB (*.db)"
        )
        if not path:
            return

        reply = QMessageBox.question(
            self,
            "Restore Database",
            "현재 DB를 선택한 백업 파일로 교체하시겠습니까?\n"
            "기존 데이터는 덮어쓰기됩니다.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            # 현재 연결 닫기
            self._db_conn.close()

            success = import_db(path)
            if success:
                # 새 연결
                self._db_conn = get_connection()
                init_db(self._db_conn)
                self._refresh_history()
                self.logger.ok(f"DB 복원 완료: {path}")
            else:
                # 복원 실패 시 기존 DB 재연결
                self._db_conn = get_connection()
                init_db(self._db_conn)
                self.logger.error("유효하지 않은 DB 파일입니다")
        except Exception as e:
            self._db_conn = get_connection()
            init_db(self._db_conn)
            self.logger.error(f"복원 실패: {e}")
