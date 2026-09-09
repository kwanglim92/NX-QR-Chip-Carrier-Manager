"""키엔스 리더기 연결 컨트롤러 (설계 §4, R4).

- 설정(``app_settings.qr_reader``) 로드/저장 + 리더기 설정 다이얼로그
- 상시 ``KeyenceClient`` 1개: 상태 → 하단 바 상태 칩, 프레임 → 로그 + ``_last_frame`` 보관
- "다중 QR 스캔" 버튼(F10, 구 카세트 스캔) → ``trigger()``
- R6: 프레임 → ``build_plan``(로드된 ATX 폴더 탭 순서, 설정의 cell_override) → **레코드 있는 칸(APPLY)을 즉시 적용**
  (``slot.qr_id`` 갱신, 그리드·탭 라벨·진행률·Pass Pool 갱신, 폴더별 DB 자동 저장). 레코드 없음·NG·충돌·중복은 로그로 요약.
  "판독 검토" 버튼 → 마지막 프레임을 실물 배치(``BoatLayout``)대로 펼친 검토 다이얼로그 → [적용] 시 선택 항목(충돌 덮어쓰기 등) 적용.
  (기존 단일 QR 경로 ``_match_qr_atx`` / ``_pool_on_qr_scanned`` 와 같은 저장 규칙)
- 접속되면 ``RD,001..N`` 으로 서치 영역 좌표를 한 번 읽어 두고(``_reader_regions``) 검토 창 배치에 쓴다.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog

from src.core.qr_reader.boat_layout import BoatLayout, build_layout, parse_region
from src.core.qr_reader.keyence_client import KeyenceClient, ReaderState
from src.core.qr_reader.payload_parser import ParsedFrame
from src.core.qr_reader.settings import (
    client_kwargs,
    load_qr_reader_settings,
    save_qr_reader_settings,
)
from src.core.qr_reader.slot_assigner import AssignError, AssignItem, AssignPlan, AssignStatus, build_plan
from src.core.slot_mapper import format_full_label, parse_slot_code
from src.ui.theme import BG2, FG2, GREEN, ORANGE, RED, TEAL

_STATE_STYLE = {
    ReaderState.DISCONNECTED.value: (FG2, "미연결"),
    ReaderState.CONNECTING.value: (TEAL, "접속 중"),
    ReaderState.CONNECTED.value: (GREEN, "연결됨"),
    ReaderState.READING.value: (ORANGE, "판독 중"),
    ReaderState.RECONNECTING.value: (ORANGE, "재접속 중"),
}


class QRReaderMixin:
    def _init_qr_reader(self) -> None:
        """UI 구성 후 호출. 설정을 읽고 클라이언트를 만들며, enabled(기본 켜짐) 면 바로 접속을 시도한다."""
        self._qr_reader_settings = load_qr_reader_settings(self._db_conn)
        self._last_frame: ParsedFrame | None = None
        self._reader_regions: dict[int, tuple[int, int, int, int]] = {}   # RD 로 읽은 서치 영역(리더기 화상 좌표)
        self._reader = KeyenceClient(self)
        self._reader.state_changed.connect(self._on_reader_state)
        self._reader.frame_received.connect(self._on_reader_frame)
        self._reader.frame_rejected.connect(lambda m: self.logger.warn(f"리더기 프레임 거부: {m}"))
        self._reader.command_error.connect(self._on_reader_command_error)
        self._reader.comm_error.connect(lambda m: self.logger.warn(f"리더기 통신: {m}"))
        # 앱 시작: '앱 시작 시 자동 접속'(기본 켜짐) 이면 접속 시도 — 실패해도 백오프 재접속으로 계속 확인
        self._apply_reader_settings(connect_now=self._qr_reader_settings["enabled"])

    def _apply_reader_settings(self, connect_now: bool) -> None:
        """설정을 클라이언트에 반영. LAN 이고 connect_now 면 접속, 아니면 끊긴 상태로 둔다(버튼 비활성)."""
        s = self._qr_reader_settings
        self._reader.close()
        self._reader_regions = {}          # 리더기(호스트)가 바뀔 수 있으므로 영역 캐시 무효화
        self._reader.configure(**client_kwargs(s))
        self._update_reader_chip(self._reader.state.value)
        if s["transport"] == "lan" and connect_now:
            self._reader.open()

    # ─── UI 반응 ───

    def _on_reader_state(self, state: str) -> None:
        self._update_reader_chip(state)
        if state == ReaderState.CONNECTED.value:
            self.logger.info(f"리더기 연결됨 {self._reader.host}:{self._reader.port}")
            if not self._reader_regions:
                self._load_reader_regions()
        elif state == ReaderState.RECONNECTING.value:
            self.logger.warn("리더기 연결 끊김 — 재접속 시도 중")

    def _load_reader_regions(self) -> None:
        """접속 직후 ``RD,001..N`` 으로 서치 영역 좌표를 읽어 둔다 (검토 창의 실물 배치용, 실패해도 개략 배치로 대체)."""
        count = self._qr_reader_settings["expected_count"]
        found: dict[int, tuple[int, int, int, int]] = {}
        pending = [count]

        def on_reply(cell: int, payload: str | None, _reason: str) -> None:
            if payload is not None:
                region = parse_region(payload)
                if region is not None:
                    found[cell] = region
            pending[0] -= 1
            if pending[0] == 0 and found:
                self._reader_regions = found
                self.logger.info(f"리더기 서치 영역 {len(found)}개 읽음 (검토 창 배치에 사용)")

        for cell in range(1, count + 1):
            self._reader.query(f"RD,{cell:03d}", lambda p, r, c=cell: on_reply(c, p, r))

    def _boat_layout(self) -> BoatLayout:
        s = self._qr_reader_settings
        return build_layout(self._reader_regions or None, s["preview_rotation"], s["cell_override"], s["expected_count"])

    def _update_reader_chip(self, state: str) -> None:
        if not hasattr(self, "btn_reader_status"):
            return
        color, label = _STATE_STYLE.get(state, (FG2, state))
        s = self._qr_reader_settings
        self.btn_reader_status.setText(f"● Reader {s['host']}  {label}")
        # 상태 바(Theme 버튼 왼쪽)의 칩 규격: 투명 배경 · 11px · 얇은 테두리, 글자색만 상태별
        self.btn_reader_status.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {BG2}; border-radius: 3px; "
            f"padding: 2px 8px; font-size: 11px; color: {color}; }}"
            f"QPushButton:hover {{ border-color: {color}; }}"
        )
        self.btn_reader_status.setToolTip(
            f"SR-X300W {s['host']}:{s['port']} — {label}\n클릭하면 리더기 설정을 엽니다."
        )
        if hasattr(self, "btn_cassette_scan"):
            self.btn_cassette_scan.setEnabled(state == ReaderState.CONNECTED.value)

    def _on_reader_frame(self, frame: ParsedFrame) -> None:
        self._last_frame = frame
        ng = frame.ng_cells
        ms = f" ({frame.scan_time_ms} ms)" if frame.scan_time_ms is not None else ""
        self.logger.ok(
            f"다중 QR 스캔: {len(frame.reads)}칸 중 {len(frame.reads) - len(ng)} 판독, NG {len(ng)}{ms}"
        )
        if hasattr(self, "btn_read_review"):
            self.btn_read_review.setEnabled(True)
        self._auto_apply_frame(frame)

    # ─── R6: 계획 → 즉시 적용 / 검토 창 ───

    def _plan_for_frame(self, frame: ParsedFrame) -> tuple[AssignPlan, list] | None:
        """프레임 → (계획, 대상 세트). 폴더 미로드·ATX 혼재·override 오류면 로그 후 None."""
        sets = list(self._atx_folder_sets()) if hasattr(self, "_atx_folder_sets") else []
        if not sets:
            self.logger.warn("로드된 ATX 폴더가 없습니다 — 폴더를 먼저 로드한 뒤 다중 QR 스캔을 실행하세요")
            return None
        atx_numbers = self._loaded_atx_numbers(sets)
        if len(atx_numbers) > 1:
            # 셀 → (port, slot) 공식에는 ATX 가 없으므로 ATX 가 섞이면 어느 폴더에 쓸지 결정할 수 없다 → 차단
            self.logger.error(
                "로드된 폴더의 ATX 번호가 여러 개입니다 (ATX "
                + ", ".join(map(str, sorted(atx_numbers)))
                + ") — 다중 QR 스캔 대상 ATX 폴더만 남기고 다시 스캔하세요"
            )
            return None
        atx = next(iter(atx_numbers), None)
        try:
            plan = build_plan(
                frame, sets,
                atx=atx,
                override=self._qr_reader_settings["cell_override"],
                set_for_port=self._set_for_port(sets, atx),
            )
        except AssignError as exc:
            self.logger.error(f"다중 QR 판독 대응 실패: {exc}")
            return None
        return plan, sets

    def _auto_apply_frame(self, frame: ParsedFrame) -> None:
        """스캔 직후: 레코드가 있는 칸(APPLY)만 현재 창에 바로 QR 입력. 나머지는 요약 로그 (상세는 '판독 검토')."""
        result = self._plan_for_frame(frame)
        if result is None:
            return
        plan, sets = result
        counts = plan.counts()
        skipped = [
            f"{label} {counts[st]}"
            for st, label in (
                (AssignStatus.NO_RECORD, "레코드 없음"), (AssignStatus.NG, "NG"), (AssignStatus.CONFLICT, "충돌"),
                (AssignStatus.DUP_FRAME, "중복(프레임)"), (AssignStatus.DUP_LOADED, "중복(기존)"),
                (AssignStatus.SAME, "동일"), (AssignStatus.EXCLUDED, "제외"),
            )
            if counts[st]
        ]
        items = plan.applicable
        if items:
            self._apply_batch(items, sets)
        else:
            self.logger.warn("다중 QR 판독: 바로 적용할 칸이 없습니다")
        if skipped:
            self.logger.info("적용 제외 — " + ", ".join(skipped) + " (상세·덮어쓰기는 '판독 검토')")

    def _open_read_review(self) -> None:
        """'판독 검토' 버튼: 마지막 스캔 프레임을 실물 배치대로 펼쳐 보여 주고, [적용] 시 선택 항목(충돌 덮어쓰기 등)을 적용."""
        frame = self._last_frame
        if frame is None:
            self.logger.warn("검토할 다중 QR 스캔 결과가 없습니다 — 먼저 다중 QR 스캔을 실행하세요")
            return
        result = self._plan_for_frame(frame)
        if result is None:
            return
        plan, sets = result

        from src.ui.dialogs.batch_read_review_dialog import BatchReadReviewDialog

        dlg = BatchReadReviewDialog(plan, sets, frame.scan_time_ms, layout=self._boat_layout(), parent=self)
        dlg.rescan_requested.connect(lambda: (dlg.reject(), self._scan_cassette()))
        try:
            if dlg.exec() != QDialog.Accepted:
                self.logger.info("판독 검토 닫음 (변경 없음)")
                return
            items = dlg.selected_items()
        finally:
            dlg.deleteLater()
        if items:
            self._apply_batch(items, sets)
        else:
            self.logger.info("판독 검토: 적용할 칸이 없습니다")

    @staticmethod
    def _loaded_atx_numbers(sets) -> set[int]:
        numbers: set[int] = set()
        for ms in sets:
            for sd in ms.slots:
                try:
                    numbers.add(parse_slot_code(sd.slot_code)["atx"])
                except (ValueError, IndexError):
                    continue
        return numbers

    def _set_for_port(self, sets, atx: int | None) -> dict[int, int]:
        """같은 Port 가 여러 폴더에 있으면 탭 순서(①②③…)의 앞 폴더를 대상으로 삼는다 (같은 ATX 안에서)."""
        mapping: dict[int, int] = {}
        shadowed: list[str] = []
        for si, ms in enumerate(sets):
            ports = set()
            for sd in ms.slots:
                try:
                    info = parse_slot_code(sd.slot_code)
                except (ValueError, IndexError):
                    continue
                if atx is None or info["atx"] == atx:
                    ports.add(info["port"])
            for port in sorted(ports):
                if port in mapping:
                    shadowed.append(f"Port {port}: {ms.po_number} (탭 {si + 1}) → {sets[mapping[port]].po_number} (탭 {mapping[port] + 1}) 사용")
                else:
                    mapping[port] = si
        for line in shadowed:
            self.logger.warn(f"같은 Port 폴더 중복 — {line}")
        return mapping

    def _grid_for_set(self, ms):
        for rec in getattr(self, "_folder_tabs", []):
            if rec.get("set") is ms:
                return rec.get("grid")
        return None

    def _apply_batch(self, items: list[AssignItem], sets) -> None:
        touched: dict[int, object] = {}
        overwritten = 0
        for it in items:
            if it.set_index is None or it.target is None or it.code is None:
                continue
            ms = sets[it.set_index]
            slot = it.target
            if slot.qr_id and slot.qr_id != it.code:
                overwritten += 1
                self.logger.warn(f"덮어쓰기: {format_full_label(slot.slot_code)} {slot.qr_id} → {it.code}")
            slot.qr_id = it.code
            touched[it.set_index] = ms
            grid = self._grid_for_set(ms)
            if grid is not None:
                grid.update_slot(slot)

        for ms in touched.values():
            try:
                ms.db_id = self._auto_save_to_db(ms)
            except Exception as exc:  # DB 실패 시 화면 데이터는 유지 (기존 Pool 경로와 동일)
                self.logger.error(f"DB 저장 실패 ({ms.po_number}, 화면 데이터는 유지됨): {exc}")

        # 순서 주의: _pool_refresh_view 는 진행률 바를 Pool 기준으로 덮어쓰므로,
        # 폴더 뷰가 활성이면 마지막에 _update_progress 로 활성 폴더 기준으로 되돌린다.
        for name in ("_atx_refresh_tab_labels", "_pool_refresh_view"):
            fn = getattr(self, name, None)
            if callable(fn):
                fn()
        pool_active = getattr(self, "_atx_pool_active", lambda: False)()
        if not pool_active and callable(getattr(self, "_update_progress", None)):
            self._update_progress()
        self.logger.ok(
            f"다중 QR 판독 적용: {len(items)}칸 매칭 (폴더 {len(touched)}개"
            + (f", 덮어쓰기 {overwritten}" if overwritten else "") + ")"
        )

    def _on_reader_command_error(self, cmd: str, code: str) -> None:
        if code == "23":
            self.logger.error("리더기가 AutoID Network Navigator 에 연결되어 있어 명령을 받지 않습니다 — Navigator 에서 연결 해제 필요")
        else:
            self.logger.error(f"리더기 명령 오류 ER,{cmd},{code}")

    # ─── 동작 ───

    def _scan_cassette(self) -> None:
        if self._qr_reader_settings["transport"] != "lan":
            self.logger.warn("리더기 전송 방식이 LAN 이 아닙니다 — 리더기 설정에서 변경하세요")
            return
        if not self._reader.is_connected():
            self.logger.warn("리더기가 연결되지 않았습니다")
            return
        if self._reader.trigger():
            self.logger.info(f"다중 QR 스캔 시작 (LON → {self._qr_reader_settings['read_seconds']:g}s → LOFF)")

    def _open_qr_reader_settings(self) -> None:
        from src.ui.dialogs.qr_reader_settings_dialog import QRReaderSettingsDialog

        dlg = QRReaderSettingsDialog(self._qr_reader_settings, self)
        dlg.rotation_applied.connect(self._save_preview_rotation)
        try:
            if dlg.exec() != QDialog.Accepted:
                return
            new_settings = dlg.result_settings()
        finally:
            dlg.deleteLater()
        self._qr_reader_settings = save_qr_reader_settings(self._db_conn, new_settings)
        # 저장 = 이 리더기를 쓰겠다는 뜻이므로 LAN 이면 즉시 접속 (자동 접속 체크는 다음 앱 시작에만 영향)
        self._apply_reader_settings(connect_now=True)
        self.logger.ok(
            "리더기 설정이 저장되었습니다"
            + ("" if self._qr_reader_settings["transport"] == "lan" else " (LAN 이 아니므로 접속하지 않음)")
        )

    def _save_preview_rotation(self, deg: int) -> None:
        """미리보기 창 [적용]: 회전만 즉시 저장 (다른 설정·접속 상태는 그대로)."""
        self._qr_reader_settings = save_qr_reader_settings(
            self._db_conn, dict(self._qr_reader_settings, preview_rotation=deg))
        self.logger.ok(f"판독 미리보기 회전 {deg}° 저장 — 판독 검토 창도 이 배치를 따릅니다")

    def _shutdown_qr_reader(self) -> None:
        reader = getattr(self, "_reader", None)
        if reader is not None:
            reader.close()
