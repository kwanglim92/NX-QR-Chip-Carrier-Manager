"""타겟 CSV 포맷 생성 + 이미지 리네임 내보내기.

출력 형식:
  QR ID,생산일자[YYYYMMDD],Frequency (KHz),Drive (%),Q,Probe Type
"""
from __future__ import annotations

import shutil
from pathlib import Path

from src.core.models import MeasurementSet


def generate_csv_rows(ms: MeasurementSet) -> list[list[str]]:
    """MeasurementSet -> CSV 행 리스트 (헤더 포함)."""
    header = ["QR ID", "생산일자[YYYYMMDD]", "Frequency (KHz)", "Drive (%)", "Q", "Probe Type"]
    rows = [header]

    for slot in ms.slots:
        if not slot.qr_id:
            continue
        probe = slot.probe_type or ms.probe_type
        rows.append([
            slot.qr_id,
            ms.production_date,
            slot.format_frequency(),
            slot.format_drive(),
            slot.format_q(),
            probe,
        ])

    return rows


def export_csv(ms: MeasurementSet, output_path: str) -> None:
    """MeasurementSet -> CSV 파일로 저장 (utf-8-sig)."""
    rows = generate_csv_rows(ms)
    path = Path(output_path)

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for row in rows:
            f.write(",".join(row) + "\n")


def export_with_images(ms: MeasurementSet, output_dir: str, csv_name: str) -> dict:
    """CSV + ZOOMIN 폴더 (이미지를 QR ID로 리네임하여 복사).

    Returns:
        dict with keys: csv_path, zoomin_dir, image_count
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # CSV 저장
    csv_path = out / csv_name
    export_csv(ms, str(csv_path))

    # ZOOMIN 폴더 생성 + 이미지 복사
    zoomin = out / "ZOOMIN"
    zoomin.mkdir(exist_ok=True)

    image_count = 0
    for slot in ms.slots:
        if slot.qr_id and slot.image_path:
            src = Path(slot.image_path)
            if src.exists():
                dst = zoomin / f"{slot.qr_id}{src.suffix}"
                shutil.copy2(str(src), str(dst))
                image_count += 1

    return {
        "csv_path": str(csv_path),
        "zoomin_dir": str(zoomin),
        "image_count": image_count,
    }
