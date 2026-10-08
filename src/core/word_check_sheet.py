"""Word 체크시트(``{Unit}_{qty}M_{Type}.docx``) 생성 — 번들 템플릿 docx 를 zip 수준에서 편집.

python-docx 없이 ``assets/templates/check_sheet_base.docx`` (AC160TS 12M 체크시트에서 중복 표만 제거한
원본)를 복사하면서 ``word/document.xml`` 과 SEM 사진 ``word/media/image1.png`` 만 바꿔 쓴다.
나머지 파트(헤더·푸터·스타일·rels)는 그대로라 Word 양식이 유지된다. 편집 항목::

    표 1 r0        Unit: {PO}  /  Type : {Tip 표기명}
    표 1 r1 좌     SEM 사진(항상 PNG, 2286000×1752600 EMU 박스에 비율 맞춤)
    표 1 r1 우     스펙 표 — min/typ/max(4열) 또는 Nominal/Specified Range(3열), 행 수 자유
    Check Item     4. Frequency Sweep 의 Pass/Fail 칸에 ■/□ (True → Pass, False → Fail, None → 둘 다 □)
    Sweep 표       Batch 1(L)…N(R) / Frequency (KHz) / Q-Factor 를 N열(10·12 또는 슬롯 수)로 재생성

모든 편집은 문자열·정규식 수준이며, 표는 템플릿의 셀 XML 을 복제해 만든다(글꼴·테두리 보존).
"""
from __future__ import annotations

import io
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from src.core.models import truncate_measurement_value

DOC_PART = "word/document.xml"
IMAGE_PART = "word/media/image1.png"
MARK_ON, MARK_OFF = "■", "□"
SWEEP_COLUMN_SIZES = (10, 12)        # 카세트 수량이 이 중 하나면 그대로, 아니면 슬롯 수만큼
SPEC_LAYOUT_HEADERS = {
    "min_typ_max": ("min", "typ", "max"),
    "nominal_range": ("Nominal Value", "Specified Range"),
}
_IMAGE_BOX_EMU = (2286000, 1752600)  # 템플릿 SEM 사진 자리(6.35×4.87 cm)
_BLANK_IMAGE_SIZE = (260, 201)
_SWEEP_GRID_TOTAL, _SWEEP_LABEL_GRID = 10449, 972     # dxa
_SWEEP_PCT_TOTAL, _SWEEP_LABEL_PCT = 5000, 456        # tcW w:type="pct" (50분의 1 %)
_SPEC_LABEL_GRID, _SPEC_TOTAL_GRID = 2520, 5760


def _project_root() -> Path:
    """개발 환경은 ``<root>/src/core/``, PyInstaller 동결 환경은 ``sys.executable`` 디렉터리."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


DEFAULT_TEMPLATE = _project_root() / "assets" / "templates" / "check_sheet_base.docx"


@dataclass
class WordSheetData:
    unit_no: str
    type_name: str
    sem_image: str | None = None
    spec_layout: str = "min_typ_max"
    spec_rows: list[list[str]] = field(default_factory=list)
    freqs: list[int | None] = field(default_factory=list)
    qs: list[int | None] = field(default_factory=list)
    n_columns: int = 12
    frequency_sweep: bool | None = None


# ─── 데이터 구성 ───

def _within(value, lo, hi) -> bool:
    return (lo is None or value >= lo) and (hi is None or value <= hi)


def build_word_sheet_data(ms, profile: dict, bounds) -> WordSheetData:
    """MeasurementSet + Tip 프로필(+ 규격 경계) → 체크시트 데이터.

    ``bounds`` 는 ``quality.spec_bounds_for`` 의 ``(f_lo, f_hi, q_lo, q_hi)`` 또는 None.
    Frequency Sweep 판정은 Freq·Q 가 모두 있는 슬롯만 보며, 경계나 값이 없으면 None(미판정).
    """
    n = ms.quantity if ms.quantity in SWEEP_COLUMN_SIZES else len(ms.slots)
    n = max(1, n)
    slots = list(ms.slots)[:n]
    pad = [None] * (n - len(slots))
    freqs = [truncate_measurement_value(s.frequency) for s in slots] + pad
    qs = [truncate_measurement_value(s.q_factor) for s in slots] + pad

    measured = [(s.frequency, s.q_factor) for s in slots if s.frequency is not None and s.q_factor is not None]
    if bounds is None or not measured:
        sweep = None
    else:
        f_lo, f_hi, q_lo, q_hi = bounds
        sweep = all(_within(f, f_lo, f_hi) and _within(q, q_lo, q_hi) for f, q in measured)

    layout = profile.get("spec_layout", "min_typ_max")
    if layout not in SPEC_LAYOUT_HEADERS:
        layout = "min_typ_max"
    return WordSheetData(
        unit_no=ms.po_number,
        type_name=profile.get("display_name") or ms.probe_type,
        sem_image=profile.get("sem_image") or None,
        spec_layout=layout,
        spec_rows=[[str(c) for c in row] for row in profile.get("spec_rows", [])],
        freqs=freqs, qs=qs, n_columns=n, frequency_sweep=sweep,
    )


# ─── XML 스캐너 ───

def _spans(xml: str, tag: str) -> list[tuple[int, int]]:
    """``xml`` 안에서 깊이 0 인 ``<tag …>…</tag>`` 블록들의 (시작, 끝) — 중첩 표/문단을 올바르게 가른다."""
    out: list[tuple[int, int]] = []
    depth = 0
    start = 0
    for m in re.finditer(rf"<{tag}>|<{tag} |</{tag}>", xml):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                out.append((start, m.end()))
        else:
            if depth == 0:
                start = m.start()
            depth += 1
    return out


def _parts(xml: str, tag: str) -> list[str]:
    return [xml[s:e] for s, e in _spans(xml, tag)]


def _text(xml: str) -> str:
    return "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml))


def _strip_ids(xml: str) -> str:
    """복제한 문단의 ``w14:paraId``/``textId`` 제거 — 문서 안에서 중복되지 않도록."""
    return re.sub(r' w14:(?:paraId|textId)="[0-9A-F]+"', "", xml)


def _run_rpr(run: str) -> str:
    m = re.search(r"<w:rPr>.*?</w:rPr>", run, flags=re.S)
    return m.group(0) if m else ""


def _para_mark_rpr(par: str) -> str:
    m = re.search(r"<w:pPr>.*?</w:pPr>", par, flags=re.S)
    return _run_rpr(m.group(0)) if m else ""


def _run(rpr: str, text: str) -> str:
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _set_para_runs(par: str, runs_xml: str) -> str:
    """문단의 기존 run 을 모두 버리고 ``runs_xml`` 로 바꾼다(``<w:pPr>`` 유지)."""
    m = re.search(r"<w:pPr>.*?</w:pPr>", par, flags=re.S)
    if m:
        head = par[:m.end()]
    else:
        head = par[:par.index(">") + 1]
    return head + runs_xml + "</w:p>"


def _set_cell_text(tc: str, text: str) -> str:
    """셀의 첫 문단 텍스트를 바꾼다. 글꼴은 기존 첫 run(없으면 문단 기호)의 rPr 을 따른다."""
    s, e = _spans(tc, "w:p")[0]
    par = tc[s:e]
    runs = _parts(par, "w:r")
    rpr = _run_rpr(runs[0]) if runs else _para_mark_rpr(par)
    new_par = _set_para_runs(par, _run(rpr, text) if text else "")
    return tc[:s] + new_par + tc[e:]


def _set_tcw(tc: str, width: int) -> str:
    return re.sub(r'<w:tcW w:w="\d+"', f'<w:tcW w:w="{width}"', tc, count=1)


def _grid(widths: list[int]) -> str:
    return "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"


def _replace_grid(tbl: str, widths: list[int]) -> str:
    return re.sub(r"<w:tblGrid>.*?</w:tblGrid>", _grid(widths), tbl, count=1, flags=re.S)


def _row_head(row: str) -> str:
    """``<w:tr …><w:trPr>…</w:trPr>`` — 첫 셀 앞까지."""
    return row[:_spans(row, "w:tc")[0][0]]


# ─── 편집 단계 ───

def _drop_duplicate_check_tables(xml: str) -> str:
    spans = [(s, e) for s, e in _spans(xml, "w:tbl") if "Check Item" in _text(xml[s:e])]
    for s, e in reversed(spans[1:]):
        xml = xml[:s] + xml[e:]
    return xml


def _find_table(xml: str, first_cell_prefix: str) -> tuple[int, int]:
    for s, e in _spans(xml, "w:tbl"):
        tbl = xml[s:e]
        rows = _spans(tbl, "w:tr")
        if not rows:
            continue
        r0 = tbl[rows[0][0]:rows[0][1]]
        cells = _spans(r0, "w:tc")
        if cells and first_cell_prefix in _text(r0[cells[0][0]:cells[0][1]]):
            return s, e
    raise ValueError(f"템플릿에 '{first_cell_prefix}' 표가 없습니다")


def _render_sweep_table(xml: str, d: WordSheetData) -> str:
    s, e = _find_table(xml, "Batch")
    tbl = xml[s:e]
    rows = _spans(tbl, "w:tr")
    n = d.n_columns
    head = _replace_grid(tbl[:rows[0][0]], [_SWEEP_LABEL_GRID] + [(_SWEEP_GRID_TOTAL - _SWEEP_LABEL_GRID) // n] * n)
    pct = round((_SWEEP_PCT_TOTAL - _SWEEP_LABEL_PCT) / n)

    headers = [f"{i}(L)" if i == 1 else f"{i}(R)" if i == n else str(i) for i in range(1, n + 1)]
    values = [headers, ["" if v is None else str(v) for v in d.freqs], ["" if v is None else str(v) for v in d.qs]]
    out_rows = []
    for (rs, re_), vals in zip(rows[:3], values):
        row = tbl[rs:re_]
        cells = _parts(row, "w:tc")
        label, val_tpl = cells[0], cells[1]
        vals = (list(vals) + [""] * n)[:n]
        new_cells = [_set_tcw(_set_cell_text(val_tpl, v), pct) for v in vals]
        out_rows.append(_strip_ids(_row_head(row) + label + "".join(new_cells) + "</w:tr>"))
    return xml[:s] + head + "".join(out_rows) + "</w:tbl>" + xml[e:]


def _render_check_marks(xml: str, d: WordSheetData) -> str:
    s, e = _find_table(xml, "Check Item")
    tbl = xml[s:e]
    rows = _spans(tbl, "w:tr")
    box_run = None
    target = None
    for rs, re_ in rows:
        row = tbl[rs:re_]
        cells = _parts(row, "w:tc")
        t = _text(cells[0]).strip()
        if "Unipeak" in t and box_run is None:
            box_run = _parts(cells[1], "w:r")[0]
        if t.startswith("4. Frequency Sweep"):
            target = (rs, re_)
    if box_run is None or target is None:
        raise ValueError("템플릿 Check Item 표 구조가 다릅니다")
    pass_mark = MARK_ON if d.frequency_sweep is True else MARK_OFF
    fail_mark = MARK_ON if d.frequency_sweep is False else MARK_OFF
    rs, re_ = target
    row = tbl[rs:re_]
    cells = _spans(row, "w:tc")
    new_row = row
    for (cs, ce), mark in reversed(list(zip(cells[1:3], (pass_mark, fail_mark)))):
        cell = row[cs:ce]
        cell = _set_para_runs_in_cell(cell, _run(_run_rpr(box_run), mark))
        new_row = new_row[:cs] + cell + new_row[ce:]
    tbl = tbl[:rs] + new_row + tbl[re_:]
    return xml[:s] + tbl + xml[e:]


def _set_para_runs_in_cell(tc: str, runs_xml: str) -> str:
    s, e = _spans(tc, "w:p")[0]
    return tc[:s] + _set_para_runs(tc[s:e], runs_xml) + tc[e:]


def _set_label_value(par: str, value: str) -> str:
    """``Unit : P25`` 꼴 문단에서 ``:`` 뒤의 run 들을 ``value`` 하나로 바꾼다."""
    runs = _spans(par, "w:r")
    k = next((i for i, (s, e) in enumerate(runs) if _text(par[s:e]).strip() == ":"), None)
    if k is None:
        return par
    src = par[runs[-1][0]:runs[-1][1]]   # 마지막 run(기존 값)의 글꼴을 따른다
    return par[:runs[k][1]] + _run(_run_rpr(src), f" {value}") + "</w:p>"


def _render_unit_type(xml: str, d: WordSheetData) -> str:
    s, e = _find_table(xml, "Unit")
    tbl = xml[s:e]
    r0s, r0e = _spans(tbl, "w:tr")[0]
    row = tbl[r0s:r0e]
    cs, ce = _spans(row, "w:tc")[0]
    cell = row[cs:ce]
    for ps, pe in reversed(_spans(cell, "w:p")):
        par = cell[ps:pe]
        t = _text(par).strip()
        if t.startswith("Unit"):
            cell = cell[:ps] + _set_label_value(par, d.unit_no) + cell[pe:]
        elif t.startswith("Type"):
            cell = cell[:ps] + _set_label_value(par, d.type_name) + cell[pe:]
    row = row[:cs] + cell + row[ce:]
    tbl = tbl[:r0s] + row + tbl[r0e:]
    return xml[:s] + tbl + xml[e:]


def _render_spec_table(xml: str, d: WordSheetData) -> str:
    s, e = _find_table(xml, "Unit")
    tbl = xml[s:e]
    r1s, r1e = _spans(tbl, "w:tr")[1]
    row = tbl[r1s:r1e]
    cs, ce = _spans(row, "w:tc")[1]
    cell = row[cs:ce]
    ns, ne = _spans(cell, "w:tbl")[0]
    nested = cell[ns:ne]

    rows = _parts(nested, "w:tr")
    head = nested[:_spans(nested, "w:tr")[0][0]]
    row0, row1, data_tpl = rows[0], rows[1], rows[2]
    data_cells = _parts(data_tpl, "w:tc")
    label_tpl, val_tpl = data_cells[0], data_cells[1]
    headers = SPEC_LAYOUT_HEADERS[d.spec_layout]
    n_vals = len(headers)

    if d.spec_layout == "min_typ_max":
        widths = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"', nested)]
        header_rows = row0 + row1
    else:
        vw = (_SPEC_TOTAL_GRID - _SPEC_LABEL_GRID) // n_vals
        widths = [_SPEC_LABEL_GRID] + [vw] * n_vals
        c0 = _parts(row0, "w:tc")
        hdr_label = c0[0].replace('<w:vMerge w:val="restart"/>', "")
        hdr_val = re.sub(r'<w:gridSpan w:val="\d+"/>', "", c0[1])
        header_rows = _row_head(row0) + hdr_label + "".join(
            _set_tcw(_set_cell_text(hdr_val, h), vw) for h in headers) + "</w:tr>"
    head = _replace_grid(head, widths)

    data_rows = []
    for spec in d.spec_rows:
        label, vals = (spec[0] if spec else ""), (list(spec[1:]) + [""] * n_vals)[:n_vals]
        cells = [_set_cell_text(label_tpl, label)] + [
            _set_tcw(_set_cell_text(val_tpl, v), widths[i + 1]) for i, v in enumerate(vals)]
        data_rows.append(_row_head(data_tpl) + "".join(cells) + "</w:tr>")
    new_nested = head + _strip_ids(header_rows + "".join(data_rows)) + "</w:tbl>"

    cell = cell[:ns] + new_nested + cell[ne:]
    row = row[:cs] + cell + row[ce:]
    tbl = tbl[:r1s] + row + tbl[r1e:]
    return xml[:s] + tbl + xml[e:]


def _render_image_extent(xml: str, image_size: tuple[int, int] | None) -> str:
    if not image_size:
        return xml
    w, h = image_size
    if w <= 0 or h <= 0:
        return xml
    scale = min(_IMAGE_BOX_EMU[0] / w, _IMAGE_BOX_EMU[1] / h)
    cx, cy = int(w * scale), int(h * scale)
    m = re.search(r"<wp:inline.*?</wp:inline>", xml, flags=re.S)
    if not m:
        return xml
    seg = m.group(0)
    seg = re.sub(r'<wp:extent cx="\d+" cy="\d+"/>', f'<wp:extent cx="{cx}" cy="{cy}"/>', seg, count=1)
    seg = re.sub(r'<a:ext cx="\d+" cy="\d+"/>', f'<a:ext cx="{cx}" cy="{cy}"/>', seg, count=1)
    return xml[:m.start()] + seg + xml[m.end():]


def render_document_xml(xml: str, d: WordSheetData, image_size: tuple[int, int] | None = None) -> str:
    xml = _drop_duplicate_check_tables(xml)
    xml = _render_sweep_table(xml, d)
    xml = _render_check_marks(xml, d)
    xml = _render_unit_type(xml, d)
    xml = _render_spec_table(xml, d)
    return _render_image_extent(xml, image_size)


# ─── 파일 쓰기 ───

def _sem_png(sem_image: str | None) -> tuple[bytes, tuple[int, int]]:
    """SEM 사진을 PNG 바이트로. 없으면 흰 빈 사진(다른 Tip 에 템플릿 사진이 남지 않게)."""
    if sem_image and Path(sem_image).is_file():
        img = Image.open(sem_image).convert("RGB")
    else:
        img = Image.new("RGB", _BLANK_IMAGE_SIZE, "white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), img.size


def write_word_check_sheet(template: str | Path, out_path: str | Path, d: WordSheetData) -> Path:
    """템플릿 docx 를 복사하면서 document.xml 과 SEM 사진만 채워 ``out_path`` 에 쓴다."""
    template = Path(template)
    out_path = Path(out_path)
    if not template.exists():
        raise FileNotFoundError(str(template))
    png, size = _sem_png(d.sem_image)
    tmp = out_path.with_suffix(".tmp")
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == DOC_PART:
                data = render_document_xml(data.decode("utf-8"), d, size).encode("utf-8")
            elif item.filename == IMAGE_PART:
                data = png
            zout.writestr(item, data)
    shutil.move(str(tmp), str(out_path))
    return out_path


def word_check_sheet_name(unit_no: str, size: int, type_name: str) -> str:
    return f"{unit_no}_{size}M_{type_name}.docx"
