"""앱 아이콘 — 칩 캐리어 + QR + Managing 느낌.

사용자 참고 이미지 반영:
  - 큰 청록 사각형 = 칩 캐리어 + QR 라벨 (한 몸체)
  - 내부 큰 QR 코드 (메인)
  - 하단 중앙 작은 돌출 = 커넥터
  - Managing 표현은 variant 별로 다르게

4가지 variant:
  M1 Simple      - 기본 골격
  M2 Check Badge - 우상단 녹색 체크 배지 (인증 완료)
  M3 Scan Line   - QR 위 수평 스캔 라인 (스캔 중)
  M4 ID Label    - QR 하단 'NX-AFM' 텍스트 배지
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, rounded_square_bg, save_ico, try_font,
)

# ─── 색상 팔레트 (사용자 참고 이미지의 청록톤) ───────────────────────────

CARRIER     = (30, 90, 124, 255)      # 깊은 청록 (#1E5A7C)
CARRIER_HI  = (60, 130, 170, 255)     # 캐리어 상단 하이라이트
CARRIER_EDGE = (20, 65, 90, 255)      # 캐리어 테두리

CONNECTOR   = (80, 110, 135, 255)     # 커넥터 (좀 더 어두운 톤)
CONNECTOR_EDGE = (50, 75, 95, 255)

QR_BG       = (250, 252, 254, 255)    # QR 라벨 흰 배경
QR_DARK     = (15, 35, 55, 255)       # QR 모듈 (거의 검정)
LABEL_SHADOW = (0, 0, 0, 100)

CHECK_BG    = (16, 185, 129, 255)     # 체크 배지 에메랄드
CHECK_FG    = (255, 255, 255, 255)

SCAN_BEAM   = (34, 211, 238, 255)     # 시안 스캔 라인

ID_BG       = (30, 41, 59, 255)       # ID 라벨 딥 네이비
ID_FG       = (251, 191, 36, 255)     # 골드 텍스트

BG          = (20, 35, 50, 255)       # 앱 아이콘 외곽 배경 (더 어두운 청록)


# ─── QR 패턴 ─────────────────────────────────────────────────────────────

def _draw_qr_7x7(draw: ImageDraw.ImageDraw,
                  x0: float, y0: float, side: float,
                  bg_color, fg_color) -> None:
    """7x7 의사-QR — 3 미니 파인더(3x3) + 데이터 모듈."""
    # 라벨 배경
    draw.rounded_rectangle(
        (x0, y0, x0 + side, y0 + side),
        radius=max(2, int(side * 0.04)),
        fill=bg_color,
    )
    cells = 7
    cell = side / cells

    def mini_finder(r, c):
        if r == 1 and c == 1:
            return "1"
        if r in (0, 2) or c in (0, 2):
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
                cx = x0 + c * cell
                cy = y0 + r * cell
                gap = cell * 0.07
                draw.rectangle(
                    (cx + gap, cy + gap, cx + cell - gap, cy + cell - gap),
                    fill=fg_color,
                )


# ─── 공통 프레임 (캐리어 + 커넥터) ───────────────────────────────────────

def _draw_carrier_frame(img: Image.Image) -> tuple[Image.Image, tuple]:
    """캐리어 본체 + 하단 돌출 커넥터. 반환: (img, QR 배치 영역 rect)."""
    size = img.width
    draw = ImageDraw.Draw(img)

    # 하단 커넥터 (캐리어 아래로 튀어나온 작은 사각형)
    conn_w = size * 0.20
    conn_h = size * 0.14
    conn_x0 = (size - conn_w) / 2
    conn_y0 = size * 0.76
    conn_x1 = conn_x0 + conn_w
    conn_y1 = conn_y0 + conn_h
    # 커넥터 내부
    draw.rounded_rectangle(
        (conn_x0, conn_y0, conn_x1, conn_y1),
        radius=max(1, int(size * 0.015)),
        fill=CONNECTOR,
        outline=CONNECTOR_EDGE,
        width=max(2, int(size * 0.008)),
    )
    # 커넥터 그립 라인
    for i in range(1, 4):
        x = conn_x0 + (conn_x1 - conn_x0) * i / 4
        draw.line(
            [(x, conn_y0 + size * 0.015), (x, conn_y1 - size * 0.015)],
            fill=CONNECTOR_EDGE,
            width=max(1, int(size * 0.005)),
        )

    # 캐리어 본체 (큰 사각형)
    carrier_pad = size * 0.08
    cx0 = carrier_pad
    cy0 = size * 0.10
    cx1 = size - carrier_pad
    cy1 = size * 0.78           # 커넥터와 약간 겹침 처리 (아래)
    draw.rounded_rectangle(
        (cx0, cy0, cx1, cy1),
        radius=max(3, int(size * 0.03)),
        fill=CARRIER,
        outline=CARRIER_EDGE,
        width=max(2, int(size * 0.012)),
    )
    # 캐리어 상단 하이라이트 (유리 느낌)
    hi_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi_layer)
    hd.rounded_rectangle(
        (cx0 + size * 0.015, cy0 + size * 0.015,
         cx1 - size * 0.015, cy0 + size * 0.05),
        radius=max(1, int(size * 0.015)),
        fill=(*CARRIER_HI[:3], 90),
    )
    img = Image.alpha_composite(img, hi_layer)

    # QR 배치 영역 반환 (캐리어 내부 거의 전체)
    qr_margin = size * 0.05
    qr_rect = (
        cx0 + qr_margin,
        cy0 + qr_margin,
        cx1 - qr_margin,
        cy1 - qr_margin,
    )
    return img, qr_rect


def _draw_qr_label_in_rect(img: Image.Image, qr_rect: tuple) -> Image.Image:
    """캐리어 내부 영역에 QR 라벨을 그림자와 함께 배치."""
    size = img.width
    x0, y0, x1, y1 = qr_rect
    w = x1 - x0
    h = y1 - y0
    side = min(w, h)
    # 중앙 정렬
    qx0 = x0 + (w - side) / 2
    qy0 = y0 + (h - side) / 2
    qx1 = qx0 + side
    qy1 = qy0 + side

    # 그림자
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sh_off = max(2, int(size * 0.012))
    sdraw.rounded_rectangle(
        (qx0 + sh_off, qy0 + sh_off, qx1 + sh_off, qy1 + sh_off),
        radius=max(2, int(size * 0.03)),
        fill=(0, 0, 0, 130),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, size * 0.01)))
    img = Image.alpha_composite(img, shadow)

    # QR
    draw = ImageDraw.Draw(img)
    _draw_qr_7x7(draw, qx0, qy0, side, QR_BG, QR_DARK)
    # QR 라벨 테두리
    draw.rounded_rectangle(
        (qx0, qy0, qx1, qy1),
        radius=max(2, int(size * 0.03)),
        outline=QR_DARK,
        width=max(1, int(size * 0.005)),
    )
    return img


# ─── M1: Simple ──────────────────────────────────────────────────────────

def design_m1_simple(size: int = BASE_SIZE) -> Image.Image:
    img = rounded_square_bg(size, BG, radius_ratio=0.16)
    img, qr_rect = _draw_carrier_frame(img)
    img = _draw_qr_label_in_rect(img, qr_rect)
    return img


# ─── M2: Check Badge ─────────────────────────────────────────────────────

def design_m2_check(size: int = BASE_SIZE) -> Image.Image:
    img = design_m1_simple(size)
    draw = ImageDraw.Draw(img)

    # 우상단 원형 체크 배지 (캐리어 모서리에 올려놓음)
    badge_r = size * 0.10
    badge_cx = size - size * 0.12
    badge_cy = size * 0.14
    # 바깥 흰 테두리 (조금의 숨 쉴 공간)
    draw.ellipse(
        (badge_cx - badge_r - 3, badge_cy - badge_r - 3,
         badge_cx + badge_r + 3, badge_cy + badge_r + 3),
        fill=(255, 255, 255, 255),
    )
    # 녹색 배지 본체
    draw.ellipse(
        (badge_cx - badge_r, badge_cy - badge_r,
         badge_cx + badge_r, badge_cy + badge_r),
        fill=CHECK_BG,
    )
    # 체크 마크 V
    cw = max(2, int(size * 0.015))
    p1 = (badge_cx - badge_r * 0.45, badge_cy + badge_r * 0.05)
    p2 = (badge_cx - badge_r * 0.1, badge_cy + badge_r * 0.40)
    p3 = (badge_cx + badge_r * 0.50, badge_cy - badge_r * 0.35)
    draw.line([p1, p2], fill=CHECK_FG, width=cw)
    draw.line([p2, p3], fill=CHECK_FG, width=cw)
    return img


# ─── M3: Scan Line ───────────────────────────────────────────────────────

def design_m3_scan(size: int = BASE_SIZE) -> Image.Image:
    img = design_m1_simple(size)

    # QR 영역 대략 위치 (M1에서 계산한 값 재사용 위해 대략 값 사용)
    # QR 영역: 캐리어 내부, 화면 중앙. M1의 배치와 매치.
    # 안전하게 재계산
    carrier_pad = size * 0.08
    cx0 = carrier_pad
    cy0 = size * 0.10
    cx1 = size - carrier_pad
    cy1 = size * 0.78
    qr_margin = size * 0.05
    x0 = cx0 + qr_margin
    y0 = cy0 + qr_margin
    x1 = cx1 - qr_margin
    y1 = cy1 - qr_margin
    w = x1 - x0
    h = y1 - y0
    side = min(w, h)
    qx0 = x0 + (w - side) / 2
    qy0 = y0 + (h - side) / 2
    qx1 = qx0 + side
    qy1 = qy0 + side

    # 수평 스캔 라인 (QR 세로 중간쯤)
    scan_y = qy0 + side * 0.52
    # 글로우 여러 겹
    for radius_mult in (6, 3):
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.line(
            [(qx0 - size * 0.01, scan_y), (qx1 + size * 0.01, scan_y)],
            fill=(*SCAN_BEAM[:3], 70 if radius_mult == 6 else 120),
            width=max(2, int(size * 0.008 * radius_mult)),
        )
        img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    # 메인 라인
    draw.line(
        [(qx0 - size * 0.005, scan_y), (qx1 + size * 0.005, scan_y)],
        fill=SCAN_BEAM,
        width=max(2, int(size * 0.012)),
    )
    # 라인 양 끝 마커
    mr = max(2, int(size * 0.012))
    draw.ellipse(
        (qx0 - mr, scan_y - mr, qx0 + mr, scan_y + mr),
        fill=SCAN_BEAM,
    )
    draw.ellipse(
        (qx1 - mr, scan_y - mr, qx1 + mr, scan_y + mr),
        fill=SCAN_BEAM,
    )
    return img


# ─── M4: ID Label ────────────────────────────────────────────────────────

def design_m4_id(size: int = BASE_SIZE) -> Image.Image:
    img = design_m1_simple(size)
    draw = ImageDraw.Draw(img)

    # QR 하단 외부 (캐리어 영역 내부이지만 QR 라벨 아래)에 작은 ID 배지
    # 캐리어 내부 하단에 배지
    badge_w = size * 0.42
    badge_h = size * 0.11
    badge_x0 = (size - badge_w) / 2
    # 캐리어 바닥 (cy1) 근처
    badge_y0 = size * 0.62
    badge_x1 = badge_x0 + badge_w
    badge_y1 = badge_y0 + badge_h

    # 배지 배경 (어두운 네이비)
    draw.rounded_rectangle(
        (badge_x0, badge_y0, badge_x1, badge_y1),
        radius=max(2, int(size * 0.02)),
        fill=ID_BG,
        outline=ID_FG,
        width=max(1, int(size * 0.005)),
    )
    # 텍스트 "NX-AFM"
    font = try_font(max(12, int(size * 0.07)), bold=True)
    text = "NX-AFM"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = badge_x0 + (badge_w - tw) / 2 - bbox[0]
        ty = badge_y0 + (badge_h - th) / 2 - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)
        tx = badge_x0 + (badge_w - tw) / 2
        ty = badge_y0 + (badge_h - th) / 2
    draw.text((tx, ty), text, fill=ID_FG, font=font)
    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_m1_simple",  design_m1_simple, "Simple (기본)"),
        ("icon_m2_check",   design_m2_check,  "Check Badge (체크 배지)"),
        ("icon_m3_scan",    design_m3_scan,   "Scan Line (스캔 라인)"),
        ("icon_m4_id",      design_m4_id,     "ID Label (NX-AFM 라벨)"),
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

    # 2x2 비교 그리드
    print("\n[Generating] comparison grid (M1~M4 2x2)")
    cell = 256
    gap = 12
    grid = Image.new(
        "RGBA",
        (cell * 2 + gap * 3, cell * 2 + gap * 3),
        (20, 20, 30, 255),
    )
    for i, (name, _, _) in enumerate(variants):
        img = Image.open(out_dir / f"{name}_256.png")
        col, row = i % 2, i // 2
        x = gap + col * (cell + gap)
        y = gap + row * (cell + gap)
        grid.paste(img, (x, y), img)
    grid_path = out_dir / "compare_m1_m2_m3_m4.png"
    grid.save(grid_path, format="PNG")
    print(f"  -> {grid_path.name}")

    print(f"\nAll Managing icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
