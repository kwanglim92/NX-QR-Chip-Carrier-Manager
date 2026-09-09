"""로트 생성 — 등급별 통과 슬롯을 12M/10M/5M 로트 폴더(기존 ATX 형식)로 기록.

로트 폴더 = ``{UnitNo}_{qty}M_{TipID}`` ::

    Summary.csv                      Batch,{batch}_{code},...,   /  Freq,...  /  Q,...
    FreqSweep/{n}_{batch}_{code}.jpg | _ZoomOut.jpg | .txt | _ZoomOut.txt
    Vision/{n}_{batch}_{code}_pickUp.png | _putBack.png

이 형식은 ``src.core.atx_parser.load_atx_folder`` 가 그대로 읽는다(라운드트립 테스트).
Unit No 는 로트마다 뒤 숫자 +1(``P2401002 → P2401003``, 자릿수 유지).
"""
from __future__ import annotations

import csv
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.core.atx_parser import load_atx_folder
from src.core.inspection.check_sheet import check_sheet_name, write_check_sheet
from src.core.inspection.grading import SlotVerdict
from src.core.inspection.mtc_parser import MtcRun, MtcSlot
from src.core.inspection.templates import GRADE_NAMES, ITEM_CATALOG
from src.core.models import MeasurementSet

LOT_SIZES: tuple[int, ...] = (12, 10, 5)

_UNIT_RE = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)$")


def next_unit_no(unit_no: str) -> str:
    """뒤 숫자 +1 (자릿수 유지). 숫자가 없으면 '_1' 접미."""
    m = _UNIT_RE.match(unit_no.strip())
    if not m:
        return f"{unit_no.strip()}_1"
    num = m.group("num")
    return f"{m.group('prefix')}{int(num) + 1:0{len(num)}d}"


def default_batch(tip_id: str, run_id: str) -> str:
    return f"{tip_id.lower()}({run_id})"


def lot_folder_name(unit_no: str, size: int, tip_id: str) -> str:
    return f"{unit_no}_{size}M_{tip_id}"


def plan_lot_sizes(counts: dict[int, int]) -> list[int]:
    """``{12: n12, 10: n10, 5: n5}`` → [12, 12, ..., 10, ..., 5, ...] (큰 로트 먼저)."""
    sizes: list[int] = []
    for size in LOT_SIZES:
        sizes.extend([size] * max(0, int(counts.get(size, 0) or 0)))
    return sizes


def validate_plan(sizes: list[int], available: int) -> str | None:
    """계획이 유효하면 None, 아니면 오류 메시지."""
    if not sizes:
        return "로트 수량이 0 입니다"
    need = sum(sizes)
    if need > available:
        return f"필요 {need}개 > 통과 {available}개"
    return None


@dataclass
class LotResult:
    folder: str
    unit_no: str
    size: int
    codes: list[str] = field(default_factory=list)
    measurement_set: MeasurementSet | None = None
    check_sheet: str | None = None


@dataclass
class CheckSheetSpec:
    """로트별 체크시트 생성 사양. ``checks_by_code[code] = {a_plus_b, unipeak, noise, frequency: bool}``."""
    template: str
    model_name: str
    checks_by_code: dict[str, dict[str, bool]] = field(default_factory=dict)

    def lot_checks(self, codes: list[str]) -> dict[str, bool | None]:
        out: dict[str, bool | None] = {"backside": None}
        for key in ("a_plus_b", "unipeak", "noise", "frequency"):
            vals = [self.checks_by_code.get(c, {}).get(key) for c in codes]
            vals = [v for v in vals if v is not None]
            out[key] = all(vals) if vals else None
        return out


def _copy(src: str | None, dst: Path) -> None:
    if src and Path(src).exists():
        shutil.copy2(src, dst)


def write_lot_folder(out_dir: str | Path, unit_no: str, size: int, tip_id: str,
                     batch: str, slots: list[MtcSlot],
                     check_sheet: CheckSheetSpec | None = None) -> LotResult:
    """슬롯들을 로트 폴더로 기록하고 ``load_atx_folder`` 로 다시 읽은 MeasurementSet 을 돌려준다."""
    folder = Path(out_dir) / lot_folder_name(unit_no, size, tip_id)
    sweep_dir = folder / "FreqSweep"
    vision_dir = folder / "Vision"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    vision_dir.mkdir(parents=True, exist_ok=True)

    batch_row = ["Batch"]
    freq_row = ["Freq"]
    q_row = ["Q"]
    codes: list[str] = []
    for n, s in enumerate(slots, start=1):
        stem = f"{n}_{batch}_{s.code}"
        batch_row.append(f"{batch}_{s.code}")
        freq_row.append("" if s.frequency is None else f"{s.frequency:g}")
        q_row.append("" if s.q is None else f"{s.q:g}")
        codes.append(s.code)
        _copy(s.sweep_image, sweep_dir / f"{stem}.jpg")
        _copy(s.sweep_txt, sweep_dir / f"{stem}.txt")
        _copy(s.zoom_image, sweep_dir / f"{stem}_ZoomOut.jpg")
        _copy(s.zoom_txt, sweep_dir / f"{stem}_ZoomOut.txt")
        _copy(s.pickup_image, vision_dir / f"{stem}_pickUp.png")
        _copy(s.putback_image, vision_dir / f"{stem}_putBack.png")

    # 원본 Summary.csv 와 같이 각 행 끝에 빈 셀(후행 콤마)
    with (folder / "Summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(batch_row + [""])
        w.writerow(freq_row + [""])
        w.writerow(q_row + [""])

    ms = load_atx_folder(str(folder))
    by_code = {s.code: s for s in slots}
    for sd in ms.slots:
        src = by_code.get(sd.slot_code)
        if src is not None:
            sd.drive = src.drive
    sheet_path = None
    if check_sheet is not None and check_sheet.template:
        sheet_path = str(folder / check_sheet_name(unit_no, size, check_sheet.model_name))
        write_check_sheet(check_sheet.template, sheet_path, unit_no, check_sheet.model_name,
                          [s.frequency for s in slots], [s.q for s in slots],
                          check_sheet.lot_checks(codes))
    return LotResult(folder=str(folder), unit_no=unit_no, size=size, codes=codes,
                     measurement_set=ms, check_sheet=sheet_path)


def build_lots(out_dir: str | Path, slots: list[MtcSlot], sizes: list[int],
               unit_no_start: str, tip_id: str, batch: str,
               check_sheet: CheckSheetSpec | None = None) -> tuple[list[LotResult], list[MtcSlot]]:
    """slots(순서 유지)를 sizes 대로 잘라 로트 폴더들을 만든다. 반환: (로트들, 남은 슬롯)."""
    err = validate_plan(sizes, len(slots))
    if err:
        raise ValueError(err)
    results: list[LotResult] = []
    unit_no = unit_no_start.strip()
    pos = 0
    for size in sizes:
        chunk = slots[pos:pos + size]
        pos += size
        results.append(write_lot_folder(out_dir, unit_no, size, tip_id, batch, chunk, check_sheet))
        unit_no = next_unit_no(unit_no)
    return results, slots[pos:]


# ─── 리포트 CSV ───

_REPORT_COLUMNS = [
    "CantileverNo", "ATX", "Port", "Slot", "Grade", "Error", "Override",
    "A+B (V)", "A-B (V)", "C-D (V)", "Frequency (kHz)", "Set Point (nm)", "Amplitude (nm)",
    "Drive (%)", "Q", "Tip X (pxl)", "Tip Y (pxl)", "X Offset (um)", "Y Offset (um)",
    "Angle", "Angle Offset", "Match Score (%)", "Sweep Score", "Sweep Reasons",
    "Vision", "Failed (industrial)",
]


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def write_report_csv(path: str | Path, run: MtcRun, verdicts: list[SlotVerdict],
                     reference_code: str | None, template_tip: str) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([f"# run={run.run_id}", f"reference={reference_code or ''}",
                    f"template={template_tip}"])
        w.writerow(_REPORT_COLUMNS)
        for v in verdicts:
            s, m = v.slot, v.metrics
            fails = ", ".join(
                f"{ITEM_CATALOG_LABEL[f.item]}={_cell(f.value)} ({f.bound})"
                for f in v.failed_items("industrial"))
            w.writerow([
                run.cantilever_no(s), s.atx, s.port, s.slot, GRADE_NAMES.get(v.grade, v.grade),
                v.error_label, "Y" if v.is_override else "",
                _cell(s.a_plus_b), _cell(s.a_minus_b), _cell(s.c_minus_d), _cell(s.frequency),
                _cell(s.set_point), _cell(s.amplitude), _cell(s.drive), _cell(s.q),
                _cell(s.tip_x), _cell(s.tip_y), _cell(m.get("x_offset_um")), _cell(m.get("y_offset_um")),
                _cell(s.angle), _cell(m.get("angle_offset_deg")), _cell(s.match_score),
                _cell(v.sweep.score if v.sweep.available else None), "; ".join(v.sweep.reasons),
                v.vision.summary(), fails,
            ])


ITEM_CATALOG_LABEL = {i.key: i.short for i in ITEM_CATALOG}
