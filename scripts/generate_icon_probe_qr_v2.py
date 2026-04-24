"""앱 아이콘 — 캔틸레버+QR 판독 컨셉 4가지 레이아웃 변주.

색상은 Slate+Cyan(P1) 통일 — 레이아웃 차이만 비교.

V1) Minimal      — 부가 요소 제거. 캔틸레버 + QR + 팁 + 빔
V2) Vertical     — 위에서 수직으로 내려오는 프로브
V3) Top View     — 대형 QR 중앙, 프로브 팁이 비스듬히 판독
V4) Sketch       — 사용자 스케치 복원: 칩 캐리어 프레임 + 내부 QR + 상단 수직 프로브
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, rounded_square_bg, save_ico,
)

# Slate + Cyan 팔레트 (P1 기준)
BG         = (51, 65, 85, 255)
PROBE      = (220, 228, 240, 255)
PROBE_EDGE = (165, 180, 200, 255)
QR_BG      = (250, 252, 254, 255)
QR_DARK    = (30, 41, 59, 255)
BEAM       = (34, 211, 238, 255)
CARRIER    = (75, 95, 125, 255)
CARRIER_EDGE = (130, 155, 185, 255)


def _draw_qr_5x5(draw: ImageDraw.ImageDraw,
                  x0: float, y0: float, side: float,
                  bg, fg,
                  pattern: list[str] | None = None) -> None:
    """5x5 pseudo-QR 그리기. 라벨 배경과 모듈 포함."""
    if pattern is None:
        pattern = [
            "11011",
            "10101",
            "11110",
            "10011",
            "11011",
        ]
    # 배경
    draw.rounded_rectangle(
        (x0, y0, x0 + side, y0 + side),
        radius=max(1, int(side * 0.06)),
        fill=bg, outline=fg, width=max(1, int(side * 0.03)),
    )
    cell = side / 5
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch == "1":
                cx = x0 + c * cell
                cy = y0 + r * cell
                gap = cell * 0.08
                draw.rectangle(
                    (cx + gap, cy + gap, cx + cell - gap, cy + cell - gap),
                    fill=fg,
                )


def _draw_beam(img: Image.Image, x: float, y0: float, y1: float,
               color, beam_w: int):
    """시안 스캔 빔 + 글로우 오버레이."""
    for radius_mult in (4, 2):
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.line(
            [(x, y0), (x, y1)],
            fill=(*color[:3], 60 if radius_mult == 4 else 110),
            width=beam_w * radius_mult,
        )
        img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    draw.line([(x, y0), (x, y1)], fill=color, width=beam_w)
    return img


# ─── V1: Minimal ─────────────────────────────────────────────────────────

def design_v1_minimal(size: int = BASE_SIZE) -> Image.Image:
    """부가 요소 제거: 캔틸레버(대각) + QR + 팁 + 빔만."""
    img = rounded_square_bg(size, BG, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 캔틸레버 암 (좌상 → 우중앙 대각)
    arm_points = [
        (size * 0.08, size * 0.18),   # 좌상 위
        (size * 0.16, size * 0.10),   # 좌상 시작점
        (size * 0.68, size * 0.50),   # 우하 위
        (size * 0.72, size * 0.58),   # 우하 아래
        (size * 0.10, size * 0.28),   # 좌상 아래
    ]
    draw.polygon(arm_points, fill=PROBE, outline=PROBE_EDGE)
    for i in range(len(arm_points)):
        p1 = arm_points[i]
        p2 = arm_points[(i + 1) % len(arm_points)]
        draw.line([p1, p2], fill=PROBE_EDGE, width=max(1, int(size * 0.006)))

    # QR 각인 (암 중앙)
    qr_side = size * 0.24
    qr_x0 = size * 0.28
    qr_y0 = size * 0.22
    _draw_qr_5x5(draw, qr_x0, qr_y0, qr_side, QR_BG, QR_DARK)

    # 팁
    tip_apex = (size * 0.70, size * 0.80)
    tip_tl = (size * 0.65, size * 0.55)
    tip_tr = (size * 0.75, size * 0.58)
    draw.polygon([tip_tl, tip_tr, tip_apex], fill=PROBE, outline=PROBE_EDGE)
    draw.line([tip_tl, tip_apex], fill=PROBE_EDGE, width=max(1, int(size * 0.006)))
    draw.line([tip_tr, tip_apex], fill=PROBE_EDGE, width=max(1, int(size * 0.006)))

    # 빔 (팁 아래 짧게)
    img = _draw_beam(img, tip_apex[0],
                      tip_apex[1] + size * 0.005,
                      size * 0.92,
                      BEAM, max(2, int(size * 0.015)))
    return img


# ─── V2: Vertical ────────────────────────────────────────────────────────

def design_v2_vertical(size: int = BASE_SIZE) -> Image.Image:
    """위에서 아래로 수직 프로브."""
    img = rounded_square_bg(size, BG, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 상단 베이스 블록 (수평 사각형)
    base_x0 = size * 0.25
    base_y0 = size * 0.08
    base_x1 = size * 0.75
    base_y1 = size * 0.16
    draw.rectangle((base_x0, base_y0, base_x1, base_y1),
                   fill=PROBE, outline=PROBE_EDGE,
                   width=max(1, int(size * 0.006)))
    # 베이스 grip 선
    for i in range(1, 4):
        x = base_x0 + (base_x1 - base_x0) * i / 4
        draw.line([(x, base_y0 + size * 0.01), (x, base_y1 - size * 0.01)],
                  fill=PROBE_EDGE, width=max(1, int(size * 0.005)))

    # 수직 프로브 기둥 (점점 좁아짐)
    col_top_left = (size * 0.42, base_y1)
    col_top_right = (size * 0.58, base_y1)
    col_bot_left = (size * 0.46, size * 0.60)
    col_bot_right = (size * 0.54, size * 0.60)
    draw.polygon([col_top_left, col_top_right, col_bot_right, col_bot_left],
                  fill=PROBE, outline=PROBE_EDGE)
    for p1, p2 in [(col_top_left, col_bot_left),
                    (col_top_right, col_bot_right),
                    (col_top_left, col_top_right),
                    (col_bot_left, col_bot_right)]:
        draw.line([p1, p2], fill=PROBE_EDGE, width=max(1, int(size * 0.006)))

    # 기둥 상단에 QR 각인
    qr_side = size * 0.12
    qr_x0 = size * 0.50 - qr_side / 2
    qr_y0 = base_y1 + size * 0.02
    _draw_qr_5x5(draw, qr_x0, qr_y0, qr_side, QR_BG, QR_DARK)

    # 팁 (기둥 하단에서 삼각형 아래로)
    tip_apex = (size * 0.50, size * 0.78)
    draw.polygon([col_bot_left, col_bot_right, tip_apex],
                  fill=PROBE, outline=PROBE_EDGE)
    draw.line([col_bot_left, tip_apex], fill=PROBE_EDGE, width=max(1, int(size * 0.006)))
    draw.line([col_bot_right, tip_apex], fill=PROBE_EDGE, width=max(1, int(size * 0.006)))

    # 빔
    img = _draw_beam(img, tip_apex[0],
                      tip_apex[1] + size * 0.005,
                      size * 0.92,
                      BEAM, max(2, int(size * 0.015)))
    return img


# ─── V3: Top View (QR 중심) ──────────────────────────────────────────────

def design_v3_topview(size: int = BASE_SIZE) -> Image.Image:
    """중앙 대형 QR + 비스듬히 내려온 프로브 팁."""
    img = rounded_square_bg(size, BG, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 중앙 대형 QR
    qr_side = size * 0.58
    qr_x0 = (size - qr_side) / 2
    qr_y0 = (size - qr_side) / 2 + size * 0.02

    # 진짜 QR 느낌을 위해 7x7 격자 + 3 파인더
    # 먼저 흰 라벨 배경
    draw.rounded_rectangle(
        (qr_x0, qr_y0, qr_x0 + qr_side, qr_y0 + qr_side),
        radius=max(2, int(size * 0.015)),
        fill=QR_BG,
        outline=QR_DARK,
        width=max(1, int(size * 0.008)),
    )

    cells = 7
    cell = qr_side / cells

    def mini_finder(cell_r, cell_c):
        if cell_r == 1 and cell_c == 1:
            return "1"
        if cell_r in (0, 2) or cell_c in (0, 2):
            return "1"
        return "0"

    qr_data = [
        "0001000",
        "0011100",
        "0000010",
        "1011001",
        "0100110",
        "0010100",
        "0001010",
    ]
    for r in range(cells):
        for c in range(cells):
            f1 = r < 3 and c < 3
            f2 = r < 3 and c >= 4
            f3 = r >= 4 and c < 3
            if f1:
                bit = mini_finder(r, c)
            elif f2:
                bit = mini_finder(r, c - 4)
            elif f3:
                bit = mini_finder(r - 4, c)
            else:
                bit = qr_data[r][c]
            if bit == "1":
                x = qr_x0 + c * cell
                y = qr_y0 + r * cell
                gap = cell * 0.06
                draw.rectangle(
                    (x + gap, y + gap, x + cell - gap, y + cell - gap),
                    fill=QR_DARK,
                )

    # 우상단에서 비스듬히 내려오는 프로브 팁 (QR 중앙을 가리킴)
    # 팁은 기울어진 삼각형
    pt_apex = (size * 0.52, size * 0.48)  # QR 중앙 근처
    pt_top1 = (size * 0.78, size * 0.14)
    pt_top2 = (size * 0.88, size * 0.22)
    draw.polygon([pt_top1, pt_top2, pt_apex],
                  fill=PROBE, outline=PROBE_EDGE)
    for p1, p2 in [(pt_top1, pt_apex), (pt_top2, pt_apex), (pt_top1, pt_top2)]:
        draw.line([p1, p2], fill=PROBE_EDGE, width=max(1, int(size * 0.007)))

    # 짧은 빔 (팁 → QR 모듈)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.line(
        [pt_apex, (size * 0.50, size * 0.50)],
        fill=(*BEAM[:3], 200),
        width=max(2, int(size * 0.018)),
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 감지 원 (QR 중앙에 1개)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    r = size * 0.06
    odraw.ellipse(
        (size * 0.50 - r, size * 0.50 - r * 0.6,
         size * 0.50 + r, size * 0.50 + r * 0.6),
        outline=(*BEAM[:3], 180),
        width=max(1, int(size * 0.008)),
    )
    img = Image.alpha_composite(img, overlay)

    return img


# ─── V4: Sketch (사용자 그림 복원) ───────────────────────────────────────

def design_v4_sketch(size: int = BASE_SIZE) -> Image.Image:
    """칩 캐리어 프레임 + 내부 QR 라벨 + 상단 수직 프로브."""
    img = rounded_square_bg(size, BG, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 칩 캐리어 프레임 (둥근 사각형, 중앙 영역)
    carrier_pad = size * 0.12
    cx0 = carrier_pad
    cy0 = size * 0.36           # 상단에 프로브 공간 확보
    cx1 = size - carrier_pad
    cy1 = size - size * 0.10
    draw.rounded_rectangle(
        (cx0, cy0, cx1, cy1),
        radius=max(2, int(size * 0.03)),
        fill=CARRIER,
        outline=CARRIER_EDGE,
        width=max(2, int(size * 0.012)),
    )

    # 캐리어 내부 QR 라벨 (중앙)
    qr_side = (cy1 - cy0) * 0.70
    qr_x0 = (cx0 + cx1) / 2 - qr_side / 2
    qr_y0 = (cy0 + cy1) / 2 - qr_side / 2
    _draw_qr_5x5(draw, qr_x0, qr_y0, qr_side, QR_BG, QR_DARK)

    # 상단에서 수직으로 내려오는 프로브
    # 베이스 (프로브 시작부)
    pb_x0 = size * 0.42
    pb_y0 = size * 0.04
    pb_x1 = size * 0.58
    pb_y1 = size * 0.14
    draw.rectangle((pb_x0, pb_y0, pb_x1, pb_y1),
                   fill=PROBE, outline=PROBE_EDGE,
                   width=max(1, int(size * 0.006)))

    # 긴 프로브 기둥 (베이스 → 캐리어 상단)
    col_x0 = size * 0.46
    col_x1 = size * 0.54
    col_y0 = pb_y1
    col_y1 = cy0 - size * 0.04  # 캐리어에 닿기 직전
    draw.rectangle((col_x0, col_y0, col_x1, col_y1),
                   fill=PROBE, outline=PROBE_EDGE,
                   width=max(1, int(size * 0.006)))

    # 뾰족한 팁 (기둥 끝)
    tip_apex_x = size * 0.50
    tip_apex_y = cy0 + size * 0.01  # 캐리어 상단에 살짝 닿음
    draw.polygon(
        [(col_x0, col_y1), (col_x1, col_y1), (tip_apex_x, tip_apex_y)],
        fill=PROBE, outline=PROBE_EDGE,
    )
    draw.line([(col_x0, col_y1), (tip_apex_x, tip_apex_y)],
              fill=PROBE_EDGE, width=max(1, int(size * 0.006)))
    draw.line([(col_x1, col_y1), (tip_apex_x, tip_apex_y)],
              fill=PROBE_EDGE, width=max(1, int(size * 0.006)))

    # 팁에서 QR 까지 얇은 빔
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.line(
        [(tip_apex_x, tip_apex_y + size * 0.008), (tip_apex_x, qr_y0 - size * 0.005)],
        fill=(*BEAM[:3], 200),
        width=max(2, int(size * 0.013)),
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # QR 상단에 감지 표시 (작은 점 + 링)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    dx = tip_apex_x
    dy = qr_y0
    r_ring = size * 0.035
    odraw.ellipse(
        (dx - r_ring, dy - r_ring * 0.6,
         dx + r_ring, dy + r_ring * 0.6),
        outline=(*BEAM[:3], 200),
        width=max(1, int(size * 0.008)),
    )
    img = Image.alpha_composite(img, overlay)

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_v1_minimal",  design_v1_minimal,  "Minimal (부가 요소 제거)"),
        ("icon_v2_vertical", design_v2_vertical, "Vertical (위->아래 수직)"),
        ("icon_v3_topview",  design_v3_topview,  "Top View (대형 QR 중심)"),
        ("icon_v4_sketch",   design_v4_sketch,   "Sketch (캐리어+QR+수직 프로브)"),
    ]

    for name, factory, label in variants:
        print(f"[Generating] {name}  - {label}")
        img = factory(BASE_SIZE)

        png_path = out_dir / f"{name}_256.png"
        img.save(png_path, format="PNG")

        # 크기별 비교 스트립
        sizes = [16, 32, 48, 64, 128]
        total_w = sum(sizes) + 10 * len(sizes) + 20
        strip = Image.new("RGBA", (total_w, max(sizes) + 20), (20, 20, 30, 255))
        x = 10
        for s in sizes:
            small = img.resize((s, s), Image.Resampling.LANCZOS)
            y = (strip.height - small.height) // 2
            strip.paste(small, (x, y), small)
            x += small.width + 10
        strip_path = out_dir / f"{name}_sizes_16_32_48_64_128.png"
        strip.save(strip_path, format="PNG")

        ico_path = out_dir / f"{name}.ico"
        save_ico(img, ico_path)

        print(f"  -> {png_path.name}")
        print(f"  -> {strip_path.name}")
        print(f"  -> {ico_path.name}")

    # 4개를 하나의 비교 그리드로 만들기 (선택 편의)
    print("\n[Generating] comparison grid (all 4 side-by-side)")
    grid_cell = 256
    gap = 12
    grid = Image.new("RGBA",
                      (grid_cell * 2 + gap * 3, grid_cell * 2 + gap * 3),
                      (20, 20, 30, 255))
    for i, (name, factory, _) in enumerate(variants):
        img = Image.open(out_dir / f"{name}_256.png")
        col, row = i % 2, i // 2
        x = gap + col * (grid_cell + gap)
        y = gap + row * (grid_cell + gap)
        grid.paste(img, (x, y), img)
    grid_path = out_dir / "compare_v1_v2_v3_v4.png"
    grid.save(grid_path, format="PNG")
    print(f"  -> {grid_path.name}")

    print(f"\nAll variants saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
