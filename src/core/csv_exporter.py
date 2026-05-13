"""타겟 CSV 포맷 생성 + 이미지 리네임 내보내기.

출력 형식:
  QR ID,생산일자[YYYYMMDD],Frequency (KHz),Drive (%),Q,Probe Type
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Literal

from src.core.capture_files import ZOOMOUT_SUFFIX, derive_zoomout_path
from src.core.models import MeasurementSet, SlotData, truncate_measurement_value

CSV_EXPORT_QR_ONLY = "qr_only"
CSV_EXPORT_ALL_SLOTS = "all_slots"
CSVExportPolicy = Literal["qr_only", "all_slots"]
CSV_HEADER = ["QR ID", "생산일자[YYYYMMDD]", "Frequency (KHz)", "Drive (%)", "Q", "Probe Type"]


def _format_measurement(value: float | int | str | None) -> str:
    formatted = truncate_measurement_value(value)
    return "" if formatted is None else str(formatted)


def _format_drive(value: float | int | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, int)):
        return f"{value:g}"
    return str(value).strip()


def _iter_export_slots(ms: MeasurementSet, policy: CSVExportPolicy):
    for slot in ms.slots:
        if policy == CSV_EXPORT_QR_ONLY and not slot.qr_id:
            continue
        yield slot


def generate_csv_rows(
    ms: MeasurementSet,
    policy: CSVExportPolicy = CSV_EXPORT_QR_ONLY,
) -> list[list[str]]:
    """MeasurementSet -> CSV 행 리스트 (헤더 포함)."""
    rows = [CSV_HEADER]

    for slot in _iter_export_slots(ms, policy):
        probe = slot.probe_type or ms.probe_type
        rows.append([
            slot.qr_id or "",
            ms.production_date,
            _format_measurement(slot.frequency),
            _format_drive(slot.drive),
            _format_measurement(slot.q_factor),
            probe or "",
        ])

    return rows


def export_csv(
    ms: MeasurementSet,
    output_path: str,
    policy: CSVExportPolicy = CSV_EXPORT_QR_ONLY,
) -> None:
    """MeasurementSet -> CSV 파일로 저장 (utf-8-sig)."""
    rows = generate_csv_rows(ms, policy)
    path = Path(output_path)

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def _slot_image_basename(slot: SlotData) -> str:
    if slot.qr_id:
        return slot.qr_id
    return f"slot_{slot.slot_index + 1:02d}"


def _unique_child_path(parent: Path, basename: str, suffix: str) -> Path:
    candidate = parent / f"{basename}{suffix}"
    if not candidate.exists():
        return candidate

    n = 1
    while True:
        candidate = parent / f"{basename}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def export_with_images(
    ms: MeasurementSet,
    output_dir: str,
    csv_name: str,
    policy: CSVExportPolicy = CSV_EXPORT_QR_ONLY,
) -> dict:
    """CSV + ZOOMIN/ZOOMOUT 폴더 (이미지를 QR ID로 리네임하여 복사).

    Returns:
        dict with keys: csv_path, zoomin_dir, zoomout_dir, image_count, zoomout_image_count
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # CSV 저장
    csv_path = out / csv_name
    export_csv(ms, str(csv_path), policy)

    # ZOOMIN / ZOOMOUT 폴더 생성 + 이미지 복사
    zoomin = out / "ZOOMIN"
    zoomin.mkdir(exist_ok=True)
    zoomout = out / "ZOOMOUT"
    zoomout.mkdir(exist_ok=True)

    image_count = 0
    zoomout_image_count = 0
    for slot in _iter_export_slots(ms, policy):
        if not slot.image_path:
            continue
        src = Path(slot.image_path)
        if not src.exists():
            continue

        basename = _slot_image_basename(slot)
        dst = _unique_child_path(zoomin, basename, src.suffix)
        shutil.copy2(str(src), str(dst))
        image_count += 1

        # Zoom-out sibling (best-effort)
        zo_src = derive_zoomout_path(src)
        if zo_src.exists():
            zo_dst = _unique_child_path(
                zoomout, f"{basename}{ZOOMOUT_SUFFIX}", zo_src.suffix
            )
            shutil.copy2(str(zo_src), str(zo_dst))
            zoomout_image_count += 1

    return {
        "csv_path": str(csv_path),
        "zoomin_dir": str(zoomin),
        "zoomout_dir": str(zoomout),
        "image_count": image_count,
        "zoomout_image_count": zoomout_image_count,
    }
