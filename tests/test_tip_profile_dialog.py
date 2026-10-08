"""Tip 관리 다이얼로그 — 목록 합집합, 추가/삭제, 레이아웃 전환, 결과 정규화, 찾아보기는 경로만 보관."""
from __future__ import annotations

import pytest
from PIL import Image

from src.ui.dialogs import tip_profile_dialog as mod
from src.ui.dialogs.tip_profile_dialog import TipProfileDialog


@pytest.fixture
def dlg(qapp):
    d = TipProfileDialog(
        ["AC160", "PPP-NCHR"],
        {"PPP-NCHR": {"display_name": "PPP-NCHR", "spec_layout": "nominal_range",
                      "spec_rows": [["Length / ㎛", "125", "115 ~ 135"]]},
         "OLD": {"display_name": "Old Tip"}},
        loaded_types=("AC160", "NEW160"),
    )
    yield d
    d.close()
    d.deleteLater()


def test_list_is_union_of_catalog_profiles_and_loaded(dlg):
    assert dlg.tip_names() == ["AC160", "PPP-NCHR", "OLD", "NEW160"]
    assert dlg.list.currentRow() == 0 and dlg.display_name.text() == "AC160"
    assert dlg.table.columnCount() == 4 and dlg.table.rowCount() == 5     # 기본 5행 min/typ/max


def test_selecting_profile_loads_its_layout_and_rows(dlg):
    dlg.list.setCurrentRow(1)
    assert dlg.layout_combo.currentData() == "nominal_range"
    assert dlg.table.columnCount() == 3 and dlg.table.rowCount() == 1
    assert dlg.table.item(0, 2).text() == "115 ~ 135"


def test_edits_persist_when_switching_rows_and_in_result(dlg):
    dlg.display_name.setText("AC160TS")
    dlg.table.item(0, 1).setText("145")
    dlg.list.setCurrentRow(1)
    dlg.list.setCurrentRow(0)
    assert dlg.display_name.text() == "AC160TS" and dlg.table.item(0, 1).text() == "145"
    out = dlg.result_profiles()
    assert out["AC160"]["display_name"] == "AC160TS"
    assert out["AC160"]["spec_rows"][0] == ["Length (um)", "145", "", ""]
    assert out["NEW160"]["display_name"] == "NEW160"                      # 미편집 Tip 은 기본 프로필
    assert dlg.result_catalog() == dlg.tip_names()


def test_add_and_remove_tip(dlg, monkeypatch):
    infos = []
    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: infos.append(a[2]))
    dlg.new_name.setText("  AC240 ")
    dlg.btn_add.click()
    assert dlg.tip_names()[-1] == "AC240" and dlg.list.currentRow() == 4
    dlg.new_name.setText("AC240")
    dlg.btn_add.click()
    assert len(infos) == 1 and "이미" in infos[0]

    dlg.list.setCurrentRow(2)             # OLD
    dlg.btn_remove.click()
    assert "OLD" not in dlg.tip_names() and "OLD" not in dlg.result_profiles()


def test_layout_switch_reshapes_columns_keeping_values(dlg):
    dlg.table.item(0, 1).setText("145")
    dlg.table.item(0, 2).setText("160")
    dlg.layout_combo.setCurrentIndex(1)
    assert dlg.table.columnCount() == 3
    assert [dlg.table.item(0, c).text() for c in range(3)] == ["Length (um)", "145", "160"]
    dlg.layout_combo.setCurrentIndex(0)
    assert dlg.table.columnCount() == 4 and dlg.table.item(0, 3).text() == ""


def test_row_add_delete_move(dlg):
    n = dlg.table.rowCount()
    dlg.btn_row_add.click()
    assert dlg.table.rowCount() == n + 1
    dlg.table.setCurrentCell(n, 0)
    dlg.table.item(n, 0).setText("Extra")
    dlg.btn_row_up.click()
    assert dlg.table.item(n - 1, 0).text() == "Extra" and dlg.table.currentRow() == n - 1
    dlg.btn_row_down.click()
    assert dlg.table.item(n, 0).text() == "Extra"
    dlg.btn_row_del.click()
    assert dlg.table.rowCount() == n


def test_browse_keeps_source_path_only_and_shows_thumbnail(dlg, tmp_path, monkeypatch):
    src = tmp_path / "sem.png"
    Image.new("RGB", (40, 30), "gray").save(src, "PNG")
    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), ""))
    dlg.btn_browse.click()
    assert dlg.sem_path.text() == str(src) and not dlg.thumb.pixmap().isNull()
    assert dlg.result_profiles()["AC160"]["sem_image"] == str(src)      # 복사는 호출자가 저장 시
    assert list(tmp_path.iterdir()) == [src]
    dlg.btn_clear_image.click()
    assert dlg.sem_path.text() == "" and dlg.thumb.text() == "미리보기 없음"


def test_empty_catalog_disables_form(qapp):
    d = TipProfileDialog([], {})
    assert not d.form_box.isEnabled() and d.result_profiles() == {}
    d.close()
