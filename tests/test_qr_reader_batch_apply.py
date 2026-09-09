"""R6: 프레임 → 계획 → 검토(스텁) → 일괄 적용 — 로드된 세트·그리드·저장·갱신 훅 검증."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QPushButton

from src.core.models import MeasurementSet, SlotData
from src.core.qr_reader.payload_parser import CellRead, ParsedFrame, parse_frame
from src.core.qr_reader.settings import save_qr_reader_settings
from src.ui.controllers.qr_reader_mixin import QRReaderMixin

FULL_RAW = Path(__file__).parent / "fixtures" / "qr_reader" / "20260909_132804_full.raw"


class _Logger:
    def __init__(self): self.lines = []
    def info(self, m): self.lines.append(("info", m))
    def ok(self, m): self.lines.append(("ok", m))
    def warn(self, m): self.lines.append(("warn", m))
    def error(self, m): self.lines.append(("error", m))


class _Grid:
    def __init__(self): self.updated = []
    def update_slot(self, slot): self.updated.append(slot.slot_code)


@pytest.fixture(autouse=True)
def _no_autoconnect(db_conn):
    """자동 접속 기본 켜짐 → 테스트가 실기기 IP 로 나가지 않도록 끈다."""
    save_qr_reader_settings(db_conn, {"enabled": False})


class _Host(QRReaderMixin, QObject):
    def __init__(self, db_conn, sets):
        super().__init__()
        self._db_conn = db_conn
        self.logger = _Logger()
        self.btn_reader_status = QPushButton()
        self.btn_cassette_scan = QPushButton()
        self.btn_read_review = QPushButton()
        self.btn_read_review.setEnabled(False)
        self._folder_tabs = [{"set": ms, "grid": _Grid(), "page": None, "folder": ""} for ms in sets]
        self.saved, self.refreshed = [], []
        self._init_qr_reader()

    def _atx_folder_sets(self): return [r["set"] for r in self._folder_tabs]
    def _auto_save_to_db(self, ms=None): self.saved.append(ms); return 100 + len(self.saved)
    def _atx_refresh_tab_labels(self): self.refreshed.append("labels")
    def _update_progress(self): self.refreshed.append("progress")
    def _pool_refresh_view(self): self.refreshed.append("pool")


def _set(port, po, atx=1, slots=range(1, 13)):
    ms = MeasurementSet(po_number=po, mode="atx")
    for i, s in enumerate(slots):
        ms.slots.append(SlotData(slot_index=i, slot_code=f"_{atx}{port}{s:02d}", frequency=396.0, q_factor=710.0))
    return ms


def _frame(codes):
    return ParsedFrame(reads=tuple(CellRead(cell=i, code=c, raw=c or "ERROR") for i, c in enumerate(codes, 1)), scan_time_ms=10)


class _AcceptDialog:
    """검토 다이얼로그 스텁: 계획을 붙잡고 [적용] 을 누른 것처럼 동작."""
    last = None

    def __init__(self, plan, sets, scan_time_ms=None, layout=None, parent=None):
        self.plan = plan
        self.layout = layout
        self.forced = set()
        _AcceptDialog.last = self
        class _Sig:
            def connect(self, *_): pass
        self.rescan_requested = _Sig()

    def exec(self): return 1
    def deleteLater(self): pass
    def selected_items(self):
        from src.core.qr_reader.slot_assigner import AssignStatus
        return [i for i in self.plan.items if i.status is AssignStatus.APPLY
                or (i.status is AssignStatus.CONFLICT and i.cell in self.forced)]


class _RejectDialog(_AcceptDialog):
    def exec(self): return 0


@pytest.fixture
def patch_dialog(monkeypatch):
    def _use(cls):
        monkeypatch.setattr("src.ui.dialogs.batch_read_review_dialog.BatchReadReviewDialog", cls)
        return cls
    return _use


def test_full_frame_applies_to_loaded_sets(qapp, db_conn, patch_dialog):
    """스캔 즉시 적용 — 검토 창 없이 레코드 있는 칸에 QR 입력."""
    patch_dialog(_AcceptDialog)
    _AcceptDialog.last = None
    sets = [_set(p, f"P{p}") for p in range(1, 6)]     # Port 6 미로드
    host = _Host(db_conn, sets)
    host._on_reader_frame(parse_frame(FULL_RAW.read_bytes()))
    assert _AcceptDialog.last is None                   # 검토 창은 열리지 않음
    assert host.btn_read_review.isEnabled()             # '판독 검토' 버튼 활성

    matched = [s for ms in sets for s in ms.slots if s.qr_id]
    assert len(matched) == 58                           # 70 판독 − Port6 12칸(제외)
    assert sets[0].slots[0].qr_id == "2680002971"
    assert sets[1].slots[0].qr_id is None and sets[1].slots[1].qr_id is None   # 셀 13·14 NG 유지
    assert sets[1].slots[2].qr_id == "2680086CB6"
    assert len(host.saved) == 5 and all(ms.db_id for ms in sets)
    assert sum(len(r["grid"].updated) for r in host._folder_tabs) == 58
    assert host.refreshed == ["labels", "pool", "progress"]   # 폴더 뷰 기준 진행률이 마지막
    assert any(k == "ok" and "58칸 매칭" in m for k, m in host.logger.lines)
    assert any("적용 제외 — NG 2, 제외 12" in m for _, m in host.logger.lines)


def test_no_record_does_not_block_auto_apply(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1", slots=range(1, 12))]          # Slot 12 레코드 없음
    host = _Host(db_conn, sets)
    host._on_reader_frame(_frame([f"C{i}" for i in range(12)]))
    assert sum(1 for s in sets[0].slots if s.qr_id) == 11
    assert any("레코드 없음 1" in m for _, m in host.logger.lines)


def test_review_dialog_opens_from_button_with_layout(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1")]
    host = _Host(db_conn, sets)
    host._open_read_review()                            # 스캔 전
    assert host.logger.lines[-1][0] == "warn" and "먼저 다중 QR 스캔" in host.logger.lines[-1][1]

    host._on_reader_frame(_frame(["A", "B"]))
    _AcceptDialog.last = None
    host._open_read_review()
    dlg = _AcceptDialog.last
    assert dlg is not None and dlg.layout is not None and dlg.layout.rotation == 270 and dlg.layout.schematic
    assert [it.status.name for it in dlg.plan.items[:2]] == ["SAME", "SAME"]   # 이미 적용된 칸은 동일로 표시


def test_review_dialog_cancel_changes_nothing(qapp, db_conn, patch_dialog):
    patch_dialog(_RejectDialog)
    sets = [_set(1, "P1")]
    host = _Host(db_conn, sets)
    host._last_frame = _frame(["A", "B"])
    host._open_read_review()
    assert all(s.qr_id is None for s in sets[0].slots)
    assert host.saved == [] and host.refreshed == []
    assert host.logger.lines[-1][1].startswith("판독 검토 닫음")


def test_no_loaded_folder_warns(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    host = _Host(db_conn, [])
    host._on_reader_frame(_frame(["A"]))
    assert host.logger.lines[-1][0] == "warn" and "폴더" in host.logger.lines[-1][1]


def test_forced_conflict_overwrites_and_logs(qapp, db_conn, patch_dialog):
    cls = patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1")]
    sets[0].slots[0].qr_id = "OLD"
    host = _Host(db_conn, sets)
    orig_init = cls.__init__

    def init_forced(self, *a, **k):
        orig_init(self, *a, **k)
        self.forced = {1}
    cls.__init__ = init_forced
    host._on_reader_frame(_frame(["NEW", "B"]))         # 즉시 적용: B 만, 충돌 칸은 유지
    assert sets[0].slots[0].qr_id == "OLD" and sets[0].slots[1].qr_id == "B"
    assert any("충돌 1" in m for _, m in host.logger.lines)
    host._open_read_review()                            # 검토 창에서 덮어쓰기 선택 → 적용
    cls.__init__ = orig_init
    assert sets[0].slots[0].qr_id == "NEW" and sets[0].slots[1].qr_id == "B"
    assert any(k == "warn" and "덮어쓰기" in m and "OLD" in m for k, m in host.logger.lines)
    assert any("덮어쓰기 1" in m for _, m in host.logger.lines)


def test_same_port_in_two_folders_uses_tab_order(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1"), _set(1, "P2")]
    host = _Host(db_conn, sets)
    host._on_reader_frame(_frame(["A"]))
    assert sets[0].slots[0].qr_id == "A" and sets[1].slots[0].qr_id is None
    assert any(k == "warn" and "같은 Port 폴더 중복" in m for k, m in host.logger.lines)


def test_multiple_atx_loaded_blocks_scan(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "PO-ATX1", atx=1), _set(1, "PO-ATX2", atx=2)]
    host = _Host(db_conn, sets)
    host._on_reader_frame(_frame(["Z1"]))
    assert host.logger.lines[-1][0] == "error" and "ATX 1, 2" in host.logger.lines[-1][1]
    assert all(s.qr_id is None for ms in sets for s in ms.slots)
    assert host.saved == []


def test_single_atx_is_passed_to_build_plan(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "PO-ATX2", atx=2)]
    host = _Host(db_conn, sets)
    host._on_reader_frame(_frame(["Z1"]))
    assert sets[0].slots[0].qr_id == "Z1"


def test_dup_in_shadowed_folder_blocks_cell(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1"), _set(1, "P2")]
    sets[1].slots[3].qr_id = "DUPCODE"                # 탭 2(선택되지 않음)에 이미 있음
    host = _Host(db_conn, sets)
    host._on_reader_frame(_frame(["DUPCODE", "OK1"]))
    assert sets[0].slots[0].qr_id is None and sets[0].slots[1].qr_id == "OK1"


def test_progress_refresh_order_folder_view_vs_pool(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1")]
    host = _Host(db_conn, sets)
    host._atx_pool_active = lambda: False
    host._on_reader_frame(_frame(["A"]))
    assert host.refreshed == ["labels", "pool", "progress"]      # 폴더 뷰: 마지막에 폴더 기준 진행률
    host.refreshed.clear()
    host._atx_pool_active = lambda: True
    host._on_reader_frame(_frame([None, "B"]))
    assert host.refreshed == ["labels", "pool"]                  # Pool 뷰: Pool 진행률 유지


def test_invalid_override_from_settings_reports_error(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    save_qr_reader_settings(db_conn, {"cell_override": {1: (1, 1), 2: (1, 1)}})
    sets = [_set(1, "P1")]
    host = _Host(db_conn, sets)
    host._on_reader_frame(_frame(["A", "B"]))
    assert host.logger.lines[-1][0] == "error" and "override" in host.logger.lines[-1][1]
    assert all(s.qr_id is None for s in sets[0].slots)


def test_db_failure_keeps_screen_data(qapp, db_conn, patch_dialog):
    patch_dialog(_AcceptDialog)
    sets = [_set(1, "P1")]
    host = _Host(db_conn, sets)
    def boom(ms=None): raise RuntimeError("disk")
    host._auto_save_to_db = boom
    host._on_reader_frame(_frame(["A"]))
    assert sets[0].slots[0].qr_id == "A"
    assert any(k == "error" and "DB 저장 실패" in m for k, m in host.logger.lines)
