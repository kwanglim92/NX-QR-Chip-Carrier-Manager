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
    display_size,
    parse_region,
    rotate_region,
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
    """리더기 화상 기준 개략 배치 — 현장 번호 순서(2026-09-09): 셀은 세로로 1→4, 카세트 1·2 는 오른쪽 열 위·아래."""
    r = schematic_regions(72)
    assert len(r) == 72 and all(0 <= x0 < x1 <= IMAGE_W and 0 <= y0 < y1 <= IMAGE_H for x0, y0, x1, y1 in r.values())
    assert r[2][1] > r[1][1] and r[2][0] == r[1][0]      # 같은 열, 아래
    assert r[5][0] > r[1][0] and r[5][1] == r[1][1]      # 다음 열
    assert r[13][0] == r[1][0] and r[13][1] > r[4][1]    # 카세트 2 는 카세트 1 아래(같은 열)
    assert r[25][0] < r[1][0] and r[25][1] == r[1][1]    # 카세트 3 은 왼쪽
    assert r[72][2] <= IMAGE_W and r[72][3] <= IMAGE_H


def test_rotate_region_matches_physical_boat():
    # 실기기 RD,001 (좌상단) — 시계 90° 회전 → 세로 화상의 우상단, 반시계 → 좌하단
    r1 = (351, 48, 497, 177)
    assert rotate_region(r1, 0) == r1
    assert rotate_region(r1, 90) == (IMAGE_H - 177, 351, IMAGE_H - 48, 497)
    assert rotate_region(r1, 270) == (48, IMAGE_W - 497, 177, IMAGE_W - 351)
    assert rotate_region(r1, 180) == (IMAGE_W - 497, IMAGE_H - 177, IMAGE_W - 351, IMAGE_H - 48)
    assert display_size(90) == (IMAGE_H, IMAGE_W) and display_size(0) == (IMAGE_W, IMAGE_H)


def test_port_frames_form_boat_layout(qapp):
    """회전 90° 후 카세트(Port) 6개가 2열×3행, 카세트마다 4열×3행 — 실물 보트 배치."""
    c = FramePreviewCanvas()
    c.set_regions(schematic_regions(72), schematic=True)
    c.set_rotation(90)
    frames = c.port_frames()
    assert sorted(frames) == [1, 2, 3, 4, 5, 6]
    xs = sorted({(f[0] + f[2]) // 2 for f in frames.values()})
    ys = sorted({(f[1] + f[3]) // 2 for f in frames.values()})
    assert len(xs) == 2 and len(ys) == 3                       # 2열 × 3행
    cells = [r for cell, r in c.display_regions().items() if 1 <= cell <= 12]
    cols = {(r[0] + r[2]) // 2 for r in cells}
    rows = {(r[1] + r[3]) // 2 for r in cells}
    assert len(cols) == 4 and len(rows) == 3                    # 카세트당 4열 × 3행
    boat = c.boat_frame()
    assert boat is not None and boat[0] < min(f[0] for f in frames.values()) and boat[1] < min(f[1] for f in frames.values())
    bx0, by0, bx1, by1 = c.content_bounds()
    assert bx0 < boat[0] and by0 < boat[1] and bx1 > boat[2] and by1 > boat[3]
    assert frames[1][1] < min(r[1] for r in cells)                # 카세트 라벨 띠가 셀 위에 있다
    c.set_rotation(0)
    assert len({(f[0] + f[2]) // 2 for f in c.port_frames().values()}) == 3   # 리더기 화상 그대로면 3열 × 2행


def test_canvas_hit_test_and_tooltip(qapp):
    c = FramePreviewCanvas()
    c.resize(600, 900)
    c.set_regions(schematic_regions(72), schematic=False)
    for rot in (0, 90, 180, 270):
        c.set_rotation(rot)
        inside = c._rect(c.regions[13]).center()
        assert c.cell_at(inside) == 13, rot
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

    got, applied = [], []
    dlg.rotation_changed.connect(got.append)
    dlg.rotation_applied.connect(applied.append)
    assert dlg.rotation == 270 and "회전 270°" in dlg.status_label.text()
    dlg._rotate()
    assert dlg.rotation == 0 and got == [0] and "회전 0°" in dlg.status_label.text()
    dlg.btn_apply.click()                                # [적용] → 현재 회전 저장 요청
    assert applied == [0] and "회전 0° 적용됨" in dlg.status_label.text()
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
