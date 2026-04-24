"""앱 아이콘 — 레퍼런스 이미지 그대로 재현.

구조:
  - 가로형 라운드 직사각형 카드 (landscape) + 하단 중앙 가는 스템
  - 좌상: LOT ID: / NX2024A
  - 좌하: STATUS: / PASS
  - 우하: QTY: / 100
  - 우상단: 햄버거 메뉴 아이콘 (3선)
  - 중앙: QR + 파란 코너 브래킷 + 파란 체크 배지
  - QR 좌우: 파란 연결선 (위/아래 2가닥씩)

산출물:
  assets/icons/icon_lotcard_v2.ico / _256.png / _sizes_*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import BASE_SIZE, rounded_square_bg, save_ico, try_font
from generate_icon_qr_manage import _draw_qr_grid, _draw_check_badge

# ─── 팔레트 ─────────────────────────────────────────────────────────────

BG          = (226, 235, 245, 255)   # 아이콘 배경 (연한 블루그레이)
CARD_FILL   = (248, 250, 252, 255)   # 카드 내부 (거의 흰색)
CARD_BORDER = (190, 200, 215, 255)   # 카드 테두리
STEM_FILL   = (220, 225, 232, 255)   # 스템 본체
STEM_BORDER = (160, 170, 185, 255)   # 스템 테두리

GRAY_DARK   = (50, 60, 75, 255)      # 진한 텍스트, QR 모듈
GRAY_MID    = (130, 145, 165, 255)   # 라벨 텍스트
WHITE       = (255, 255, 255, 255)

BLUE        = (59, 130, 246, 255)    # 브래킷, 체크, 연결선
BLUE_LIGHT  = (147, 197, 253, 255)   # 연결선 보조


def design_lotcard(size: int = BASE_SIZE) -> Image.Image:
    img = rounded_square_bg(size, BG, radius_ratio=0.16).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # ── 1. 가로형 카드 본체 ─────────────────────────────────────
    card_w  = size * 0.86
    card_h  = size * 0.62
    card_x0 = (size - card_w) / 2
    card_y0 = size * 0.08
    card_x1 = card_x0 + card_w
    card_y1 = card_y0 + card_h
    card_r  = int(size * 0.055)

    # 카드 그림자 (연한 오프셋)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw  = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (card_x0 + 3, card_y0 + 4, card_x1 + 3, card_y1 + 4),
        radius=card_r,
        fill=(160, 175, 195, 55),
    )
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    # 카드 본체
    draw.rounded_rectangle(
        (card_x0, card_y0, card_x1, card_y1),
        radius=card_r,
        fill=CARD_FILL,
        outline=CARD_BORDER,
        width=max(2, int(size * 0.010)),
    )

    # ── 2. 하단 스템(핸들) ────────────────────────────────────────
    stem_w  = size * 0.085
    stem_h  = size * 0.22
    stem_x0 = (size - stem_w) / 2
    stem_y0 = card_y1 - 2        # 카드와 겹쳐서 자연스럽게 연결
    stem_x1 = stem_x0 + stem_w
    stem_y1 = stem_y0 + stem_h

    # 스템 본체
    draw.rectangle(
        (stem_x0, stem_y0, stem_x1, stem_y1),
        fill=STEM_FILL,
    )
    # 스템 좌우 테두리 선
    lw_stem = max(1, int(size * 0.009))
    draw.line([(stem_x0, stem_y0), (stem_x0, stem_y1)],
               fill=STEM_BORDER, width=lw_stem)
    draw.line([(stem_x1, stem_y0), (stem_x1, stem_y1)],
               fill=STEM_BORDER, width=lw_stem)
    draw.line([(stem_x0, stem_y1), (stem_x1, stem_y1)],
               fill=STEM_BORDER, width=lw_stem)

    # ── 3. 카드 내부 레이아웃 설정 ───────────────────────────────
    inner_pad = size * 0.048    # 카드 내부 여백
    cx = size / 2               # 아이콘 가로 중앙
    cy = card_y0 + card_h / 2   # 카드 세로 중앙

    # QR 크기: 카드 높이의 58%, 가로 동일(정사각)
    qr_side = card_h * 0.58
    qr_x0   = cx - qr_side / 2
    qr_y0   = card_y0 + (card_h - qr_side) / 2
    qr_x1   = qr_x0 + qr_side
    qr_y1   = qr_y0 + qr_side

    # ── 4. 텍스트 폰트 ───────────────────────────────────────────
    font_lbl = try_font(max(7, int(size * 0.036)), bold=False)
    font_val = try_font(max(8, int(size * 0.046)), bold=True)

    # ── 5. 좌상단: LOT ID: / NX2024A ─────────────────────────────
    tx_left   = card_x0 + inner_pad
    ty_upper  = card_y0 + inner_pad * 0.9
    draw.text((tx_left, ty_upper),
               "LOT ID:", font=font_lbl, fill=GRAY_MID)
    draw.text((tx_left, ty_upper + size * 0.040),
               "NX2024A", font=font_val, fill=GRAY_DARK)

    # ── 6. 좌하단: STATUS: / PASS ─────────────────────────────────
    ty_lower = cy + card_h * 0.08
    draw.text((tx_left, ty_lower),
               "STATUS:", font=font_lbl, fill=GRAY_MID)
    draw.text((tx_left, ty_lower + size * 0.040),
               "PASS", font=font_val, fill=GRAY_DARK)

    # ── 7. 우하단: QTY: / 100 ─────────────────────────────────────
    tx_right  = qr_x1 + inner_pad * 0.6
    draw.text((tx_right, ty_lower),
               "QTY:", font=font_lbl, fill=GRAY_MID)
    draw.text((tx_right, ty_lower + size * 0.040),
               "100", font=font_val, fill=GRAY_DARK)

    # ── 8. 우상단: 햄버거 메뉴(3선) ──────────────────────────────
    hmb_x0   = qr_x1 + inner_pad * 0.4
    hmb_x1   = card_x1 - inner_pad * 0.8
    hmb_y    = card_y0 + inner_pad * 1.0
    hmb_gap  = size * 0.025
    hmb_lw   = max(1, int(size * 0.014))
    hmb_color = (185, 195, 210, 255)
    for i in range(3):
        y = hmb_y + i * hmb_gap
        # 3번째 줄은 조금 짧게 (레퍼런스 스타일)
        x0_line = hmb_x0
        x1_line = hmb_x1 if i < 2 else hmb_x0 + (hmb_x1 - hmb_x0) * 0.65
        draw.line([(x0_line, y), (x1_line, y)],
                   fill=hmb_color, width=hmb_lw)

    # ── 9. QR 연결선 (좌우 2가닥씩) ──────────────────────────────
    conn_y_top  = qr_y0 + qr_side * 0.28
    conn_y_bot  = qr_y0 + qr_side * 0.72
    conn_lw     = max(1, int(size * 0.010))
    # 좌측 선: QR 왼쪽 → 카드 왼쪽 가장자리
    left_end  = card_x0 + inner_pad * 0.3
    left_start = qr_x0
    # 우측 선: QR 오른쪽 → 카드 오른쪽 가장자리
    right_start = qr_x1
    right_end   = card_x1 - inner_pad * 0.3
    for conn_y in (conn_y_top, conn_y_bot):
        draw.line([(left_start, conn_y), (left_end, conn_y)],
                   fill=BLUE, width=conn_lw)
        draw.line([(right_start, conn_y), (right_end, conn_y)],
                   fill=BLUE, width=conn_lw)

    # ── 10. QR 흰 배경 ───────────────────────────────────────────
    draw.rounded_rectangle(
        (qr_x0, qr_y0, qr_x1, qr_y1),
        radius=max(2, int(qr_side * 0.03)),
        fill=(255, 255, 255, 255),
        outline=(220, 228, 238, 255),
        width=1,
    )

    # ── 11. QR 격자 + 파란 코너 브래킷 ──────────────────────────
    qr_inner_pad = qr_side * 0.07
    _draw_qr_grid(
        draw,
        qr_x0 + qr_inner_pad,
        qr_y0 + qr_inner_pad,
        qr_side - 2 * qr_inner_pad,
        cells=7,
        fg=GRAY_DARK,
        bracket_color=BLUE,
    )

    # ── 12. 체크 배지 (QR 중앙) ──────────────────────────────────
    img = _draw_check_badge(
        img,
        cx=cx,
        cy=qr_y0 + qr_side / 2,
        r=qr_side * 0.185,
        bg=BLUE,
        fg=WHITE,
        outline=(255, 255, 255, 255),
    )

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    name    = "icon_lotcard_v2"
    label   = "LotCard v2 (ref exact)"

    print(f"[Generating] {name}  - {label}")
    img = design_lotcard(BASE_SIZE)

    png_path = out_dir / f"{name}_256.png"
    img.save(png_path, format="PNG")

    # 소형 크기 스트립
    sizes     = [16, 32, 48, 64, 128]
    total_w   = sum(sizes) + 10 * len(sizes) + 20
    strip     = Image.new("RGBA", (total_w, max(sizes) + 20), (20, 20, 30, 255))
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
    print(f"\nSaved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
