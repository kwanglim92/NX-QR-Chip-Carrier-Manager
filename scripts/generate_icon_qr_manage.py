"""앱 아이콘 — QR 코드로 칩 캐리어를 관리한다는 느낌 (사용자 3개 레퍼런스 종합).

3가지 컨셉:
  X1 Scanner + QR        - QR 스캐너가 QR을 읽는 동작 (레퍼런스 2)
  X2 QR + Big Check      - QR 전체 + 중앙 대형 체크 (레퍼런스 3)
  X3 Carrier + QR + Check - 캐리어+QR+체크 배지 (레퍼런스 1 + M2 개선판)

공통 팔레트: 밝은 그레이 + 브라이트 블루. 산뜻한 관리자 앱 톤.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, rounded_square_bg, save_ico,
)

# ─── 색상 팔레트 (밝은 톤) ────────────────────────────────────────────────

BG_APP      = (224, 232, 243, 255)   # 아이콘 외곽 연한 블루그레이
BG_PANEL    = (246, 248, 251, 255)   # 내부 패널 거의 흰색
GRAY_DARK   = (55, 65, 81, 255)      # QR 모듈, 진한 테두리
GRAY_MID    = (107, 114, 128, 255)   # 캐리어/스캐너 본체
GRAY_LIGHT  = (209, 213, 219, 255)   # 보조 라인
WHITE       = (255, 255, 255, 255)

BLUE        = (59, 130, 246, 255)    # 브라이트 블루 (체크, 브래킷)
BLUE_DARK   = (37, 99, 235, 255)
YELLOW      = (252, 211, 77, 255)    # 스캐너 렌즈 창
PINK        = (244, 114, 182, 255)   # 스캐너 트리거

CHECK_BG    = BLUE
CHECK_FG    = WHITE


# ─── QR 격자 그리기 ──────────────────────────────────────────────────────

def _draw_qr_grid(draw: ImageDraw.ImageDraw,
                   x0: float, y0: float, side: float,
                   cells: int = 8,
                   fg=GRAY_DARK,
                   bracket_color=None) -> tuple:
    """파인더 3개 + 데이터 모듈 있는 pseudo-QR. 선택적 모서리 브래킷."""
    cell = side / cells

    def mini_finder(r: int, c: int) -> str:
        """3x3 finder (외곽 + 중앙)."""
        if r == 1 and c == 1:
            return "1"
        if r in (0, 2) or c in (0, 2):
            return "1"
        return "0"

    # 8x8 기준 데이터 패턴 (파인더 3x3 제외한 영역)
    data_pattern = [
        "00010111",
        "00111010",
        "00001101",
        "10110010",
        "01010110",
        "00101001",
        "01101101",
        "10010110",
    ]
    for r in range(cells):
        for c in range(cells):
            f1 = r < 3 and c < 3
            f2 = r < 3 and c >= (cells - 3)
            f3 = r >= (cells - 3) and c < 3
            if f1:
                bit = mini_finder(r, c)
            elif f2:
                bit = mini_finder(r, c - (cells - 3))
            elif f3:
                bit = mini_finder(r - (cells - 3), c)
            else:
                if r < len(data_pattern) and c < len(data_pattern[0]):
                    bit = data_pattern[r][c]
                else:
                    bit = "0"
            if bit == "1":
                cx = x0 + c * cell
                cy = y0 + r * cell
                gap = cell * 0.08
                draw.rectangle(
                    (cx + gap, cy + gap, cx + cell - gap, cy + cell - gap),
                    fill=fg,
                )

    if bracket_color is not None:
        # 네 모서리 L자 브래킷
        bw = max(3, int(side * 0.025))
        blen = side * 0.18
        # 좌상
        draw.line([(x0, y0), (x0 + blen, y0)], fill=bracket_color, width=bw)
        draw.line([(x0, y0), (x0, y0 + blen)], fill=bracket_color, width=bw)
        # 우상
        draw.line([(x0 + side, y0), (x0 + side - blen, y0)], fill=bracket_color, width=bw)
        draw.line([(x0 + side, y0), (x0 + side, y0 + blen)], fill=bracket_color, width=bw)
        # 좌하
        draw.line([(x0, y0 + side), (x0 + blen, y0 + side)], fill=bracket_color, width=bw)
        draw.line([(x0, y0 + side), (x0, y0 + side - blen)], fill=bracket_color, width=bw)
        # 우하
        draw.line([(x0 + side, y0 + side), (x0 + side - blen, y0 + side)],
                  fill=bracket_color, width=bw)
        draw.line([(x0 + side, y0 + side), (x0 + side, y0 + side - blen)],
                  fill=bracket_color, width=bw)

    return (x0, y0, x0 + side, y0 + side)


def _draw_check_badge(img: Image.Image, cx: float, cy: float, r: float,
                       bg=CHECK_BG, fg=CHECK_FG, outline=WHITE) -> Image.Image:
    """원형 체크 배지."""
    draw = ImageDraw.Draw(img)
    # 흰 테두리
    draw.ellipse(
        (cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3),
        fill=outline,
    )
    # 메인 원
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
    # 체크마크 V
    cw = max(2, int(r * 0.22))
    p1 = (cx - r * 0.45, cy + r * 0.05)
    p2 = (cx - r * 0.1, cy + r * 0.40)
    p3 = (cx + r * 0.50, cy - r * 0.35)
    draw.line([p1, p2], fill=fg, width=cw)
    draw.line([p2, p3], fill=fg, width=cw)
    return img


# ─── X1: Scanner + QR ────────────────────────────────────────────────────

def design_x1_scanner(size: int = BASE_SIZE) -> Image.Image:
    """좌측 스캐너 + 우측 QR + 중간 스캔 빔."""
    img = rounded_square_bg(size, BG_APP, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 우측 QR (아이콘 우측 2/3 사용)
    qr_side = size * 0.48
    qr_x0 = size * 0.46
    qr_y0 = (size - qr_side) / 2
    # QR 흰 배경
    draw.rounded_rectangle(
        (qr_x0 - size * 0.015, qr_y0 - size * 0.015,
         qr_x0 + qr_side + size * 0.015, qr_y0 + qr_side + size * 0.015),
        radius=max(2, int(size * 0.02)),
        fill=BG_PANEL,
    )
    _draw_qr_grid(draw, qr_x0, qr_y0, qr_side, cells=7,
                   fg=GRAY_DARK, bracket_color=BLUE)

    # 좌측 스캐너 — 단순화된 핸드헬드 리더기
    # 본체 (둥근 사각형, 대각선 방향)
    sc_body_x0 = size * 0.08
    sc_body_y0 = size * 0.22
    sc_body_x1 = size * 0.40
    sc_body_y1 = size * 0.46
    draw.rounded_rectangle(
        (sc_body_x0, sc_body_y0, sc_body_x1, sc_body_y1),
        radius=max(3, int(size * 0.03)),
        fill=GRAY_MID,
        outline=GRAY_DARK,
        width=max(2, int(size * 0.008)),
    )
    # 렌즈 창 (노란 사각)
    lens_x0 = sc_body_x0 + (sc_body_x1 - sc_body_x0) * 0.55
    lens_y0 = sc_body_y0 + (sc_body_y1 - sc_body_y0) * 0.20
    lens_x1 = sc_body_x1 - (sc_body_x1 - sc_body_x0) * 0.05
    lens_y1 = sc_body_y0 + (sc_body_y1 - sc_body_y0) * 0.80
    draw.rounded_rectangle(
        (lens_x0, lens_y0, lens_x1, lens_y1),
        radius=max(2, int(size * 0.012)),
        fill=YELLOW,
    )
    # 트리거 버튼 (핑크 점)
    trig_r = size * 0.022
    trig_cx = sc_body_x0 + (sc_body_x1 - sc_body_x0) * 0.25
    trig_cy = sc_body_y0 + (sc_body_y1 - sc_body_y0) * 0.55
    draw.ellipse(
        (trig_cx - trig_r, trig_cy - trig_r, trig_cx + trig_r, trig_cy + trig_r),
        fill=PINK,
    )
    # 손잡이 (아래쪽 기울어진 사각형)
    grip_points = [
        (sc_body_x0 + size * 0.02, sc_body_y1 - size * 0.005),
        (sc_body_x0 + size * 0.12, sc_body_y1 - size * 0.005),
        (sc_body_x0 + size * 0.08, sc_body_y1 + size * 0.20),
        (sc_body_x0 - size * 0.02, sc_body_y1 + size * 0.20),
    ]
    draw.polygon(grip_points, fill=GRAY_MID, outline=GRAY_DARK)
    # 그립 아웃라인 강조
    for i in range(len(grip_points)):
        p1 = grip_points[i]
        p2 = grip_points[(i + 1) % len(grip_points)]
        draw.line([p1, p2], fill=GRAY_DARK, width=max(1, int(size * 0.006)))

    # 스캔 빔 (렌즈 중앙 → QR 중앙)
    beam_from = ((lens_x0 + lens_x1) / 2, (lens_y0 + lens_y1) / 2)
    beam_to = (qr_x0 + qr_side * 0.5, qr_y0 + qr_side * 0.5)
    for mult, alpha in [(4, 60), (2, 110)]:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.line(
            [beam_from, beam_to],
            fill=(*BLUE[:3], alpha),
            width=max(2, int(size * 0.012 * mult)),
        )
        img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    draw.line(
        [beam_from, beam_to],
        fill=BLUE,
        width=max(2, int(size * 0.012)),
    )

    return img


# ─── X2: QR + Big Check ──────────────────────────────────────────────────

def design_x2_bigcheck(size: int = BASE_SIZE) -> Image.Image:
    """대형 QR + 중앙 큰 파란 체크 + 네 모서리 브래킷."""
    img = rounded_square_bg(size, BG_APP, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 중앙 영역에 큰 QR 영역 흰 배경
    qr_pad = size * 0.12
    qr_x0 = qr_pad
    qr_y0 = qr_pad
    qr_side = size - 2 * qr_pad
    draw.rounded_rectangle(
        (qr_x0, qr_y0, qr_x0 + qr_side, qr_y0 + qr_side),
        radius=max(3, int(size * 0.025)),
        fill=BG_PANEL,
    )
    _draw_qr_grid(draw, qr_x0, qr_y0, qr_side, cells=9,
                   fg=GRAY_DARK, bracket_color=BLUE)

    # 중앙 대형 체크 배지
    img = _draw_check_badge(
        img,
        cx=size / 2,
        cy=size / 2,
        r=size * 0.18,
        bg=BLUE,
        fg=WHITE,
        outline=BG_APP,   # 외곽 링이 BG와 자연스럽게 녹아듬
    )

    return img


# ─── X3: Carrier + QR + Check Badge ──────────────────────────────────────

def design_x3_carrier_check(size: int = BASE_SIZE) -> Image.Image:
    """칩 캐리어 프레임 + QR + 하단 커넥터 + 우상단 체크 배지 (밝은 톤)."""
    img = rounded_square_bg(size, BG_APP, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 하단 커넥터
    conn_w = size * 0.22
    conn_h = size * 0.14
    conn_x0 = (size - conn_w) / 2
    conn_y0 = size * 0.76
    conn_x1 = conn_x0 + conn_w
    conn_y1 = conn_y0 + conn_h
    draw.rounded_rectangle(
        (conn_x0, conn_y0, conn_x1, conn_y1),
        radius=max(1, int(size * 0.015)),
        fill=GRAY_MID,
        outline=GRAY_DARK,
        width=max(2, int(size * 0.008)),
    )
    # 커넥터 그립 라인
    for i in range(1, 5):
        x = conn_x0 + (conn_x1 - conn_x0) * i / 5
        draw.line(
            [(x, conn_y0 + size * 0.015), (x, conn_y1 - size * 0.015)],
            fill=GRAY_DARK,
            width=max(1, int(size * 0.005)),
        )

    # 캐리어 본체 (라이트 그레이)
    carrier_pad = size * 0.08
    cx0 = carrier_pad
    cy0 = size * 0.08
    cx1 = size - carrier_pad
    cy1 = size * 0.78
    draw.rounded_rectangle(
        (cx0, cy0, cx1, cy1),
        radius=max(3, int(size * 0.03)),
        fill=GRAY_LIGHT,
        outline=GRAY_DARK,
        width=max(2, int(size * 0.010)),
    )

    # 캐리어 상단 하이라이트
    hi = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.rounded_rectangle(
        (cx0 + size * 0.015, cy0 + size * 0.015,
         cx1 - size * 0.015, cy0 + size * 0.05),
        radius=max(1, int(size * 0.015)),
        fill=(255, 255, 255, 120),
    )
    img = Image.alpha_composite(img, hi)
    draw = ImageDraw.Draw(img)

    # 내부 QR 라벨 (흰 배경)
    lb_pad = size * 0.04
    lbx0 = cx0 + lb_pad
    lby0 = cy0 + lb_pad
    lbx1 = cx1 - lb_pad
    lby1 = cy1 - lb_pad
    lb_w = lbx1 - lbx0
    lb_h = lby1 - lby0
    qr_side = min(lb_w, lb_h) * 0.92
    qx0 = (lbx0 + lbx1) / 2 - qr_side / 2
    qy0 = (lby0 + lby1) / 2 - qr_side / 2
    draw.rounded_rectangle(
        (qx0, qy0, qx0 + qr_side, qy0 + qr_side),
        radius=max(2, int(size * 0.02)),
        fill=BG_PANEL,
        outline=GRAY_DARK,
        width=max(1, int(size * 0.005)),
    )
    _draw_qr_grid(draw, qx0, qy0, qr_side, cells=7, fg=GRAY_DARK)

    # 우상단 체크 배지
    img = _draw_check_badge(
        img,
        cx=size - size * 0.12,
        cy=size * 0.13,
        r=size * 0.085,
        bg=BLUE,
        fg=WHITE,
        outline=BG_APP,
    )

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_x1_scanner",       design_x1_scanner,       "Scanner + QR"),
        ("icon_x2_bigcheck",      design_x2_bigcheck,      "QR + Big Check"),
        ("icon_x3_carrier_check", design_x3_carrier_check, "Carrier + QR + Check"),
    ]

    for name, factory, label in variants:
        print(f"[Generating] {name}  - {label}")
        img = factory(BASE_SIZE)

        png_path = out_dir / f"{name}_256.png"
        img.save(png_path, format="PNG")

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

    # 3개 1x3 비교 그리드
    print("\n[Generating] comparison grid (X1 X2 X3)")
    cell = 256
    gap = 12
    grid = Image.new(
        "RGBA",
        (cell * 3 + gap * 4, cell + gap * 2),
        (20, 20, 30, 255),
    )
    for i, (name, _, _) in enumerate(variants):
        im = Image.open(out_dir / f"{name}_256.png")
        x = gap + i * (cell + gap)
        y = gap
        grid.paste(im, (x, y), im)
    grid_path = out_dir / "compare_x1_x2_x3.png"
    grid.save(grid_path, format="PNG")
    print(f"  -> {grid_path.name}")

    print(f"\nAll QR-manage icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
