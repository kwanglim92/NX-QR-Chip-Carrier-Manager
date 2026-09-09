"""보트/카세트 배치 계산 — 리더기 서치 영역 좌표를 실물 배치의 격자 위치로 옮긴다 (Qt 무관).

- 실물: 보트(Boat) 1장 = 카세트(Port) 6개 세로 2열×3행, 카세트마다 칩 4열×3행(12개).
- 리더기 화상(1920×1200)에는 보트가 눕혀져 잡히므로 ``preview_rotation``(기본 270°) 만큼 돌린 좌표로 배치를 계산한다.
- 판독 미리보기(그리기)와 카세트 판독 검토(카드 격자)가 같은 배치를 쓰도록 여기서 한 번만 계산한다.
- 리더기에서 ``RD`` 좌표를 못 읽으면 ``schematic_regions`` (현장 확인 2026-09-09 의 번호 순서) 를 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.core.qr_reader.slot_assigner import SLOTS_PER_PORT, cell_to_port_slot

IMAGE_W, IMAGE_H = 1920, 1200          # SR-X300W 화상 좌표계
Region = tuple[int, int, int, int]     # (x0, y0, x1, y1)

CELL_W, CELL_H, CELL_GAP = 146, 129, 3


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
    """좌표를 못 읽을 때 쓰는 개략 배치 (리더기 화상 기준).

    현장 확인(2026-09-09, 270° 회전 기준)과 같은 번호 순서:
    카세트 c(0-based) 는 화상 (열 = 2 − c÷2, 행 = c%2), 카세트 안의 셀 i(0-based) 는 (열 = i÷4, 행 = i%4) —
    즉 270° 로 돌리면 Port 1·2 가 윗줄 왼쪽·오른쪽, 셀 1~4 가 카세트 맨 아랫줄 왼쪽→오른쪽이 된다.
    """
    regions: dict[int, Region] = {}
    cas_w, cas_h = 3 * (CELL_W + CELL_GAP) + 60, 4 * (CELL_H + CELL_GAP) + 40
    for cell in range(1, count + 1):
        cas = (cell - 1) // SLOTS_PER_PORT
        i = (cell - 1) % SLOTS_PER_PORT
        cas_col, cas_row = (2 - (cas // 2) % 3), cas % 2
        cx, cy = 351 + cas_col * cas_w, 48 + cas_row * cas_h
        x0 = cx + (i // 4) * (CELL_W + CELL_GAP)
        y0 = cy + (i % 4) * (CELL_H + CELL_GAP)
        regions[cell] = (x0, y0, x0 + CELL_W, y0 + CELL_H)
    return regions


def display_size(rotation: int) -> tuple[int, int]:
    """회전 후 화상 크기 (90/270 이면 가로·세로가 바뀐다)."""
    return (IMAGE_H, IMAGE_W) if rotation in (90, 270) else (IMAGE_W, IMAGE_H)


def rotate_region(region: Region, rotation: int) -> Region:
    """리더기 화상 좌표의 영역을 화면 표시용으로 회전(시계 방향 °). 결과도 (x0, y0, x1, y1) 정규화."""
    x0, y0, x1, y1 = region
    if rotation == 90:
        pts = [(IMAGE_H - y, x) for x, y in ((x0, y0), (x1, y1))]
    elif rotation == 180:
        pts = [(IMAGE_W - x, IMAGE_H - y) for x, y in ((x0, y0), (x1, y1))]
    elif rotation == 270:
        pts = [(y, IMAGE_W - x) for x, y in ((x0, y0), (x1, y1))]
    else:
        return region
    (ax, ay), (bx, by) = pts
    return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)


def bbox(regions, pad: int = 0) -> Region:
    xs0, ys0, xs1, ys1 = zip(*regions)
    return min(xs0) - pad, min(ys0) - pad, max(xs1) + pad, max(ys1) + pad


def _cluster(values: list[float], tolerance: float) -> dict[float, int]:
    """값을 오름차순으로 묶어 군집 번호(0..)를 매긴다. 인접 값 차이가 tolerance 이하면 같은 군집."""
    out: dict[float, int] = {}
    idx = -1
    prev: float | None = None
    for v in sorted(set(values)):
        if prev is None or v - prev > tolerance:
            idx += 1
        out[v] = idx
        prev = v
    return out


def _grid_positions(regions: dict[int, Region]) -> dict[int, tuple[int, int]]:
    """영역 중심을 행/열로 군집화 → {key: (row, col)}. 허용 오차는 영역 크기의 절반."""
    if not regions:
        return {}
    cx = {k: (r[0] + r[2]) / 2 for k, r in regions.items()}
    cy = {k: (r[1] + r[3]) / 2 for k, r in regions.items()}
    tol_x = max(r[2] - r[0] for r in regions.values()) / 2
    tol_y = max(r[3] - r[1] for r in regions.values()) / 2
    cols = _cluster(list(cx.values()), tol_x)
    rows = _cluster(list(cy.values()), tol_y)
    return {k: (rows[cy[k]], cols[cx[k]]) for k in regions}


@dataclass
class BoatLayout:
    """실물 배치 격자: Port 패널 위치와 셀 카드 위치 (모두 (row, col), 0-based, 회전 적용 후)."""

    rotation: int
    schematic: bool
    port_positions: dict[int, tuple[int, int]] = field(default_factory=dict)
    cell_positions: dict[int, tuple[int, int]] = field(default_factory=dict)
    display_regions: dict[int, Region] = field(default_factory=dict)

    @property
    def port_cols(self) -> int:
        return 1 + max((c for _r, c in self.port_positions.values()), default=0)

    @property
    def port_rows(self) -> int:
        return 1 + max((r for r, _c in self.port_positions.values()), default=0)

    def cell_cols(self, port: int) -> int:
        cols = [c for cell, (_r, c) in self.cell_positions.items() if cell_to_port_slot(cell, {})[0] == port]
        return 1 + max(cols, default=0)


def build_layout(regions: dict[int, Region] | None, rotation: int, override: dict | None = None,
                 count: int = 72) -> BoatLayout:
    """리더기 영역(없으면 개략 배치)을 회전해 Port 패널·셀 격자 위치를 계산한다.

    - 셀 위치는 같은 Port 안에서 상대적인 (row, col).
    - Port 패널 위치는 각 Port 셀들의 경계 상자 중심으로 계산 (실물: 2열 × 3행).
    """
    schematic = not regions
    src = regions if regions else schematic_regions(count)
    override = override or {}
    disp = {cell: rotate_region(r, rotation) for cell, r in src.items()}

    by_port: dict[int, dict[int, Region]] = {}
    for cell, r in disp.items():
        port, _slot = cell_to_port_slot(cell, override)
        by_port.setdefault(port, {})[cell] = r

    cell_positions: dict[int, tuple[int, int]] = {}
    for port, cells in by_port.items():
        cell_positions.update(_grid_positions(cells))
    port_positions = _grid_positions({port: bbox(cells.values()) for port, cells in by_port.items()})
    return BoatLayout(rotation=rotation, schematic=schematic, port_positions=port_positions,
                      cell_positions=cell_positions, display_regions=disp)
