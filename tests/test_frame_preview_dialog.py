"""판독 미리보기 — RD 영역 파싱, 개략 배치, 캔버스 히트테스트, 가짜 리더기에서 영역 로드·재판독."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF

from src.core.qr_reader.payload_parser import parse_frame
from src.ui.dialogs.frame_preview_dialog import (
    IMAGE_H,
    IMAGE_W,
    FramePreviewCanvas,
    FramePreviewDialog,
    parse_region,
    schematic_regions,
)
from tests.test_qr_reader_client import FakeReader, wait_until

FULL_RAW = Path(__file__).parent / "fixtures" / "qr_reader" / "20260909_132804_full.raw"


def test_parse_region_real_payloads():
    assert parse_region("0351004804970177") == (351, 48, 497, 177)     # 실기기 RD,001
    assert parse_region("1640103417751164") == (1640, 1034, 1775, 1164)  # 실기기 RD,072
    assert parse_region("0000000000000000") is None                    # 미정의
    assert parse_region("abc") is None and parse_region("0500004804970177") is None  # x1<=x0


def test_schematic_regions_layout():
    r = schematic_regions(72)
    assert len(r) == 72 and all(0 <= x0 < x1 <= IMAGE_W and 0 <= y0 < y1 <= IMAGE_H for x0, y0, x1, y1 in r.values())
    assert r[2][0] > r[1][0] and r[2][1] == r[1][1]      # 같은 행, 오른쪽
    assert r[4][1] > r[1][1] and r[4][0] == r[1][0]      # 다음 행
    assert r[13][0] > r[3][0]                            # 카세트 2 는 오른쪽
    assert r[37][1] > r[12][1]                           # 카세트 4 는 아랫줄


def test_canvas_hit_test_and_tooltip(qapp):
    c = FramePreviewCanvas()
    c.resize(960, 600)
    c.set_regions(schematic_regions(72), schematic=False)
    x0, y0, x1, y1 = c.regions[13]
    s, ox, oy = c._transform()
    inside = QPointF(ox + (x0 + x1) / 2 * s, oy + (y0 + y1) / 2 * s)
    assert c.cell_at(inside) == 13
    assert c.cell_at(QPointF(1, 1)) is None
    c.set_frame(parse_frame(FULL_RAW.read_bytes()))
    assert c.codes[13] is None and c.codes[1] == "2680002971"
    c.grab()   # paintEvent 가 예외 없이 도는지


def test_dialog_loads_regions_from_reader_and_reads_again(qapp):
    server = FakeReader()
    dlg = FramePreviewDialog({"host": "127.0.0.1", "port": server.serverPort(), "read_seconds": 0.2})
    dlg.show()
    assert wait_until(lambda: len(dlg._regions) == 72, 5000)
    assert not dlg.canvas.schematic and dlg.canvas.regions[1] == schematic_regions(72)[1]
    assert "실제 영역 72개" in dlg.status_label.text() and "판독 전" in dlg.status_label.text()
    assert server.received[:2] == ["RD,001", "RD,002"] and server.received[71] == "RD,072"

    dlg._read_again()
    assert wait_until(lambda: dlg.canvas.codes.get(1) == "2680002971", 4000)
    assert "판독 70/72" in dlg.status_label.text() and dlg.btn_read.isEnabled()
    assert server.received[-2:] == ["LON", "LOFF"]
    dlg.close()
    assert dlg._client is None
    server.close()


def test_dialog_falls_back_to_schematic_when_regions_undefined(qapp):
    server = FakeReader()
    dlg = FramePreviewDialog({"host": "127.0.0.1", "port": server.serverPort(), "expected_count": 80})
    dlg.show()
    assert wait_until(lambda: dlg.btn_reload.isEnabled() and len(dlg._regions) == 72, 6000)
    assert "미정의 영역 8개" in dlg.status_label.text()
    dlg.close()
    server.close()


def test_dialog_without_reader_keeps_schematic(qapp):
    probe = FakeReader()
    port = probe.serverPort()
    probe.close()
    dlg = FramePreviewDialog({"host": "127.0.0.1", "port": port, "connect_timeout_s": 0.5}, parse_frame(FULL_RAW.read_bytes()))
    dlg.show()
    assert wait_until(lambda: "통신" in dlg.status_label.text() or dlg.btn_reload.isEnabled(), 4000)
    assert dlg.canvas.schematic and dlg.canvas.codes[13] is None and dlg.canvas.codes[72] == "2680086CBC"
    dlg.close()
