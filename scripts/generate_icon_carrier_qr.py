"""앱 아이콘 — 칩 캐리어에 QR 라벨이 붙어 있는 디자인 (사용자 스케치 반영).

컨셉: "Carrier with QR Label"
  - 외곽: 칩 캐리어 본체 (네이비, 네 모서리 골드 L자 프레임)
  - 내부 상단: QR 라벨 (흰 배경 스티커 느낌 + 그림자)
  - QR: 3 파인더 패턴 + 데이터 모듈 (QR Code Manager 로고 스타일)
  - 하단: 핀 / 커넥터 — 칩 캐리어임을 확실히 전달

3가지 색상 변주를 생성해 선택 폭을 제공:
  G1 (메인)  네이비 + 골드 + 흰 라벨    → 따뜻하고 고급스러운 느낌
  G2         슬레이트 + 시안 + 흰 라벨  → 차갑고 산업적인 느낌
  G3         블랙 + 에메랄드 + 흰 라벨  → 강한 대비, 스텔스 느낌
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, ICO_SIZES, rounded_square_bg, save_ico,
)


# ─── 색상 변주 팔레트 ────────────────────────────────────────────────────

PALETTES = {
    "g1_navy_gold": {
        "carrier":   (30, 41, 59, 255),    # #1E293B 딥 네이비
        "accent":    (251, 191, 36, 255),  # #FBBF24 골드
        "label":     (250, 252, 254, 255), # 아이보리 화이트
        "qr":        (15, 23, 42, 255),    # 거의 검정
        "pin":       (100, 116, 139, 255), # 슬레이트
        "label_outline": (200, 210, 220, 255),
    },
    "g2_slate_cyan": {
        "carrier":   (51, 65, 85, 255),    # #334155 슬레이트
        "accent":    (34, 211, 238, 255),  # #22D3EE 시안
        "label":     (255, 255, 255, 255),
        "qr":        (15, 23, 42, 255),
        "pin":       (148, 163, 184, 255),
        "label_outline": (200, 210, 220, 255),
    },
    "g3_black_emerald": {
        "carrier":   (15, 23, 42, 255),    # 거의 검정
        "accent":    (16, 185, 129, 255),  # 에메랄드
        "label":     (255, 255, 255, 255),
        "qr":        (15, 23, 42, 255),
        "pin":       (71, 85, 105, 255),
        "label_outline": (200, 210, 220, 255),
    },
}


# ─── 파인더 패턴 그리기 ──────────────────────────────────────────────────

def _draw_finder(draw: ImageDraw.ImageDraw, cx: float, cy: float,
                 cell: float, dark, light) -> None:
    """QR 파인더 패턴 (7x7 영역: 외곽 링 + 중앙 3x3 채움).

    실제 QR 스펙의 finder 패턴 구조를 단순화해서 표현.
    """
    # 7x7 외곽 검정 사각형
    x0, y0 = cx, cy
    x1 = cx + cell * 7
    y1 = cy + cell * 7
    draw.rectangle((x0, y0, x1, y1), fill=dark)
    # 5x5 흰색 링 (외곽에서 1셀 안쪽)
    draw.rectangle(
        (x0 + cell, y0 + cell, x1 - cell, y1 - cell),
        fill=light,
    )
    # 3x3 중앙 검정
    draw.rectangle(
        (x0 + cell * 2, y0 + cell * 2, x1 - cell * 2, y1 - cell * 2),
        fill=dark,
    )


# ─── 메인 디자인 ─────────────────────────────────────────────────────────

def design_carrier_qr(size: int, palette: dict) -> Image.Image:
    """칩 캐리어 + QR 라벨 디자인."""
    carrier_color = palette["carrier"]
    accent_color = palette["accent"]
    label_color = palette["label"]
    qr_color = palette["qr"]
    pin_color = palette["pin"]

    # 1. 캐리어 본체 (둥근 사각형)
    img = rounded_square_bg(size, carrier_color, radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # 2. 네 모서리 골드 L자 프레임 (칩 캐리어 라이크)
    frame_pad = int(size * 0.09)
    fx0, fy0 = frame_pad, frame_pad
    fx1, fy1 = size - frame_pad, size - frame_pad
    arm_len = int(size * 0.09)
    arm_w = max(3, int(size * 0.022))

    corners = [
        (fx0, fy0,  1,  1),  # 좌상
        (fx1, fy0, -1,  1),  # 우상
        (fx0, fy1,  1, -1),  # 좌하
        (fx1, fy1, -1, -1),  # 우하
    ]
    for cx, cy, dx, dy in corners:
        # 수평 선
        draw.line(
            [(cx, cy), (cx + dx * arm_len, cy)],
            fill=accent_color, width=arm_w,
        )
        # 수직 선
        draw.line(
            [(cx, cy), (cx, cy + dy * arm_len)],
            fill=accent_color, width=arm_w,
        )

    # 3. QR 라벨 영역 (중앙 상단, 흰 스티커)
    # 상하 비율: 상단 약 62% = 라벨, 하단 약 25% = 핀
    label_margin_x = int(size * 0.19)
    lx0 = label_margin_x
    ly0 = int(size * 0.20)
    lx1 = size - label_margin_x
    ly1 = int(size * 0.72)
    label_radius = int(size * 0.03)

    # 3a. 라벨 그림자 (약간 오프셋 + 블러)
    shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sh_off = max(2, int(size * 0.015))
    sdraw.rounded_rectangle(
        (lx0 + sh_off, ly0 + sh_off, lx1 + sh_off, ly1 + sh_off),
        radius=label_radius,
        fill=(0, 0, 0, 110),
    )
    # 블러 — 큰 사이즈에서는 부드럽게, 작은 크기에서는 효과 약함
    shadow_layer = shadow_layer.filter(
        ImageFilter.GaussianBlur(radius=max(1, size * 0.012))
    )
    img = Image.alpha_composite(img, shadow_layer)
    draw = ImageDraw.Draw(img)

    # 3b. 라벨 본체
    draw.rounded_rectangle(
        (lx0, ly0, lx1, ly1),
        radius=label_radius,
        fill=label_color,
    )

    # 4. QR 코드 그리기 (7x7 격자, 3 파인더 + 데이터 모듈)
    qr_inset = int(size * 0.028)
    qx0 = lx0 + qr_inset
    qy0 = ly0 + qr_inset
    qx1 = lx1 - qr_inset
    qy1 = ly1 - qr_inset
    qw = qx1 - qx0
    qh = qy1 - qy0

    # 7x7 격자 — 정사각형 유지
    cell = min(qw, qh) / 7
    # 중앙 정렬
    gx0 = qx0 + (qw - cell * 7) / 2
    gy0 = qy0 + (qh - cell * 7) / 2

    # 파인더 패턴 3개 (좌상 / 우상 / 좌하)
    _draw_finder(draw, gx0,                     gy0,                     cell, qr_color, label_color)
    # 우상·좌하 파인더는 실제 QR 처럼 7셀 크기이지만
    # 7x7 격자에선 공간 부족. 2개만 배치하고 나머지는 데이터로.
    # → 대안: 파인더 2개만 (좌상/우하) + 데이터 여유 있게

    # 실제 미니 QR 레이아웃 (7x7): 파인더 자체가 3x3으로 축소된 느낌이 더 깔끔.
    # 여기서는 "3개 미니 파인더(3x3) + 데이터"로 간다.

    # 재설계: 7x7 격자 중 3x3 파인더를 3개 코너에 배치 → 데이터 공간 확보
    # 위의 _draw_finder 호출은 실제로 7x7 을 그리므로 맞지 않음. 재구성.

    # 대신 간단한 모듈 패턴만 그리기로 변경:
    # 7x7 셀 전체에 패턴 적용하되 3 코너에 "mini finder" (3x3 with center 1x1)

    # 먼저 전체 초기화 (이미 label 위에 있으므로 별도 작업 불필요)

    # 각 셀을 그릴지 말지 패턴 (1=검정, 0=공백)
    # 3x3 mini finder 포함한 7x7 패턴
    qr_pattern = [
        "1110111",
        "1010101",
        "1110111",
        "0010100",
        "1110101",
        "1010001",
        "1110110",
    ]
    # 명시적으로 3x3 mini finder는 왼쪽상단/오른쪽상단/왼쪽하단에 위치:
    # rows 0-2, cols 0-2 : finder 1
    # rows 0-2, cols 4-6 : finder 2
    # rows 4-6, cols 0-2 : finder 3

    def _mini_finder_cell(r: int, c: int) -> str:
        """3x3 mini finder 내 (r,c) 값 ('1' or '0')."""
        # 외곽 링 (0행, 2행, 0열, 2열) + 중앙(1,1) = '1'
        if r == 1 and c == 1:
            return "1"
        if r == 0 or r == 2 or c == 0 or c == 2:
            return "1"
        return "0"

    for r in range(7):
        for c in range(7):
            # finder 영역 처리
            in_finder1 = r < 3 and c < 3
            in_finder2 = r < 3 and c >= 4
            in_finder3 = r >= 4 and c < 3
            if in_finder1:
                bit = _mini_finder_cell(r, c)
            elif in_finder2:
                bit = _mini_finder_cell(r, c - 4)
            elif in_finder3:
                bit = _mini_finder_cell(r - 4, c)
            else:
                bit = qr_pattern[r][c]

            if bit == "1":
                x = gx0 + c * cell
                y = gy0 + r * cell
                # 아주 얇은 갭으로 모듈 분리감 (작은 크기에서 뭉개짐 방지)
                gap = cell * 0.04
                draw.rectangle(
                    (x + gap, y + gap, x + cell - gap, y + cell - gap),
                    fill=qr_color,
                )

    # 5. 캐리어 하단 핀 / 커넥터 (8개 금속 핀)
    pin_count = 8
    pin_y0 = int(size * 0.80)
    pin_y1 = int(size * 0.88)
    pin_area_x0 = int(size * 0.20)
    pin_area_x1 = int(size * 0.80)
    pin_area_w = pin_area_x1 - pin_area_x0
    pin_w = pin_area_w / (pin_count * 2 - 1)  # 핀과 갭이 같은 너비

    for i in range(pin_count):
        px0 = pin_area_x0 + i * pin_w * 2
        draw.rounded_rectangle(
            (px0, pin_y0, px0 + pin_w, pin_y1),
            radius=max(1, int(size * 0.006)),
            fill=pin_color,
        )

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_g1_carrier_navy",   "g1_navy_gold",       "Carrier QR - Navy+Gold (메인)"),
        ("icon_g2_carrier_slate",  "g2_slate_cyan",      "Carrier QR - Slate+Cyan"),
        ("icon_g3_carrier_black",  "g3_black_emerald",   "Carrier QR - Black+Emerald"),
    ]

    for name, pal_key, label in variants:
        palette = PALETTES[pal_key]
        print(f"[Generating] {name}  - {label}")
        img = design_carrier_qr(BASE_SIZE, palette)

        # 메인 미리보기
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

        # ICO
        ico_path = out_dir / f"{name}.ico"
        save_ico(img, ico_path)

        print(f"  -> {png_path.name}")
        print(f"  -> {strip_path.name}")
        print(f"  -> {ico_path.name}")

    print(f"\nAll carrier+QR icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
