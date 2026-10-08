"""Word 체크시트 docx 생성 테스트 — 번들 템플릿 zip 편집, SEM 사진 교체, 표 재생성, 마크."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.dom import minidom

import pytest
from PIL import Image

from src.core.models import MeasurementSet, SlotData
from src.core.word_check_sheet import (
    DEFAULT_TEMPLATE,
    WordSheetData,
    _parts,
    _text,
    build_word_sheet_data,
    word_check_sheet_name,
    write_word_check_sheet,
)

ROOT = Path(__file__).resolve().parent.parent


def _tables(xml: str) -> list[str]:
    return _parts(xml, "w:tbl")


def _rows(tbl: str) -> list[list[str]]:
    return [[_text(c) for c in _parts(r, "w:tc")] for r in _parts(tbl, "w:tr")]


def _spec_table(top_table: str) -> str:
    """표 1 r1 우측 셀에 중첩된 스펙 표."""
    return _parts(_parts(_parts(top_table, "w:tr")[1], "w:tc")[1], "w:tbl")[0]


def _check_table(xml: str) -> str:
    return next(t for t in _tables(xml) if "Check Item" in _text(t))


def _docx(path: Path) -> tuple[zipfile.ZipFile, str]:
    z = zipfile.ZipFile(path)
    return z, z.read("word/document.xml").decode("utf-8")


@pytest.fixture
def sem_jpeg(tmp_path: Path) -> Path:
    p = tmp_path / "sem.jpg"
    Image.new("RGB", (400, 200), "gray").save(p, "JPEG")
    return p


def _data(**kw) -> WordSheetData:
    base = dict(
        unit_no="P2601001", type_name="AC160TS", spec_layout="min_typ_max",
        spec_rows=[["Length (um)", "145", "160", "175"], ["Width (um)", "38", "40", "42"]],
        freqs=[300, 310, None] + [None] * 9, qs=[450, None, 470] + [None] * 9, n_columns=12,
        frequency_sweep=True,
    )
    base.update(kw)
    return WordSheetData(**base)


def test_name():
    assert word_check_sheet_name("P2601001", 12, "AC160TS") == "P2601001_12M_AC160TS.docx"


def test_template_bundled_and_has_single_check_item_table():
    assert DEFAULT_TEMPLATE == ROOT / "assets" / "templates" / "check_sheet_base.docx"
    _, xml = _docx(DEFAULT_TEMPLATE)
    assert sum("Check Item" in _text(t) for t in _tables(xml)) == 1


def test_write_12_columns_fills_unit_type_sweep_and_marks(tmp_path, sem_jpeg):
    out = tmp_path / "P2601001_12M_AC160TS.docx"
    write_word_check_sheet(DEFAULT_TEMPLATE, out, _data(sem_image=str(sem_jpeg)))

    z, xml = _docx(out)
    minidom.parseString(xml.encode("utf-8"))                       # well-formed
    tpl = zipfile.ZipFile(DEFAULT_TEMPLATE)
    for part in ("word/header1.xml", "word/footer1.xml", "word/_rels/document.xml.rels",
                 "[Content_Types].xml", "word/styles.xml"):
        assert z.read(part) == tpl.read(part)
    assert set(z.namelist()) == set(tpl.namelist())

    img = Image.open(io.BytesIO(z.read("word/media/image1.png")))
    assert img.format == "PNG" and img.size == (400, 200)          # JPEG → PNG 변환
    assert '<wp:extent cx="2286000" cy="1143000"/>' in xml          # 2:1 비율로 박스 폭에 맞춤
    assert '<a:ext cx="2286000" cy="1143000"/>' in xml

    tables = _tables(xml)
    assert sum("Check Item" in _text(t) for t in tables) == 1
    assert _rows(tables[0])[0][0] == "Unit: P2601001Type : AC160TS"

    sweep = _rows(tables[-1])
    assert sweep[0] == ["Batch", "1(L)"] + [str(i) for i in range(2, 12)] + ["12(R)"]
    assert sweep[1] == ["Frequency (KHz)", "300", "310"] + [""] * 10
    assert sweep[2] == ["Q-Factor", "450", "", "470"] + [""] * 9
    assert len(sweep) == 3

    check = _rows(_check_table(xml))
    assert next(r for r in check if r[0].startswith("4. Frequency Sweep"))[1:] == ["■", "□"]
    assert next(r for r in check if "Unipeak" in r[0])[1:] == ["■", "□"]   # 나머지는 템플릿 그대로(Pass 기본 체크)

    spec = _rows(_spec_table(tables[0]))
    assert spec[0] == ["Technical Data", "Lever"] and spec[1] == ["", "min", "typ", "max"]
    assert spec[2] == ["Length (um)", "145", "160", "175"] and spec[3] == ["Width (um)", "38", "40", "42"]
    assert len(spec) == 4

    def dupes(x: str) -> int:   # 템플릿 자체도 텍스트 상자(mc:AlternateContent 폴백)로 ID 가 2개 겹친다
        ids = re.findall(r'w14:paraId="([0-9A-F]+)"', x)
        return len(ids) - len(set(ids))
    assert dupes(xml) <= dupes(tpl.read("word/document.xml").decode("utf-8"))   # 복제 문단이 새 중복을 만들지 않음


def test_write_10_columns_and_nominal_range(tmp_path):
    out = tmp_path / "P2601002_10M_PPP-NCHR.docx"
    d = _data(unit_no="P2601002", type_name="PPP-NCHR", n_columns=10, spec_layout="nominal_range",
              spec_rows=[["Length / ㎛", "125", "115 ~ 135"], ["Thickness", "4"]],
              freqs=[320] * 10, qs=[500] * 10)
    write_word_check_sheet(DEFAULT_TEMPLATE, out, d)
    _, xml = _docx(out)
    minidom.parseString(xml.encode("utf-8"))
    tables = _tables(xml)
    sweep = _rows(tables[-1])
    assert len(sweep[0]) == 11 and sweep[0][-1] == "10(R)" and sweep[1][1:] == ["320"] * 10
    assert tables[-1].count("<w:gridCol") == 11
    nested = _spec_table(tables[0])
    spec = _rows(nested)
    assert spec[0] == ["Technical Data", "Nominal Value", "Specified Range"]
    assert spec[1] == ["Length / ㎛", "125", "115 ~ 135"] and spec[2] == ["Thickness", "4", ""]
    assert nested.count("<w:gridCol") == 3 and "vMerge" not in nested and "gridSpan" not in nested
    assert _rows(tables[0])[0][0] == "Unit: P2601002Type : PPP-NCHR"


@pytest.mark.parametrize("sweep, marks", [(None, ["□", "□"]), (False, ["□", "■"])])
def test_frequency_sweep_marks(tmp_path, sweep, marks):
    out = tmp_path / "x.docx"
    write_word_check_sheet(DEFAULT_TEMPLATE, out, _data(frequency_sweep=sweep))
    _, xml = _docx(out)
    check = _rows(_check_table(xml))
    assert next(r for r in check if r[0].startswith("4. Frequency Sweep"))[1:] == marks


def test_missing_image_writes_blank_png(tmp_path):
    out = tmp_path / "x.docx"
    write_word_check_sheet(DEFAULT_TEMPLATE, out, _data(sem_image=str(tmp_path / "none.png")))
    z, _ = _docx(out)
    img = Image.open(io.BytesIO(z.read("word/media/image1.png")))
    assert img.format == "PNG" and img.size == (260, 201) and img.getpixel((0, 0)) == (255, 255, 255)
    assert z.read("word/media/image1.png") != zipfile.ZipFile(DEFAULT_TEMPLATE).read("word/media/image1.png")


def _ms(freqs_qs, quantity=12, probe="AC160"):
    slots = [SlotData(slot_index=i, slot_code=str(i), frequency=f, q_factor=q, qr_id=f"QR{i}")
             for i, (f, q) in enumerate(freqs_qs)]
    return MeasurementSet(po_number="P2601001", quantity=quantity, probe_type=probe, slots=slots)


def test_build_word_sheet_data_pass_fail_with_spec_bounds():
    profile = {"display_name": "AC160TS", "sem_image": "", "spec_layout": "nominal_range",
               "spec_rows": [["Length", 125, "115 ~ 135"]]}
    bounds = (250.0, 350.0, None, None)

    d = build_word_sheet_data(_ms([(300.7, 450.2), (349.9, None), (None, None)]), profile, bounds)
    assert d.unit_no == "P2601001" and d.type_name == "AC160TS" and d.sem_image is None
    assert d.n_columns == 12 and d.freqs == [300, 349, None] + [None] * 9
    assert d.qs == [450, None, None] + [None] * 9
    assert d.frequency_sweep is True and d.spec_rows == [["Length", "125", "115 ~ 135"]]

    assert build_word_sheet_data(_ms([(300, 450), (360, 450)]), profile, bounds).frequency_sweep is False
    assert build_word_sheet_data(_ms([(300, 450)]), profile, None).frequency_sweep is None
    assert build_word_sheet_data(_ms([(None, None)]), profile, bounds).frequency_sweep is None

    short = build_word_sheet_data(_ms([(300, 450)] * 5, quantity=5), {}, None)
    assert short.n_columns == 5 and short.type_name == "AC160" and short.spec_layout == "min_typ_max"
    assert build_word_sheet_data(_ms([(300, 450)] * 3, quantity=10), {}, None).n_columns == 10


def test_missing_template_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_word_check_sheet(tmp_path / "nope.docx", tmp_path / "out.docx", _data())
