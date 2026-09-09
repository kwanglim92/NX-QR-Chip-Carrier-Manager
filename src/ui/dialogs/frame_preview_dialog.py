"""판독 미리보기 창 — 리더기 서치 영역을 실물 보트 배치처럼 그리고 판독 결과를 칸에 표시 (설계 §4 "테스트 판독 미리보기").

- 리더기 ``RD,nnn`` 로 영역 좌표(1920×1200 화상 기준, ``aaaabbbbccccdddd``)를 읽어 그린다. AutoID Network Navigator 없이
  어느 칸이 몇 번인지, 셀 → Port/Slot 대응이 어떻게 되는지 확인할 수 있다.
- **실물 배치**: 보트(Boat) 1장에 카세트 6개가 세로 2열×3행, 카세트마다 칩 4열×3행(12개). 리더기 화상에는 보트가 눕혀져
  (카세트 3열×2행, 카세트당 3열×4행) 잡히므로 ``preview_rotation``(기본 270°, 현장 확인) 만큼 돌려 실물처럼 세워 보여 준다.
  카세트(Port) 단위 테두리와 보트 테두리를 함께 그린다.
- 접속 불가·좌표 미정의면 규약대로 그린 개략 배치(점선)를 보여준다.
- ``[다시 판독]`` 은 임시 클라이언트로 LON→LOFF 를 수행해 칸을 갱신한다. 매칭·DB 는 건드리지 않는다.
- 비모달. 창 닫힘과 함께 임시 클라이언트를 정리한다.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core.qr_reader.boat_layout import (   # noqa: F401 — 테스트·호출자 호환을 위해 재노출
    IMAGE_H,
    IMAGE_W,
    Region,
    bbox as _bbox,
    display_size,
    parse_region,
    rotate_region,
    schematic_regions,
)
from src.core.qr_reader.keyence_client import KeyenceClient
from src.core.qr_reader.payload_parser import ParsedFrame
from src.core.qr_reader.settings import PREVIEW_ROTATIONS, client_kwargs, normalize_qr_reader_settings
from src.core.qr_reader.slot_assigner import cell_to_port_slot
from src.ui.theme import ACCENT, BG, BG2, BG3, BG4, FG, FG2, FG3, GREEN

CASSETTE_PAD = 14                      # 카세트 테두리 여백(화상 단위)
CASSETTE_LABEL_H = 30                  # 카세트 라벨(Port n) 띠 높이
CONTENT_MARGIN = 12                    # 보트 바깥 여백
BOAT_PAD = 34                          # 보트 테두리 여백
BOAT_TITLE_H = 44                      # 보트 제목 띠 높이


class FramePreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.regions: dict[int, Region] = {}       # 리더기 화상 좌표(원본)
        self.codes: dict[int, str | None] = {}     # cell → code (None = NG). 비어 있으면 판독 전
        self.override: dict[int, tuple[int, int]] = {}
        self.schematic = True
        self.rotation = 270
        self.setMinimumSize(480, 480)
        self.setMouseTracking(True)

    def set_regions(self, regions: dict[int, Region], schematic: bool) -> None:
        self.regions = dict(regions)
        self.schematic = schematic
        self.update()

    def set_frame(self, frame: ParsedFrame | None) -> None:
        self.codes = {r.cell: r.code for r in frame.reads} if frame else {}
        self.update()

    def set_rotation(self, rotation: int) -> None:
        self.rotation = rotation if rotation in PREVIEW_ROTATIONS else 0
        self.update()

    # ── 배치 계산 (표시 좌표 = 회전된 화상 단위) ──

    def display_regions(self) -> dict[int, Region]:
        return {cell: rotate_region(r, self.rotation) for cell, r in self.regions.items()}

    def port_frames(self) -> dict[int, Region]:
        """카세트(Port) 별 테두리 — 그 Port 에 대응하는 셀들의 경계 상자 + 여백."""
        groups: dict[int, list[Region]] = {}
        for cell, r in self.display_regions().items():
            port, _slot = cell_to_port_slot(cell, self.override)
            groups.setdefault(port, []).append(r)
        frames = {}
        for port, rs in sorted(groups.items()):
            x0, y0, x1, y1 = _bbox(rs, CASSETTE_PAD)
            frames[port] = (x0, y0 - CASSETTE_LABEL_H, x1, y1)     # 위쪽에 라벨 띠
        return frames

    def boat_frame(self) -> Region | None:
        frames = list(self.port_frames().values())
        if not frames:
            return None
        x0, y0, x1, y1 = _bbox(frames, BOAT_PAD)
        return x0, y0 - BOAT_TITLE_H, x1, y1

    def content_bounds(self) -> Region:
        """화면에 맞출 표시 영역 — 보트 테두리 + 여백. 영역이 없으면 회전된 화상 전체."""
        boat = self.boat_frame()
        if boat is None:
            w, h = display_size(self.rotation)
            return 0, 0, w, h
        x0, y0, x1, y1 = boat
        return x0 - CONTENT_MARGIN, y0 - CONTENT_MARGIN, x1 + CONTENT_MARGIN, y1 + CONTENT_MARGIN

    # ── 화면 변환 ──

    def _transform(self) -> tuple[float, float, float]:
        """표시 좌표 → 위젯 픽셀: (scale, ox, oy). 보트가 위젯을 꽉 채우도록 맞춘다."""
        bx0, by0, bx1, by1 = self.content_bounds()
        w, h = bx1 - bx0, by1 - by0
        scale = min(self.width() / w, self.height() / h)
        ox = (self.width() - w * scale) / 2 - bx0 * scale
        oy = (self.height() - h * scale) / 2 - by0 * scale
        return scale, ox, oy

    def _rect_display(self, region: Region) -> QRectF:
        s, ox, oy = self._transform()
        x0, y0, x1, y1 = region
        return QRectF(ox + x0 * s, oy + y0 * s, (x1 - x0) * s, (y1 - y0) * s)

    def _rect(self, region: Region) -> QRectF:
        """리더기 화상 좌표의 영역 → 화면 사각형(회전 적용)."""
        return self._rect_display(rotate_region(region, self.rotation))

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
        self.setToolTip(f"셀 {cell} → Port {port} Slot {slot}\n코드: {code if code else 'NG (미판독)'}\n리더기 영역 ({x0},{y0})–({x1},{y1})")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG))
        s, ox, oy = self._transform()

        small = QFont(self.font())
        small.setPixelSize(max(8, int(10 * s * 2.2)))
        code_font = QFont(self.font())
        code_font.setPixelSize(max(8, int(11 * s * 2.2)))
        code_font.setBold(True)
        title_font = QFont(self.font())
        title_font.setPixelSize(max(10, int(15 * s * 2.2)))
        title_font.setBold(True)
        label_font = QFont(self.font())
        label_font.setPixelSize(max(9, int(12 * s * 2.2)))
        label_font.setBold(True)
        line = Qt.DashLine if self.schematic else Qt.SolidLine

        # 보트 테두리 + 제목
        boat = self.boat_frame()
        if boat is not None:
            br = self._rect_display(boat)
            p.setPen(QPen(QColor(FG3), 2, line))
            p.setBrush(QColor("#11111b"))
            p.drawRoundedRect(br, 10, 10)
            p.setFont(title_font)
            p.setPen(QColor(FG))
            p.drawText(QRectF(br.left(), br.top(), br.width(), BOAT_TITLE_H * s), Qt.AlignCenter, "Boat")

        # 카세트(Port) 테두리 + 라벨
        for port, frame in self.port_frames().items():
            fr = self._rect_display(frame)
            p.setPen(QPen(QColor(BG4), 1.5, line))
            p.setBrush(QColor(BG))
            p.drawRoundedRect(fr, 8, 8)
            p.setFont(label_font)
            p.setPen(QColor(ACCENT))
            p.drawText(QRectF(fr.left() + 8 * s, fr.top(), fr.width() - 16 * s, CASSETTE_LABEL_H * s),
                       Qt.AlignLeft | Qt.AlignVCenter, f"Port {port}  (카세트 {port})")

        # 셀
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
            p.setPen(QPen(border, 2 if has_frame and code else 1, line))
            p.setBrush(fill)
            p.drawRoundedRect(r, 4, 4)

            _port, slot = cell_to_port_slot(cell, self.override)
            p.setFont(small)
            p.setPen(QColor(FG2))
            p.drawText(r.adjusted(4, 2, -4, -2), Qt.AlignLeft | Qt.AlignTop, f"{cell}")
            p.drawText(r.adjusted(4, 2, -4, -2), Qt.AlignRight | Qt.AlignTop, f"S{slot}")
            if has_frame:
                label = code if code else "NG"
                f = QFont(code_font)
                while f.pixelSize() > 7 and QFontMetricsF(f).horizontalAdvance(label) > r.width() - 6:
                    f.setPixelSize(f.pixelSize() - 1)          # 코드 10자리가 칸 폭에 들어가도록 축소
                p.setFont(f)
                p.setPen(text_color)
                p.drawText(r.adjusted(3, 0, -3, -3), Qt.AlignHCenter | Qt.AlignBottom, label)
        p.end()


class FramePreviewDialog(QDialog):
    rotation_changed = Signal(int)     # [회전] 으로 표시 방향이 바뀜 (설정 폼에 반영용)
    rotation_applied = Signal(int)     # [적용] — 현재 회전을 설정에 저장해 달라는 요청

    def __init__(self, settings: dict, frame: ParsedFrame | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("판독 미리보기 — 보트 / 카세트 배치")
        self.setModal(False)
        self.resize(820, 900)
        self._settings = normalize_qr_reader_settings(settings)
        self._client: KeyenceClient | None = None
        self._regions: dict[int, Region] = {}
        self._pending = 0

        outer = QVBoxLayout(self)
        head = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        self.status_label.setWordWrap(True)
        head.addWidget(self.status_label, 1)
        self.btn_rotate = QPushButton("회전 ↻")
        self.btn_rotate.setToolTip("표시 방향을 90° 씩 돌립니다 (0 → 90 → 180 → 270). 설정 창의 '미리보기 회전'에 반영됩니다.")
        self.btn_rotate.clicked.connect(self._rotate)
        self.btn_apply = QPushButton("적용")
        self.btn_apply.setToolTip("현재 회전 방향을 리더기 설정(미리보기 회전)에 바로 저장합니다. 카세트 판독 검토 창도 이 배치를 따릅니다.")
        self.btn_apply.clicked.connect(self._apply_rotation)
        self.btn_reload = QPushButton("영역 다시 읽기")
        self.btn_reload.clicked.connect(self._load_regions)
        self.btn_read = QPushButton("다시 판독")
        self.btn_read.setProperty("accent", "true")
        self.btn_read.clicked.connect(self._read_again)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        for b in (self.btn_rotate, self.btn_apply, self.btn_reload, self.btn_read, btn_close):
            head.addWidget(b)
        outer.addLayout(head)

        self.canvas = FramePreviewCanvas()
        self.canvas.override = dict(self._settings["cell_override"])
        self.canvas.set_rotation(self._settings["preview_rotation"])
        outer.addWidget(self.canvas, 1)

        legend = QLabel("실물 배치: 보트 1장 = 카세트(Port) 6개 2열×3행, 카세트당 칩 4열×3행 · 실선 = 리더기에서 읽은 실제 서치 영역 · "
                        "점선 = 개략 배치(좌표 미확인) · 초록 = 판독 · 회색 = NG · 칸 위에 마우스를 올리면 상세")
        legend.setWordWrap(True)
        legend.setStyleSheet(f"color: {FG3}; font-size: 11px;")
        outer.addWidget(legend)

        self.canvas.set_regions(schematic_regions(self._settings["expected_count"]), schematic=True)
        self.set_frame(frame)
        self._load_regions()

    # ─── 상태 ───

    @property
    def rotation(self) -> int:
        return self.canvas.rotation

    def _rotate(self) -> None:
        idx = PREVIEW_ROTATIONS.index(self.canvas.rotation)
        deg = PREVIEW_ROTATIONS[(idx + 1) % len(PREVIEW_ROTATIONS)]
        self.canvas.set_rotation(deg)
        self._settings["preview_rotation"] = deg
        self._refresh_status()
        self.rotation_changed.emit(deg)

    def _apply_rotation(self) -> None:
        self.rotation_applied.emit(self.canvas.rotation)
        self._refresh_status(f"회전 {self.canvas.rotation}° 적용됨")

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
        self.status_label.setText(
            f"{self._settings['host']}:{self._settings['port']} · {src} · 회전 {self.canvas.rotation}° · {self._frame_text}"
            + (f" · {extra}" if extra else ""))

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
