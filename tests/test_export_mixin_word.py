"""ExportMixin — Save CSV 시 폴더(카세트)별 Word 체크시트 생성, Tip 프로필 없으면 생략, Tip 관리 저장."""
from __future__ import annotations

import zipfile

import pytest
from PIL import Image
from PySide6.QtCore import QObject

from src.core.models import MeasurementSet, SlotData
from src.core.tip_profiles import load_tip_profiles, save_tip_profiles
from src.ui.controllers.export_mixin import ExportMixin
from src.ui.controllers.settings_mixin import SettingsMixin
from tests.test_qr_reader_mixin import _Logger


class _Tabs:
    def __init__(self, idx=0): self.idx = idx
    def currentIndex(self): return self.idx


class _Host(ExportMixin, SettingsMixin, QObject):
    def __init__(self, db_conn, sets):
        super().__init__()
        self._db_conn = db_conn
        self.logger = _Logger()
        self.export_tabs = _Tabs(0)
        self._sets = sets

    def _atx_folder_sets(self): return self._sets


def _set(po: str, qty: int, probe: str, n: int) -> MeasurementSet:
    ms = MeasurementSet(po_number=po, quantity=qty, probe_type=probe, production_date="20261008",
                        source_folder=f"C:/atx/{po}_{qty}M_{probe}")
    for i in range(n):
        ms.slots.append(SlotData(slot_index=i, slot_code=str(i + 1), frequency=300 + i, drive=1.0,
                                 q_factor=500 + i, qr_id=f"26800029{i:02d}"))
    return ms


@pytest.fixture
def host(qapp, db_conn):
    return _Host(db_conn, [_set("P2601001", 12, "AC160", 12), _set("P2601002", 10, "AC160", 10)])


def _doc_xml(path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_skips_without_profile_and_warns(host, tmp_path):
    host._write_word_sheets(host._sets, tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert [m for k, m in host.logger.lines if k == "warn"] == ["Tip 'AC160' 프로필 없음 — Word 체크시트 생략 (Tip 관리…)"] * 2


def test_merged_scope_writes_one_docx_per_folder(host, tmp_path):
    save_tip_profiles(host._db_conn, {"AC160": {"display_name": "AC160TS"}})
    host._save_spec_limits({"AC160": {"freq_min": 250, "freq_max": 350, "q_min": None, "q_max": None}})
    merged, _ = host._build_atx_merged_ms(host._sets) if hasattr(host, "date_edit") else (MeasurementSet(po_number="합본"), [])
    assert host._word_sheet_sets(merged) == host._sets          # 합본 → 원본 폴더 세트들
    host._write_word_sheets(host._word_sheet_sets(merged), tmp_path)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["P2601001_12M_AC160TS.docx", "P2601002_10M_AC160TS.docx"]
    xml = _doc_xml(tmp_path / "P2601002_10M_AC160TS.docx")
    assert "10(R)" in xml and "P2601002" in xml and "AC160TS" in xml
    assert sum(1 for k, _ in host.logger.lines if k == "ok") == 2


def test_single_scope_writes_only_that_set(host, tmp_path):
    save_tip_profiles(host._db_conn, {"ac160": {"display_name": "AC160TS"}})   # 대소문자 무시 매칭
    target = host._sets[1]
    assert host._word_sheet_sets(target) == [target]
    host._write_word_sheets([target], tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["P2601002_10M_AC160TS.docx"]


def test_manual_merge_uses_slot_probe_type_and_slot_count(host, tmp_path):
    save_tip_profiles(host._db_conn, {"PPP-NCHR": {"display_name": "PPP-NCHR", "spec_layout": "nominal_range"}})
    host.export_tabs = _Tabs(1)
    merged = MeasurementSet(mode="manual", po_number="BOX-7", probe_type="", production_date="20261008")
    for i in range(5):
        merged.slots.append(SlotData(slot_index=i, slot_code=str(i), frequency=320, drive=1.0, q_factor=400,
                                     qr_id=f"2684080D{i:02X}", probe_type="PPP-NCHR", serial_number="S1"))
    assert host._word_sheet_sets(merged) == [merged]
    host._write_word_sheets([merged], tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["BOX-7_5M_PPP-NCHR.docx"]
    assert "5(R)" in _doc_xml(tmp_path / "BOX-7_5M_PPP-NCHR.docx")


class _DlgStub:
    result = {}
    catalog = []

    def __init__(self, catalog, profiles, loaded, parent):
        _DlgStub.seen = (list(catalog), dict(profiles), list(loaded))

    def exec(self): return 1
    def deleteLater(self): pass
    def result_profiles(self): return _DlgStub.result
    def result_catalog(self): return _DlgStub.catalog


def test_open_tip_profiles_saves_profiles_catalog_and_copies_image(host, tmp_path, monkeypatch):
    src = tmp_path / "sem.jpg"
    Image.new("RGB", (20, 10), "gray").save(src, "JPEG")
    store = tmp_path / "store"
    monkeypatch.setattr("src.core.tip_profiles.tip_images_dir", lambda: store)
    monkeypatch.setattr("src.ui.dialogs.tip_profile_dialog.TipProfileDialog", _DlgStub)
    host._save_tip_catalog(["PPP-NCHR"])
    _DlgStub.result = {"AC160": {"display_name": "AC160TS", "sem_image": str(src)}}
    _DlgStub.catalog = ["PPP-NCHR", "AC160"]

    host._open_tip_profiles()
    assert _DlgStub.seen == (["PPP-NCHR"], {}, ["AC160", "AC160"])
    saved = load_tip_profiles(host._db_conn)
    assert saved["AC160"]["sem_image"] == str(store / "AC160.png") and (store / "AC160.png").exists()
    assert host._load_tip_catalog() == ["PPP-NCHR", "AC160"]
    assert host.logger.lines[-1] == ("ok", "Tip 프로필 저장: 1개")
