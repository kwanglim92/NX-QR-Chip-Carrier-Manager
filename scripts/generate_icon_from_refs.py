"""앱 아이콘 — 사용자 제공 2개 레퍼런스 이미지 기반.

2가지 컨셉 (레퍼런스 그대로, 보정 최소화):
  R1 Dashboard   - 중앙 '페달형 칩 캐리어 + QR + 체크' + 주변 대시보드(차트/OK/DB)
  R2 LotCard     - 페달형 칩 캐리어 + 비스듬한 반투명 카드(LOT ID/PASS/QTY + QR)

산출물:
  assets/icons/icon_r1_dashboard.ico / _256.png / _sizes_*.png
  assets/icons/icon_r2_lotcard.ico   / _256.png / _sizes_*.png
  assets/icons/compare_r1_r2.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, rounded_square_bg, save_ico, try_font,
)
from generate_icon_qr_manage import (  # noqa: E402
    _draw_qr_grid, _draw_check_badge,
)

# ─── 색상 팔레트 ─────────────────────────────────────────────────────────

BG_CREAM    = (246, 240, 229, 255)
BG_SOFT     = (230, 238, 247, 255)

GRAY_DARK   = (55, 65, 81, 255)
GRAY_MID    = (120, 130, 145, 255)
GRAY_LIGHT  = (205, 213, 221, 255)
PANEL       = (248, 250, 252, 255)
WHITE       = (255, 255, 255, 255)

BLUE        = (59, 130, 246, 255)
BLUE_DARK   = (37, 99, 235, 255)
BLUE_SOFT   = (147, 197, 253, 255)

GREEN       = (74, 222, 128, 255)
GREEN_DARK  = (5, 122, 85, 255)
GREEN_SOFT  = (209, 250, 229, 255)
AMBER       = (251, 191, 36, 255)
AMBER_SOFT  = (254, 215, 170, 255)


# ─── 페달형 칩 캐리어 실루엣 (레퍼런스 그대로) ──────────────────────────

def _carrier_polygon(cx: float, cy_body: float,
                      body_w: float, body_h: float,
                      neck_h: float, neck_w: float,
                      handle_h: float, handle_w: float,
                      corner_r: float) -> list[tuple[float, float]]:
    """
    캐리어 외곽 경로 (본체 + 사다리꼴 목 + 직사각 핸들)를 포인트 리스트로 반환.
    모서리 라운딩은 별도 ellipse 마스킹으로 본체만 처리하고, 폴리곤은 직선 경계.
    """
    bx0 = cx - body_w / 2
    bx1 = cx + body_w / 2
    by0 = cy_body - body_h / 2
    by1 = cy_body + body_h / 2

    # 목(neck): 본체 바로 아래 사다리꼴
    ny0 = by1
    ny1 = by1 + neck_h
    # 목은 본체 너비 → 핸들 너비로 좁아짐
    nx0_top = cx - body_w / 2 + corner_r * 0.1
    nx1_top = cx + body_w / 2 - corner_r * 0.1
    nx0_bot = cx - neck_w / 2
    nx1_bot = cx + neck_w / 2

    # 핸들(handle): 목 바로 아래 직사각형
    hy0 = ny1
    hy1 = ny1 + handle_h
    hx0 = cx - handle_w / 2
    hx1 = cx + handle_w / 2

    # 시계 방향 외곽 경로
    return [
        (bx0 + corner_r, by0),
        (bx1 - corner_r, by0),
        (bx1, by0 + corner_r),
        (bx1, by1 - corner_r),
        (bx1 - corner_r, by1),
        (nx1_top, ny0),
        (nx1_bot, ny1),
        (hx1, hy0),
        (hx1, hy1),
        (hx0, hy1),
        (hx0, hy0),
        (nx0_bot, ny1),
        (nx0_top, ny0),
        (bx0 + corner_r, by1),
        (bx0, by1 - corner_r),
        (bx0, by0 + corner_r),
    ]


def _draw_carrier(img: Image.Image,
                   cx: float, cy_body: float,
                   body_w: float, body_h: float,
                   neck_h: float, neck_w: float,
                   handle_h: float, handle_w: float,
                   *,
                   fill=GRAY_LIGHT,
                   outline=GRAY_DARK,
                   outline_w: int = 3,
                   highlight: bool = True) -> None:
    """페달형 캐리어 실루엣을 그린다 (QR 는 별도 함수로 추가)."""
    draw = ImageDraw.Draw(img)
    corner_r = min(body_w, body_h) * 0.09
    poly = _carrier_polygon(
        cx, cy_body, body_w, body_h,
        neck_h, neck_w, handle_h, handle_w, corner_r,
    )
    draw.polygon(poly, fill=fill, outline=outline)
    # 외곽 라인 굵게
    for i in range(len(poly)):
        p1 = poly[i]
        p2 = poly[(i + 1) % len(poly)]
        draw.line([p1, p2], fill=outline, width=outline_w)

    # 본체 상단 하이라이트 (얇은 광택)
    if highlight:
        bx0 = cx - body_w / 2
        bx1 = cx + body_w / 2
        by0 = cy_body - body_h / 2
        hi = Image.new("RGBA", img.size, (0, 0, 0, 0))
        hd = ImageDraw.Draw(hi)
        hd.rounded_rectangle(
            (bx0 + body_w * 0.06, by0 + body_h * 0.05,
             bx1 - body_w * 0.06, by0 + body_h * 0.11),
            radius=max(1, int(body_h * 0.03)),
            fill=(255, 255, 255, 110),
        )
        img.alpha_composite(hi)

    # 핸들 하단 핀 자국 (세로 2줄)
    pin_y0 = cy_body + body_h / 2 + neck_h + handle_h * 0.30
    pin_y1 = cy_body + body_h / 2 + neck_h + handle_h * 0.85
    for frac in (0.35, 0.65):
        px = cx - handle_w / 2 + handle_w * frac
        draw.line(
            [(px, pin_y0), (px, pin_y1)],
            fill=outline,
            width=max(1, outline_w - 1),
        )


def _draw_qr_in_body(img: Image.Image,
                      cx: float, cy_body: float,
                      body_w: float, body_h: float,
                      *,
                      qr_cells: int = 7,
                      outline=GRAY_DARK,
                      outline_w: int = 2,
                      bracket_color=None) -> tuple[float, float, float]:
    """캐리어 본체 내부에 QR 흰 배경 + 격자. (qr_cx, qr_cy, qr_side) 반환."""
    draw = ImageDraw.Draw(img)
    inner_pad = min(body_w, body_h) * 0.12
    side = min(body_w, body_h) - 2 * inner_pad
    qx0 = cx - side / 2
    qy0 = cy_body - side / 2
    draw.rounded_rectangle(
        (qx0, qy0, qx0 + side, qy0 + side),
        radius=max(2, int(side * 0.04)),
        fill=PANEL,
        outline=outline,
        width=outline_w,
    )
    _draw_qr_grid(
        draw,
        qx0 + side * 0.06, qy0 + side * 0.06,
        side * 0.88,
        cells=qr_cells,
        fg=GRAY_DARK,
        bracket_color=bracket_color,
    )
    return cx, cy_body, side


# ─── R1: Dashboard 스타일 (레퍼런스 1) ──────────────────────────────────

def _draw_line_chart(draw: ImageDraw.ImageDraw,
                      x0: float, y0: float, w: float, h: float,
                      color=BLUE):
    """우상향 라인 차트 카드 (프레임 + 선 + 화살표)."""
    draw.rounded_rectangle(
        (x0, y0, x0 + w, y0 + h),
        radius=max(2, int(h * 0.14)),
        fill=PANEL,
        outline=GRAY_LIGHT,
        width=2,
    )
    pad = h * 0.18
    pts = [
        (x0 + pad,             y0 + h - pad),
        (x0 + w * 0.35,        y0 + h * 0.55),
        (x0 + w * 0.60,        y0 + h * 0.68),
        (x0 + w * 0.88,        y0 + h * 0.22),
    ]
    lw = max(2, int(h * 0.09))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=lw)
    # 화살표
    tip = pts[-1]
    a = h * 0.18
    draw.polygon(
        [
            (tip[0] + a * 0.2, tip[1] - a * 0.3),
            (tip[0] - a * 0.7, tip[1] - a * 0.1),
            (tip[0] - a * 0.2, tip[1] + a * 0.6),
        ],
        fill=color,
    )


def _draw_bar_chart(draw: ImageDraw.ImageDraw,
                     x0: float, y0: float, w: float, h: float,
                     color=AMBER):
    """상승 3단 막대 차트 (얇은 간격)."""
    draw.rounded_rectangle(
        (x0, y0, x0 + w, y0 + h),
        radius=max(2, int(h * 0.14)),
        fill=PANEL,
        outline=GRAY_LIGHT,
        width=2,
    )
    pad_x = w * 0.14
    pad_y = h * 0.18
    gap = w * 0.06
    n = 3
    bw = (w - 2 * pad_x - gap * (n - 1)) / n
    heights = [0.30, 0.55, 0.82]
    for i, hf in enumerate(heights):
        bx0 = x0 + pad_x + i * (bw + gap)
        by1 = y0 + h - pad_y
        by0 = by1 - (h - 2 * pad_y) * hf
        draw.rounded_rectangle(
            (bx0, by0, bx0 + bw, by1),
            radius=max(1, int(bw * 0.18)),
            fill=color,
        )


def _draw_info_card(draw: ImageDraw.ImageDraw,
                     x0: float, y0: float, w: float, h: float,
                     bar_color=BLUE_SOFT):
    """가로 바 3줄 정보 카드."""
    draw.rounded_rectangle(
        (x0, y0, x0 + w, y0 + h),
        radius=max(2, int(h * 0.12)),
        fill=PANEL,
        outline=GRAY_LIGHT,
        width=2,
    )
    pad = h * 0.18
    slot_h = (h - 2 * pad) / 3
    widths = [0.82, 0.82, 0.58]
    bar_h = slot_h * 0.45
    for i, wf in enumerate(widths):
        by = y0 + pad + i * slot_h + (slot_h - bar_h) / 2
        draw.rounded_rectangle(
            (x0 + pad, by, x0 + pad + (w - 2 * pad) * wf, by + bar_h),
            radius=max(1, int(bar_h * 0.4)),
            fill=bar_color,
        )


def _draw_ok_pill(draw: ImageDraw.ImageDraw,
                   x0: float, y0: float, w: float, h: float,
                   font: ImageFont.ImageFont,
                   fill=BLUE, fg=WHITE):
    draw.rounded_rectangle(
        (x0, y0, x0 + w, y0 + h),
        radius=int(h / 2),
        fill=fill,
    )
    bbox = draw.textbbox((0, 0), "OK", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (x0 + (w - tw) / 2 - bbox[0],
         y0 + (h - th) / 2 - bbox[1]),
        "OK",
        font=font,
        fill=fg,
    )


def _draw_database_cyl(draw: ImageDraw.ImageDraw,
                        cx: float, cy: float, w: float, h: float,
                        color=BLUE_SOFT, outline=BLUE_DARK, lw: int = 2):
    x0 = cx - w / 2
    x1 = cx + w / 2
    y0 = cy - h / 2
    y1 = cy + h / 2
    ell_h = w * 0.38
    # 본체 사각형
    draw.rectangle((x0, y0 + ell_h / 2, x1, y1 - ell_h / 2),
                    fill=color)
    draw.line([(x0, y0 + ell_h / 2), (x0, y1 - ell_h / 2)], fill=outline, width=lw)
    draw.line([(x1, y0 + ell_h / 2), (x1, y1 - ell_h / 2)], fill=outline, width=lw)
    # 상단 타원
    draw.ellipse((x0, y0, x1, y0 + ell_h),
                  fill=color, outline=outline, width=lw)
    # 중간 림 2개
    for yf in (0.38, 0.66):
        my = y0 + (y1 - y0 - ell_h) * yf
        draw.ellipse((x0, my, x1, my + ell_h),
                      outline=outline, width=lw)
    # 하단 타원
    draw.ellipse((x0, y1 - ell_h, x1, y1),
                  fill=color, outline=outline, width=lw)


def design_r1_dashboard(size: int = BASE_SIZE) -> Image.Image:
    img = rounded_square_bg(size, BG_CREAM, radius_ratio=0.18).convert("RGBA")

    # ─── 1) 중앙 페달형 캐리어 ─────────────────────────────────────
    body_w = size * 0.44
    body_h = size * 0.44
    neck_h = size * 0.05
    neck_w = size * 0.22
    handle_h = size * 0.08
    handle_w = size * 0.18
    cx = size / 2
    cy_body = size * 0.47

    _draw_carrier(
        img, cx, cy_body,
        body_w, body_h,
        neck_h, neck_w,
        handle_h, handle_w,
        fill=GRAY_LIGHT,
        outline=GRAY_DARK,
        outline_w=max(2, int(size * 0.012)),
    )
    qx, qy, qs = _draw_qr_in_body(
        img, cx, cy_body, body_w, body_h,
        qr_cells=7,
        outline=GRAY_DARK,
        outline_w=max(1, int(size * 0.008)),
    )
    img = _draw_check_badge(
        img, cx=qx, cy=qy, r=qs * 0.18,
        bg=BLUE, fg=WHITE, outline=PANEL,
    )
    draw = ImageDraw.Draw(img)

    # ─── 2) 위성 요소 ─────────────────────────────────────────────
    sat_w = size * 0.20
    sat_h = size * 0.15

    # 좌상단 라인 차트
    _draw_line_chart(draw,
                      x0=size * 0.05, y0=size * 0.06,
                      w=sat_w, h=sat_h, color=BLUE)
    # 우상단 막대 차트
    _draw_bar_chart(draw,
                     x0=size - sat_w - size * 0.05, y0=size * 0.06,
                     w=sat_w, h=sat_h, color=AMBER)
    # 좌측 정보 카드 (블루)
    _draw_info_card(draw,
                     x0=size * 0.03, y0=size * 0.40,
                     w=size * 0.18, h=size * 0.18,
                     bar_color=BLUE_SOFT)
    # 우측 정보 카드 (앰버)
    _draw_info_card(draw,
                     x0=size - size * 0.18 - size * 0.03, y0=size * 0.40,
                     w=size * 0.18, h=size * 0.18,
                     bar_color=AMBER_SOFT)

    # 좌하단 OK 필
    ok_w = size * 0.18
    ok_h = size * 0.10
    font_ok = try_font(int(ok_h * 0.55), bold=True)
    _draw_ok_pill(draw,
                   x0=size * 0.06, y0=size - ok_h - size * 0.08,
                   w=ok_w, h=ok_h, font=font_ok,
                   fill=BLUE, fg=WHITE)
    # 우하단 DB 실린더
    db_w = size * 0.14
    db_h = size * 0.15
    _draw_database_cyl(draw,
                        cx=size - db_w * 0.85, cy=size - db_h * 0.65,
                        w=db_w, h=db_h,
                        color=BLUE_SOFT, outline=BLUE_DARK, lw=2)

    return img


# ─── R2: LotCard 스타일 (레퍼런스 2) ────────────────────────────────────

def _trapezoid_card(p_tl, p_tr, p_br, p_bl,
                     fill=(235, 245, 255, 220),
                     outline=(139, 173, 212, 255),
                     outline_w: int = 2) -> Image.Image:
    """카드 다각형 (반투명 블루). 별도 RGBA 레이어에 그려 반환."""
    # 카드 경계 바운딩 박스
    xs = [p[0] for p in (p_tl, p_tr, p_br, p_bl)]
    ys = [p[1] for p in (p_tl, p_tr, p_br, p_bl)]
    return (xs, ys)  # (caller uses polygon directly on overlay)


def design_r2_lotcard(size: int = BASE_SIZE) -> Image.Image:
    img = rounded_square_bg(size, BG_SOFT, radius_ratio=0.18).convert("RGBA")

    # ─── 1) 배경 캐리어 (약간 어두운 슬레이트) ───────────────────
    body_w = size * 0.58
    body_h = size * 0.38
    neck_h = size * 0.05
    neck_w = size * 0.22
    handle_h = size * 0.12
    handle_w = size * 0.18
    cx = size / 2
    cy_body = size * 0.43

    _draw_carrier(
        img, cx, cy_body,
        body_w, body_h,
        neck_h, neck_w,
        handle_h, handle_w,
        fill=(198, 208, 220, 255),
        outline=(76, 92, 110, 255),
        outline_w=max(2, int(size * 0.010)),
    )

    # ─── 2) 비스듬한 반투명 블루 카드 오버레이 ───────────────────
    card_w = size * 0.92
    card_h = size * 0.54
    card_cx = size / 2
    card_cy = size * 0.46

    skew_x = size * 0.035
    skew_y = size * 0.018
    p_tl = (card_cx - card_w / 2 - skew_x, card_cy - card_h / 2 + skew_y)
    p_tr = (card_cx + card_w / 2 - skew_x, card_cy - card_h / 2 - skew_y)
    p_br = (card_cx + card_w / 2 + skew_x, card_cy + card_h / 2 - skew_y)
    p_bl = (card_cx - card_w / 2 + skew_x, card_cy + card_h / 2 + skew_y)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon([p_tl, p_tr, p_br, p_bl],
                fill=(228, 240, 252, 215),
                outline=(120, 160, 205, 255))
    # 카드 외곽 굵은 라인
    lw_card = max(1, int(size * 0.006))
    for a, b in [(p_tl, p_tr), (p_tr, p_br), (p_br, p_bl), (p_bl, p_tl)]:
        od.line([a, b], fill=(120, 160, 205, 255), width=lw_card)
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # ─── 3) 카드 내부 텍스트 (4 코너) ───────────────────────────
    font_label = try_font(max(7, int(size * 0.038)), bold=True)
    font_value = try_font(max(9, int(size * 0.050)), bold=True)

    text_color_lbl = (105, 125, 150, 255)
    text_color_val = (40, 55, 75, 255)

    # 좌상단: LOT ID / NX2024A
    tx_l = card_cx - card_w * 0.46
    ty_top = card_cy - card_h * 0.40
    draw.text((tx_l, ty_top), "LOT ID:", font=font_label, fill=text_color_lbl)
    draw.text((tx_l, ty_top + size * 0.046), "NX2024A",
               font=font_value, fill=text_color_val)

    # 좌하단: STATUS / PASS (녹색 배지)
    tx_bl = card_cx - card_w * 0.46
    ty_bot = card_cy + card_h * 0.08
    draw.text((tx_bl, ty_bot), "STATUS:", font=font_label, fill=text_color_lbl)
    pass_w = size * 0.14
    pass_h = size * 0.062
    pass_x0 = tx_bl
    pass_y0 = ty_bot + size * 0.046
    draw.rounded_rectangle(
        (pass_x0, pass_y0, pass_x0 + pass_w, pass_y0 + pass_h),
        radius=int(pass_h / 2),
        fill=GREEN_SOFT,
        outline=GREEN,
        width=2,
    )
    bbox = draw.textbbox((0, 0), "PASS", font=font_label)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (pass_x0 + (pass_w - tw) / 2 - bbox[0],
         pass_y0 + (pass_h - th) / 2 - bbox[1]),
        "PASS",
        font=font_label,
        fill=GREEN_DARK,
    )

    # 우하단: QTY / 100
    tx_br = card_cx + card_w * 0.28
    ty_br = card_cy + card_h * 0.08
    draw.text((tx_br, ty_br), "QTY:", font=font_label, fill=text_color_lbl)
    draw.text((tx_br, ty_br + size * 0.046), "100",
               font=font_value, fill=text_color_val)

    # ─── 4) 카드 중앙 QR + 코너 브래킷 + 체크 ───────────────────
    qr_side = card_h * 0.62
    qr_cx = card_cx
    qr_cy = card_cy - card_h * 0.02
    qx0 = qr_cx - qr_side / 2
    qy0 = qr_cy - qr_side / 2
    draw.rounded_rectangle(
        (qx0, qy0, qx0 + qr_side, qy0 + qr_side),
        radius=max(2, int(qr_side * 0.04)),
        fill=PANEL,
        outline=(180, 200, 220, 255),
        width=1,
    )
    _draw_qr_grid(
        draw,
        qx0 + qr_side * 0.06, qy0 + qr_side * 0.06,
        qr_side * 0.88,
        cells=7,
        fg=GRAY_DARK,
        bracket_color=BLUE,
    )
    img = _draw_check_badge(
        img, cx=qr_cx, cy=qr_cy, r=qr_side * 0.18,
        bg=BLUE, fg=WHITE, outline=PANEL,
    )

    # ─── 5) QR 좌우로 뻗는 연결 라인 ─────────────────────────────
    draw = ImageDraw.Draw(img)
    lw_conn = max(1, int(size * 0.007))
    line_color = (130, 170, 210, 255)
    left_x0 = qx0 - size * 0.005
    left_x1 = card_cx - card_w * 0.45
    right_x0 = qx0 + qr_side + size * 0.005
    right_x1 = card_cx + card_w * 0.45
    # 좌측 라인: 위/아래 두 가닥
    for dy_f in (-0.10, 0.10):
        y = qr_cy + card_h * dy_f
        draw.line([(left_x0, y), (left_x1, y)], fill=line_color, width=lw_conn)
        draw.line([(right_x0, y), (right_x1, y)], fill=line_color, width=lw_conn)

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_r1_dashboard", design_r1_dashboard, "Dashboard (Ref1)"),
        ("icon_r2_lotcard",   design_r2_lotcard,   "LotCard (Ref2)"),
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

    # 2개 1x2 비교 그리드
    print("\n[Generating] comparison grid (R1 R2)")
    cell = 256
    gap = 12
    grid = Image.new(
        "RGBA",
        (cell * 2 + gap * 3, cell + gap * 2),
        (20, 20, 30, 255),
    )
    for i, (name, _, _) in enumerate(variants):
        im = Image.open(out_dir / f"{name}_256.png")
        x = gap + i * (cell + gap)
        y = gap
        grid.paste(im, (x, y), im)
    grid_path = out_dir / "compare_r1_r2.png"
    grid.save(grid_path, format="PNG")
    print(f"  -> {grid_path.name}")

    print(f"\nAll reference-based icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
