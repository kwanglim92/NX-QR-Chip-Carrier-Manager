"""앱 아이콘 — Dashboard v2 (레퍼런스 이미지 그대로 재현).

구조:
  - 흰 배경 (iOS 스타일 대형 라운드 코너)
  - 중앙 캐리어: 상단 둥근 + 하단 모따기(chamfer) 팔각형 + 아래 얇은 스템
  - 캐리어 내부: 큰 QR + 파란 코너 브래킷 + 파란 체크 배지
  - 좌상단: 라인 차트 (L축 + 파란 화살표 선)
  - 우상단: 막대 차트 (3단 노랑 바 + 베이스라인)
  - 좌중단: 3줄 파란 바 카드
  - 우중단: 3줄 노랑 바 카드
  - 좌하단: "OK" 파란 필 버튼
  - 우하단: 폴더 아이콘 (DB 실린더 대체)

산출물:
  assets/icons/icon_dashboard_v2.ico / _256.png / _sizes_*.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import BASE_SIZE, rounded_square_bg, save_ico, try_font
from generate_icon_qr_manage import _draw_check_badge

# ─── 팔레트 ─────────────────────────────────────────────────────────────

BG_WHITE    = (255, 255, 255, 255)
GRAY_DARK   = (55, 65, 81, 255)
GRAY_MID    = (107, 114, 128, 255)
GRAY_LIGHT  = (220, 224, 228, 255)
GRAY_CARRIER= (215, 218, 224, 255)
PANEL       = (255, 255, 255, 255)
WHITE       = (255, 255, 255, 255)

BLUE        = (59, 130, 246, 255)
BLUE_DARK   = (37, 99, 235, 255)
BLUE_FILL   = (59, 130, 246, 255)
BLUE_SOFT   = (147, 197, 253, 255)

AMBER       = (245, 158, 11, 255)
AMBER_SOFT  = (253, 230, 138, 255)

AXIS_COLOR  = (75, 85, 99, 255)   # 차트 축 라인


# ─── 캐리어 형상 (팔각형: 상단 라운드 + 하단 모따기) ────────────────────

def _carrier_shape_pts(cx: float, cy_body: float,
                        body_w: float, body_h: float,
                        corner_r: float, chamfer: float,
                        stem_w: float, stem_h: float) -> list[tuple[float, float]]:
    """
    팔각형(상단 2코너 라운드 + 하단 2코너 45° 모따기) + 아래 스템 경로.
    상단 코너는 arc_steps 개의 점으로 근사.
    """
    x0 = cx - body_w / 2
    x1 = cx + body_w / 2
    y0 = cy_body - body_h / 2
    y1 = cy_body + body_h / 2
    arc_steps = 14

    pts: list[tuple[float, float]] = []

    # ── 좌상단 라운드 코너 (π → 3π/2) ──
    acx, acy = x0 + corner_r, y0 + corner_r
    for i in range(arc_steps + 1):
        a = math.pi + (i / arc_steps) * (math.pi / 2)
        pts.append((acx + corner_r * math.cos(a), acy + corner_r * math.sin(a)))

    # ── 우상단 라운드 코너 (3π/2 → 2π) ──
    acx, acy = x1 - corner_r, y0 + corner_r
    for i in range(arc_steps + 1):
        a = 3 * math.pi / 2 + (i / arc_steps) * (math.pi / 2)
        pts.append((acx + corner_r * math.cos(a), acy + corner_r * math.sin(a)))

    # ── 우측 직선 내려옴 ──
    pts.append((x1, y1 - chamfer))
    # ── 우하단 모따기 ──
    pts.append((x1 - chamfer, y1))
    # ── 스템 오른쪽 ──
    pts.append((cx + stem_w / 2, y1))
    pts.append((cx + stem_w / 2, y1 + stem_h))
    # ── 스템 바닥 ──
    pts.append((cx - stem_w / 2, y1 + stem_h))
    # ── 스템 왼쪽 ──
    pts.append((cx - stem_w / 2, y1))
    # ── 좌하단 모따기 ──
    pts.append((x0 + chamfer, y1))
    pts.append((x0, y1 - chamfer))
    # (좌측 직선은 첫 점으로 자동 닫힘)

    return pts


def _draw_carrier(img: Image.Image,
                   cx: float, cy_body: float,
                   body_w: float, body_h: float,
                   corner_r: float, chamfer: float,
                   stem_w: float, stem_h: float,
                   fill=GRAY_CARRIER, outline=GRAY_DARK,
                   lw: int = 3) -> None:
    """캐리어 + 스템을 img에 직접 그린다."""
    # 그림자 (아래-오른쪽 오프셋)
    shadow_off = max(2, int(img.size[0] * 0.010))
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shd)
    pts_shd = _carrier_shape_pts(
        cx + shadow_off, cy_body + shadow_off,
        body_w, body_h, corner_r, chamfer, stem_w, stem_h,
    )
    sdraw.polygon(pts_shd, fill=(100, 110, 130, 55))
    img.alpha_composite(shd)

    draw = ImageDraw.Draw(img)
    pts = _carrier_shape_pts(cx, cy_body, body_w, body_h, corner_r, chamfer, stem_w, stem_h)

    # 본체 채우기
    draw.polygon(pts, fill=fill)
    # 외곽선 (세그먼트별)
    for i in range(len(pts)):
        draw.line([pts[i], pts[(i + 1) % len(pts)]], fill=outline, width=lw)


# ─── QR 코드 (파인더 패턴 포함, 9×9 셀) ──────────────────────────────────

_QR9 = [
    "111111011",
    "100001001",
    "101101011",
    "101101001",
    "100001010",
    "111111010",
    "001000101",
    "010110010",
    "101001101",
]


def _draw_qr9(draw: ImageDraw.ImageDraw,
               x0: float, y0: float, side: float,
               fg=GRAY_DARK) -> None:
    """9×9 의사-QR (파인더 패턴 포함). bracket 은 별도 함수."""
    n = 9
    cell = side / n
    for r in range(n):
        for c in range(n):
            if _QR9[r][c] == "1":
                gap = cell * 0.06
                draw.rectangle(
                    (x0 + c * cell + gap,
                     y0 + r * cell + gap,
                     x0 + (c + 1) * cell - gap,
                     y0 + (r + 1) * cell - gap),
                    fill=fg,
                )


def _draw_brackets(draw: ImageDraw.ImageDraw,
                    x0: float, y0: float, side: float,
                    color=BLUE, blen_ratio: float = 0.22,
                    bw: int = 4) -> None:
    """QR 4 모서리 L자 파란 브래킷."""
    blen = side * blen_ratio
    corners = [
        # (시작점, 가로끝, 세로끝)
        ((x0,        y0),        (x0 + blen, y0),        (x0,        y0 + blen)),
        ((x0 + side, y0),        (x0 + side - blen, y0), (x0 + side, y0 + blen)),
        ((x0,        y0 + side), (x0 + blen, y0 + side), (x0,        y0 + side - blen)),
        ((x0 + side, y0 + side), (x0 + side - blen, y0 + side), (x0 + side, y0 + side - blen)),
    ]
    for origin, h_end, v_end in corners:
        draw.line([origin, h_end], fill=color, width=bw)
        draw.line([origin, v_end], fill=color, width=bw)


# ─── 위성 요소들 ──────────────────────────────────────────────────────────

def _draw_line_chart(draw: ImageDraw.ImageDraw,
                      x0: float, y0: float, w: float, h: float) -> None:
    """L자 축 + 우상향 파란 선 + 화살표."""
    lw = max(2, int(h * 0.06))
    # L축
    ax_y = y0 + h * 0.88
    ax_x = x0 + w * 0.08
    draw.line([(ax_x, y0 + h * 0.12), (ax_x, ax_y)], fill=AXIS_COLOR, width=lw)
    draw.line([(ax_x, ax_y), (x0 + w * 0.95, ax_y)], fill=AXIS_COLOR, width=lw)
    # 데이터 선
    pts = [
        (ax_x + w * 0.05,  ax_y - h * 0.12),
        (ax_x + w * 0.28,  ax_y - h * 0.38),
        (ax_x + w * 0.52,  ax_y - h * 0.28),
        (ax_x + w * 0.76,  ax_y - h * 0.68),
    ]
    dlw = max(2, int(h * 0.09))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=BLUE, width=dlw)
    # 화살표 (마지막 점 우상방)
    tip = pts[-1]
    a = h * 0.16
    draw.polygon([
        (tip[0] + a * 0.25, tip[1] - a * 0.25),
        (tip[0] - a * 0.60, tip[1] - a * 0.05),
        (tip[0] - a * 0.15, tip[1] + a * 0.55),
    ], fill=BLUE)


def _draw_bar_chart(draw: ImageDraw.ImageDraw,
                     x0: float, y0: float, w: float, h: float) -> None:
    """베이스라인 + 3단 노랑 막대."""
    lw = max(2, int(h * 0.06))
    base_y = y0 + h * 0.88
    ax_x   = x0 + w * 0.08
    # 베이스라인 + 좌측 축
    draw.line([(ax_x, y0 + h * 0.12), (ax_x, base_y)], fill=AXIS_COLOR, width=lw)
    draw.line([(ax_x, base_y), (x0 + w * 0.95, base_y)], fill=AXIS_COLOR, width=lw)
    # 3개 막대
    n = 3
    usable_w = w * 0.80
    pad_x = ax_x - x0 + w * 0.06
    gap = usable_w * 0.08
    bw = (usable_w - gap * (n + 1)) / n
    heights = [0.32, 0.56, 0.84]
    for i, hf in enumerate(heights):
        bx0 = x0 + pad_x + gap + i * (bw + gap)
        by0 = base_y - (h * 0.72) * hf
        draw.rounded_rectangle(
            (bx0, by0, bx0 + bw, base_y),
            radius=max(1, int(bw * 0.20)),
            fill=AMBER,
        )


def _draw_info_card(draw: ImageDraw.ImageDraw,
                     x0: float, y0: float, w: float, h: float,
                     bar_color) -> None:
    """얇은 박스 + 3줄 바."""
    lw = max(1, int(h * 0.05))
    draw.rectangle((x0, y0, x0 + w, y0 + h),
                    fill=(250, 251, 252, 255),
                    outline=GRAY_LIGHT)
    pad = h * 0.16
    slot_h = (h - 2 * pad) / 3
    bh = slot_h * 0.48
    widths = [1.0, 1.0, 0.62]
    for i, wf in enumerate(widths):
        by = y0 + pad + i * slot_h + (slot_h - bh) / 2
        bw = (w - 2 * pad) * wf
        draw.rounded_rectangle(
            (x0 + pad, by, x0 + pad + bw, by + bh),
            radius=max(1, int(bh * 0.4)),
            fill=bar_color,
        )


def _draw_ok_pill(draw: ImageDraw.ImageDraw,
                   x0: float, y0: float, w: float, h: float,
                   font: ImageFont.ImageFont) -> None:
    draw.rounded_rectangle(
        (x0, y0, x0 + w, y0 + h),
        radius=int(h / 2),
        fill=BLUE,
    )
    bbox = draw.textbbox((0, 0), "OK", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (x0 + (w - tw) / 2 - bbox[0],
         y0 + (h - th) / 2 - bbox[1] - h * 0.04),
        "OK",
        font=font,
        fill=WHITE,
    )


def _draw_folder(draw: ImageDraw.ImageDraw,
                  cx: float, cy: float, w: float, h: float,
                  fill=(245, 210, 90, 255),
                  outline=AXIS_COLOR,
                  lw: int = 3) -> None:
    """폴더 아이콘: 탭이 있는 직사각형."""
    # 폴더 탭 (상단 왼쪽 작은 사각형)
    tab_w = w * 0.42
    tab_h = h * 0.18
    tab_x0 = cx - w / 2
    tab_y0 = cy - h / 2
    tab_x1 = tab_x0 + tab_w
    tab_y1 = tab_y0 + tab_h

    # 폴더 본체
    body_x0 = cx - w / 2
    body_y0 = tab_y1 - lw / 2          # 탭과 이어짐
    body_x1 = cx + w / 2
    body_y1 = cy + h / 2

    body_r = max(2, int(h * 0.06))
    tab_r  = max(1, int(tab_h * 0.35))

    # 탭
    draw.rounded_rectangle(
        (tab_x0, tab_y0, tab_x1, tab_y1),
        radius=tab_r,
        fill=fill,
        outline=outline,
        width=lw,
    )
    # 본체 (탭 아래 덮어씌워 경계 숨김)
    draw.rounded_rectangle(
        (body_x0, body_y0, body_x1, body_y1),
        radius=body_r,
        fill=fill,
        outline=outline,
        width=lw,
    )
    # 탭과 본체 사이 내부 연결선 가림 (같은 fill 색으로 덮기)
    draw.rectangle(
        (body_x0 + lw, body_y0, body_x1 - lw, body_y0 + lw + 2),
        fill=fill,
    )


# ─── 메인 디자인 ─────────────────────────────────────────────────────────

def design_dashboard_v2(size: int = BASE_SIZE) -> Image.Image:
    img = rounded_square_bg(size, BG_WHITE, radius_ratio=0.185).convert("RGBA")

    # ── 1. 캐리어 ──────────────────────────────────────────────────
    body_w   = size * 0.500
    body_h   = size * 0.488
    corner_r = size * 0.072
    chamfer  = size * 0.068
    stem_w   = size * 0.072
    stem_h   = size * 0.165
    cx       = size / 2
    cy_body  = size * 0.420

    _draw_carrier(
        img, cx, cy_body,
        body_w, body_h,
        corner_r, chamfer,
        stem_w, stem_h,
        fill=GRAY_CARRIER,
        outline=GRAY_DARK,
        lw=max(2, int(size * 0.013)),
    )

    # ── 2. QR + 브래킷 + 체크 ──────────────────────────────────────
    qr_side = body_w * 0.820
    qx0     = cx - qr_side / 2
    qy0     = cy_body - qr_side / 2 - body_h * 0.01
    qr_bg_pad = qr_side * 0.04

    # QR 흰 배경
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (qx0 - qr_bg_pad, qy0 - qr_bg_pad,
         qx0 + qr_side + qr_bg_pad, qy0 + qr_side + qr_bg_pad),
        radius=max(2, int(qr_side * 0.04)),
        fill=(255, 255, 255, 255),
    )

    # QR 격자
    _draw_qr9(draw, qx0, qy0, qr_side, fg=GRAY_DARK)

    # 브래킷
    blen_px = max(3, int(size * 0.025))
    _draw_brackets(
        draw, qx0, qy0, qr_side,
        color=BLUE,
        blen_ratio=0.215,
        bw=max(3, int(size * 0.016)),
    )

    # 체크 배지
    img = _draw_check_badge(
        img,
        cx=cx,
        cy=qy0 + qr_side / 2,
        r=qr_side * 0.195,
        bg=BLUE,
        fg=WHITE,
        outline=WHITE,
    )
    draw = ImageDraw.Draw(img)

    # ── 3. 위성 요소 배치 ──────────────────────────────────────────
    sat_w  = size * 0.200
    sat_h  = size * 0.165
    card_w = size * 0.168
    card_h = size * 0.148

    # (좌상단) 라인 차트
    _draw_line_chart(draw,
                      x0=size * 0.045, y0=size * 0.070,
                      w=sat_w, h=sat_h)

    # (우상단) 막대 차트
    _draw_bar_chart(draw,
                     x0=size - sat_w - size * 0.045, y0=size * 0.070,
                     w=sat_w, h=sat_h)

    # (좌중단) 파란 바 카드
    _draw_info_card(draw,
                     x0=size * 0.032, y0=size * 0.440,
                     w=card_w, h=card_h,
                     bar_color=BLUE_SOFT)

    # (우중단) 노란 바 카드
    _draw_info_card(draw,
                     x0=size - card_w - size * 0.032, y0=size * 0.440,
                     w=card_w, h=card_h,
                     bar_color=AMBER_SOFT)

    # (좌하단) OK 필 버튼
    ok_w   = size * 0.185
    ok_h   = size * 0.092
    ok_x0  = size * 0.072
    ok_y0  = size * 0.810
    font_ok = try_font(max(9, int(ok_h * 0.62)), bold=True)
    _draw_ok_pill(draw,
                   x0=ok_x0, y0=ok_y0,
                   w=ok_w, h=ok_h,
                   font=font_ok)

    # (우하단) 폴더 아이콘
    fold_w = size * 0.172
    fold_h = size * 0.148
    fold_cx = size - fold_w * 0.72
    fold_cy = size * 0.862
    _draw_folder(draw,
                  cx=fold_cx, cy=fold_cy,
                  w=fold_w, h=fold_h,
                  fill=(245, 192, 55, 255),
                  outline=AXIS_COLOR,
                  lw=max(2, int(size * 0.011)))

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    name  = "icon_dashboard_v2"
    label = "Dashboard v2 (ref + folder)"

    print(f"[Generating] {name}  - {label}")
    img = design_dashboard_v2(BASE_SIZE)

    png_path = out_dir / f"{name}_256.png"
    img.save(png_path, format="PNG")

    sizes   = [16, 32, 48, 64, 128]
    total_w = sum(sizes) + 10 * len(sizes) + 20
    strip   = Image.new("RGBA", (total_w, max(sizes) + 20), (20, 20, 30, 255))
    x = 10
    for s in sizes:
        sm = img.resize((s, s), Image.Resampling.LANCZOS)
        y  = (strip.height - sm.height) // 2
        strip.paste(sm, (x, y), sm)
        x += sm.width + 10
    strip_path = out_dir / f"{name}_sizes_16_32_48_64_128.png"
    strip.save(strip_path, format="PNG")

    ico_path = out_dir / f"{name}.ico"
    save_ico(img, ico_path)

    print(f"  -> {png_path.name}")
    print(f"  -> {strip_path.name}")
    print(f"  -> {ico_path.name}")
    print(f"\nSaved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
