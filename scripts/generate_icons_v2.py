"""앱 아이콘 생성기 v2 — 완전히 다른 3가지 컨셉 (색상 톤 + 심볼 구성 변경).

D) Resonance Peak       — AFM 공진 피크 (Clean Lab: 화이트+에메랄드+네이비)
E) Cantilever + Sample  — AFM 탐침과 샘플   (Instrument Dark: 딥네이비+시안 네온)
F) Waveform + ID        — 파형 + 바코드 ID  (Precision Gold: 블랙+골드+틸)

기존 v1 (generate_icons.py) 의 유틸리티를 재사용한다.

실행:
  python scripts/generate_icons_v2.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# v1 스크립트에서 유틸리티 재사용
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, ICO_SIZES,
    rounded_square_bg, save_ico, try_font,
)


# ─── 컨셉 D: Resonance Peak ──────────────────────────────────────────────

# Clean Lab 팔레트
D_BG       = (245, 247, 250, 255)   # 연 블루 그레이
D_GRID     = (209, 217, 224, 255)
D_PEAK     = (0, 184, 169, 255)     # 에메랄드
D_PEAK_FILL = (0, 184, 169, 60)
D_INK      = (26, 26, 46, 255)      # 딥 네이비

def design_d(size: int = BASE_SIZE) -> Image.Image:
    """AFM 공진 피크 그래프 + 우하단 QR 스탬프."""
    img = rounded_square_bg(size, D_BG, radius_ratio=0.18)
    draw = ImageDraw.Draw(img)

    # 그래프 영역
    pad = int(size * 0.11)
    graph_x0 = pad
    graph_y0 = int(size * 0.18)
    graph_w = size - pad * 2
    graph_h = int(size * 0.50)
    baseline_y = graph_y0 + graph_h

    # 얇은 격자
    grid_vw = max(1, size // 256)
    for i in range(1, 5):
        x = graph_x0 + graph_w * i / 5
        draw.line([(x, graph_y0), (x, baseline_y)], fill=D_GRID, width=grid_vw)
    for i in range(1, 4):
        y = graph_y0 + graph_h * i / 4
        draw.line([(graph_x0, y), (graph_x0 + graph_w, y)], fill=D_GRID, width=grid_vw)

    # 가우시안 피크 곡선
    peak_x = graph_x0 + graph_w * 0.5
    peak_top_y = graph_y0 + graph_h * 0.08
    amp = baseline_y - peak_top_y
    sigma = graph_w * 0.09

    points = []
    steps = size * 2
    for i in range(steps + 1):
        x = graph_x0 + graph_w * i / steps
        dx = x - peak_x
        y = baseline_y - amp * math.exp(-0.5 * (dx / sigma) ** 2)
        points.append((x, y))

    # 피크 아래 면 채우기 (반투명 에메랄드)
    fill_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fill_layer)
    fill_pts = points + [(graph_x0 + graph_w, baseline_y), (graph_x0, baseline_y)]
    fdraw.polygon(fill_pts, fill=D_PEAK_FILL)
    img = Image.alpha_composite(img, fill_layer)

    # 피크 라인
    draw = ImageDraw.Draw(img)
    draw.line(points, fill=D_PEAK, width=max(3, int(size * 0.022)))

    # 피크 정점 마커
    mr = max(2, int(size * 0.02))
    draw.ellipse(
        (peak_x - mr, peak_top_y - mr, peak_x + mr, peak_top_y + mr),
        fill=D_PEAK,
        outline=D_INK,
        width=max(1, int(size * 0.006)),
    )

    # 우하단 QR 스탬프 (5x5 의사 QR)
    qr_side = int(size * 0.20)
    qr_ox = size - pad - qr_side
    qr_oy = size - int(size * 0.08) - qr_side
    # 얇은 프레임
    draw.rounded_rectangle(
        (qr_ox - 3, qr_oy - 3, qr_ox + qr_side + 3, qr_oy + qr_side + 3),
        radius=3, fill=D_BG, outline=D_INK,
        width=max(1, int(size * 0.006)),
    )
    pattern = [
        "11011",
        "00110",
        "11101",
        "10010",
        "01011",
    ]
    qc = qr_side / 5
    for rr, bits in enumerate(pattern):
        for cc, ch in enumerate(bits):
            if ch == "1":
                x1 = qr_ox + cc * qc
                y1 = qr_oy + rr * qc
                draw.rectangle((x1, y1, x1 + qc - 1, y1 + qc - 1), fill=D_INK)

    return img


# ─── 컨셉 E: Cantilever + Sample ─────────────────────────────────────────

# Instrument Dark 팔레트
E_BG       = (10, 22, 40, 255)
E_CANT     = (200, 208, 220, 255)   # 실버
E_TIP      = (235, 240, 248, 255)
E_GLOW     = (0, 212, 255, 255)     # 사이안 네온
E_SAMPLE   = (44, 62, 80, 255)
E_SAMPLE_HL = (90, 110, 135, 255)
E_WHITE    = (255, 255, 255, 255)

def design_e(size: int = BASE_SIZE) -> Image.Image:
    """AFM 캔틸레버 + 탐침 글로우 + 샘플 표면 + 우상단 QR."""
    img = rounded_square_bg(size, E_BG)
    draw = ImageDraw.Draw(img)

    # 샘플 표면 (하단 수평 바)
    sample_top = int(size * 0.72)
    sample_bot = int(size * 0.88)
    sm_pad = int(size * 0.08)
    draw.rectangle(
        (sm_pad, sample_top, size - sm_pad, sample_bot),
        fill=E_SAMPLE,
    )
    # 샘플 상단 하이라이트
    draw.line(
        [(sm_pad, sample_top), (size - sm_pad, sample_top)],
        fill=E_SAMPLE_HL,
        width=max(1, int(size * 0.008)),
    )

    # 캔틸레버 암 (좌상에서 중앙 아래로 기울어진 길쭉한 다각형)
    # 좌상단 고정부가 두껍고 팁 쪽은 좁아지는 형태
    arm = [
        (size * 0.08, size * 0.18),   # 좌상 (위)
        (size * 0.22, size * 0.12),   # 우상 (위)
        (size * 0.62, size * 0.50),   # 팁 위
        (size * 0.60, size * 0.55),   # 팁 아래
        (size * 0.20, size * 0.24),   # 좌하 (아래)
    ]
    draw.polygon(arm, fill=E_CANT, outline=E_WHITE, width=max(1, int(size * 0.005)))

    # 탐침 팁 (캔틸레버 끝에서 아래로 삼각형)
    tip_top_l = (size * 0.57, size * 0.50)
    tip_top_r = (size * 0.63, size * 0.52)
    tip_apex  = (size * 0.60, size * 0.70)  # 샘플 바로 위
    draw.polygon([tip_top_l, tip_top_r, tip_apex], fill=E_TIP)

    # 탐침-샘플 상호작용 글로우 (동심원, 점점 투명)
    for i, r in enumerate([int(size * 0.04), int(size * 0.07),
                            int(size * 0.10), int(size * 0.14)]):
        alpha = 160 - i * 35
        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.ellipse(
            (tip_apex[0] - r, tip_apex[1] - r,
             tip_apex[0] + r, tip_apex[1] + r),
            outline=(*E_GLOW[:3], alpha),
            width=max(1, int(size * 0.008)),
        )
        img = Image.alpha_composite(img, overlay)

    # 우상단 소형 QR
    draw = ImageDraw.Draw(img)
    qr_side = int(size * 0.18)
    qr_pad = int(size * 0.08)
    qr_ox = size - qr_pad - qr_side
    qr_oy = qr_pad
    draw.rounded_rectangle(
        (qr_ox - 3, qr_oy - 3, qr_ox + qr_side + 3, qr_oy + qr_side + 3),
        radius=3, fill=(18, 30, 48, 255),
    )
    pattern = [
        "11011",
        "10101",
        "01110",
        "10011",
        "11010",
    ]
    qc = qr_side / 5
    for rr, bits in enumerate(pattern):
        for cc, ch in enumerate(bits):
            if ch == "1":
                x1 = qr_ox + cc * qc
                y1 = qr_oy + rr * qc
                draw.rectangle(
                    (x1, y1, x1 + qc - 1, y1 + qc - 1),
                    fill=E_WHITE,
                )

    return img


# ─── 컨셉 F: Waveform + ID Strip ─────────────────────────────────────────

# Precision Gold 팔레트
F_BG       = (15, 20, 25, 255)
F_GOLD     = (255, 184, 0, 255)
F_GOLD_FILL = (255, 184, 0, 45)
F_TEAL     = (0, 168, 204, 255)
F_WHITE    = (255, 255, 255, 255)
F_GRAY     = (180, 180, 190, 255)

def design_f(size: int = BASE_SIZE) -> Image.Image:
    """상단 크로마토그래프 파형 + 하단 바코드 ID + 작은 타이포."""
    img = rounded_square_bg(size, F_BG)
    draw = ImageDraw.Draw(img)

    pad = int(size * 0.10)
    # 상단 파형 영역
    wave_y0 = int(size * 0.14)
    wave_y1 = int(size * 0.55)
    baseline_y = wave_y1 - max(1, int(size * 0.01))
    wave_h = baseline_y - wave_y0

    # 4개 피크 (center_frac, height_frac, sigma_frac) — 크로마토그래프 느낌
    peaks = [
        (0.18, 0.70, 0.045),
        (0.38, 0.50, 0.040),
        (0.58, 0.95, 0.035),   # 메인 피크
        (0.78, 0.60, 0.045),
    ]

    inner_w = size - 2 * pad
    points = []
    steps = size * 2
    for i in range(steps + 1):
        x = pad + inner_w * i / steps
        y_val = 0.0
        for cf, hf, sf in peaks:
            cx = pad + inner_w * cf
            sigma = inner_w * sf
            dx = x - cx
            y_val += hf * math.exp(-0.5 * (dx / sigma) ** 2)
        y = baseline_y - y_val * wave_h * 0.85
        points.append((x, y))

    # 면 채우기
    fill_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fill_layer)
    fill_pts = points + [(points[-1][0], baseline_y), (points[0][0], baseline_y)]
    fdraw.polygon(fill_pts, fill=F_GOLD_FILL)
    img = Image.alpha_composite(img, fill_layer)

    # 파형 라인
    draw = ImageDraw.Draw(img)
    draw.line(points, fill=F_GOLD, width=max(3, int(size * 0.022)))

    # 연결 띠 (파형과 ID 사이 은은한 세로 점선)
    conn_x = size // 2
    y = int(size * 0.58)
    while y < int(size * 0.65):
        y2 = min(y + max(1, int(size * 0.012)), int(size * 0.65))
        draw.line([(conn_x, y), (conn_x, y2)],
                  fill=F_GRAY, width=max(1, int(size * 0.006)))
        y += max(2, int(size * 0.022))

    # 하단 바코드 스트립 (두께 가변)
    bar_y0 = int(size * 0.67)
    bar_y1 = int(size * 0.82)
    bar_pad = pad + int(size * 0.03)
    bar_pattern = [3, 1, 2, 1, 3, 2, 1, 1, 2, 3, 1, 2]
    total_units = sum(bar_pattern) + len(bar_pattern)
    unit = (size - 2 * bar_pad) / total_units
    bx = bar_pad
    for i, w_units in enumerate(bar_pattern):
        w = unit * w_units
        if i % 2 == 0:
            draw.rectangle((bx, bar_y0, bx + w, bar_y1), fill=F_TEAL)
        bx += w + unit

    # 하단 타이포 "AFM-QR"
    font = try_font(max(10, int(size * 0.09)), bold=True)
    text = "AFM-QR"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (size - tw) / 2 - bbox[0]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)
        tx = (size - tw) / 2
    ty = int(size * 0.85)
    draw.text((tx, ty), text, fill=F_WHITE, font=font)

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    designs = [
        ("icon_d_resonance_peak", design_d, "Resonance Peak (Clean Lab)"),
        ("icon_e_cantilever",     design_e, "Cantilever + Sample (Instrument Dark)"),
        ("icon_f_waveform_id",    design_f, "Waveform + ID (Precision Gold)"),
    ]

    for name, factory, label in designs:
        print(f"[Generating] {name}  - {label}")
        img = factory(BASE_SIZE)

        # 메인 미리보기 PNG
        png_path = out_dir / f"{name}_256.png"
        img.save(png_path, format="PNG")

        # 작은 크기 비교 스트립
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

        # 멀티 해상도 ICO
        ico_path = out_dir / f"{name}.ico"
        save_ico(img, ico_path)

        print(f"  -> {png_path.name}")
        print(f"  -> {strip_path.name}")
        print(f"  -> {ico_path.name}")

    print(f"\nAll v2 icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
