"""Pass Pool 워크플로우 — 로드된 폴더 탭들의 규격(Spec) 통과 슬롯을 폴더명 섹션으로
묶어 모아 보고(ATX Mode 우측 Pass Pool 탭), 각 pass 카드에 하단 QR 바로 직접 QR을
태깅한다.

pass 기준: frequency·q_factor 가 모두 존재하고 ``quality.evaluate_slot`` 을 통과.
규격 미설정 probe 는 측정값만 있으면 통과(quality 정책과 동일).

Port 번호는 (폴더 로드순 → 폴더 내 ATX·Port 오름차순)으로 1,2,3,4… 연속 부여한다.
QR 태깅은 카드의 원본 슬롯/세트에 기록되고 원본 세트가 즉시 DB 저장된다.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.csv_exporter import export_csv
from src.core.models import MeasurementSet, SlotData
from src.core.quality import evaluate_slot
from src.core.slot_mapper import circled_number, parse_slot_code
from src.ui.theme import CHART_CYCLE

CARRIER_SLOTS = 12


class PassPoolMixin:
    def _init_pool_state(self):
        # 폴더 탭 레코드: [{folder, set, grid, page}, ...] (ATXImportMixin 이 채움)
        self._folder_tabs: list[dict] = []
        self._pool_item_map: dict[str, tuple] = {}
        self._pool_display: dict[str, str] = {}   # key → 연속 Port 표시 라벨
        self._pool_folders: list[dict] = []       # 칩 스트립 범례/재정렬용 (폴더 탭 순서)
        self._pool_selected_key: str | None = None
        self._pool_checked_keys: set[str] = set()  # 캐리어(12) 조립 선택

    # ─── pass 필터 (폴더 섹션 + 연속 Port) ───

    def _pool_pass_items(self) -> list[dict]:
        """규격 통과 슬롯 → 단일 연속 스택용 flat 아이템 리스트.
        전 폴더에 걸쳐 연속 Port(gport)를 부여하고 (-gport, snum) 로 정렬한다
        (맨 위 = 높은 Port, 맨 아래 = Port1). 각 아이템에 출처(PO) 색을 실어 폴더를 구분한다."""
        spec_limits = self._load_spec_limits()
        self._pool_item_map = {}
        self._pool_display = {}
        sets = self._atx_folder_sets()

        # 칩 스트립 범례/재정렬용 폴더 목록(폴더 탭 순서) — 순번(①②③) 포함
        self._pool_folders = [
            {"key": f"set{idx}", "po": ms.po_number,
             "color": CHART_CYCLE[idx % len(CHART_CYCLE)],
             "number": circled_number(idx + 1)}
            for idx, ms in enumerate(sets)
        ]

        raw: list[dict] = []
        for set_idx, ms in enumerate(sets):
            for slot in ms.slots:
                if slot.frequency is None or slot.q_factor is None:
                    continue
                probe = slot.probe_type or ms.probe_type or ""
                if not evaluate_slot(slot.frequency, slot.q_factor, spec_limits.get(probe)):
                    continue
                try:
                    info = parse_slot_code(slot.slot_code)
                    atx, port, snum, parsed = info["atx"], info["port"], info["slot"], True
                except (ValueError, IndexError):
                    atx, port, snum, parsed = 0, 0, slot.slot_index + 1, False
                key = f"{set_idx}:{slot.slot_index}"
                raw.append({
                    "key": key, "set_idx": set_idx, "ms": ms, "slot": slot,
                    "atx": atx, "port": port, "snum": snum, "parsed": parsed,
                })
                self._pool_item_map[key] = (ms, slot)

        # (폴더, ATX, Port) 그룹에 연속 Port 번호 부여
        groups = sorted({(r["set_idx"], r["atx"], r["port"]) for r in raw})
        gport = {g: i + 1 for i, g in enumerate(groups)}
        for r in raw:
            r["gport"] = gport[(r["set_idx"], r["atx"], r["port"])]

        # ATX 슬롯 그리드와 동일하게 Port 내림차순(→ 맨 아래가 Port1), 포트 내부는 Slot 오름차순.
        raw.sort(key=lambda r: (-r["gport"], r["snum"]))

        items: list[dict] = []
        for r in raw:
            slot, ms = r["slot"], r["ms"]
            if r["parsed"]:
                header = f"Port{r['gport']} Slot{r['snum']}"
                full = f"ATX{r['atx']} Port{r['port']} Slot{r['snum']}"
            else:
                header = f"#{slot.slot_index + 1}"
                full = header
            self._pool_display[r["key"]] = header
            items.append({
                "key": r["key"],
                "header": header,
                "tooltip": f"{ms.po_number} · {full} · {ms.probe_type}",
                "frequency": slot.frequency,
                "q_factor": slot.q_factor,
                "qr_id": slot.qr_id,
                "slot_code": slot.slot_code,
                "origin": ms.po_number,
                "origin_color": CHART_CYCLE[r["set_idx"] % len(CHART_CYCLE)],
                "origin_number": circled_number(r["set_idx"] + 1),
            })
        return items

    def _pool_refresh_view(self):
        items = self._pool_pass_items()
        if self._pool_selected_key not in self._pool_item_map:
            self._pool_selected_key = None
        self.pool_widget.set_passes(items)
        strip = getattr(self, "pool_folder_strip", None)
        if strip is not None:
            strip.set_folders(self._pool_folders)
        if self._pool_selected_key is not None:
            self.pool_widget.select(self._pool_selected_key)
        # 캐리어 선택 상태 재동기화(사라진 키 정리 → 카드 재적용 → 카운트)
        self._pool_checked_keys &= set(self._pool_item_map.keys())
        self.pool_widget.apply_checks(self._pool_checked_keys)
        self.pool_widget.set_selection_count(len(self._pool_checked_keys))
        self._pool_update_progress()

    @staticmethod
    def _pool_labels(slot: SlotData) -> tuple[str, str]:
        """(카드 헤더 폴백, 전체 라벨) 반환."""
        try:
            info = parse_slot_code(slot.slot_code)
            header = f"Port{info['port']} Slot{info['slot']}"
            full = f"ATX{info['atx']} Port{info['port']} Slot{info['slot']}"
        except (ValueError, IndexError):
            header = full = f"#{slot.slot_index + 1}"
        return header, full

    # ─── 카드 선택 (하단 QR 바 대상 지정) ───

    def _pool_on_card_clicked(self, key: str):
        entry = self._pool_item_map.get(key)
        if entry is None:
            return
        ms, slot = entry
        self._pool_selected_key = key
        self.pool_widget.select(key)

        label = self._pool_display.get(key) or self._pool_labels(slot)[1]
        self.atx_img_group.setTitle(f"FreqSweep 이미지 — {ms.po_number} {label}")
        self.atx_image_viewer.load_image(slot.image_path)
        self.qr_input.set_target_label(label)

    # ─── 캐리어(12) 명시적 선택 조립 ───

    def _pool_on_card_checked(self, key: str, checked: bool):
        """카드 체크 → 캐리어 선택 집합 갱신(상한 12 강제)."""
        if checked and key not in self._pool_checked_keys:
            if len(self._pool_checked_keys) >= CARRIER_SLOTS:
                # 초과 체크 되돌림 + 경고
                self.pool_widget.apply_checks(self._pool_checked_keys)
                self.qr_input.show_error(f"캐리어는 최대 {CARRIER_SLOTS}개입니다")
            else:
                self._pool_checked_keys.add(key)
        elif not checked:
            self._pool_checked_keys.discard(key)
        self.pool_widget.set_selection_count(len(self._pool_checked_keys))

    def _pool_clear_selection(self):
        self._pool_checked_keys.clear()
        self.pool_widget.apply_checks(set())
        self.pool_widget.set_selection_count(0)

    def _pool_assemble_carrier(self):
        """체크된 pass 슬롯을 한 장의 캐리어 CSV로 내보낸다(선택 순서=Pool 순서)."""
        keys = [k for k in self.pool_widget.order if k in self._pool_checked_keys]
        if not keys:
            self.qr_input.show_error("캐리어에 넣을 pass 슬롯을 선택하세요")
            return

        carrier = MeasurementSet(
            mode="atx",
            production_date=self.date_edit.date().toString("yyyyMMdd"),
            po_number="carrier",
            probe_type="",
        )
        for i, key in enumerate(keys):
            ms, slot = self._pool_item_map[key]
            carrier.slots.append(
                replace(slot, slot_index=i, probe_type=(slot.probe_type or ms.probe_type or None))
            )

        if len(keys) < CARRIER_SLOTS:
            resp = QMessageBox.question(
                self, "부분 캐리어",
                f"선택 {len(keys)}개 ({CARRIER_SLOTS} 미만)입니다. 부분 캐리어로 내보낼까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if resp != QMessageBox.Yes:
                return

        # 미완성(QR 미태깅) 처리 정책 + 행 존재 확인 (Export 경로 재사용)
        policy = self._choose_incomplete_export_policy(
            carrier, "QR 있는 값만 반출", "전체 슬롯 반출"
        )
        if policy is None:
            return
        if not self._has_export_rows(carrier, policy):
            self.qr_input.show_error("내보낼 데이터가 없습니다 (QR 매칭된 슬롯 없음)")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "캐리어 CSV 저장", "carrier_QR.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".csv":
            out = out.with_suffix(".csv")
        try:
            export_csv(carrier, str(out), policy)
            self.logger.ok(f"캐리어 CSV 저장: {out} (슬롯 {len(keys)}개)")
            self._statusbar.showMessage(f"캐리어 CSV 저장: {out}")
        except Exception as e:
            self.logger.error(f"캐리어 CSV 저장 실패: {e}")

    # ─── Pass Pool 진입 토글 (상단 스트립) ───

    def _on_pass_pool_toggled(self, checked: bool):
        """상단 [Pass Pool] 토글 → 콘텐츠 스택을 폴더 뷰 ↔ Pass Pool 로 전환."""
        stack = getattr(self, "atx_content_stack", None)
        if stack is None:
            return
        if checked:
            self._pool_refresh_view()
            stack.setCurrentWidget(self._pool_page)
            if self._pool_selected_key and self._pool_selected_key in self._pool_item_map:
                self._pool_on_card_clicked(self._pool_selected_key)
            self._pool_update_progress()
        else:
            stack.setCurrentWidget(self.atx_view_tabs)
            idx = self.atx_view_tabs.currentIndex()
            if idx >= 0:
                self._on_atx_view_changed(idx)
            else:
                self._update_progress()
        self._update_pool_button()

    def _update_pool_button(self):
        """토글 버튼 라벨을 현재 pass 매칭 수(matched/total)로 갱신."""
        btn = getattr(self, "btn_pass_pool", None)
        if btn is None:
            return
        total = len(self._pool_item_map)
        matched = sum(1 for _ms, s in self._pool_item_map.values() if s.qr_id is not None)
        btn.setText(f"🎯 Pass Pool {matched}/{total}")

    # ─── QR 직접 태깅 ───

    def _atx_pool_active(self) -> bool:
        btn = getattr(self, "btn_pass_pool", None)
        return btn is not None and btn.isChecked()

    def _pool_on_qr_scanned(self, qr_id: str):
        key = self._pool_selected_key
        if key is None or key not in self._pool_item_map:
            self.qr_input.show_error("pass 카드를 먼저 선택하세요")
            self.qr_input.focus_input()
            return

        # 로드된 폴더 전체에 대한 QR 중복 검사
        for ms in self._atx_folder_sets():
            for slot in ms.slots:
                if slot.qr_id == qr_id:
                    self.qr_input.show_error(f"중복 QR: {qr_id}")
                    self.qr_input.focus_input()
                    return

        ms, slot = self._pool_item_map[key]
        label = self._pool_display.get(key) or self._pool_labels(slot)[1]
        if slot.qr_id:
            self.qr_input.show_error(f"{label}에 이미 QR이 있습니다")
            self.qr_input.focus_input()
            return

        slot.qr_id = qr_id
        self.pool_widget.update_card(
            key, frequency=slot.frequency, q_factor=slot.q_factor, qr_id=qr_id
        )
        self.qr_input.show_success(f"{label} ← {qr_id}")
        self.logger.ok(f"QR 매칭(Pool): {label} = {qr_id}")

        # 원본 세트 저장 (source_folder 로 중복 감지 → 이후 UPDATE 고정)
        try:
            ms.db_id = self._auto_save_to_db(ms)
        except Exception as e:
            self.logger.error(f"DB 저장 실패 (화면 데이터는 유지됨): {e}")

        self._atx_refresh_tab_labels()   # 폴더 탭 matched/total 동기화
        self._pool_update_progress()

        next_key = self._pool_next_unmatched(key)
        if next_key is not None:
            self._pool_on_card_clicked(next_key)
        else:
            self.logger.ok("모든 pass 슬롯 QR 매칭 완료!")
        self.qr_input.focus_input()

    def _pool_next_unmatched(self, after_key: str) -> str | None:
        """after_key 다음부터(순환) 첫 미매칭 pass 카드 key."""
        order = self.pool_widget.order
        if not order:
            return None
        try:
            start = order.index(after_key)
        except ValueError:
            start = -1
        n = len(order)
        for step in range(1, n + 1):
            key = order[(start + step) % n]
            entry = self._pool_item_map.get(key)
            if entry and entry[1].qr_id is None:
                return key
        return None

    def _pool_update_progress(self):
        total = len(self._pool_item_map)
        matched = sum(1 for _ms, slot in self._pool_item_map.values() if slot.qr_id is not None)

        self._update_pool_button()

        if total == 0:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self._statusbar.showMessage("Pass Pool 매칭: 0/0")
            return

        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(matched)
        if matched == total:
            self._statusbar.showMessage(f"Pass Pool: 모든 {total}개 pass 매칭 완료!")
        else:
            self._statusbar.showMessage(f"Pass Pool 매칭: {matched}/{total}")
