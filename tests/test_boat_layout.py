"""보트/카세트 배치 계산 — 회전·군집화·Port/셀 격자 위치 (Qt 무관)."""
from __future__ import annotations

from src.core.qr_reader.boat_layout import (
    IMAGE_H,
    IMAGE_W,
    _cluster,
    bbox,
    build_layout,
    display_size,
    parse_region,
    rotate_region,
    schematic_regions,
)


def test_cluster_groups_close_values():
    assert _cluster([10, 12, 100, 103, 250], 5) == {10: 0, 12: 0, 100: 1, 103: 1, 250: 2}
    assert _cluster([], 5) == {}


def test_build_layout_schematic_270_matches_physical_boat():
    lay = build_layout(None, 270, None, 72)
    assert lay.schematic and lay.rotation == 270
    assert lay.port_positions == {1: (0, 0), 2: (0, 1), 3: (1, 0), 4: (1, 1), 5: (2, 0), 6: (2, 1)}
    assert lay.port_cols == 2 and lay.port_rows == 3
    assert [lay.cell_positions[c] for c in (1, 2, 3, 4)] == [(2, 0), (2, 1), (2, 2), (2, 3)]
    assert [lay.cell_positions[c] for c in (5, 6, 7, 8)] == [(1, 0), (1, 1), (1, 2), (1, 3)]
    assert [lay.cell_positions[c] for c in (9, 10, 11, 12)] == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert lay.cell_positions[61] == (2, 0) and lay.cell_cols(1) == 4
    assert all(0 <= x0 < x1 <= IMAGE_H and 0 <= y0 < y1 <= IMAGE_W for x0, y0, x1, y1 in lay.display_regions.values())


def test_build_layout_rotation_0_is_reader_view():
    lay = build_layout(schematic_regions(72), 0, None, 72)
    assert not lay.schematic
    assert lay.port_cols == 3 and lay.port_rows == 2
    assert lay.port_positions[1] == (0, 2) and lay.port_positions[2] == (1, 2) and lay.port_positions[5] == (0, 0)
    assert [lay.cell_positions[c] for c in (1, 2, 3, 4)] == [(0, 0), (1, 0), (2, 0), (3, 0)]   # 세로로 1→4


def test_build_layout_uses_override_for_port_grouping():
    override = {1: (2, 1)}                     # 셀 1 을 Port 2 로 재정의 → Port 2 패널에 들어간다
    lay = build_layout(None, 270, override, 24)
    assert sorted(lay.port_positions) == [1, 2]
    assert 1 in lay.cell_positions and lay.cell_positions[1] == (2, 0)   # Port 1 자리를 비우고 Port 2 안에서 위치 계산


def test_parse_rotate_bbox_helpers():
    assert parse_region("0351004804970177") == (351, 48, 497, 177) and parse_region("0" * 16) is None
    assert rotate_region((351, 48, 497, 177), 270) == (48, IMAGE_W - 497, 177, IMAGE_W - 351)
    assert display_size(270) == (IMAGE_H, IMAGE_W)
    assert bbox([(0, 0, 10, 10), (20, 5, 30, 40)], 2) == (-2, -2, 32, 42)
