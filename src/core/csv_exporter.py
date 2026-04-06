"""타겟 CSV 포맷 생성.

출력 형식:
  QR ID,생산일자[YYYYMMDD],Frequency (KHz),Drive (%),Q,Probe Type
"""
from __future__ import annotations

from pathlib import Path

from src.core.models import MeasurementSet


def generate_csv_rows(ms: MeasurementSet) -> list[list[str]]:
    """MeasurementSet → CSV 행 리스트 (헤더 포함)."""
    header = ["QR ID", "생산일자[YYYYMMDD]", "Frequency (KHz)", "Drive (%)", "Q", "Probe Type"]
    rows = [header]

    for slot in ms.slots:
        if not slot.qr_id:
            continue
        rows.append([
            slot.qr_id,
            ms.production_date,
            slot.format_frequency(),
            slot.format_drive(),
            slot.format_q(),
            ms.probe_type,
        ])

    return rows


def export_csv(ms: MeasurementSet, output_path: str) -> None:
    """MeasurementSet → CSV 파일로 저장 (utf-8-sig)."""
    rows = generate_csv_rows(ms)
    path = Path(output_path)

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for row in rows:
            f.write(",".join(row) + "\n")
