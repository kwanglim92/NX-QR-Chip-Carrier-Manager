"""수동 측정 워크플로우 — Probe Type 탭 + 드래그&드롭 카드 그리드."""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog

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
        self._manual_grids: dict[str, ManualGridWidget] = {}  # serial -> grid (고유)
        self.selected_manual_index: int = -1

        # MeasurementSet 초기화 (수동 모드)
        if not hasattr(self, 'measurement_set') or self.measurement_set is None:
            self.measurement_set = MeasurementSet(mode="manual")

        # Phase 7C: 비동기 OCR 파이프라인
        self._ocr_pool = QThreadPool()
        self._ocr_pool.setMaxThreadCount(_OCR_MAX_THREADS)
        # 배치별 추적: {batch_id: {"total", "done", "success", "label", "unresolved_sizes"}}
        self._ocr_batches: dict[str, dict] = {}
        self._manual_ocr_active_slots: set[int] = set()
        self._manual_capture_rename_queue: dict[int, str] = {}

    # ─── 탭 관리 ───

    @staticmethod
    def _format_tab_title(tip_name: str, serial: str) -> str:
        """탭 표시 라벨: 'Tip (시리얼)'. Tip 이 없으면 시리얼만."""
        tip = (tip_name or "").strip()
        serial = (serial or "").strip()
        if tip and serial:
            return f"{tip} ({serial})"
        return tip or serial

    def _create_manual_grid(self, serial: str, tip_name: str, contact_mode: bool = False):
        """그리드 생성 + 모든 시그널 결선(추가/이력 로드 공용). _manual_grids 등록."""
        grid = ManualGridWidget(
            serial_number=serial, tip_name=tip_name, contact_mode=contact_mode
        )
        grid.set_columns(self.manual_col_spin.value())
        grid.card_clicked.connect(self._on_manual_card_selected)
        grid.card_removed.connect(self._on_manual_card_removed)
        grid.images_dropped.connect(
            lambda paths, g=grid: self._on_images_dropped(g, paths)
        )
        grid.create_empty_requested.connect(
            lambda n, g=grid: self._create_empty_cards(g, n)
        )
        grid.clear_requested.connect(lambda g=grid: self._clear_grid_cards(g))
        self._manual_grids[serial] = grid
        return grid

    def _add_probe_tab(self):
        from src.ui.dialogs.add_tab_dialog import AddTabDialog

        dlg = AddTabDialog(
            self._load_tip_catalog(), set(self._manual_grids.keys()), self
        )
        if dlg.exec() != QDialog.Accepted:
            return

        # 카탈로그 변경분 즉시 영속화
        if dlg.catalog_changed():
            self._save_tip_catalog(dlg.result_catalog())

        serial = dlg.result_serial()
        tip_name = dlg.result_tip()
        # 시리얼이 곧 탭의 고유 키 — 같은 Tip 이름이라도 시리얼이 다르면 허용
        if serial in self._manual_grids:
            self.logger.warn(f"시리얼 '{serial}' 탭이 이미 존재합니다")
            return

        grid = self._create_manual_grid(serial, tip_name, dlg.result_contact_mode())

        # Overview(맨 앞, index 0) 뒤에 append
        title = self._format_tab_title(tip_name, serial)
        self.manual_tabs.addTab(grid, title)
        self.manual_tabs.setCurrentIndex(self.manual_tabs.count() - 1)

        self.logger.ok(f"'{title}' 탭 추가됨")
        self._refresh_overview()

    def _remove_current_probe_tab(self):
        idx = self.manual_tabs.currentIndex()
        grid = self.manual_tabs.widget(idx)
        # Overview(그리드가 아님) 탭은 삭제 불가
        if not isinstance(grid, ManualGridWidget):
            self.logger.warn("Overview 탭은 삭제할 수 없습니다")
            return
        title = self._format_tab_title(grid.tip_name, grid.serial_number)
        reply = QMessageBox.question(
            self,
            "탭 삭제",
            f"'{title}' 탭과 모든 카드를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._prepare_manual_reorder()

        # 해당 탭(시리얼)의 SlotData 제거
        self._manual_grids.pop(grid.serial_number, None)
        indices = grid.get_slot_indices()
        self.measurement_set.slots = [
            s for s in self.measurement_set.slots
            if s.slot_index not in indices
        ]
        grid.deleteLater()

        self.manual_tabs.removeTab(idx)
        self._renumber_manual_slots()
        self.logger.info(f"'{title}' 탭 삭제됨")
        self._refresh_overview()
        self._update_progress()
        # F-15: 삭제 연산도 DB에 즉시 반영 — 재시작 시 삭제된 슬롯 부활 방지
        self._auto_save_to_db()

    # ─── 이미지 불러오기 (파일/폴더 다이얼로그) ───

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}

    def _browse_manual_images(self):
        """현재 탭에 이미지를 파일 또는 폴더 다이얼로그로 불러오기."""
        grid = self._active_manual_grid()
        if grid is None:
            return

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
            self._on_images_dropped(grid, paths)

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

        grid = self._active_manual_grid()
        if grid is None:
            return

        production_date = self.date_edit.date().toString("yyyyMMdd")
        # 시리얼 기준 디렉터리 — 같은 Tip 이름·다른 시리얼 간 파일 충돌 방지
        safe_probe = sanitize_capture_filename_part(
            grid.serial_number, fallback="serial"
        )
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

        self._on_images_dropped(grid, [saved_path])
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

        # 카드 Zoom-Out 썸네일 갱신 (존재 여부 가시화)
        self._refresh_card_zoomout(slot.slot_index)

        # If the viewer is currently showing zoom-out for this slot, refresh.
        btn_out = getattr(self, "btn_zoom_out_view", None)
        if (
            btn_out is not None
            and btn_out.isChecked()
            and self.selected_manual_index == slot.slot_index
        ):
            self.manual_image_viewer.load_image(str(target))

    def _active_manual_grid(self) -> "ManualGridWidget | None":
        if not self._manual_grids:
            QMessageBox.warning(self, "Warning", "탭을 먼저 추가하세요.")
            return None

        idx = self.manual_tabs.currentIndex()
        widget = self.manual_tabs.widget(idx) if idx >= 0 else None
        if not isinstance(widget, ManualGridWidget):
            QMessageBox.warning(self, "Warning", "탭을 선택하세요.")
            return None
        return widget

    # ─── 클립보드 붙여넣기 ───

    def _paste_or_browse_manual_image(self):
        """이미지 뷰어 클릭: 클립보드 이미지가 있으면 붙여넣기, 없으면 불러오기."""
        if getattr(self, "current_mode", None) != "manual":
            return
        image = QGuiApplication.clipboard().image()
        if image is not None and not image.isNull():
            self._paste_manual_image(image)
        else:
            self._browse_manual_images()

    def _paste_manual_image(self, image) -> None:
        """클립보드 QImage 를 현재 Zoom 토글에 맞춰 투입.

        Zoom-In: 활성 탭에 새 카드 생성. Zoom-Out: 선택 카드에 부착.
        캡처 흐름과 동일한 파일 경로 규칙(``captures_root`` / 시리얼)을 재사용.
        """
        btn_out = getattr(self, "btn_zoom_out_view", None)
        is_zoomout = btn_out is not None and btn_out.isChecked()

        if is_zoomout:
            if self.selected_manual_index < 0:
                QMessageBox.warning(
                    self, "붙여넣기", "Zoom-Out을 붙여넣을 카드를 먼저 선택하세요."
                )
                return
            slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
            if slot is None or not slot.image_path:
                QMessageBox.warning(
                    self, "붙여넣기", "선택된 카드에 Zoom-In 이미지가 없습니다."
                )
                return
            target = derive_zoomout_path(slot.image_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not image.save(str(target), "PNG"):
                QMessageBox.warning(self, "붙여넣기", "Zoom-Out 이미지를 저장하지 못했습니다.")
                return
            self.logger.ok(f"#{slot.slot_index + 1} Zoom-Out 붙여넣기: {target.name}")
            self._refresh_card_zoomout(slot.slot_index)
            # 현재 Zoom-Out 보기 중이면 즉시 갱신
            self.manual_image_viewer.load_image(str(target))
            return

        # Zoom-In: 새 카드 생성
        grid = self._active_manual_grid()
        if grid is None:
            return
        production_date = self.date_edit.date().toString("yyyyMMdd")
        safe_probe = sanitize_capture_filename_part(
            grid.serial_number, fallback="serial"
        )
        capture_base = captures_root() / production_date / safe_probe
        zoomin_path, _zo_reserved = next_pending_capture_pair(capture_base)
        if not image.save(str(zoomin_path), "PNG"):
            QMessageBox.warning(self, "붙여넣기", "이미지를 저장하지 못했습니다.")
            return
        self._on_images_dropped(grid, [str(zoomin_path)])
        self.qr_input.focus_input()
        self.logger.ok(f"Zoom-In 붙여넣기 추가: {zoomin_path.name}")

    # ─── 이미지 드롭 처리 ───

    def _on_images_dropped(self, grid, paths: list[str]):
        """이미지 드롭 → pristine 카드 즉시 렌더 + 백그라운드 OCR 큐잉 (Phase 7C).

        ``grid`` 는 대상 탭의 :class:`ManualGridWidget` (시리얼/Tip 보유).
        OCR은 ``QThreadPool`` 에 넣어 최대 4개 병렬 실행. 각 결과가 도착하면
        ``_on_ocr_done`` 이 메인 스레드에서 호출되어 카드·SlotData·DB·로그를 갱신.
        """
        if grid is None:
            return
        if self.measurement_set.mode != "manual":
            self.measurement_set = MeasurementSet(mode="manual")

        self.measurement_set.production_date = self.date_edit.date().toString("yyyyMMdd")

        # Filter out zoom-out siblings (backtick-suffix stems) — only zoom-in
        # images become slots. Capture flow already passes zoom-in only.
        paths = self._filter_zoomin_only(paths)
        if not paths:
            return

        tip_name = grid.tip_name
        serial = grid.serial_number
        label = self._format_tab_title(tip_name, serial)

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
            "label": label,
            "unresolved_sizes": unresolved_sizes,
        }

        # Phase E: 선택된 '빈 카드'(이미지 없음)가 이 그리드에 있으면 첫 이미지로 채움
        fill_idx = None
        if self.selected_manual_index in grid._cards:
            sel_slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)
            if sel_slot is not None and not sel_slot.image_path:
                fill_idx = self.selected_manual_index

        # 1단계 (동기, 즉시 반영): pristine SlotData + 카드 렌더
        first_index = None
        queued: list[tuple[int, str, object]] = []  # (idx, path, roi)
        for i, path in enumerate(paths):
            active_roi = _resolve_roi(path)

            if i == 0 and fill_idx is not None:
                # 기존 빈 카드를 채움 (새 슬롯 생성하지 않음)
                idx = fill_idx
                slot = self.measurement_set.find_slot_by_index(idx)
                if slot is not None:
                    slot.image_path = path
                card = grid._cards.get(idx)
                if card is not None:
                    card.set_image_path(path)
            else:
                idx = self._manual_slot_counter
                self._manual_slot_counter += 1
                slot = SlotData(
                    slot_index=idx,
                    slot_code=str(idx + 1),
                    image_path=path,
                    frequency=None,
                    q_factor=None,
                    source="manual_entry",
                    probe_type=tip_name,
                    serial_number=serial,
                    contact_mode=grid.contact_mode,
                )
                self.measurement_set.slots.append(slot)
                card = ManualCard(idx, path, contact_mode=grid.contact_mode)
                grid.add_card(card)

            queued.append((idx, path, active_roi))
            self._manual_ocr_active_slots.add(idx)
            if first_index is None:
                first_index = idx

        self.logger.info(
            f"'{label}' 탭에 {len(paths)}개 이미지 추가 — OCR 백그라운드 시작 "
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
            label = batch["label"]
            unresolved = batch["unresolved_sizes"]

            if success == total:
                self.logger.ok(
                    f"'{label}' OCR 완료: {success}/{total} 전부 성공"
                )
            elif success > 0:
                self.logger.ok(
                    f"'{label}' OCR 완료: {success}/{total} 일부 성공"
                )
            else:
                self.logger.warn(
                    f"'{label}' OCR 완료: 0/{total} — 수기 입력으로 진행. "
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

        # 이미지 뷰어 업데이트 — 현재 Zoom 토글 상태를 유지(시리얼 내 자유 토글)
        self._load_current_zoom_image()

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

    def _on_zoom_view_toggled(self, level: str) -> None:
        """Zoom-In/Zoom-Out 뷰를 자유롭게 토글.

        Zoom-Out 데이터 유무와 무관하게 토글이 유지된다(없으면 플레이스홀더 표시).
        이 상태에서 캡처/붙여넣기로 해당 줌 레벨을 바로 채울 수 있다.
        """
        self._apply_zoom_toggle_visual(level)
        self._load_current_zoom_image()

    def _refresh_card_zoomout(self, slot_index: int) -> None:
        """해당 슬롯 카드의 Zoom-Out 썸네일을 갱신(줌아웃 캡처/붙여넣기 직후)."""
        for grid in self._manual_grids.values():
            card = grid._cards.get(slot_index)
            if card is not None:
                card.refresh_zoomout()
                return

    def _load_current_zoom_image(self) -> None:
        """현재 선택 카드 + 토글 상태에 맞는 이미지를 뷰어에 로드(없으면 플레이스홀더)."""
        btn_out = getattr(self, "btn_zoom_out_view", None)
        is_zoomout = btn_out is not None and btn_out.isChecked()

        slot = None
        if self.selected_manual_index >= 0:
            slot = self.measurement_set.find_slot_by_index(self.selected_manual_index)

        if slot is None or not slot.image_path:
            self.manual_image_viewer.load_image(None)
            return

        if is_zoomout:
            zo_path = derive_zoomout_path(slot.image_path)
            self.manual_image_viewer.load_image(
                str(zo_path) if zo_path.exists() else None
            )
        else:
            self.manual_image_viewer.load_image(slot.image_path)

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
        if idx < 0:
            return None
        widget = self.manual_tabs.widget(idx)
        return widget if isinstance(widget, ManualGridWidget) else None

    def _prepare_manual_reorder(self) -> None:
        if self._manual_ocr_active_slots:
            self._ocr_pool.waitForDone(3000)
        self._ocr_batches.clear()
        self._manual_ocr_active_slots.clear()
        self._manual_capture_rename_queue.clear()

    def _ordered_manual_slot_indices(self) -> list[int]:
        ordered: list[int] = []
        for tab_idx in range(self.manual_tabs.count()):
            widget = self.manual_tabs.widget(tab_idx)
            if isinstance(widget, ManualGridWidget):
                ordered.extend(widget.get_slot_indices())
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
            f"Freq={freq} kHz, Q={q}"
        )

        self._refresh_overview()
        self._update_progress()
        self._auto_save_to_db()

        # 현재 탭에서 다음 미입력 카드로 이동
        self._advance_to_next_empty()

    def _advance_to_next_empty(self):
        """현재 탭에서 다음 측정값 미입력 카드로 이동."""
        grid = self._current_manual_grid()
        if grid is None:
            return  # 전체 현황 탭 또는 비선택

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

        for serial, grid in self._manual_grids.items():
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
            tab_label = self._format_tab_title(grid.tip_name, serial)
            lbl = QLabel(f"  {tab_label}: {complete}/{total} {status}")
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

        # 모든 그리드 탭 제거 (Overview 탭은 남김)
        for grid in self._manual_grids.values():
            grid.deleteLater()
        self._manual_grids.clear()

        # 뒤에서부터 제거: 그리드 탭만 (Overview 보존, 위치 무관)
        for i in reversed(range(self.manual_tabs.count())):
            if isinstance(self.manual_tabs.widget(i), ManualGridWidget):
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

    def _create_empty_cards(self, grid, n: int):
        """선택 탭(grid)에 빈 카드(이미지 없음) n개를 미리 생성."""
        if grid is None or n <= 0:
            return
        first_new = None
        for _ in range(n):
            idx = self._manual_slot_counter
            self._manual_slot_counter += 1
            if first_new is None:
                first_new = idx
            slot = SlotData(
                slot_index=idx,
                slot_code=str(idx + 1),
                image_path=None,
                frequency=None,
                q_factor=None,
                source="manual_entry",
                probe_type=grid.tip_name,
                serial_number=grid.serial_number,
                contact_mode=grid.contact_mode,
            )
            self.measurement_set.slots.append(slot)
            card = ManualCard(idx, None, contact_mode=grid.contact_mode)
            grid.add_card(card)

        self._refresh_overview()
        self._update_progress()
        self._auto_save_to_db()
        title = self._format_tab_title(grid.tip_name, grid.serial_number)
        self.logger.ok(f"'{title}' 탭에 빈 카드 {n}개 생성")

        # 첫 빈 카드 자동 선택 — QR/이미지 채우기를 클릭 없이 바로 시작
        if first_new is not None:
            self._on_manual_card_selected(first_new)

    def _clear_grid_cards(self, grid):
        """선택 탭(grid)의 카드만 모두 삭제 (탭은 유지). 다른 탭은 영향 없음."""
        if grid is None:
            return
        indices = set(grid.get_slot_indices())
        if not indices:
            self.logger.info("비울 카드가 없습니다")
            return

        title = self._format_tab_title(grid.tip_name, grid.serial_number)
        reply = QMessageBox.question(
            self,
            "이 탭 비우기",
            f"'{title}' 탭의 카드 {len(indices)}개를 삭제하시겠습니까? (탭은 유지됩니다)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 진행 중 OCR 안전 처리 + 배치/큐 정리
        self._prepare_manual_reorder()

        grid.clear_all()
        self.measurement_set.slots = [
            s for s in self.measurement_set.slots if s.slot_index not in indices
        ]
        if self.selected_manual_index in indices:
            self.selected_manual_index = -1
            self.manual_image_viewer.clear()
            self.manual_freq_input.setValue(0)
            self.manual_q_input.setValue(0)

        self._renumber_manual_slots()
        self._refresh_overview()
        self._update_progress()
        self._auto_save_to_db()
        self.logger.ok(f"'{title}' 탭의 카드를 비웠습니다")

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

        items_by_serial: dict[str, list[tuple[int, str]]] = {}
        for slot in self.measurement_set.slots:
            if slot.image_path:
                items_by_serial.setdefault(
                    slot.serial_number or "", []
                ).append((slot.slot_index, slot.image_path))

        total = sum(len(v) for v in items_by_serial.values())
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

        # 시리얼(탭)별로 batch 분리 — _on_ocr_done 의 요약 로그가 그룹별로 출력됨
        for serial, items in items_by_serial.items():
            grid = self._manual_grids.get(serial)
            label = (
                self._format_tab_title(grid.tip_name, serial)
                if grid is not None else (serial or "?")
            )
            batch_id = uuid.uuid4().hex
            self._ocr_batches[batch_id] = {
                "total": len(items),
                "done": 0,
                "success": 0,
                "label": label,
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

    # ─── Log 패널 토글 ───

    def _toggle_manual_log_panel(self, hidden: bool) -> None:
        """Manual 페이지 로그 패널 표시/숨김 + 숨길 때 좌측 영역 확장."""
        grp = getattr(self, "manual_log_grp", None)
        if grp is not None:
            grp.setVisible(not hidden)
        btn = getattr(self, "btn_toggle_log", None)
        if btn is not None:
            btn.setText("🗎 Log 보기" if hidden else "🗎 Log 숨기기")
        splitter = getattr(self, "manual_splitter", None)
        if splitter is not None:
            # 숨기면 좌측(이미지) 비중↑, 보이면 원래 비율로 복귀
            splitter.setSizes([1100, 700] if hidden else [800, 1000])

    def _on_manual_tab_changed(self, _idx: int = -1):
        """탭 전환 시 좌측 패널(이미지·측정 입력)을 모드에 맞게 표시/숨김.

        컨택 탭(QR-only)은 이미지·주파수·Q를 쓰지 않으므로 해당 위젯을 숨긴다.
        """
        grid = self._current_manual_grid()
        contact = bool(grid is not None and grid.contact_mode)
        for w in (
            getattr(self, "manual_img_group", None),
            getattr(self, "manual_data_group", None),
            getattr(self, "btn_apply_manual", None),
        ):
            if w is not None:
                w.setVisible(not contact)

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
