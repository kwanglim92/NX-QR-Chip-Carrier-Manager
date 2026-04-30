"""ATX 결과 폴더 파싱.

폴더명 규칙: {PO번호}_{수량}M_{ProbeType}
예: P2601001_12M_AC160
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from src.core.models import MeasurementSet, SlotData, truncate_measurement_value
from src.core.slot_mapper import parse_slot_code

_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "latin-1")


def _read_csv_text(path: Path) -> str:
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return path.read_text(encoding="latin-1")


def parse_folder_name(folder_name: str) -> dict:
    """폴더명에서 PO번호, 수량, ProbeType 추출.

    예: 'P2601001_12M_AC160' → {'po': 'P2601001', 'qty': 12, 'probe_type': 'AC160'}
    """
    m = re.match(r"^(P\d+)_(\d+)M_(.+)$", folder_name)
    if not m:
        return {"po": folder_name, "qty": 0, "probe_type": ""}
    return {
        "po": m.group(1),
        "qty": int(m.group(2)),
        "probe_type": m.group(3),
    }


def parse_summary_csv(csv_path: Path) -> list[dict]:
    """Summary.csv 파싱 → [{slot_code, frequency, q_factor}, ...].

    Summary.csv 구조 (3행):
      Row 1: Batch, ac160(...)_1102, ac160(...)_1103, ...
      Row 2: Freq, 327.6, 306.63, ...
      Row 3: Q, 614.23, 420.25, ...
    """
    text = _read_csv_text(csv_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    results = []
    if len(lines) < 3:
        return results

    batches = lines[0].split(",")
    freqs = lines[1].split(",")
    qs = lines[2].split(",")

    for i in range(1, len(batches)):
        batch = batches[i].strip()
        if not batch:
            continue

        # 슬롯 코드 추출: 마지막 _XXXX 부분
        m = re.search(r"_(\d{4})$", batch)
        slot_code = m.group(1) if m else str(i)

        freq_val = None
        q_val = None
        if i < len(freqs) and freqs[i].strip():
            freq_val = truncate_measurement_value(freqs[i].strip())
        if i < len(qs) and qs[i].strip():
            q_val = truncate_measurement_value(qs[i].strip())

        results.append({
            "batch": batch,
            "slot_code": slot_code,
            "frequency": freq_val,
            "q_factor": q_val,
        })

    return results


def find_freqsweep_image(freqsweep_dir: Path, slot_index: int, batch: str) -> str | None:
    """FreqSweep 폴더에서 해당 슬롯의 .jpg 파일 경로를 찾음.

    파일명 패턴: {번호}_{batch}_{slot_code}.jpg
    """
    if not freqsweep_dir.exists():
        return None

    prefix = f"{slot_index + 1}_"
    for f in freqsweep_dir.iterdir():
        if f.name.startswith(prefix) and f.suffix.lower() == ".jpg" and "ZoomOut" not in f.name:
            return str(f)
    return None


def load_atx_folder(folder_path: str) -> MeasurementSet:
    """ATX 결과 폴더를 로드하여 MeasurementSet 반환."""
    folder = Path(folder_path)
    info = parse_folder_name(folder.name)

    ms = MeasurementSet(
        po_number=info["po"],
        quantity=info["qty"],
        probe_type=info["probe_type"],
        source_folder=str(folder),
        mode="atx",
    )

    summary_path = folder / "Summary.csv"
    if not summary_path.exists():
        return ms

    parsed = parse_summary_csv(summary_path)
    freqsweep_dir = folder / "FreqSweep"

    for i, entry in enumerate(parsed):
        img = find_freqsweep_image(freqsweep_dir, i, entry["batch"])
        slot = SlotData(
            slot_index=i,
            slot_code=entry["slot_code"],
            frequency=entry["frequency"],
            q_factor=entry["q_factor"],
            image_path=img,
            source="summary_csv",
        )
        ms.slots.append(slot)

    return ms
