"""ATX 폴더 로드 워크플로우 — Browse 다중 선택 + 폴더별 탭 관리."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QDialog, QWidget, QVBoxLayout

from src.core.atx_parser import load_atx_folder
from src.core.slot_mapper import circled_number, format_full_label
from src.ui.dialogs.slot_edit_dialog import SlotEditDialog
from src.ui.widgets.slot_grid_widget import SlotGridWidget


class ATXImportMixin:
    # ─── Browse (단일/다중 폴더) ───

    def _browse_atx_folder(self):
        # 네이티브 윈도우 탐색기로 상위 폴더 하나 선택 → 하위 ATX 폴더 자동 스캔
        parent = QFileDialog.getExistingDirectory(
            self, "ATX 폴더(또는 폴더들이 담긴 상위 폴더) 선택"
        )
        if not parent:
            return

        folders = self._scan_atx_folders(parent)
        if not folders:
            self.logger.warn(f"ATX 결과 폴더(Summary.csv 보유)를 찾지 못했습니다: {parent}")
            self._statusbar.showMessage("ATX 결과 폴더를 찾지 못했습니다")
            return

        self.logger.section("ATX 폴더 로드")
        opened = []
        for folder in folders:
            self.logger.info(f"폴더: {folder}")
            try:
                ms = load_atx_folder(folder)
            except Exception as e:
                self.logger.error(f"폴더 파싱 실패: {e}")
                continue
            self._atx_open_set_in_tab(ms, folder)
            self._add_recent_folder(folder)
            opened.append(ms)

        if opened:
            msg = (f"ATX 폴더 {len(opened)}개 로드 완료" if len(opened) > 1
                   else f"ATX 폴더 로드 완료: {opened[0].po_number}")
            self._statusbar.showMessage(msg)

    @staticmethod
    def _scan_atx_folders(parent: str) -> list[str]:
        """선택 폴더가 ATX 폴더면 그것만, 아니면 하위의 ATX 폴더(Summary.csv 보유)들을 반환."""
        p = Path(parent)
        if (p / "Summary.csv").exists():
            return [str(p)]
        try:
            children = sorted(p.iterdir(), key=lambda c: c.name)
        except OSError:
            return []
        return [str(c) for c in children if c.is_dir() and (c / "Summary.csv").exists()]

    # ─── 폴더 탭 관리 ───

    def _atx_open_set_in_tab(self, ms, folder: str, persist: bool = True):
        """폴더 set 을 탭으로 연다(이미 있으면 교체). persist=False 면 DB 재저장/일자 스탬프 생략."""
        ms.source_folder = ms.source_folder or folder
        if not ms.production_date:
            ms.production_date = self.date_edit.date().toString("yyyyMMdd")

        rec = next((r for r in self._folder_tabs if r["folder"] == folder), None)
        if rec is not None:
            rec["set"] = ms
            rec["grid"].load_measurement_set(ms)
        else:
            grid = SlotGridWidget()
            grid.slot_clicked.connect(self._on_slot_selected)
            grid.slot_reset_qr.connect(self._on_slot_reset_qr)
            grid.slot_edit_requested.connect(self._open_atx_slot_edit_dialog)
            grid.load_measurement_set(ms)

            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(4, 4, 4, 4)
            lay.addWidget(grid, 1)

            rec = {"folder": folder, "set": ms, "grid": grid, "page": page}
            self._folder_tabs.append(rec)
            self.atx_view_tabs.addTab(page, "")

        self._atx_refresh_tab_labels()

        if persist:
            try:
                ms.db_id = self._auto_save_to_db(ms)
            except Exception as e:
                self.logger.error(f"DB 저장 실패 (화면 데이터는 유지됨): {e}")

        self.logger.ok(f"{ms.po_number}: {len(ms.slots)}개 슬롯 로드")

        # Pass Pool 데이터/배지 갱신 (뷰 자체는 폴더 뷰로 유지)
        self._pool_refresh_view()

        # 새 폴더는 폴더 뷰로 표시 (Pass Pool 토글 해제 → 스택 폴더 페이지)
        if getattr(self, "btn_pass_pool", None) is not None:
            self.btn_pass_pool.setChecked(False)
        if getattr(self, "atx_content_stack", None) is not None:
            self.atx_content_stack.setCurrentWidget(self.atx_view_tabs)
        self.atx_view_tabs.setCurrentWidget(rec["page"])
        # 단일 탭 등 currentChanged 미발화 케이스 대비 명시적 리바인딩
        self._on_atx_view_changed(self.atx_view_tabs.currentIndex())

    def _atx_folder_sets(self) -> list:
        return [r["set"] for r in self._folder_tabs]

    def _atx_refresh_tab_labels(self):
        # 폴더 순번(①②③) 프리픽스 — Pass Pool 카드/칩 번호와 통일(위치 기준, 재정렬 시 재부여)
        for num, r in enumerate(self._folder_tabs, start=1):
            idx = self.atx_view_tabs.indexOf(r["page"])
            if idx < 0:
                continue
            s = r["set"]
            self.atx_view_tabs.setTabText(
                idx, f"{circled_number(num)} {s.po_number} {s.matched_count}/{s.total_count}"
            )
        # 폴더 뷰에서 매칭해도 Pass Pool 배지가 최신이 되도록 pass 맵 재계산 후 갱신
        if hasattr(self, "_pool_pass_items"):
            self._pool_pass_items()
            self._update_pool_button()

    def _on_atx_tab_moved(self, _from_idx: int, _to_idx: int):
        """폴더 탭 드래그 재정렬 → _folder_tabs 를 시각 순서에 동기화하고 파생 뷰를 갱신."""
        # 칩 재정렬이 탭을 프로그램적으로 옮기는 중이면 무시(QTabWidget 의 페이지 동기화는 유지)
        if getattr(self, "_suppress_tab_moved", False):
            return
        order = []
        for i in range(self.atx_view_tabs.count()):
            page = self.atx_view_tabs.widget(i)
            rec = next((r for r in self._folder_tabs if r["page"] is page), None)
            if rec is not None:
                order.append(rec)
        if len(order) != len(self._folder_tabs):
            self.logger.warn("탭 순서 동기화 불일치 — 재정렬을 건너뜁니다")
            return
        self._folder_tabs = order
        self._after_folder_reorder()

    def _on_pool_folders_reordered(self, keys: list):
        """Pass Pool 폴더 칩 드래그 재정렬 → keys(현재 _folder_tabs 인덱스 'set{i}' 시각 순서)대로
        _folder_tabs 와 폴더 탭줄을 함께 재배열한 뒤 파생 뷰를 갱신한다."""
        try:
            new_order = [self._folder_tabs[int(k[3:])] for k in keys]
        except (ValueError, IndexError):
            new_order = []
        if len(new_order) != len(self._folder_tabs):
            self.logger.warn("Pool 폴더 순서 동기화 불일치 — 재정렬을 건너뜁니다")
            return
        self._folder_tabs = new_order
        # 폴더 탭줄을 같은 순서로 물리 이동. blockSignals 대신 가드 플래그를 쓰는 이유:
        # QTabWidget 은 tabBar().tabMoved 로 내부 페이지 순서를 동기화하므로 시그널을
        # 막으면 widget(i) 가 옛 순서로 남는다. 우리 핸들러만 no-op 시킨다.
        self._suppress_tab_moved = True
        try:
            for target, rec in enumerate(new_order):
                cur = self.atx_view_tabs.indexOf(rec["page"])
                if cur != -1 and cur != target:
                    self.atx_view_tabs.tabBar().moveTab(cur, target)
        finally:
            self._suppress_tab_moved = False
        self._after_folder_reorder()

    def _after_folder_reorder(self):
        """폴더 순서 변경 후 공통 갱신 — 위치 종속 선택 초기화 + 탭 번호·Pool·Export 재계산."""
        # 탭 순번(①②③) 실시간 재부여
        self._atx_refresh_tab_labels()
        # Pass Pool 키는 set_idx 기반(위치 종속) → 재정렬 시 무효화되므로 캐리어 선택 초기화
        if hasattr(self, "_pool_checked_keys"):
            self._pool_checked_keys.clear()
        self._pool_refresh_view()
        self._update_pool_button()
        if hasattr(self, "_populate_export_scope_combo"):
            self._populate_export_scope_combo()

    def _on_atx_view_changed(self, index: int):
        # 구성/상태 초기화 완료 전 조기 발화 방지
        if not hasattr(self, "progress_bar") or not hasattr(self, "_folder_tabs"):
            return
        w = self.atx_view_tabs.widget(index)
        rec = next((r for r in self._folder_tabs if r["page"] is w), None)
        if rec is None:
            return
        ms = rec["set"]
        self.slot_grid = rec["grid"]
        self.measurement_sets["atx"] = ms
        self.selected_slot_index = 0
        self.atx_folder_input.setText(rec["folder"])
        self.lbl_po.setText(ms.po_number)
        self.lbl_probe_type.setText(ms.probe_type)
        self.lbl_quantity.setText(f"{ms.quantity}M ({len(ms.slots)}개 슬롯)")
        self._update_progress()
        if ms.slots:
            self._on_slot_selected(ms.slots[0].slot_index)

    def _on_atx_tab_close(self, index: int):
        w = self.atx_view_tabs.widget(index)
        rec = next((r for r in self._folder_tabs if r["page"] is w), None)
        if rec is None:
            return
        self._folder_tabs.remove(rec)
        self.atx_view_tabs.removeTab(index)
        rec["page"].deleteLater()
        self.logger.info(f"폴더 탭 제거: {rec['set'].po_number}")

        if not self._folder_tabs:
            self.slot_grid = self._atx_dummy_grid
            self.measurement_sets["atx"] = None
            self.atx_folder_input.clear()
            self.lbl_po.setText("-")
            self.lbl_probe_type.setText("-")
            self.lbl_quantity.setText("-")
        # 폴더 닫힘은 뒤 폴더들의 set_idx 를 밀어 Pass Pool 키를 무효화 → 캐리어 선택 초기화
        if hasattr(self, "_pool_checked_keys"):
            self._pool_checked_keys.clear()
        self._pool_refresh_view()
        self._update_pool_button()

    # ─── 슬롯 선택/편집 (활성 폴더 탭 기준) ───

    def _on_slot_selected(self, slot_index: int):
        self.selected_slot_index = slot_index
        self.slot_grid.select_slot(slot_index)

        if not self.measurement_set:
            return

        slot = self.measurement_set.find_slot_by_index(slot_index)
        if not slot:
            return

        # 이미지 표시 + GroupBox 타이틀 업데이트
        label = format_full_label(slot.slot_code)
        self.atx_img_group.setTitle(f"FreqSweep 이미지 — {label}")
        self.atx_image_viewer.load_image(slot.image_path)

        # QR 입력 대상
        self.qr_input.set_target_label(label)

        self.logger.info(
            f"{label} 선택 — Freq: {slot.format_frequency()}, Q: {slot.format_q()}"
        )

    def _open_atx_slot_edit_dialog(self, slot_index: int):
        """Open the ATX slot edit dialog from the card context menu."""
        if not self.measurement_set:
            self.logger.warn("수정할 ATX 데이터가 없습니다")
            return

        slot = self.measurement_set.find_slot_by_index(slot_index)
        if not slot:
            self.logger.warn("수정할 슬롯을 선택하세요")
            return

        self._on_slot_selected(slot_index)
        dialog_slot = replace(
            slot,
            probe_type=slot.probe_type or self.measurement_set.probe_type or None,
        )
        dlg = SlotEditDialog(dialog_slot, parent=self)

        while dlg.exec() == QDialog.Accepted:
            updated = dlg.result_data()
            qr_id = updated.qr_id
            if qr_id and self._has_duplicate_qr(slot.slot_index, qr_id):
                self.qr_input.show_error(f"중복 QR: {qr_id}")
                self.qr_input.focus_input()
                dlg.focus_qr_input()
                continue

            slot.probe_type = updated.probe_type
            slot.frequency = updated.frequency
            slot.q_factor = updated.q_factor
            slot.qr_id = updated.qr_id
            slot.source = updated.source

            self.slot_grid.update_slot(slot)
            self._on_slot_selected(slot.slot_index)
            self._update_progress()
            self._atx_refresh_tab_labels()
            self._auto_save_to_db()

            self.logger.ok(f"슬롯 수정 완료: {dlg.slot_label.text()}")
            return

    def _has_duplicate_qr(self, slot_index: int, qr_id: str) -> bool:
        if not self.measurement_set:
            return False

        for other in self.measurement_set.slots:
            if other.slot_index != slot_index and other.qr_id == qr_id:
                return True
        return False
