"""앱 아이콘 생성기 — NX QR Chip Carrier Manager (Phase 8 선택 에셋).

3가지 디자인 컨셉을 Pillow 로 프로그래매틱 생성:
  A) QR Grid + AFM Sweep Wave — 기술적·계측 느낌
  B) Chip Carrier 12-Slot       — 생산·상태 관리 느낌
  C) NX Monogram + QR           — 미니멀·모던

출력:
  assets/icons/icon_a_qr_wave.ico       (16/32/48/64/128/256 멀티 해상도)
  assets/icons/icon_a_qr_wave_256.png   (미리보기)
  assets/icons/icon_b_chip_grid.ico
  assets/icons/icon_b_chip_grid_256.png
  assets/icons/icon_c_nx_monogram.ico
  assets/icons/icon_c_nx_monogram_256.png

실행:
  python scripts/generate_icons.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Catppuccin Mocha 팔레트 (앱 테마와 일치)
BG       = (30, 30, 46, 255)      # #1e1e2e base
BG2      = (49, 50, 68, 255)      # #313244 surface0
BG3      = (69, 71, 90, 255)      # #45475a surface1
FG       = (205, 214, 244, 255)   # #cdd6f4 text
ACCENT   = (137, 180, 250, 255)   # #89b4fa blue
GREEN    = (166, 227, 161, 255)   # #a6e3a1
ORANGE   = (250, 179, 135, 255)   # #fab387 peach
RED      = (243, 139, 168, 255)   # #f38ba8
PURPLE   = (203, 166, 247, 255)   # #cba6f7 mauve
CYAN     = (148, 226, 213, 255)   # #94e2d5

ICO_SIZES = [16, 32, 48, 64, 128, 256]
BASE_SIZE = 256


# ─── 공용 유틸 ───────────────────────────────────────────────────────────

def rounded_square_bg(
    size: int,
    fill,
    radius_ratio: float = 0.18,
    outline=None,
    outline_width: int = 0,
):
    """둥근 사각형 배경 이미지."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = int(size * radius_ratio)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=r,
        fill=fill,
        outline=outline,
        width=outline_width,
    )
    return img


def save_ico(base_img: Image.Image, out_path: Path):
    """256x256 기준 이미지를 멀티 해상도 ICO로 저장."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base_img.save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
    )


def try_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    """Windows 기본 폰트 우선, 실패 시 fallback."""
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ─── 디자인 A: QR Grid + Sweep Wave ──────────────────────────────────────

def design_a(size: int = BASE_SIZE) -> Image.Image:
    """QR 격자 + 사인파형 곡선 오버레이."""
    img = rounded_square_bg(size, BG2)
    draw = ImageDraw.Draw(img)

    # 격자 영역 (여백 12%)
    pad = int(size * 0.12)
    grid_area = size - pad * 2
    cells = 7  # 7x7 의사-QR
    cell = grid_area / cells
    ox, oy = pad, pad

    # 의사-QR 패턴 (실제 QR 은 아님, 디자인 상징)
    pattern = [
        "1110111",
        "1000101",
        "1011101",
        "1010011",
        "0011010",
        "1101011",
        "1110101",
    ]
    for row, bits in enumerate(pattern):
        for col, ch in enumerate(bits):
            if ch != "1":
                continue
            x1 = ox + col * cell
            y1 = oy + row * cell
            x2 = x1 + cell - max(1, cell * 0.08)
            y2 = y1 + cell - max(1, cell * 0.08)
            draw.rectangle((x1, y1, x2, y2), fill=FG)

    # Finder pattern 강조 (좌상, 우상, 좌하 세 코너 7x7 QR 모양)
    for (cr, cc) in [(0, 0), (0, 4), (4, 0)]:
        # 외곽 3x3
        x1 = ox + cc * cell
        y1 = oy + cr * cell
        x2 = x1 + 3 * cell
        y2 = y1 + 3 * cell
        draw.rectangle((x1, y1, x2 - cell * 0.1, y2 - cell * 0.1),
                       outline=ACCENT, width=max(2, int(cell * 0.2)))

    # Sweep Wave — 격자 위를 가로지르는 사인파
    wave_y_center = size * 0.62
    amp = size * 0.12
    freq = 2.2  # 주기 수
    points = []
    for i in range(size * 2):
        x = i / 2
        t = (x - pad) / grid_area
        y = wave_y_center + math.sin(t * math.pi * 2 * freq) * amp
        points.append((x, y))

    # 언더레이 글로우 (반투명 두꺼운 선)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    glow_color = (*ACCENT[:3], 80)
    gdraw.line(points, fill=glow_color, width=max(6, int(size * 0.04)))

    # 메인 라인
    mdraw = ImageDraw.Draw(glow)
    mdraw.line(points, fill=CYAN, width=max(3, int(size * 0.018)))

    img = Image.alpha_composite(img, glow)

    return img


# ─── 디자인 B: Chip Carrier 12-Slot ──────────────────────────────────────

def design_b(size: int = BASE_SIZE) -> Image.Image:
    """3x4 슬롯 그리드 + 상태 컬러 믹스."""
    img = rounded_square_bg(size, BG)
    draw = ImageDraw.Draw(img)

    # 슬롯 매트릭스 3행 x 4열
    rows, cols = 3, 4
    pad = int(size * 0.14)
    area = size - pad * 2
    gap = int(area * 0.08)
    slot_w = (area - gap * (cols - 1)) / cols
    slot_h = (area - gap * (rows - 1)) / rows
    slot_d = min(slot_w, slot_h)  # 원형 크기

    # 상태 패턴: Done=GREEN, InProgress=ORANGE, Empty=BG3
    # 총 12개 중 6 done / 3 progress / 3 empty — 일반적 생산 상태 분포
    status_grid = [
        ["D", "D", "D", "P"],
        ["D", "D", "P", "P"],
        ["D", "E", "E", "E"],
    ]
    color_map = {"D": GREEN, "P": ORANGE, "E": BG3}

    for r in range(rows):
        for c in range(cols):
            cx = pad + c * (slot_w + gap) + slot_w / 2
            cy = pad + r * (slot_h + gap) + slot_h / 2
            state = status_grid[r][c]
            color = color_map[state]
            d = slot_d * 0.88
            # 슬롯 원
            draw.ellipse(
                (cx - d / 2, cy - d / 2, cx + d / 2, cy + d / 2),
                fill=color,
                outline=FG,
                width=max(1, int(size * 0.006)),
            )
            # 중앙 포인트 (측정 마크)
            if state == "D":
                r_pt = d * 0.15
                draw.ellipse(
                    (cx - r_pt, cy - r_pt, cx + r_pt, cy + r_pt),
                    fill=BG,
                )

    # 우하단 QR 인디케이터 (5x5 의사-QR)
    qr_side = int(size * 0.22)
    qr_ox = size - pad - qr_side
    qr_oy = size - pad - qr_side
    # QR 배경 프레임
    draw.rounded_rectangle(
        (qr_ox - 4, qr_oy - 4, qr_ox + qr_side + 4, qr_oy + qr_side + 4),
        radius=4,
        fill=BG,
        outline=ACCENT,
        width=2,
    )
    qr_cells = 5
    qr_pattern = [
        "11011",
        "10101",
        "01110",
        "10101",
        "11011",
    ]
    qc = qr_side / qr_cells
    for rr, bits in enumerate(qr_pattern):
        for cc, ch in enumerate(bits):
            if ch == "1":
                x1 = qr_ox + cc * qc
                y1 = qr_oy + rr * qc
                draw.rectangle(
                    (x1, y1, x1 + qc - 1, y1 + qc - 1),
                    fill=ACCENT,
                )

    return img


# ─── 디자인 C: NX Monogram + QR ──────────────────────────────────────────

def design_c(size: int = BASE_SIZE) -> Image.Image:
    """미니멀 NX 타이포 + 우하단 소형 QR."""
    # 배경 그라디언트 (ACCENT → PURPLE)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size), ACCENT)
    # 간단한 대각선 그라디언트
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for i in range(size):
        alpha = int(255 * (i / size))
        odraw.line(
            [(0, i), (size, i)],
            fill=(PURPLE[0], PURPLE[1], PURPLE[2], alpha // 2),
        )
    grad = Image.alpha_composite(grad, overlay)

    # 둥근 사각형 마스크로 클리핑
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    r = int(size * 0.18)
    mdraw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=255)
    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)

    # 중앙 NX 모노그램
    font = try_font(int(size * 0.5), bold=True)
    text = "NX"
    # bounding box 로 중앙 정렬
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) / 2 - bbox[0]
        ty = (size - th) / 2 - bbox[1] - int(size * 0.04)
    except AttributeError:
        tw, th = draw.textsize(text, font=font)
        tx = (size - tw) / 2
        ty = (size - th) / 2

    # 약간의 그림자
    shadow_offset = max(1, int(size * 0.012))
    draw.text((tx + shadow_offset, ty + shadow_offset), text,
              font=font, fill=(0, 0, 0, 90))
    draw.text((tx, ty), text, font=font, fill=FG)

    # 우하단 소형 QR (5x5)
    pad = int(size * 0.09)
    qr_side = int(size * 0.20)
    qr_ox = size - pad - qr_side
    qr_oy = size - pad - qr_side
    draw.rounded_rectangle(
        (qr_ox - 4, qr_oy - 4, qr_ox + qr_side + 4, qr_oy + qr_side + 4),
        radius=3,
        fill=BG,
    )
    qr_cells = 5
    qr_pattern = [
        "11101",
        "10011",
        "01110",
        "11001",
        "10111",
    ]
    qc = qr_side / qr_cells
    for rr, bits in enumerate(qr_pattern):
        for cc, ch in enumerate(bits):
            if ch == "1":
                x1 = qr_ox + cc * qc
                y1 = qr_oy + rr * qc
                draw.rectangle(
                    (x1, y1, x1 + qc - 1, y1 + qc - 1),
                    fill=ORANGE,
                )

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    designs = [
        ("icon_a_qr_wave",     design_a, "QR Grid + Sweep Wave"),
        ("icon_b_chip_grid",   design_b, "Chip Carrier 12-Slot"),
        ("icon_c_nx_monogram", design_c, "NX Monogram + QR"),
    ]

    for name, factory, label in designs:
        print(f"[Generating] {name}  - {label}")
        img = factory(BASE_SIZE)

        # 256px 미리보기 PNG
        preview_path = out_dir / f"{name}_256.png"
        img.save(preview_path, format="PNG")

        # 멀티 해상도 ICO
        ico_path = out_dir / f"{name}.ico"
        save_ico(img, ico_path)

        print(f"  → {preview_path.relative_to(project_root)}")
        print(f"  → {ico_path.relative_to(project_root)}")

    print(f"\nAll icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
