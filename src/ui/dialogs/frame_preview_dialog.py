"""판독 미리보기 창 — 리더기 서치 영역을 실제 좌표대로 그리고 판독 결과를 칸에 표시 (설계 §4 "테스트 판독 미리보기").

- 리더기 ``RD,nnn`` 로 영역 좌표(1920×1200 화상 기준, ``aaaabbbbccccdddd``)를 읽어 그린다. AutoID Network Navigator 없이
  어느 칸이 몇 번인지, 셀 → Port/Slot 대응이 어떻게 되는지 확인할 수 있다.
- 접속 불가·좌표 미정의면 규약(카세트 2행×3열, 카세트당 3열×4행)대로 그린 개략 배치를 보여준다.
- ``[다시 판독]`` 은 임시 클라이언트로 LON→LOFF 를 수행해 칸을 갱신한다. 매칭·DB 는 건드리지 않는다.
- 비모달. 창 닫힘과 함께 임시 클라이언트를 정리한다.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core.qr_reader.keyence_client import KeyenceClient
from src.core.qr_reader.payload_parser import ParsedFrame
from src.core.qr_reader.settings import client_kwargs, normalize_qr_reader_settings
from src.core.qr_reader.slot_assigner import SLOTS_PER_PORT, cell_to_port_slot
from src.ui.theme import ACCENT, BG, BG2, BG3, BG4, FG, FG2, FG3, GREEN, RED, TEAL, YELLOW

IMAGE_W, IMAGE_H = 1920, 1200          # SR-X300W 화상 좌표계
Region = tuple[int, int, int, int]     # (x0, y0, x1, y1)


def parse_region(payload: str) -> Region | None:
    """``RD`` 응답 ``aaaabbbbccccdddd`` → (x0, y0, x1, y1). 미정의(전부 0)나 형식 오류는 None."""
    text = payload.strip()
    if len(text) != 16 or not text.isdigit():
        return None
    x0, y0, x1, y1 = (int(text[i:i + 4]) for i in range(0, 16, 4))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def schematic_regions(count: int) -> dict[int, Region]:
    """좌표를 못 읽을 때 쓰는 개략 배치 — 카세트 2행×3열, 카세트당 3열×4행(규약 순서)."""
    regions: dict[int, Region] = {}
    cell_w, cell_h, gap = 146, 129, 3
    cas_w, cas_h = 3 * (cell_w + gap) + 60, 4 * (cell_h + gap) + 40
    for cell in range(1, count + 1):
        cas = (cell - 1) // SLOTS_PER_PORT
        i = (cell - 1) % SLOTS_PER_PORT
        cx, cy = 351 + (cas % 3) * cas_w, 48 + (cas // 3) * cas_h
        x0 = cx + (i % 3) * (cell_w + gap)
        y0 = cy + (i // 3) * (cell_h + gap)
        regions[cell] = (x0, y0, x0 + cell_w, y0 + cell_h)
    return regions


class FramePreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.regions: dict[int, Region] = {}
        self.codes: dict[int, str | None] = {}     # cell → code (None = NG). 비어 있으면 판독 전
        self.override: dict[int, tuple[int, int]] = {}
        self.schematic = True
        self.setMinimumSize(640, 400)
        self.setMouseTracking(True)

    def set_regions(self, regions: dict[int, Region], schematic: bool) -> None:
        self.regions = dict(regions)
        self.schematic = schematic
        self.update()

    def set_frame(self, frame: ParsedFrame | None) -> None:
        self.codes = {r.cell: r.code for r in frame.reads} if frame else {}
        self.update()

    def _transform(self) -> tuple[float, float, float]:
        scale = min(self.width() / IMAGE_W, self.height() / IMAGE_H)
        ox = (self.width() - IMAGE_W * scale) / 2
        oy = (self.height() - IMAGE_H * scale) / 2
        return scale, ox, oy

    def _rect(self, region: Region) -> QRectF:
        s, ox, oy = self._transform()
        x0, y0, x1, y1 = region
        return QRectF(ox + x0 * s, oy + y0 * s, (x1 - x0) * s, (y1 - y0) * s)

    def cell_at(self, pos) -> int | None:
        for cell, region in self.regions.items():
            if self._rect(region).contains(pos):
                return cell
        return None

    def mouseMoveEvent(self, event) -> None:
        cell = self.cell_at(event.position())
        if cell is None:
            self.setToolTip("")
            return
        port, slot = cell_to_port_slot(cell, self.override)
        code = self.codes.get(cell, "—") if self.codes else "(판독 전)"
        x0, y0, x1, y1 = self.regions[cell]
        self.setToolTip(f"셀 {cell} → Port {port} Slot {slot}\n코드: {code if code else 'NG (미판독)'}\n영역 ({x0},{y0})–({x1},{y1})")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG))
        s, ox, oy = self._transform()
        p.setPen(QPen(QColor(BG3), 1))
        p.setBrush(QColor("#11111b"))
        p.drawRect(QRectF(ox, oy, IMAGE_W * s, IMAGE_H * s))

        small = QFont(self.font())
        small.setPixelSize(max(8, int(11 * s * 2.2)))
        code_font = QFont(self.font())
        code_font.setPixelSize(max(8, int(12 * s * 2.2)))
        code_font.setBold(True)

        for cell, region in sorted(self.regions.items()):
            r = self._rect(region)
            has_frame = bool(self.codes)
            code = self.codes.get(cell) if has_frame else None
            if not has_frame:
                border, fill, text_color = QColor(ACCENT), QColor(BG2), QColor(FG2)
            elif code is None:
                border, fill, text_color = QColor(BG4), QColor(BG3), QColor(FG3)
            else:
                border, fill, text_color = QColor(GREEN), QColor(BG2), QColor(GREEN)
            p.setPen(QPen(border, 2 if has_frame and code else 1, Qt.DashLine if self.schematic else Qt.SolidLine))
            p.setBrush(fill)
            p.drawRoundedRect(r, 4, 4)

            port, slot = cell_to_port_slot(cell, self.override)
            p.setFont(small)
            p.setPen(QColor(FG2))
            p.drawText(r.adjusted(4, 2, -4, -2), Qt.AlignLeft | Qt.AlignTop, f"{cell}")
            p.drawText(r.adjusted(4, 2, -4, -2), Qt.AlignRight | Qt.AlignTop, f"P{port}·S{slot}")
            if has_frame:
                p.setFont(code_font)
                p.setPen(text_color)
                label = code if code else "NG"
                p.drawText(r.adjusted(3, 0, -3, -3), Qt.AlignHCenter | Qt.AlignBottom, label)
        p.end()


class FramePreviewDialog(QDialog):
    def __init__(self, settings: dict, frame: ParsedFrame | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("판독 미리보기 — 리더기 서치 영역")
        self.setModal(False)
        self.resize(1000, 700)
        self._settings = normalize_qr_reader_settings(settings)
        self._client: KeyenceClient | None = None
        self._regions: dict[int, Region] = {}
        self._pending = 0

        outer = QVBoxLayout(self)
        head = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        head.addWidget(self.status_label, 1)
        self.btn_reload = QPushButton("영역 다시 읽기")
        self.btn_reload.clicked.connect(self._load_regions)
        self.btn_read = QPushButton("다시 판독")
        self.btn_read.setProperty("accent", "true")
        self.btn_read.clicked.connect(self._read_again)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        for b in (self.btn_reload, self.btn_read, btn_close):
            head.addWidget(b)
        outer.addLayout(head)

        self.canvas = FramePreviewCanvas()
        self.canvas.override = dict(self._settings["cell_override"])
        outer.addWidget(self.canvas, 1)

        legend = QLabel("실선 = 리더기에서 읽은 실제 서치 영역 · 점선 = 개략 배치(좌표 미확인) · 초록 = 판독 · 회색 = NG · 칸 위에 마우스를 올리면 상세")
        legend.setStyleSheet(f"color: {FG3}; font-size: 11px;")
        outer.addWidget(legend)

        self.canvas.set_regions(schematic_regions(self._settings["expected_count"]), schematic=True)
        self.set_frame(frame)
        self._load_regions()

    # ─── 상태 ───

    def set_frame(self, frame: ParsedFrame | None) -> None:
        self.canvas.set_frame(frame)
        if frame is not None:
            ng = frame.ng_cells
            ms = f", {frame.scan_time_ms} ms" if frame.scan_time_ms is not None else ""
            self._frame_text = f"판독 {len(frame.reads) - len(ng)}/{len(frame.reads)}, NG {len(ng)}칸{ms}"
        else:
            self._frame_text = "판독 전"
        self._refresh_status()

    def _refresh_status(self, extra: str = "") -> None:
        n = len(self._regions)
        src = f"실제 영역 {n}개" if n else "개략 배치 (영역 좌표 미확인)"
        self.status_label.setText(f"{self._settings['host']}:{self._settings['port']} · {src} · {self._frame_text}" + (f" · {extra}" if extra else ""))

    # ─── 임시 클라이언트 ───

    def _ensure_client(self) -> KeyenceClient:
        if self._client is None:
            c = KeyenceClient(self)
            c.configure(auto_reconnect=False, **client_kwargs(self._settings))
            c.comm_error.connect(lambda m: self._refresh_status(f"통신: {m}"))
            c.frame_received.connect(self._on_frame)
            c.frame_rejected.connect(lambda m: self._refresh_status(f"프레임 거부: {m}"))
            c.command_error.connect(lambda cmd, code: self._refresh_status(f"명령 오류 ER,{cmd},{code}"))
            self._client = c
        return self._client

    def _when_connected(self, action) -> None:
        client = self._ensure_client()
        if client.is_connected():
            action()
            return

        def on_state(st: str) -> None:
            if st == "connected":
                client.state_changed.disconnect(on_state)
                action()
        client.state_changed.connect(on_state)
        client.open()

    def _load_regions(self) -> None:
        count = self._settings["expected_count"]
        self.btn_reload.setEnabled(False)
        self._refresh_status("영역 좌표 읽는 중…")
        found: dict[int, Region] = {}
        self._pending = count

        def on_reply(cell: int, payload: str | None, reason: str) -> None:
            self._pending -= 1
            if payload is not None:
                region = parse_region(payload)
                if region is not None:
                    found[cell] = region
            if self._pending == 0:
                self.btn_reload.setEnabled(True)
                if found:
                    self._regions = found
                    self.canvas.set_regions(found, schematic=False)
                    missing = count - len(found)
                    self._refresh_status(f"미정의 영역 {missing}개" if missing else "")
                else:
                    self._regions = {}
                    self._refresh_status(reason or "영역 좌표를 읽지 못했습니다")

        def start() -> None:
            client = self._ensure_client()
            for cell in range(1, count + 1):
                client.query(f"RD,{cell:03d}", lambda payload, reason, c=cell: on_reply(c, payload, reason))

        self._when_connected(start)

    def _read_again(self) -> None:
        self.btn_read.setEnabled(False)
        self._refresh_status("판독 중…")
        self._when_connected(lambda: self._ensure_client().trigger())

    def _on_frame(self, frame: ParsedFrame) -> None:
        self.btn_read.setEnabled(True)
        self.set_frame(frame)

    def closeEvent(self, event) -> None:
        # 클라이언트는 이 창의 자식이라 창과 함께 파괴된다. deleteLater 를 따로 걸면 창이 먼저 파괴될 때 이중 삭제로 abort.
        if self._client is not None:
            self._client.close()
            self._client = None
        super().closeEvent(event)
