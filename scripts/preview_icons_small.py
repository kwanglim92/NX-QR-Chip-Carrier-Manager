"""작은 크기 미리보기 — 실제 작업표시줄/트레이에서의 가독성 체크."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from generate_icons import BASE_SIZE, design_a, design_b, design_c


def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "assets" / "icons"

    factories = [
        ("icon_a_qr_wave", design_a),
        ("icon_b_chip_grid", design_b),
        ("icon_c_nx_monogram", design_c),
    ]
    sizes = [16, 32, 48, 64, 128]

    for name, factory in factories:
        # 고해상도에서 렌더 후 LANCZOS 로 축소 (실제 시스템 아이콘 로딩 방식과 유사)
        master = factory(BASE_SIZE)
        row_items = []
        total_w = 0
        for s in sizes:
            small = master.resize((s, s), Image.Resampling.LANCZOS)
            row_items.append(small)
            total_w += s + 10
        # 가로로 나열된 비교 스트립 생성
        strip_h = max(sizes) + 20
        strip = Image.new("RGBA", (total_w + 20, strip_h + 20), (20, 20, 30, 255))
        x = 10
        for small in row_items:
            y = (strip.height - small.height) // 2
            strip.paste(small, (x, y), small)
            x += small.width + 10
        out_path = out_dir / f"{name}_sizes_16_32_48_64_128.png"
        strip.save(out_path, format="PNG")
        print(f"  -> {out_path.name}")


if __name__ == "__main__":
    main()
