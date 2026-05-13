"""수동 측정 워크플로우 — Probe Type 탭 + 드래그&드롭 카드 그리드."""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox, QFileDialog

from src.core.capture_files import (
    captures_root,
    derive_zoomout_path,
    final_capture_pair,
    final_capture_path,
    is_app_capture_path,
    is_zoomout_filename,
    next_pending_capture_pair,
    next_pending_capture_path,
    sanitize_capture_filename_part,
)
from src.core.manual_slot_order import renumber_manual_slots
from src.core.models import MeasurementSet, SlotData, truncate_measurement_value
from src.core.ocr_settings import (
    load_roi_for,
    save_roi_for,
    resolution_key,
)
from src.core.ocr_worker import OcrRunnable
from src.ui.dialogs.roi_calibrator import RoiCalibratorDialog
from src.ui.widgets.manual_card import ManualCard
from src.ui.widgets.manual_grid_widget import ManualGridWidget
from src.ui.widgets.screen_capture_overlay import ScreenCaptureOverlay

# Phase 7C: 동시 OCR 스레드 수 상한 (4개)
_OCR_MAX_THREADS = 4


class ManualImportMixin:
    def _init_manual_state(self):
        self._manual_slot_counter: int = 0
        self._manual_grids: dict[str, ManualGridWidget] = {}  # probe_type -> grid
        self.selected_manual_index: int = -1

        # MeasurementSet 초기화 (수동 모드)
        if not hasattr(self, 'measurement_set') or self.measurement_set is None:
            self.measurement_set = MeasurementSet(mode="manual")

        # Phase 7C: 비동기 OCR 파이프라인
        self._ocr_pool = QThreadPool()
        self._ocr_pool.setMaxThreadCount(_OCR_MAX_THREADS)
        # 배치별 추적: {batch_id: {"total", "done", "success", "probe_type", "unresolved_sizes"}}
        self._ocr_batches: dict[str, dict] = {}
        self._manual_ocr_active_slots: set[int] = set()
        self._manual_capture_rename_queue: dict[int, str] = {}

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

        self._prepare_manual_reorder()

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
        self._renumber_manual_slots()
        self.logger.info(f"'{probe_type}' 탭 삭제됨")
        self._refresh_overview()
        self._update_progress()
        # F-15: 삭제 연산도 DB에 즉시 반영 — 재시작 시 삭제된 슬롯 부활 방지
        self._auto_save_to_db()

    # ─── 이미지 불러오기 (파일/폴더 다이얼로그) ───

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}

    def _browse_manual_images(self):
        """현재 탭에 이미지를 파일 또는 폴더 다이얼로그로 불러오기."""
        if not self._manual_grids:
            QMessageBox.warning(self, "Warning", "Probe Type 탭을 먼저 추가하세요.")
            return

        idx = self.manual_tabs.currentIndex()
        if idx >= self.manual_tabs.count() - 1:
            QMessageBox.warning(self, "Warning", "Probe Type 탭을 선택하세요.")
            return

        probe_type = self.manual_tabs.tabText(idx)

        box = QMessageBox(self)
        box.setWindowTitle("이미지 불러오기")
        box.setText("불러올 방식을 선택하세요.")
        btn_files = box.addButton("파일 선택", QMessageBox.AcceptRole)
        btn_folder = box.addButton("폴더 선택", QMessageBox.AcceptRole)
        box.addButton("취소", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()

        if clicked is btn_files:
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                "이미지 파일 선택",
                "",
                "이미지 파일 (*.jpg *.jpeg *.png *.bmp);;모든 파일 (*)",
            )
            paths = self._filter_zoomin_only(paths)
        elif clicked is btn_folder:
            folder = QFileDialog.getExistingDirectory(self, "이미지 폴더 선택")
            if not folder:
                return
            paths = self._scan_folder_for_images(folder)
            if not paths:
                QMessageBox.information(
                    self, "알림", "선택한 폴더에서 Zoom-In 이미지 파일을 찾을 수 없습니다."
                )
                return
        else:
            return

        if paths:
            self._on_images_dropped(probe_type, paths)

    def _filter_zoomin_only(self, paths: list[str]) -> list[str]:
        """Drop zoom-out images (filename stem ends with ZOOMOUT_SUFFIX)."""
        from pathlib import Path

        kept: list[str] = []
        skipped = 0
        for p in paths:
            if is_zoomout_filename(Path(p).name):
                skipped += 1
                continue
            kept.append(p)
        if skipped:
            self.logger.info(
                f"Zoom-Out 이미지 {skipped}개 건너뜀 (파일명에 '`' 접미사)"
            )
        return kept

    def _scan_folder_for_images(self, folder: str) -> list[str]:
        """폴더 내 Zoom-In 이미지 파일을 이름순으로 반환 (하위 폴더 미포함)."""
        from pathlib import Path

        return sorted(
            str(p)
            for p in Path(folder).iterdir()
            if p.is_file()
            and p.suffix.lower() in self.IMAGE_EXTENSIONS
            and not is_zoomout_filename(p.name)
        )

    def _capture_manual_image(self, capture_mode: str = "region"):
        """Capture a Zoom-In screen region and add it to the active Manual tab.

        Zoom-Out is captured separately via :meth:`_capture_manual_image_zoomout`
        so the operator has time to switch the probe SW between zoom levels.
        """
        if getattr(self, "current_mode", None) != "manual":
            return

        probe_type = self._active_manual_probe_type()
        if probe_type is None:
            return

        production_date = self.date_edit.date().toString("yyyyMMdd")
        safe_probe = sanitize_capture_filename_part(probe_type, fallback="probe")
        capture_base = captures_root() / production_date / safe_probe
        # Reserve a matching counter on both subdirs so a later zoom-out capture
        # can land on the sibling path without colliding with another slot.
        zoomin_path, _zo_reserved = next_pending_capture_pair(capture_base)

        window_state = self.windowState()
        accepted = False
        error_msg: str | None = None
        saved_path: str | None = None

        self.hide()
        QApplication.processEvents()
        try:
            overlay = ScreenCaptureOverlay(
                capture_mode=capture_mode, label="Zoom-In"
            )
            accepted = overlay.exec() == QDialog.Accepted
            screen, rect = overlay.selected_region()
            overlay.deleteLater()
            QApplication.processEvents()

            if accepted and screen is not None and rect is not None:
                pixmap = screen.grabWindow(
                    0, rect.x(), rect.y(), rect.width(), rect.height()
                )
                if pixmap.isNull():
                    error_msg = "Zoom-In 화면 캡처에 실패했습니다."
                elif pixmap.save(str(zoomin_path), "PNG"):
                    saved_path = str(zoomin_path)
                else:
                    error_msg = "Zoom-In 캡처 이미지를 저장하지 못했습니다."
        except Exception as exc:
            error_msg = f"화면 캡처 중 오류가 발생했습니다: {exc}"
        finally:
            self.show()
            self.setWindowState(window_state)
            self.raise_()
            self.activateWindow()
            QApplication.processEvents()

        if error_msg:
            QMessageBox.warning(self, "Capture", error_msg)
            return
        if not accepted:
            self.logger.info("Zoom-In 캡처 취소됨")
            return
        if not saved_path:
            return

        self._on_images_dropped(probe_type, [saved_path])
        self.qr_input.focus_input()
        mode_label = "Window Capture" if capture_mode == "window" else "Region Capture"
        self.logger.ok(
            f"Zoom-In 캡처 추가 ({mode_label}): {zoomin_path.name}"
        )

    def _capture_manual_image_zoomout(self, capture_mode: str = "region"):
        """Capture a Zoom-Out image and attach it to the currently selected card."""
        if getattr(self, "current_mode", None) != "manual":
            return

        if self.selected_manual_index < 0:
            QMessageBox.warning(
                self, "Capture",
                "Zoom-Out을 첨부할 카드를 먼저 선택하세요."
            )
            return

        slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
        if slot is None or not slot.image_path:
            QMessageBox.warning(
                self, "Capture",
                "선택된 카드에 Zoom-In 이미지가 없습니다."
            )
            return

        target = derive_zoomout_path(slot.image_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        overwriting = target.exists()

        window_state = self.windowState()
        accepted = False
        error_msg: str | None = None
        saved = False

        self.hide()
        QApplication.processEvents()
        try:
            overlay = ScreenCaptureOverlay(
                capture_mode=capture_mode, label="Zoom-Out"
            )
            accepted = overlay.exec() == QDialog.Accepted
            screen, rect = overlay.selected_region()
            overlay.deleteLater()
            QApplication.processEvents()

            if accepted and screen is not None and rect is not None:
                pixmap = screen.grabWindow(
                    0, rect.x(), rect.y(), rect.width(), rect.height()
                )
                if pixmap.isNull():
                    error_msg = "Zoom-Out 화면 캡처에 실패했습니다."
                elif pixmap.save(str(target), "PNG"):
                    saved = True
                else:
                    error_msg = "Zoom-Out 캡처 이미지를 저장하지 못했습니다."
        except Exception as exc:
            error_msg = f"화면 캡처 중 오류가 발생했습니다: {exc}"
        finally:
            self.show()
            self.setWindowState(window_state)
            self.raise_()
            self.activateWindow()
            QApplication.processEvents()

        if error_msg:
            QMessageBox.warning(self, "Capture", error_msg)
            return
        if not accepted:
            self.logger.info("Zoom-Out 캡처 취소됨")
            return
        if not saved:
            return

        mode_label = "Window Capture" if capture_mode == "window" else "Region Capture"
        action = "교체" if overwriting else "추가"
        self.logger.ok(
            f"#{slot.slot_index + 1} Zoom-Out {action} ({mode_label}): {target.name}"
        )

        # If the viewer is currently showing zoom-out for this slot, refresh.
        btn_out = getattr(self, "btn_zoom_out_view", None)
        if (
            btn_out is not None
            and btn_out.isChecked()
            and self.selected_manual_index == slot.slot_index
        ):
            self.manual_image_viewer.load_image(str(target))

    def _active_manual_probe_type(self) -> str | None:
        if not self._manual_grids:
            QMessageBox.warning(self, "Warning", "Probe Type 탭을 먼저 추가하세요.")
            return None

        idx = self.manual_tabs.currentIndex()
        if idx < 0 or idx >= self.manual_tabs.count() - 1:
            QMessageBox.warning(self, "Warning", "Probe Type 탭을 선택하세요.")
            return None

        return self.manual_tabs.tabText(idx)

    # ─── 이미지 드롭 처리 ───

    def _on_images_dropped(self, probe_type: str, paths: list[str]):
        """이미지 드롭 → pristine 카드 즉시 렌더 + 백그라운드 OCR 큐잉 (Phase 7C).

        OCR은 ``QThreadPool`` 에 넣어 최대 4개 병렬 실행. 각 결과가 도착하면
        ``_on_ocr_done`` 이 메인 스레드에서 호출되어 카드·SlotData·DB·로그를 갱신.
        """
        if self.measurement_set.mode != "manual":
            self.measurement_set = MeasurementSet(mode="manual")

        self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")

        # Filter out zoom-out siblings (backtick-suffix stems) — only zoom-in
        # images become slots. Capture flow already passes zoom-in only.
        paths = self._filter_zoomin_only(paths)
        if not paths:
            return

        grid = self._manual_grids.get(probe_type)
        if not grid:
            return

        # Phase 7A-A1: 이미지 해상도별 ROI 프로파일 조회 — 배치 내 동일 해상도 캐시
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            Image = None  # type: ignore[assignment]

        roi_cache: dict[str, object] = {}
        unresolved_sizes: set[str] = set()

        def _resolve_roi(image_path: str):
            if Image is None or not hasattr(self, "_db_conn"):
                return None
            try:
                with Image.open(image_path) as im:
                    w, h = im.size
            except (FileNotFoundError, OSError):
                return None
            key = resolution_key(w, h)
            if key not in roi_cache:
                roi_cache[key] = load_roi_for(self._db_conn, w, h)
                if roi_cache[key] is None:
                    unresolved_sizes.add(key)
            return roi_cache[key]

        # 배치 ID — 한 드롭의 결과를 모아 요약 로그를 찍기 위함
        batch_id = uuid.uuid4().hex
        self._ocr_batches[batch_id] = {
            "total": len(paths),
            "done": 0,
            "success": 0,
            "probe_type": probe_type,
            "unresolved_sizes": unresolved_sizes,
        }

        # 1단계 (동기, 즉시 반영): pristine SlotData + 카드 렌더
        first_index = None
        queued: list[tuple[int, str, object]] = []  # (idx, path, roi)
        for path in paths:
            idx = self._manual_slot_counter
            self._manual_slot_counter += 1

            active_roi = _resolve_roi(path)

            slot = SlotData(
                slot_index=idx,
                slot_code=str(idx + 1),
                image_path=path,
                frequency=None,
                q_factor=None,
                source="manual_entry",
                probe_type=probe_type,
            )
            self.measurement_set.slots.append(slot)

            card = ManualCard(idx, path)
            grid.add_card(card)

            queued.append((idx, path, active_roi))
            self._manual_ocr_active_slots.add(idx)
            if first_index is None:
                first_index = idx

        self.logger.info(
            f"'{probe_type}' 탭에 {len(paths)}개 이미지 추가 — OCR 백그라운드 시작 "
            f"(스레드 {_OCR_MAX_THREADS}개 병렬)"
        )
        self._refresh_overview()
        self._update_progress()
        # pristine 상태를 DB에 저장 (OCR 완료 후 UPDATE로 값 반영)
        self._auto_save_to_db()

        if first_index is not None:
            self._on_manual_card_selected(first_index)

        # 2단계 (비동기): OCR 작업 큐잉
        for idx, path, active_roi in queued:
            runnable = OcrRunnable(
                slot_index=idx,
                image_path=path,
                roi=active_roi,
                batch_id=batch_id,
            )
            # Qt가 메인 스레드 슬롯으로 queued delivery
            runnable.signals.finished.connect(self._on_ocr_done)
            self._ocr_pool.start(runnable)

    def _on_ocr_done(self, slot_index: int, reading, batch_id: str) -> None:
        """OCR 워커 완료 콜백 (메인 스레드에서 실행됨).

        - SlotData · ManualCard 값 갱신
        - 배치 카운터 증가, 모든 작업 완료 시 요약 로그 + DB 저장
        """
        # 배치가 여전히 유효한지 (리셋·탭 삭제 등으로 없어졌을 수 있음)
        batch = self._ocr_batches.get(batch_id)
        if batch is None:
            return
        if self.measurement_set is None:
            return

        slot = self.measurement_set.find_slot_by_index(slot_index)
        if slot is not None:
            # OCR 결과 반영 (None이면 pristine 유지)
            if reading.frequency is not None:
                slot.frequency = truncate_measurement_value(reading.frequency)
            if reading.q_factor is not None:
                slot.q_factor = truncate_measurement_value(reading.q_factor)

            # 카드 UI 업데이트 — grid 탐색 (probe_type별)
            if reading.frequency is not None or reading.q_factor is not None:
                for grid in self._manual_grids.values():
                    if slot_index in grid._cards:
                        grid.update_card(
                            slot_index,
                            frequency=slot.frequency,
                            q_factor=slot.q_factor,
                            qr_id=slot.qr_id,
                        )
                        break

        self._manual_ocr_active_slots.discard(slot_index)
        queued_qr = self._manual_capture_rename_queue.pop(slot_index, None)
        if slot is not None and queued_qr:
            self._finalize_manual_capture_image(slot, queued_qr, force=True)

        # 배치 카운터
        batch["done"] += 1
        if reading.frequency is not None or reading.q_factor is not None:
            batch["success"] += 1

        if batch["done"] >= batch["total"]:
            # 배치 완료 — 요약 로그 + 최종 DB 저장
            total = batch["total"]
            success = batch["success"]
            probe_type = batch["probe_type"]
            unresolved = batch["unresolved_sizes"]

            if success == total:
                self.logger.ok(
                    f"'{probe_type}' OCR 완료: {success}/{total} 전부 성공"
                )
            elif success > 0:
                self.logger.ok(
                    f"'{probe_type}' OCR 완료: {success}/{total} 일부 성공"
                )
            else:
                self.logger.warn(
                    f"'{probe_type}' OCR 완료: 0/{total} — 수기 입력으로 진행. "
                    f"🎯 Calibrate OCR 로 좌표 재조정 또는 해상도 프로파일 추가 필요"
                )

            # Phase 7A-A1: 프로파일 없는 해상도 안내 (1회만)
            for size_key in unresolved:
                self.logger.warn(
                    f"해상도 {size_key}에 저장된 ROI 프로파일 없음 → "
                    f"코드 기본값({resolution_key(722, 479)} 기준) 사용 중. "
                    f"🎯 Calibrate OCR 로 이 해상도의 프로파일을 생성하세요."
                )

            self._refresh_overview()
            self._update_progress()
            self._auto_save_to_db()
            del self._ocr_batches[batch_id]

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

        # 이미지 뷰어 업데이트 — 카드 전환 시 항상 Zoom-In으로 reset
        self._reset_zoom_toggle_to_in()
        self.manual_image_viewer.load_image(slot.image_path)

        # 입력값 복원
        if slot.frequency is not None:
            self.manual_freq_input.setValue(slot.frequency)
        else:
            self.manual_freq_input.setValue(0)

        if slot.q_factor is not None:
            self.manual_q_input.setValue(slot.q_factor)
        else:
            self.manual_q_input.setValue(0)

        # QR 입력 대상
        probe = slot.probe_type or "?"
        self.qr_input.set_target_label(f"#{slot_index + 1} ({probe})")

    def _apply_zoom_toggle_visual(self, active: str) -> None:
        """Move the ``accent`` dynamic property to the active toggle and repolish.

        ``active`` must be ``"zoomin"`` or ``"zoomout"``. Signals are blocked so
        ``setChecked`` does not re-trigger the click handler.
        """
        btn_in = getattr(self, "btn_zoom_in_view", None)
        btn_out = getattr(self, "btn_zoom_out_view", None)
        for btn, level in ((btn_in, "zoomin"), (btn_out, "zoomout")):
            if btn is None:
                continue
            is_active = level == active
            btn.blockSignals(True)
            btn.setChecked(is_active)
            btn.setProperty("accent", "true" if is_active else "false")
            btn.blockSignals(False)
            style = btn.style()
            if style is not None:
                style.unpolish(btn)
                style.polish(btn)
            btn.update()

    def _reset_zoom_toggle_to_in(self) -> None:
        """Set the Zoom-In/Out toggle back to Zoom-In without firing handlers."""
        self._apply_zoom_toggle_visual("zoomin")

    def _on_zoom_view_toggled(self, level: str) -> None:
        """Switch the manual image viewer between Zoom-In and Zoom-Out files."""
        if self.selected_manual_index < 0:
            # No selection — keep toggle on Zoom-In silently.
            self._reset_zoom_toggle_to_in()
            return

        slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
        if not slot or not slot.image_path:
            self._reset_zoom_toggle_to_in()
            return

        if level == "zoomin":
            self._apply_zoom_toggle_visual("zoomin")
            self.manual_image_viewer.load_image(slot.image_path)
            return

        # level == "zoomout"
        zo_path = derive_zoomout_path(slot.image_path)
        if not zo_path.exists():
            self.logger.info("Zoom-Out 이미지 없음 — Zoom-In으로 복귀")
            self._reset_zoom_toggle_to_in()
            self.manual_image_viewer.load_image(slot.image_path)
            return

        self._apply_zoom_toggle_visual("zoomout")
        self.manual_image_viewer.load_image(str(zo_path))

    def _on_manual_card_removed(self, slot_index: int):
        self._prepare_manual_reorder()

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

        was_selected = self.selected_manual_index == slot_index
        if was_selected:
            self.selected_manual_index = -1

        self._renumber_manual_slots()
        if self.selected_manual_index >= 0:
            self._on_manual_card_selected(self.selected_manual_index)
        elif was_selected:
            current_grid = self._current_manual_grid()
            if current_grid and current_grid.get_slot_indices():
                self._on_manual_card_selected(current_grid.get_slot_indices()[0])
            else:
                self.manual_image_viewer.clear()

        self.logger.info(f"카드 #{slot_index + 1} 삭제됨")
        self._refresh_overview()
        self._update_progress()
        # F-15: 카드 삭제도 DB에 즉시 반영
        self._auto_save_to_db()

    def _current_manual_grid(self):
        idx = self.manual_tabs.currentIndex()
        if idx < 0 or idx >= self.manual_tabs.count() - 1:
            return None
        return self._manual_grids.get(self.manual_tabs.tabText(idx))

    def _prepare_manual_reorder(self) -> None:
        if self._manual_ocr_active_slots:
            self._ocr_pool.waitForDone(3000)
        self._ocr_batches.clear()
        self._manual_ocr_active_slots.clear()
        self._manual_capture_rename_queue.clear()

    def _ordered_manual_slot_indices(self) -> list[int]:
        ordered: list[int] = []
        for tab_idx in range(max(0, self.manual_tabs.count() - 1)):
            probe_type = self.manual_tabs.tabText(tab_idx)
            grid = self._manual_grids.get(probe_type)
            if grid:
                ordered.extend(grid.get_slot_indices())
        return ordered

    def _renumber_manual_slots(self) -> None:
        if not self.measurement_set:
            return

        old_selected = self.selected_manual_index
        mapping = renumber_manual_slots(
            self.measurement_set.slots,
            self._ordered_manual_slot_indices(),
        )
        for grid in self._manual_grids.values():
            grid.reindex_cards(mapping)

        self.selected_manual_index = mapping.get(old_selected, -1)
        self._manual_slot_counter = len(self.measurement_set.slots)

        for slot in self.measurement_set.slots:
            self._sync_manual_capture_filename(slot)

    def _sync_manual_capture_filename(self, slot: SlotData) -> None:
        if not slot.image_path or not slot.qr_id:
            return
        if not is_app_capture_path(slot.image_path):
            return

        old_path = Path(slot.image_path)
        new_zoomin, new_zoomout = final_capture_pair(
            old_path, slot.slot_index, slot.qr_id
        )
        try:
            if old_path.resolve() == new_zoomin.resolve():
                return
            old_path.rename(new_zoomin)
        except OSError as exc:
            self.logger.warn(f"캡처 이미지 순번 파일명 갱신 실패: {exc}")
            return

        old_zoomout = derive_zoomout_path(old_path)
        if old_zoomout.exists():
            try:
                old_zoomout.rename(new_zoomout)
            except OSError as exc:
                self.logger.warn(f"Zoom-Out 순번 파일명 갱신 실패: {exc}")

        slot.image_path = str(new_zoomin)
        for grid in self._manual_grids.values():
            card = grid._cards.get(slot.slot_index)
            if card:
                card.set_image_path(str(new_zoomin))
                break

    # ─── 데이터 입력 ───

    def _apply_manual_entry(self):
        if self.selected_manual_index < 0:
            self.logger.warn("카드를 먼저 선택하세요")
            return

        slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
        if not slot:
            return

        freq = truncate_measurement_value(self.manual_freq_input.value())
        q = truncate_measurement_value(self.manual_q_input.value())

        if freq is None or q is None or freq <= 0 or q <= 0:
            self.logger.warn("Frequency와 Q 값을 입력하세요")
            return

        slot.frequency = freq
        slot.q_factor = q

        # 카드 업데이트
        for grid in self._manual_grids.values():
            if self.selected_manual_index in grid._cards:
                grid.update_card(
                    self.selected_manual_index,
                    frequency=freq, q_factor=q, qr_id=slot.qr_id,
                )
                break

        probe = slot.probe_type or "?"
        self.logger.ok(
            f"#{slot.slot_index + 1} ({probe}): "
            f"Freq={freq} KHz, Q={q}"
        )

        self._refresh_overview()
        self._update_progress()
        self._auto_save_to_db()

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

        # 기존 내용 역순 제거 (위젯/서브레이아웃/Spacer 모두 안전 처리)
        for i in reversed(range(self._overview_layout.count())):
            item = self._overview_layout.takeAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None:
                    sub_layout.deleteLater()
            del item

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

        # 모든 Probe Type 탭 제거 (마지막 Overview 탭은 남김)
        for grid in self._manual_grids.values():
            grid.deleteLater()
        self._manual_grids.clear()

        # 뒤에서부터 제거: 인덱스 시프트/이벤트 반복 방지
        for i in reversed(range(self.manual_tabs.count() - 1)):
            self.manual_tabs.removeTab(i)

        # 상태 리셋
        self._manual_slot_counter = 0
        self.selected_manual_index = -1
        self._ocr_batches.clear()  # in-flight OCR 결과를 안전하게 무시 (batch None 가드 활용)
        self._manual_ocr_active_slots.clear()
        self._manual_capture_rename_queue.clear()
        self.measurement_set = MeasurementSet(mode="manual")

        # UI 리셋
        self.manual_image_viewer.clear()
        self.manual_freq_input.setValue(0)
        self.manual_q_input.setValue(0)

        self._refresh_overview()
        self._update_progress()
        self.logger.section("수동 모드 초기화")
        self.logger.ok("모든 데이터가 초기화되었습니다")

    # ─── OCR 재실행 (Refresh) ───

    def _refresh_manual_ocr(self):
        """저장된 ROI 로 현재 로드된 모든 카드의 OCR 을 재실행.

        ROI Calibrator 에서 ROI 좌표를 변경/저장한 뒤, 폴더 재로드 없이
        기존 카드들에 새 ROI 를 즉시 적용하기 위한 워크플로우 단축 기능.
        OCR 결과가 None 이면 슬롯의 기존 값(수기 입력 등)은 그대로 유지된다.
        """
        if not self.measurement_set or not self.measurement_set.slots:
            self.logger.warn("재적용할 데이터가 없습니다")
            return

        items_by_probe: dict[str, list[tuple[int, str]]] = {}
        for slot in self.measurement_set.slots:
            if slot.image_path:
                items_by_probe.setdefault(
                    slot.probe_type or "Default", []
                ).append((slot.slot_index, slot.image_path))

        total = sum(len(v) for v in items_by_probe.values())
        if total == 0:
            self.logger.warn("재OCR 가능한 이미지 슬롯이 없습니다")
            return

        reply = QMessageBox.question(
            self,
            "OCR 재실행",
            f"새 ROI 로 {total}개 카드의 OCR 을 재실행합니다.\n"
            f"수기 입력값도 덮어씌워집니다. 계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 진행 중 OCR 안전 처리: 기존 워커 완료 대기 + 배치 무효화
        self._ocr_pool.waitForDone(3000)
        self._ocr_batches.clear()
        self._manual_ocr_active_slots.clear()
        self._manual_capture_rename_queue.clear()

        # 해상도별 ROI 캐시 (기존 _on_images_dropped 와 동일 패턴)
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            Image = None  # type: ignore[assignment]

        roi_cache: dict[str, object] = {}

        def _resolve_roi(image_path: str):
            if Image is None or not hasattr(self, "_db_conn"):
                return None
            try:
                with Image.open(image_path) as im:
                    w, h = im.size
            except (FileNotFoundError, OSError):
                return None
            key = resolution_key(w, h)
            if key not in roi_cache:
                roi_cache[key] = load_roi_for(self._db_conn, w, h)
            return roi_cache[key]

        self.logger.section(f"OCR 재실행: {total}개 카드")

        # probe_type 별로 batch 분리 — _on_ocr_done 의 요약 로그가 그룹별로 출력됨
        for probe_type, items in items_by_probe.items():
            batch_id = uuid.uuid4().hex
            self._ocr_batches[batch_id] = {
                "total": len(items),
                "done": 0,
                "success": 0,
                "probe_type": probe_type,
                "unresolved_sizes": set(),
            }
            for slot_index, image_path in items:
                active_roi = _resolve_roi(image_path)
                runnable = OcrRunnable(
                    slot_index=slot_index,
                    image_path=image_path,
                    roi=active_roi,
                    batch_id=batch_id,
                )
                runnable.signals.finished.connect(self._on_ocr_done)
                self._manual_ocr_active_slots.add(slot_index)
                self._ocr_pool.start(runnable)

        self._update_progress()

    # ─── 열 수 변경 ───

    def _on_manual_columns_changed(self, n: int):
        for grid in self._manual_grids.values():
            grid.set_columns(n)

    # ─── ROI Calibrator (F-14 / Phase 7A) ───

    def _open_roi_calibrator(self):
        """OCR ROI 좌표를 시각적으로 편집 (해상도별 프로파일 기반).

        다이얼로그에서 Save 시 ``ocr_settings.save_roi_for(conn, W, H, roi)`` 로
        저장된 참조 이미지의 해상도 프로파일에 저장.
        """
        # 현재 선택된 Manual 카드 이미지를 참조 이미지로 자동 로드 (있으면)
        sample_image = None
        if hasattr(self, "measurement_set") and self.measurement_set is not None:
            if 0 <= self.selected_manual_index:
                slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
                if slot and slot.image_path:
                    sample_image = slot.image_path

        # 참조 이미지 해상도 기반으로 기존 프로파일 조회 (있으면 사전 로드)
        current_roi = None
        if sample_image and hasattr(self, "_db_conn"):
            try:
                from PIL import Image
                with Image.open(sample_image) as im:
                    w, h = im.size
                current_roi = load_roi_for(self._db_conn, w, h)
            except (ImportError, FileNotFoundError, OSError):
                pass

        dlg = RoiCalibratorDialog(
            self,
            initial_roi=current_roi,
            sample_image=sample_image,
        )
        if dlg.exec() != QDialog.Accepted:
            self.logger.info("ROI Calibrator 취소됨")
            return

        new_roi = dlg.result_roi()
        resolution = dlg.result_resolution()

        if resolution is None:
            # 참조 이미지 없이 저장 시도 → 불가 (B3에서 이미 차단되지만 이중 방어)
            self.logger.warn(
                "ROI 저장 불가 — 참조 이미지 없이는 해상도를 결정할 수 없습니다."
            )
            return

        w, h = resolution
        try:
            save_roi_for(self._db_conn, w, h, new_roi)
        except Exception as e:
            self.logger.error(f"ROI 저장 실패: {e}")
            return

        self.logger.ok(
            f"ROI 업데이트 [{resolution_key(w, h)}]: "
            f"freq={new_roi.get('frequency')}, q={new_roi.get('q_factor')}"
        )
