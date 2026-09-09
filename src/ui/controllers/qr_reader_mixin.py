"""키엔스 리더기 연결 컨트롤러 (설계 §4, R4).

- 설정(``app_settings.qr_reader``) 로드/저장 + 리더기 설정 다이얼로그
- 상시 ``KeyenceClient`` 1개: 상태 → 하단 바 상태 칩, 프레임 → 로그 + ``_last_frame`` 보관
- "카세트 스캔" 버튼(F10) → ``trigger()``
- R6: 프레임 → ``build_plan``(로드된 ATX 폴더 탭 순서, 설정의 cell_override) → 검토 다이얼로그 →
  [적용] 시 선택 항목의 ``slot.qr_id`` 갱신, 그리드·탭 라벨·진행률·Pass Pool 갱신, 폴더별 DB 자동 저장.
  (기존 단일 QR 경로 ``_match_qr_atx`` / ``_pool_on_qr_scanned`` 와 같은 저장 규칙)
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog

from src.core.qr_reader.keyence_client import KeyenceClient, ReaderState
from src.core.qr_reader.payload_parser import ParsedFrame
from src.core.qr_reader.settings import (
    client_kwargs,
    load_qr_reader_settings,
    save_qr_reader_settings,
)
from src.core.qr_reader.slot_assigner import AssignError, AssignItem, build_plan
from src.core.slot_mapper import format_full_label, parse_slot_code
from src.ui.theme import FG2, GREEN, ORANGE, RED, TEAL

_STATE_STYLE = {
    ReaderState.DISCONNECTED.value: (FG2, "미연결"),
    ReaderState.CONNECTING.value: (TEAL, "접속 중"),
    ReaderState.CONNECTED.value: (GREEN, "연결됨"),
    ReaderState.READING.value: (ORANGE, "판독 중"),
    ReaderState.RECONNECTING.value: (ORANGE, "재접속 중"),
}


class QRReaderMixin:
    def _init_qr_reader(self) -> None:
        """UI 구성 후 호출. 설정을 읽고 클라이언트를 만들며, enabled 면 접속한다."""
        self._qr_reader_settings = load_qr_reader_settings(self._db_conn)
        self._last_frame: ParsedFrame | None = None
        self._reader = KeyenceClient(self)
        self._reader.state_changed.connect(self._on_reader_state)
        self._reader.frame_received.connect(self._on_reader_frame)
        self._reader.frame_rejected.connect(lambda m: self.logger.warn(f"리더기 프레임 거부: {m}"))
        self._reader.command_error.connect(self._on_reader_command_error)
        self._reader.comm_error.connect(lambda m: self.logger.warn(f"리더기 통신: {m}"))
        self._apply_reader_settings()

    def _apply_reader_settings(self) -> None:
        """설정을 클라이언트에 반영. LAN + enabled 면 접속, 아니면 끊고 버튼 비활성."""
        s = self._qr_reader_settings
        self._reader.close()
        self._reader.configure(**client_kwargs(s))
        self._update_reader_chip(self._reader.state.value)
        if s["transport"] == "lan" and s["enabled"]:
            self._reader.open()

    # ─── UI 반응 ───

    def _on_reader_state(self, state: str) -> None:
        self._update_reader_chip(state)
        if state == ReaderState.CONNECTED.value:
            self.logger.info(f"리더기 연결됨 {self._reader.host}:{self._reader.port}")
        elif state == ReaderState.RECONNECTING.value:
            self.logger.warn("리더기 연결 끊김 — 재접속 시도 중")

    def _update_reader_chip(self, state: str) -> None:
        if not hasattr(self, "btn_reader_status"):
            return
        color, label = _STATE_STYLE.get(state, (FG2, state))
        s = self._qr_reader_settings
        self.btn_reader_status.setText(f"● Reader {s['host']}  {label}")
        self.btn_reader_status.setStyleSheet(
            f"QPushButton {{ color: {color}; font-size: 12px; text-align: left; }}"
        )
        self.btn_reader_status.setToolTip(
            f"SR-X300W {s['host']}:{s['port']} — {label}\n클릭하면 리더기 설정을 엽니다."
        )
        self.btn_cassette_scan.setEnabled(state == ReaderState.CONNECTED.value)

    def _on_reader_frame(self, frame: ParsedFrame) -> None:
        self._last_frame = frame
        ng = frame.ng_cells
        ms = f" ({frame.scan_time_ms} ms)" if frame.scan_time_ms is not None else ""
        self.logger.ok(
            f"카세트 스캔: {len(frame.reads)}칸 중 {len(frame.reads) - len(ng)} 판독, NG {len(ng)}{ms}"
        )
        self._review_frame(frame)

    # ─── R6: 계획 → 검토 → 일괄 적용 ───

    def _review_frame(self, frame: ParsedFrame) -> None:
        sets = list(self._atx_folder_sets()) if hasattr(self, "_atx_folder_sets") else []
        if not sets:
            self.logger.warn("로드된 ATX 폴더가 없습니다 — 폴더를 먼저 로드한 뒤 카세트 스캔을 실행하세요")
            return
        try:
            plan = build_plan(
                frame, sets,
                override=self._qr_reader_settings["cell_override"],
                set_for_port=self._set_for_port(sets),
            )
        except AssignError as exc:
            self.logger.error(f"카세트 판독 대응 실패: {exc}")
            return

        from src.ui.dialogs.batch_read_review_dialog import BatchReadReviewDialog

        dlg = BatchReadReviewDialog(plan, sets, frame.scan_time_ms, self)
        dlg.rescan_requested.connect(lambda: (dlg.reject(), self._scan_cassette()))
        if dlg.exec() != QDialog.Accepted:
            self.logger.info("카세트 판독 적용 취소")
            return
        self._apply_batch(dlg.selected_items(), sets)

    def _set_for_port(self, sets) -> dict[int, int]:
        """같은 Port 가 여러 폴더에 있으면 탭 순서(①②③…)의 앞 폴더를 대상으로 삼는다."""
        mapping: dict[int, int] = {}
        shadowed: list[str] = []
        for si, ms in enumerate(sets):
            ports = set()
            for sd in ms.slots:
                try:
                    ports.add(parse_slot_code(sd.slot_code)["port"])
                except (ValueError, IndexError):
                    continue
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

        for name in ("_atx_refresh_tab_labels", "_update_progress", "_pool_refresh_view"):
            fn = getattr(self, name, None)
            if callable(fn):
                fn()
        self.logger.ok(
            f"카세트 판독 적용: {len(items)}칸 매칭 (폴더 {len(touched)}개"
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
            self.logger.info(f"카세트 스캔 시작 (LON → {self._qr_reader_settings['read_seconds']:g}s → LOFF)")

    def _open_qr_reader_settings(self) -> None:
        from src.ui.dialogs.qr_reader_settings_dialog import QRReaderSettingsDialog

        dlg = QRReaderSettingsDialog(self._qr_reader_settings, self)
        if dlg.exec() != QDialog.Accepted:
            return
        self._qr_reader_settings = save_qr_reader_settings(self._db_conn, dlg.result_settings())
        self._apply_reader_settings()
        self.logger.ok("리더기 설정이 저장되었습니다")

    def _shutdown_qr_reader(self) -> None:
        reader = getattr(self, "_reader", None)
        if reader is not None:
            reader.close()
