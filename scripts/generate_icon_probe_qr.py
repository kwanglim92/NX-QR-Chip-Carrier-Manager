"""앱 아이콘 — AFM 캔틸레버가 QR을 판독하는 동작 (사용자 재스케치 반영).

컨셉: "Probe Reads QR"
  - 좌상단: 캔틸레버 고정부(베이스) + 대각선 아래로 뻗은 암
  - 암 표면: QR 각인 (프로브 식별자 느낌)
  - 우하단: 뾰족한 팁 + 샘플 방향 스캔 빔 (시안)
  - 팁 아래: 감지 동심원 (판단/인식 완료 표현)
  - 하단: 샘플 표면 띠

3가지 색상 변주:
  P1 (메인) Slate + Cyan  — G2와 일관된 톤, 사용자가 선택한 색상
  P2        Navy + Gold   — 이전 G1 톤, 따뜻한 분위기
  P3        Black + Emerald — 강한 대비
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from generate_icons import (  # noqa: E402
    BASE_SIZE, ICO_SIZES, rounded_square_bg, save_ico,
)


# ─── 색상 변주 팔레트 ────────────────────────────────────────────────────

PALETTES = {
    "p1_slate_cyan": {
        "bg":        (51, 65, 85, 255),    # 슬레이트
        "probe":     (220, 228, 240, 255), # 라이트 그레이 (캔틸레버)
        "probe_edge":(165, 180, 200, 255),
        "qr_bg":     (250, 252, 254, 255), # QR 배경 (흰 라벨)
        "qr_dark":   (30, 41, 59, 255),    # QR 모듈
        "beam":      (34, 211, 238, 255),  # 시안 스캔 빔
        "sample":    (26, 34, 51, 255),
        "sample_hi": (85, 110, 140, 255),
        "detect":    (34, 211, 238, 255),  # 감지 원 = 빔 색
    },
    "p2_navy_gold": {
        "bg":        (30, 41, 59, 255),
        "probe":     (230, 220, 190, 255), # 황동 느낌
        "probe_edge":(180, 160, 110, 255),
        "qr_bg":     (250, 252, 254, 255),
        "qr_dark":   (20, 28, 45, 255),
        "beam":      (251, 191, 36, 255),  # 골드
        "sample":    (18, 25, 40, 255),
        "sample_hi": (80, 95, 120, 255),
        "detect":    (251, 191, 36, 255),
    },
    "p3_black_emerald": {
        "bg":        (15, 23, 42, 255),
        "probe":     (210, 220, 230, 255),
        "probe_edge":(140, 160, 180, 255),
        "qr_bg":     (250, 252, 254, 255),
        "qr_dark":   (15, 23, 42, 255),
        "beam":      (16, 185, 129, 255),  # 에메랄드
        "sample":    (8, 14, 26, 255),
        "sample_hi": (60, 80, 100, 255),
        "detect":    (16, 185, 129, 255),
    },
}


# ─── 디자인 ──────────────────────────────────────────────────────────────

def design_probe_qr(size: int, pal: dict) -> Image.Image:
    """AFM 캔틸레버 + QR 각인 + 스캔 빔 + 판단 신호."""
    img = rounded_square_bg(size, pal["bg"], radius_ratio=0.16)
    draw = ImageDraw.Draw(img)

    # ── 1) 캔틸레버 고정부 (좌상 베이스) ──────────────────────────────
    base_x0 = size * 0.06
    base_y0 = size * 0.10
    base_x1 = size * 0.24
    base_y1 = size * 0.24
    draw.rectangle(
        (base_x0, base_y0, base_x1, base_y1),
        fill=pal["probe"],
        outline=pal["probe_edge"],
        width=max(1, int(size * 0.006)),
    )
    # 고정부 내부 grip 라인
    for i in range(1, 4):
        y = base_y0 + (base_y1 - base_y0) * i / 4
        draw.line([(base_x0 + size * 0.015, y), (base_x1 - size * 0.015, y)],
                  fill=pal["probe_edge"],
                  width=max(1, int(size * 0.005)))

    # ── 2) 캔틸레버 암 (사다리꼴, 좌상 → 우하) ─────────────────────────
    # 베이스 우측에서 시작해 팁으로 수렴
    arm_top_left     = (base_x1 - size * 0.01, base_y0 + size * 0.015)
    arm_top_right    = (size * 0.66, size * 0.51)
    arm_bottom_right = (size * 0.68, size * 0.59)
    arm_bottom_left  = (base_x1 - size * 0.01, base_y1 - size * 0.015)
    arm_polygon = [arm_top_left, arm_top_right, arm_bottom_right, arm_bottom_left]
    draw.polygon(
        arm_polygon,
        fill=pal["probe"],
        outline=pal["probe_edge"],
    )
    # 두꺼운 아웃라인 재강조
    for i in range(len(arm_polygon)):
        p1 = arm_polygon[i]
        p2 = arm_polygon[(i + 1) % len(arm_polygon)]
        draw.line([p1, p2],
                  fill=pal["probe_edge"],
                  width=max(1, int(size * 0.006)))

    # ── 3) QR 각인 (암 중앙에 흰 라벨 + QR 패턴) ─────────────────────
    # 암 중심점 계산 (사다리꼴 중심에 살짝 왼쪽으로 치우침)
    qr_cx = size * 0.36
    qr_cy = size * 0.30
    qr_side = size * 0.20

    qr_x0 = qr_cx - qr_side / 2
    qr_y0 = qr_cy - qr_side / 2
    qr_x1 = qr_cx + qr_side / 2
    qr_y1 = qr_cy + qr_side / 2

    # 라벨 배경 (약간 그림자 → 각인 효과)
    draw.rounded_rectangle(
        (qr_x0, qr_y0, qr_x1, qr_y1),
        radius=max(1, int(size * 0.012)),
        fill=pal["qr_bg"],
        outline=pal["qr_dark"],
        width=max(1, int(size * 0.005)),
    )

    # 5x5 QR 패턴 (3 파인더 축소 + 데이터)
    cells = 5
    cell_w = qr_side / cells
    pattern = [
        "11011",
        "10101",
        "11110",
        "10011",
        "11011",
    ]
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch == "1":
                x = qr_x0 + c * cell_w
                y = qr_y0 + r * cell_w
                gap = cell_w * 0.08
                draw.rectangle(
                    (x + gap, y + gap, x + cell_w - gap, y + cell_w - gap),
                    fill=pal["qr_dark"],
                )

    # ── 4) 캔틸레버 팁 (암 우하단에서 아래로 삼각형) ────────────────
    tip_top_left  = (size * 0.62, size * 0.56)
    tip_top_right = (size * 0.70, size * 0.58)
    tip_apex      = (size * 0.65, size * 0.74)
    draw.polygon(
        [tip_top_left, tip_top_right, tip_apex],
        fill=pal["probe"],
        outline=pal["probe_edge"],
    )
    draw.line([tip_top_left, tip_apex],
              fill=pal["probe_edge"], width=max(1, int(size * 0.006)))
    draw.line([tip_top_right, tip_apex],
              fill=pal["probe_edge"], width=max(1, int(size * 0.006)))

    # ── 5) 샘플 표면 (하단 띠) ────────────────────────────────────────
    sample_y0 = int(size * 0.85)
    sample_y1 = int(size * 0.92)
    sm_pad = int(size * 0.08)
    draw.rectangle(
        (sm_pad, sample_y0, size - sm_pad, sample_y1),
        fill=pal["sample"],
    )
    # 샘플 상단 하이라이트
    draw.line(
        [(sm_pad, sample_y0), (size - sm_pad, sample_y0)],
        fill=pal["sample_hi"],
        width=max(1, int(size * 0.008)),
    )

    # ── 6) 스캔 빔 (팁 → 샘플, 시안 수직선 + 글로우) ─────────────────
    beam_x = tip_apex[0]
    beam_y_start = tip_apex[1] + size * 0.005
    beam_y_end = sample_y0 - size * 0.005
    # 글로우 (반투명 두꺼운 줄기)
    for radius_mult in (4, 2):
        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        beam_w_glow = max(2, int(size * 0.012 * radius_mult))
        odraw.line(
            [(beam_x, beam_y_start), (beam_x, beam_y_end)],
            fill=(*pal["beam"][:3], 60 if radius_mult == 4 else 110),
            width=beam_w_glow,
        )
        img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    # 메인 빔
    draw.line(
        [(beam_x, beam_y_start), (beam_x, beam_y_end)],
        fill=pal["beam"],
        width=max(2, int(size * 0.015)),
    )

    # ── 7) 감지 동심원 (샘플 위, 판단 완료 표현) ─────────────────────
    detect_x = beam_x
    detect_y = sample_y0
    for i, r in enumerate([
        int(size * 0.04),
        int(size * 0.07),
        int(size * 0.10),
    ]):
        alpha = 180 - i * 55
        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.ellipse(
            (detect_x - r, detect_y - r * 0.5,
             detect_x + r, detect_y + r * 0.5),  # 약간 납작한 타원 (투시 느낌)
            outline=(*pal["detect"][:3], alpha),
            width=max(1, int(size * 0.006)),
        )
        img = Image.alpha_composite(img, overlay)

    # ── 8) 우상단 작은 체크마크 (선택적 — '판독 완료' 강조) ──────────
    draw = ImageDraw.Draw(img)
    chk_cx = size * 0.84
    chk_cy = size * 0.18
    chk_r = size * 0.06
    # 체크 배경 원
    draw.ellipse(
        (chk_cx - chk_r, chk_cy - chk_r, chk_cx + chk_r, chk_cy + chk_r),
        fill=pal["detect"],
    )
    # 체크 마크 (V 자)
    chk_w = max(2, int(size * 0.012))
    p1 = (chk_cx - chk_r * 0.45, chk_cy)
    p2 = (chk_cx - chk_r * 0.1, chk_cy + chk_r * 0.4)
    p3 = (chk_cx + chk_r * 0.5, chk_cy - chk_r * 0.35)
    draw.line([p1, p2], fill=(255, 255, 255, 255), width=chk_w)
    draw.line([p2, p3], fill=(255, 255, 255, 255), width=chk_w)

    return img


# ─── 실행 ────────────────────────────────────────────────────────────────

def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_p1_probe_slate",   "p1_slate_cyan",     "Probe Reads QR - Slate+Cyan (메인)"),
        ("icon_p2_probe_navy",    "p2_navy_gold",      "Probe Reads QR - Navy+Gold"),
        ("icon_p3_probe_black",   "p3_black_emerald",  "Probe Reads QR - Black+Emerald"),
    ]

    for name, pal_key, label in variants:
        palette = PALETTES[pal_key]
        print(f"[Generating] {name}  - {label}")
        img = design_probe_qr(BASE_SIZE, palette)

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

    print(f"\nAll probe+QR icons saved to: {out_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
