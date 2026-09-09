"""로트 체크시트(``{Unit}_{qty}M_{모델명}.xlsx``) 생성 — 템플릿 xlsx 를 zip 수준에서 편집.

openpyxl 로 열어 저장하면 SEM/SPEC 이미지(drawing)가 사라지므로, ``xl/worksheets/sheet1.xml`` 의
셀만 바꿔 쓰고 나머지 파트는 그대로 복사한다. 템플릿 셀 배치(기존 P2601001_12M_AC160TS.xlsx)::

    B4  Unit           B5  Type(정식 모델명)
    L26/M26 Backside surface   L28/M28 A+B   L31/M31 Unipeak   L32/M32 Noise   L34/M34 Frequency Sweep
    B41..M41 Frequency (1(L) ~ 12(R))        B42..M42 Q-Factor

Pass 열(L)에 ``■``/``□``, Fail 열(M)에 반대. 로트가 12개 미만이면 남는 열은 비운다.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SHEET_PART = "xl/worksheets/sheet1.xml"
CELL_UNIT = "B4"
CELL_TYPE = "B5"
CHECK_ROWS: dict[str, int] = {"backside": 26, "a_plus_b": 28, "unipeak": 31, "noise": 32, "frequency": 34}
FREQ_ROW = 41
Q_ROW = 42
VALUE_COLS = "BCDEFGHIJKLM"   # 1(L) ~ 12(R)
MARK_ON, MARK_OFF = "■", "□"

_CELL_RE = r'<c r="{ref}"(?P<attrs>[^>]*?)(?:/>|>.*?</c>)'


def _style_of(attrs: str) -> str:
    m = re.search(r'\ss="(\d+)"', attrs)
    return f' s="{m.group(1)}"' if m else ""


def _set_cell(xml: str, ref: str, value) -> str:
    """ref 셀을 value 로 교체(문자열 → inlineStr, 숫자 → n, None → 빈 셀). 셀이 없으면 그대로."""
    m = re.search(_CELL_RE.format(ref=ref), xml, flags=re.S)
    if not m:
        return xml
    style = _style_of(m.group("attrs"))
    if value is None or value == "":
        new = f'<c r="{ref}"{style}/>'
    elif isinstance(value, (int, float)):
        new = f'<c r="{ref}"{style}><v>{value:g}</v></c>'
    else:
        new = f'<c r="{ref}"{style} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
    return xml[:m.start()] + new + xml[m.end():]


def render_sheet_xml(xml: str, unit_no: str, model_name: str,
                     freqs: list[float | None], qs: list[float | None],
                     checks: dict[str, bool | None]) -> str:
    xml = _set_cell(xml, CELL_UNIT, unit_no)
    xml = _set_cell(xml, CELL_TYPE, model_name)
    for key, row in CHECK_ROWS.items():
        ok = checks.get(key)
        if ok is None:
            continue   # 템플릿 값 유지(예: Backside surface 는 수동)
        xml = _set_cell(xml, f"L{row}", MARK_ON if ok else MARK_OFF)
        xml = _set_cell(xml, f"M{row}", MARK_OFF if ok else MARK_ON)
    for i, col in enumerate(VALUE_COLS):
        f = freqs[i] if i < len(freqs) else None
        q = qs[i] if i < len(qs) else None
        xml = _set_cell(xml, f"{col}{FREQ_ROW}", f)
        xml = _set_cell(xml, f"{col}{Q_ROW}", q)
    return xml


def write_check_sheet(template: str | Path, out_path: str | Path, unit_no: str, model_name: str,
                      freqs: list[float | None], qs: list[float | None],
                      checks: dict[str, bool | None]) -> Path:
    """템플릿 xlsx 를 복사하면서 sheet1.xml 만 채워 ``out_path`` 에 쓴다. 이미지 등은 그대로."""
    template = Path(template)
    out_path = Path(out_path)
    if not template.exists():
        raise FileNotFoundError(str(template))
    tmp = out_path.with_suffix(".tmp")
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == SHEET_PART:
                data = render_sheet_xml(data.decode("utf-8"), unit_no, model_name, freqs, qs, checks
                                        ).encode("utf-8")
            zout.writestr(item, data)
    shutil.move(str(tmp), str(out_path))
    return out_path


def check_sheet_name(unit_no: str, size: int, model_name: str) -> str:
    return f"{unit_no}_{size}M_{model_name}.xlsx"
