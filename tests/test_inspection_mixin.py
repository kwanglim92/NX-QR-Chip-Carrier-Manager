"""Inspection 믹스인 통합 테스트 — 실제 메인 윈도우(offscreen) + fixture 런 폴더.

파일 다이얼로그/확인 창은 monkeypatch 로 우회한다. 실 DB 보호: ``get_db_path`` 를 tmp 로 패치.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from src.core.inspection.templates import REJECT_KEY

pytest.importorskip("requests", reason="메인 윈도우는 requests(업로더)가 필요 — 필드 노트북 3.12 에는 없음")

FIXTURE = Path(__file__).parent / "fixtures" / "mtc" / "20260909"


@pytest.fixture
def app_window(qapp, tmp_path, monkeypatch):
    from src.core import database
    monkeypatch.setattr(database, "get_db_dir", lambda: tmp_path / "db")
    monkeypatch.setattr(database, "get_db_path", lambda: tmp_path / "db" / "chip_carrier.db")
    (tmp_path / "db").mkdir()
    # 리더기 자동 접속·업데이트 확인 등 외부 접촉 차단
    from src.ui.controllers import qr_reader_mixin
    monkeypatch.setattr(qr_reader_mixin.QRReaderMixin, "_init_qr_reader", lambda self: None, raising=False)
    monkeypatch.setattr(qr_reader_mixin.QRReaderMixin, "_shutdown_qr_reader", lambda self: None, raising=False)
    from src.ui.main_window import ChipCarrierManagerApp
    win = ChipCarrierManagerApp()
    yield win
    win._shutdown_inspection()
    win._db_conn.close()


def _open_fixture(win, qapp, monkeypatch):
    from src.ui.controllers import inspection_mixin as im
    monkeypatch.setattr(im.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(FIXTURE)))
    win._switch_mode("inspection")
    win._insp_open()
    assert win._insp_worker is not None
    assert win._insp_worker.wait(15000)
    qapp.processEvents()
    return win


def test_mode_button_and_page_index(app_window):
    win = app_window
    win._switch_mode("inspection")
    assert win.stack.currentWidget() is win.inspection_page
    assert win.current_mode == "inspection"
    assert not win._bottom_bar.isVisible()
    assert win.btn_inspection_mode.property("accent") == "true"


def test_open_run_grades_and_fills_table(app_window, qapp, monkeypatch):
    win = _open_fixture(app_window, qapp, monkeypatch)
    assert win._insp_run.run_id == "20260909"
    assert len(win._insp_verdicts) == 7
    assert win._insp_ref.code == "1101"
    p = win.inspection_page
    assert p.table.rowCount() == 7
    assert p.lbl_total.text() == "Total: 7"
    assert "산업용" in p.lbl_counts.text()
    assert p.ref_group.title() == "Reference Cantilever (20260909_1101)"
    assert p.ref_fields["tip_x"].text().startswith("1,209.42")
    # 첫 행 자동 선택 → 상세 채움
    assert win._insp_selected == "1101"
    assert p.info_table1.item(0, 0).text() == "1209.420"
    assert p.lbl_sweep_path.text().endswith("Port1_1.jpg")
    assert p.fail_combo.count() == 0 and p.lbl_formula.text() == "산업용 통과"
    # Grouping 기본값
    assert p.grp_batch_edit.text() == "ac160(20260909)"
    assert p.grp_path_edit.text() == str(FIXTURE.parent)


def test_filter_and_selection_detail(app_window, qapp, monkeypatch):
    win = _open_fixture(app_window, qapp, monkeypatch)
    p = win.inspection_page
    p.chk_grade["industrial"].setChecked(False)
    assert p.table.rowCount() < 7
    p.chk_grade["industrial"].setChecked(True)
    p.select_code("3212")
    qapp.processEvents()
    assert win._insp_selected == "3212"
    assert p.fail_combo.count() >= 2                # Q, Sweep Shape …
    assert "<" in p.lbl_formula.text()
    assert "Sweep: score" in p.lbl_vision_verdict.text()
    p.select_code("1111")
    qapp.processEvents()
    assert "does not exist" in p.lbl_sweep_path.text()
    # ZoomOut 전환
    win._insp_set_zoom(True)
    assert p.btn_zoom_out.isChecked() and not p.btn_zoom_in.isChecked()


def test_override_and_reference_change(app_window, qapp, monkeypatch):
    win = _open_fixture(app_window, qapp, monkeypatch)
    v = win._insp_verdict("1101")
    assert v.grade == "industrial"
    win._insp_override("1101", grade="research")
    assert win._insp_verdict("1101").grade == "research"
    assert win._insp_verdict("1101").is_override
    win._insp_override("1101", broken=True)
    assert win._insp_verdict("1101").broken
    win._insp_override("1101", reset=True)
    assert win._insp_verdict("1101").grade == "industrial"
    # 기준 변경 → 재판정(override 유지) + 기준 표시 갱신
    win._insp_override("1204", grade="recheck")
    win._insp_set_reference("1102")
    assert win._insp_ref.code == "1102"
    assert win.inspection_page.ref_group.title().endswith("(20260909_1102)")
    assert win._insp_verdict("1204").grade == "recheck"
    # 오프셋이 새 기준으로 재계산됨
    assert win._insp_verdict("1101").metrics["ref_tip_x"] == win._insp_ref.tip_x


def test_template_save_syncs_spec_limits_and_regrades(app_window, qapp, monkeypatch):
    win = _open_fixture(app_window, qapp, monkeypatch)
    p = win.inspection_page
    before = {v.code: v.grade for v in win._insp_verdicts}
    # 산업용 Q 상한을 300 으로 낮추면 1101(Q 422) 이 산업용에서 밀려난다
    rec = p.item_widgets["industrial"]["q"]
    rec["b"].setValue(300)
    win._insp_save_template()
    assert win._insp_verdict("1101").grade != "industrial"
    assert before["1101"] == "industrial"
    limits = win._load_spec_limits()
    assert limits["AC160"] == {"freq_min": 200.0, "freq_max": 400.0, "q_min": 200.0, "q_max": 300.0}
    saved = win._load_inspection_templates()
    assert saved["AC160"]["grades"][0]["items"]["q"]["max"] == 300.0


def test_new_and_delete_template(app_window, qapp, monkeypatch):
    win = app_window
    from src.ui.controllers import inspection_mixin as im

    class _FakeDlg:
        DialogCode = im.NewTemplateDialog.DialogCode

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return self.DialogCode.Accepted

        def result_template(self):
            return ("AC240", "AC160")

    monkeypatch.setattr(im, "NewTemplateDialog", _FakeDlg)
    win._insp_new_template()
    assert win._insp_current_tip == "AC240"
    assert set(win._load_inspection_templates()) == {"AC160", "AC240"}
    assert win.inspection_page.tip_combo.currentText() == "AC240"
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    win._insp_delete_template()
    assert set(win._insp_templates) == {"AC160"} and win._insp_current_tip == "AC160"


def test_grouping_validation_and_lot_build_opens_atx_tabs(app_window, qapp, monkeypatch, tmp_path):
    win = _open_fixture(app_window, qapp, monkeypatch)
    p = win.inspection_page
    # 산업용 통과 슬롯 수 만큼만 로트 가능
    avail = len(win._insp_available_slots())
    assert avail >= 1
    p.grp_unit_edit.setText("P2401002")
    p.grp_path_edit.setText(str(tmp_path / "lots"))
    (tmp_path / "lots").mkdir()
    p.grp_spin[12].setValue(1)
    win._insp_update_grouping()
    assert p.lbl_grp_status.text() == "INVALID" and not p.btn_grp_run.isEnabled()
    p.grp_spin[12].setValue(0)
    # 1개짜리 로트가 없으므로 5M 로트 1개를 만들려면 통과 5개 필요 → 연구용 포함해 수동 조정
    for code in [v.code for v in win._insp_verdicts if v.grade != "industrial"]:
        win._insp_override(code, grade="industrial")
    p.grp_spin[5].setValue(1)
    win._insp_update_grouping()
    assert p.lbl_grp_status.text() == "OK" and p.btn_grp_run.isEnabled()
    assert p.lbl_remain.text() == str(len(win._insp_available_slots()) - 5)

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    tabs_before = win.atx_view_tabs.count()
    win._insp_build_lots()
    lot_dir = tmp_path / "lots" / "P2401002_5M_AC160"
    assert (lot_dir / "Summary.csv").exists()
    assert win.atx_view_tabs.count() == tabs_before + 1
    assert win.current_mode == "atx"
    ms = win._folder_tabs[-1]["set"]
    assert ms.po_number == "P2401002" and ms.total_count == 5 and ms.db_id is not None
    assert p.grp_unit_edit.text() == "P2401003"
    assert len(win._insp_grouped) == 5
    # 내보낸 슬롯은 Grouping 대상에서 빠지고 표 Error 열에 로트 표시
    win._switch_mode("inspection")
    assert len(win._insp_available_slots()) == 7 - 5
    p.chk_grade[REJECT_KEY].setChecked(True)
    shown = [p.table.item(r, 4).text() for r in range(p.table.rowCount())]
    assert sum("→ P2401002" in t for t in shown) == 5


def test_save_report(app_window, qapp, monkeypatch, tmp_path):
    win = _open_fixture(app_window, qapp, monkeypatch)
    from src.ui.controllers import inspection_mixin as im
    out = tmp_path / "rep.csv"
    monkeypatch.setattr(im.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    win._insp_save_report()
    assert out.exists() and "20260909_1101" in out.read_text(encoding="utf-8-sig")
