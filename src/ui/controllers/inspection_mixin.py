"""Inspection 워크플로우 — MTC 런 폴더 열기 → 자동 판정(QThread) → 결과표/상세 →
템플릿 편집·저장(Spec Limits 동기화) → 로트 생성(ATX 탭 자동 오픈).

상태
----
- ``_insp_run``       : MtcRun (없으면 None)
- ``_insp_verdicts``  : list[SlotVerdict] (표 순서 = 런 슬롯 순서)
- ``_insp_ref``       : 기준 MtcSlot, ``_insp_ref_tip`` : 기준 팁 측정(TipMeasure)
- ``_insp_templates`` : {tip_id: template}, ``_insp_current_tip``
- ``_insp_grouped``   : {code: unit_no} — 이미 로트로 내보낸 슬롯(재사용 방지)
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from src.core.inspection.grading import formula_text, grade_counts, grade_run, regrade
from src.core.inspection.lot_builder import (
    CheckSheetSpec,
    build_lots,
    default_batch,
    plan_lot_sizes,
    validate_plan,
    write_report_csv,
)
from src.core.inspection.mtc_parser import MtcSlot, is_mtc_run_folder, load_mtc_run
from src.core.inspection.reference import auto_reference
from src.core.inspection.sweep_shape import read_sweep_txt
from src.core.inspection.templates import (
    ALL_GRADE_KEYS,
    GRADE_NAMES,
    ITEM_BY_KEY,
    clone_template,
    default_template,
    get_grade,
    get_item,
    industrial_spec_limits,
    model_name_of,
    normalize_template,
)
from src.core.inspection.vision_check import measure_tip
from src.ui.dialogs.image_popup_dialog import ImagePopupDialog
from src.ui.dialogs.inspection_template_dialog import NewTemplateDialog

LAST_TIP_KEY = "inspection_last_tip"
LOT_DIR_KEY = "inspection_lot_dir"
LAST_BATCH_KEY = "inspection_last_batch"
SPLITTERS_KEY = "inspection_splitters"
DEFAULT_TIP = "AC160"


class InspectionWorker(QThread):
    """런 전체 판정을 워커 스레드에서 실행(SKILL 13). 결과는 시그널로 메인 스레드에 전달."""

    progress = Signal(int, int)
    finished_ok = Signal(object)   # list[SlotVerdict]
    failed = Signal(str)

    def __init__(self, run, template: dict, ref: MtcSlot | None, parent=None):
        super().__init__(parent)
        self._run, self._template, self._ref = run, template, ref

    def run(self) -> None:
        try:
            verdicts = grade_run(self._run, self._template, self._ref, progress=self.progress.emit)
        except Exception as e:  # noqa: BLE001 — 워커 예외는 UI 로 전달
            self.failed.emit(str(e))
            return
        self.finished_ok.emit(verdicts)


def _f(v, nd: int = 2) -> str:
    if v is None:
        return "-"
    return f"{v:.{nd}f}"


class InspectionMixin:
    # ─── 초기화 ───

    def _init_inspection_state(self):
        self._insp_run = None
        self._insp_verdicts = []
        self._insp_ref: MtcSlot | None = None
        self._insp_ref_tip = None
        self._insp_worker: InspectionWorker | None = None
        self._insp_selected: str | None = None
        self._insp_show_zoom = False
        self._insp_grouped: dict[str, str] = {}
        self._insp_overrides: dict[str, tuple[str | None, bool | None]] = {}
        self._insp_explorers: list = []   # 열려 있는 Sweep Explorer 창들(비모달)
        self._insp_layout_win = None      # 레이아웃 보기 창(비모달, 1개)

        self._insp_templates = self._load_inspection_templates()
        if not self._insp_templates:
            self._insp_templates = {DEFAULT_TIP: default_template(DEFAULT_TIP)}
        from src.core.database import load_setting
        last = load_setting(self._db_conn, LAST_TIP_KEY, None)
        self._insp_current_tip = last if last in self._insp_templates else next(iter(self._insp_templates))
        lot_dir = load_setting(self._db_conn, LOT_DIR_KEY, "")
        self._insp_last_batch = load_setting(self._db_conn, LAST_BATCH_KEY, "") or ""

        p = self.inspection_page
        p.btn_open.clicked.connect(self._insp_open)
        p.btn_run.clicked.connect(self._insp_run_grading)
        p.btn_run_top.clicked.connect(self._insp_run_grading)
        p.btn_save.clicked.connect(self._insp_save_report)
        p.row_selected.connect(self._insp_on_row)
        p.context_requested.connect(self._insp_context_menu)
        for chk in p.chk_grade.values():
            chk.toggled.connect(lambda _c: self._insp_refresh_table())
        p.fail_combo.currentIndexChanged.connect(lambda _i: self._insp_update_formula())
        p.tip_combo.currentTextChanged.connect(self._insp_on_tip_changed)
        p.btn_new_tpl.clicked.connect(self._insp_new_template)
        p.btn_del_tpl.clicked.connect(self._insp_delete_template)
        p.btn_save_tpl.clicked.connect(self._insp_save_template)
        p.btn_vision_toggle.toggled.connect(lambda _c: self._insp_show_detail())
        p.btn_set_ref.clicked.connect(lambda: self._insp_set_reference(self._insp_selected))
        p.btn_grp_change.clicked.connect(self._insp_choose_lot_dir)
        p.btn_sheet_browse.clicked.connect(self._insp_choose_sheet_template)
        p.grp_grade_combo.currentIndexChanged.connect(lambda _i: self._insp_update_grouping())
        for sp in p.grp_spin.values():
            sp.valueChanged.connect(lambda _v: self._insp_update_grouping())
        p.grp_unit_edit.textChanged.connect(lambda _t: self._insp_update_grouping())
        p.btn_grp_run.clicked.connect(self._insp_build_lots)
        p.btn_zoom_in.clicked.connect(lambda: self._insp_set_zoom(False))
        p.btn_zoom_out.clicked.connect(lambda: self._insp_set_zoom(True))
        for viewer in (p.vision_viewer, p.sweep_viewer, p.zoom_viewer):
            viewer.double_clicked.connect(self._insp_popup_image)
        p.chart.double_clicked.connect(self._insp_open_explorer)
        p.btn_layout.clicked.connect(self._insp_open_layout)

        p.grp_path_edit.setText(lot_dir or "")
        p.apply_splitter_sizes(load_setting(self._db_conn, SPLITTERS_KEY, None))
        p.set_template_names(sorted(self._insp_templates), self._insp_current_tip)
        p.template_to_form(self._insp_templates[self._insp_current_tip])
        p.clear_detail()
        p.set_reference(None, {})
        self._insp_update_grouping()

    def _shutdown_inspection(self):
        try:
            from src.core.database import save_setting
            save_setting(self._db_conn, SPLITTERS_KEY, self.inspection_page.splitter_sizes())
        except Exception:
            pass
        w = self._insp_worker
        if w is not None and w.isRunning():
            w.wait(3000)
        for win in list(self._insp_explorers):
            win.close()
        if self._insp_layout_win is not None:
            self._insp_layout_win.close()

    # ─── 템플릿 ───

    def _insp_current_template(self) -> dict:
        """폼 값을 정규화한 템플릿(저장 여부와 무관)."""
        raw = self.inspection_page.form_to_template(self._insp_current_tip)
        return normalize_template(raw) or default_template(self._insp_current_tip)

    def _insp_on_tip_changed(self, tip: str):
        if not tip or tip == self._insp_current_tip or tip not in self._insp_templates:
            return
        # 편집 중이던 폼은 메모리에만 보관(저장은 Save)
        self._insp_templates[self._insp_current_tip] = self._insp_current_template()
        self._insp_current_tip = tip
        self.inspection_page.template_to_form(self._insp_templates[tip])
        from src.core.database import save_setting
        save_setting(self._db_conn, LAST_TIP_KEY, tip)
        self._insp_update_batch_default()

    def _insp_new_template(self):
        suggestions = list(self._load_tip_catalog())
        try:
            from src.core.database import get_probe_type_list
            suggestions += [t for t in get_probe_type_list(self._db_conn) if t]
        except Exception:
            pass
        dlg = NewTemplateDialog(sorted(self._insp_templates), self, sorted(set(suggestions)))
        if dlg.exec() != dlg.DialogCode.Accepted or dlg.result_template() is None:
            return
        tip, source = dlg.result_template()
        self._insp_templates[self._insp_current_tip] = self._insp_current_template()
        base = self._insp_templates.get(source) if source else None
        self._insp_templates[tip] = clone_template(base, tip) if base else default_template(tip)
        self._insp_current_tip = tip
        self._save_inspection_templates(self._insp_templates)
        p = self.inspection_page
        p.set_template_names(sorted(self._insp_templates), tip)
        p.template_to_form(self._insp_templates[tip])
        self.logger.ok(f"검사 템플릿 추가: {tip}" + (f" (복사: {source})" if source else ""))
        self._insp_update_batch_default()

    def _insp_delete_template(self):
        tip = self._insp_current_tip
        if QMessageBox.question(self, "템플릿 삭제", f"'{tip}' 템플릿을 삭제할까요?") != QMessageBox.Yes:
            return
        self._insp_templates.pop(tip, None)
        if not self._insp_templates:
            self._insp_templates[DEFAULT_TIP] = default_template(DEFAULT_TIP)
        self._insp_current_tip = next(iter(sorted(self._insp_templates)))
        self._save_inspection_templates(self._insp_templates)
        p = self.inspection_page
        p.set_template_names(sorted(self._insp_templates), self._insp_current_tip)
        p.template_to_form(self._insp_templates[self._insp_current_tip])
        self.logger.info(f"검사 템플릿 삭제: {tip}")

    def _insp_save_template(self):
        tpl = self._insp_current_template()
        self._insp_templates[self._insp_current_tip] = tpl
        self._save_inspection_templates(self._insp_templates)
        # 산업용 Frequency/Q → Spec Limits 동기화
        limits = self._load_spec_limits()
        spec = industrial_spec_limits(tpl)
        if spec:
            limits[tpl["tip_id"]] = spec
        else:
            limits.pop(tpl["tip_id"], None)
        self._save_spec_limits(limits)
        self.logger.ok(f"검사 템플릿 저장: {tpl['tip_id']} (Spec Limits 동기화: "
                       f"Freq {spec['freq_min'] if spec else '-'}~{spec['freq_max'] if spec else '-'}, "
                       f"Q {spec['q_min'] if spec else '-'}~{spec['q_max'] if spec else '-'})")
        self._statusbar.showMessage(f"템플릿 저장: {tpl['tip_id']}")
        if self._insp_verdicts:
            self._insp_regrade()

    # ─── 런 폴더 열기 / 판정 ───

    def _insp_open(self):
        start = self.inspection_page.path_edit.text() or ""
        folder = QFileDialog.getExistingDirectory(self, "MTC 런 폴더 선택 (예: 20260909)", start)
        if not folder:
            return
        if not is_mtc_run_folder(folder):
            QMessageBox.warning(self, "런 폴더 아님",
                                "PSPD.txt / FreqSweep.txt / Vision.txt 중 하나도 없습니다.")
            return
        self.logger.section("MTC Inspection")
        try:
            run = load_mtc_run(folder)
        except Exception as e:
            self.logger.error(f"런 폴더 파싱 실패: {e}")
            return
        if not run.slots:
            self.logger.warn(f"슬롯 데이터가 없습니다: {folder}")
            return
        self._insp_run = run
        self._insp_verdicts = []
        self._insp_grouped = {}
        self._insp_overrides = {}
        self._insp_selected = None
        self._insp_ref = auto_reference(run)
        self._insp_ref_tip = measure_tip(self._insp_ref.pickup_image) if (
            self._insp_ref and self._insp_ref.pickup_image) else None
        p = self.inspection_page
        p.path_edit.setText(folder)
        if not p.grp_path_edit.text():
            p.grp_path_edit.setText(str(Path(folder).parent))
        self._insp_update_batch_default(force=True)
        self.logger.info(f"런 {run.run_id}: {len(run.slots)}개 슬롯, 기준 = "
                         f"{run.cantilever_no(self._insp_ref) if self._insp_ref else '없음'}")
        self._insp_show_reference()
        self._insp_start_worker()

    def _insp_update_batch_default(self, force: bool = False):
        """Batch 기본값: 마지막으로 로트를 만들 때 쓴 값 → 없으면 `{tip소문자}({run})`."""
        p = self.inspection_page
        if self._insp_run is None:
            return
        if force or not p.grp_batch_edit.text():
            p.grp_batch_edit.setText(
                self._insp_last_batch or default_batch(self._insp_current_tip, self._insp_run.run_id))

    def _insp_choose_sheet_template(self):
        p = self.inspection_page
        path, _ = QFileDialog.getOpenFileName(self, "체크시트 템플릿 xlsx", p.sheet_edit.text() or "",
                                              "Excel (*.xlsx)")
        if path:
            p.sheet_edit.setText(path)

    def _insp_check_sheet_spec(self) -> CheckSheetSpec | None:
        """현재 템플릿의 체크시트 사양 + 슬롯별 체크 결과(산업용 기준)."""
        tpl = self._insp_current_template()
        template_path = tpl.get("check_sheet_template") or ""
        if not template_path:
            return None
        if not Path(template_path).exists():
            self.logger.warn(f"체크시트 템플릿을 찾을 수 없어 건너뜀: {template_path}")
            return None
        noise_min = (get_item(tpl, "industrial", "sweep_shape") or {}).get("min")
        checks: dict[str, dict[str, bool]] = {}
        for v in self._insp_verdicts:
            failed = {f.item for f in v.failed_items("industrial")}
            score = v.metrics.get("sweep_shape")
            checks[v.code] = {
                "a_plus_b": "a_plus_b" not in failed,
                "unipeak": bool(v.sweep.available and v.sweep.n_peaks == 1),
                "noise": bool(score is not None and (noise_min is None or score >= noise_min)),
                "frequency": "frequency" not in failed,
            }
        return CheckSheetSpec(template=template_path, model_name=model_name_of(tpl), checks_by_code=checks)

    def _insp_start_worker(self):
        if self._insp_run is None:
            return
        if self._insp_worker is not None and self._insp_worker.isRunning():
            return
        self._insp_set_busy(True)
        w = InspectionWorker(self._insp_run, self._insp_current_template(), self._insp_ref, self)
        w.progress.connect(lambda d, t: self._statusbar.showMessage(f"Inspection 판정 중… {d}/{t}"))
        w.finished_ok.connect(self._insp_on_graded)
        w.failed.connect(self._insp_on_failed)
        w.finished.connect(lambda: self._insp_set_busy(False))
        self._insp_worker = w
        w.start()

    def _insp_set_busy(self, busy: bool):
        p = self.inspection_page
        for b in (p.btn_open, p.btn_run, p.btn_run_top, p.btn_grp_run, p.btn_set_ref):
            b.setEnabled(not busy)

    def _insp_on_failed(self, msg: str):
        self.logger.error(f"Inspection 판정 실패: {msg}")
        self._statusbar.showMessage("Inspection 판정 실패")

    def _insp_on_graded(self, verdicts):
        self._insp_verdicts = list(verdicts)
        for v in self._insp_verdicts:
            ov = self._insp_overrides.get(v.code)
            if ov:
                v.override_grade, v.override_broken = ov
        counts = grade_counts(self._insp_verdicts)
        self.logger.ok("판정 완료: " + " · ".join(f"{GRADE_NAMES[k]} {counts.get(k, 0)}" for k in ALL_GRADE_KEYS))
        self._statusbar.showMessage(f"Inspection 판정 완료 ({len(self._insp_verdicts)} 슬롯)")
        self._insp_refresh_table()
        p = self.inspection_page
        target = self._insp_selected if self._insp_selected in p._codes else (p._codes[0] if p._codes else None)
        if target:
            p.select_code(target)
        else:
            p.clear_detail()
        self._insp_update_grouping()

    def _insp_run_grading(self):
        if self._insp_run is None:
            self._statusbar.showMessage("먼저 런 폴더를 여세요")
            return
        if self._insp_verdicts:
            self._insp_regrade()
        else:
            self._insp_start_worker()

    def _insp_regrade(self, recompute_vision: bool = False):
        """템플릿/기준만 바뀐 경우: sweep·vision 결과를 재사용해 즉시 재판정(override 유지)."""
        if not self._insp_verdicts:
            return
        tpl = self._insp_current_template()
        ref_tip = self._insp_ref_tip if recompute_vision else None
        self._insp_verdicts = regrade(self._insp_verdicts, tpl, self._insp_ref, ref_tip)
        counts = grade_counts(self._insp_verdicts)
        self.logger.info("재판정: " + " · ".join(f"{GRADE_NAMES[k]} {counts.get(k, 0)}" for k in ALL_GRADE_KEYS))
        self._insp_refresh_table()
        if self._insp_selected:
            self.inspection_page.select_code(self._insp_selected)
            self._insp_show_detail()
        self._insp_update_grouping()

    # ─── 결과표 ───

    def _insp_refresh_table(self):
        p = self.inspection_page
        if self._insp_run is None:
            p.set_rows([])
            p.lbl_total.setText("Total: 0")
            p.lbl_counts.setText("")
            return
        allowed = p.grade_filter()
        rows = []
        for v in self._insp_verdicts:
            if v.grade not in allowed:
                continue
            err = v.error_label
            lot = self._insp_grouped.get(v.code)
            if lot:
                err = (err + "  " if err else "") + f"→ {lot}"
            rows.append({
                "code": v.code, "atx": v.slot.atx, "port": v.slot.port, "slot": v.slot.slot,
                "grade": v.grade, "grade_name": v.grade_name, "error": err,
                "no": self._insp_run.cantilever_no(v.slot), "override": v.is_override,
            })
        p.set_rows(rows)
        counts = grade_counts(self._insp_verdicts)
        p.lbl_total.setText(f"Total: {len(rows)}")
        p.lbl_counts.setText(" · ".join(f"{GRADE_NAMES[k]} {counts.get(k, 0)}" for k in ALL_GRADE_KEYS))
        self._insp_refresh_layout()

    def _insp_verdict(self, code: str | None):
        if not code:
            return None
        for v in self._insp_verdicts:
            if v.code == code:
                return v
        return None

    def _insp_on_row(self, code: str):
        self._insp_selected = code
        self._insp_show_detail()
        if self._insp_layout_win is not None:
            self._insp_layout_win.select(code)

    # ─── 레이아웃 보기 (비모달 창) ───

    def _insp_open_layout(self):
        if self._insp_layout_win is None:
            from src.ui.widgets.inspection_layout_window import InspectionLayoutWindow
            win = InspectionLayoutWindow(self)
            win.cell_clicked.connect(self._insp_layout_cell_clicked)
            win.cell_double_clicked.connect(self._insp_layout_cell_double_clicked)
            win.cell_context_requested.connect(self._insp_context_menu)
            win.mode_combo.currentIndexChanged.connect(lambda _i: self._insp_refresh_layout())
            win.closed.connect(self._insp_layout_closed)
            self._insp_layout_win = win
        self._insp_refresh_layout()
        self._insp_layout_win.select(self._insp_selected)
        self._insp_layout_win.show()
        self._insp_layout_win.raise_()
        self._insp_layout_win.activateWindow()

    def _insp_layout_closed(self, _win):
        self._insp_layout_win = None

    def _insp_refresh_layout(self):
        win = self._insp_layout_win
        if win is None:
            return
        win.update_view(self._insp_run, self._insp_verdicts,
                        self._insp_ref.code if self._insp_ref else None,
                        self._insp_grouped, self.inspection_page.grade_filter())

    def _insp_layout_cell_clicked(self, code: str):
        # 표 행 선택 → row_selected → _insp_on_row (상세 갱신 + 레이아웃 선택 표시)
        p = self.inspection_page
        if code in p._codes:
            p.select_code(code)
        else:
            # 필터로 표에 없는 슬롯: 상세만 갱신
            self._insp_on_row(code)

    def _insp_layout_cell_double_clicked(self, code: str):
        self._insp_layout_cell_clicked(code)
        self._insp_open_explorer()

    # ─── 상세 ───

    def _insp_show_reference(self):
        ref = self._insp_ref
        if ref is None or self._insp_run is None:
            self.inspection_page.set_reference(None, {})
            return
        self.inspection_page.set_reference(self._insp_run.cantilever_no(ref), {
            "tip_x": ref.tip_x, "tip_y": ref.tip_y, "angle": ref.angle,
            "a_plus_b": ref.a_plus_b, "a_minus_b": ref.a_minus_b, "c_minus_d": ref.c_minus_d,
        })

    def _insp_show_detail(self):
        p = self.inspection_page
        v = self._insp_verdict(self._insp_selected)
        if v is None:
            p.clear_detail()
            return
        s, m = v.slot, v.metrics
        # 이미지
        img = s.putback_image if p.btn_vision_toggle.isChecked() else s.pickup_image
        p.vision_viewer.load_image(img)
        p.set_path_label(p.lbl_vision_path, img)
        p.sweep_viewer.load_image(s.sweep_image)
        p.set_path_label(p.lbl_sweep_path, s.sweep_image,
                         f"…/TipExchanger{s.atx}/Port{s.port}_{s.slot}.jpg does not exist")
        p.zoom_viewer.load_image(s.zoom_image)
        p.set_path_label(p.lbl_zoom_path, s.zoom_image,
                         f"…/TipExchanger{s.atx}/Port{s.port}_{s.slot}_ZoomOut.jpg does not exist")
        # Info
        p.set_info(
            [_f(s.tip_x, 3), _f(s.tip_y, 3), _f(m.get("x_offset_um"), 3), _f(m.get("y_offset_um"), 3),
             _f(s.frequency, 2), _f(m.get("sweep_shape"), 0)],
            [_f(s.set_point), _f(s.drive), _f(s.q), _f(s.a_plus_b), _f(s.a_minus_b), _f(s.c_minus_d),
             _f(s.angle, 3), _f(s.match_score)],
        )
        vis = v.vision.summary() if v.vision else "-"
        if v.override_broken is not None:
            vis += "  (수동: " + ("파손" if v.override_broken else "정상") + ")"
        p.lbl_vision_verdict.setText(f"Vision: {vis}   ·   Sweep: {v.sweep.summary()}")
        # Fail items (산업용 기준)
        p.fail_combo.blockSignals(True)
        p.fail_combo.clear()
        for f in v.failed_items("industrial"):
            p.fail_combo.addItem(f.label, f.item)
        p.fail_combo.blockSignals(False)
        self._insp_update_formula()
        # 차트
        self._insp_draw_chart(v)
        self._insp_sync_explorers(v)

    def _insp_update_formula(self):
        p = self.inspection_page
        v = self._insp_verdict(self._insp_selected)
        item = p.fail_combo.currentData()
        if v is None or not item:
            p.lbl_formula.setText("-" if v is None else "산업용 통과")
            return
        spec = get_item(self._insp_current_template(), "industrial", item)
        p.lbl_formula.setText(formula_text(item, spec, v.metrics))

    def _insp_set_zoom(self, zoomed_out: bool):
        self._insp_show_zoom = zoomed_out
        p = self.inspection_page
        p.btn_zoom_in.setChecked(not zoomed_out)
        p.btn_zoom_out.setChecked(zoomed_out)
        v = self._insp_verdict(self._insp_selected)
        if v is not None:
            self._insp_draw_chart(v)

    def _insp_draw_chart(self, v):
        s = v.slot
        path = s.zoom_txt if self._insp_show_zoom else s.sweep_txt
        freqs, amps = read_sweep_txt(path)
        self.inspection_page.chart.show(v.sweep, freqs, amps, s.set_point, zoomed_out=self._insp_show_zoom)

    def _insp_open_explorer(self):
        """sweep 판정 차트 더블클릭 → 비모달 Sweep Explorer 창(pyqtgraph)."""
        v = self._insp_verdict(self._insp_selected)
        if v is None or self._insp_run is None:
            return
        try:
            from src.ui.widgets.sweep_explorer_window import SweepExplorerWindow
        except ImportError as e:
            self.logger.error(f"Sweep Explorer 를 열 수 없습니다 (pyqtgraph 필요): {e}")
            return
        win = SweepExplorerWindow(self)
        win.closed.connect(lambda w: self._insp_explorers.remove(w) if w in self._insp_explorers else None)
        self._insp_explorers.append(win)
        win.show_slot(v, self._insp_run, self._insp_ref)
        win.show()
        win.raise_()

    def _insp_sync_explorers(self, v):
        """메인 표 선택이 바뀌면 '따라가기' 가 켜진 Explorer 창을 갱신."""
        for win in self._insp_explorers:
            if win.chk_follow.isChecked() and win.slot_code != v.code:
                win.show_slot(v, self._insp_run, self._insp_ref)

    def _insp_popup_image(self, path: str):
        """이미지 뷰어 더블클릭 → 원본 크기(화면 90% 이내) 확대 창."""
        if not path or not Path(path).exists():
            return
        dlg = ImagePopupDialog(path, self)
        dlg.exec()

    # ─── 기준 / override (우클릭) ───

    def _insp_set_reference(self, code: str | None):
        v = self._insp_verdict(code)
        if v is None or self._insp_run is None:
            return
        if not v.slot.has_sweep or not v.slot.has_vision:
            QMessageBox.warning(self, "기준 불가", "sweep 과 Vision 값이 모두 있는 슬롯만 기준으로 지정할 수 있습니다.")
            return
        self._insp_ref = v.slot
        self._insp_ref_tip = measure_tip(v.slot.pickup_image) if v.slot.pickup_image else None
        self.logger.info(f"기준 캔틸레버 변경: {self._insp_run.cantilever_no(v.slot)}")
        self._insp_show_reference()
        self._insp_regrade(recompute_vision=True)

    def _insp_context_menu(self, code: str, global_pos):
        v = self._insp_verdict(code)
        if v is None:
            return
        menu = QMenu(self)
        sub = menu.addMenu("등급 수동 변경")
        for key in ALL_GRADE_KEYS:
            act = sub.addAction(GRADE_NAMES[key])
            act.setCheckable(True)
            act.setChecked(v.override_grade == key)
            act.triggered.connect(lambda _c=False, k=key: self._insp_override(code, grade=k))
        sub.addSeparator()
        sub.addAction("자동 판정으로 되돌리기").triggered.connect(
            lambda: self._insp_override(code, grade=None, reset=True))
        act_b = menu.addAction("파손 해제 (정상으로)" if v.broken else "파손 표시")
        act_b.triggered.connect(lambda: self._insp_override(code, broken=not v.broken))
        menu.addSeparator()
        menu.addAction("기준 캔틸레버로 지정").triggered.connect(lambda: self._insp_set_reference(code))
        menu.addAction("폴더 열기").triggered.connect(lambda: self._insp_open_folder(v.slot))
        menu.exec(global_pos)

    def _insp_override(self, code: str, grade: str | None = None, broken: bool | None = None,
                       reset: bool = False):
        v = self._insp_verdict(code)
        if v is None:
            return
        if reset:
            v.override_grade, v.override_broken = None, None
        else:
            if grade is not None:
                v.override_grade = grade
            if broken is not None:
                v.override_broken = broken
        self._insp_overrides[code] = (v.override_grade, v.override_broken)
        self.logger.info(f"{code}: 수동 지정 → {v.grade_name}" + (" / 파손" if v.broken else ""))
        self._insp_refresh_table()
        self.inspection_page.select_code(code)
        self._insp_show_detail()
        self._insp_update_grouping()

    def _insp_open_folder(self, slot: MtcSlot):
        target = slot.sweep_image or slot.pickup_image or (self._insp_run.folder if self._insp_run else None)
        if not target:
            return
        try:
            os.startfile(str(Path(target).parent))  # type: ignore[attr-defined]
        except Exception as e:
            self.logger.warn(f"폴더 열기 실패: {e}")

    # ─── 리포트 ───

    def _insp_save_report(self):
        if self._insp_run is None or not self._insp_verdicts:
            self._statusbar.showMessage("저장할 판정 결과가 없습니다")
            return
        default = str(Path(self._insp_run.folder) / f"Inspection_{self._insp_run.run_id}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "검사 리포트 저장", default, "CSV (*.csv)")
        if not path:
            return
        try:
            write_report_csv(path, self._insp_run, self._insp_verdicts,
                             self._insp_ref.code if self._insp_ref else None, self._insp_current_tip)
        except Exception as e:
            self.logger.error(f"리포트 저장 실패: {e}")
            return
        self.logger.ok(f"검사 리포트 저장: {path}")
        self._statusbar.showMessage(f"리포트 저장: {path}")

    # ─── Grouping ───

    def _insp_available_slots(self) -> list[MtcSlot]:
        grade = self.inspection_page.grp_grade_combo.currentData()
        return [v.slot for v in self._insp_verdicts
                if v.grade == grade and v.code not in self._insp_grouped]

    def _insp_update_grouping(self):
        p = self.inspection_page
        avail = self._insp_available_slots()
        sizes = plan_lot_sizes(p.lot_counts())
        p.lbl_grp_available.setText(str(len(avail)))
        p.lbl_remain.setText(str(len(avail) - sum(sizes)))
        err = validate_plan(sizes, len(avail)) if avail else "통과 슬롯 없음"
        if not err and not p.grp_unit_edit.text().strip():
            err = "Unit No 필요"
        if not err and not p.grp_path_edit.text().strip():
            err = "출력 경로 필요"
        if self._insp_run is None:
            p.set_grouping_status("", None)
            p.btn_grp_run.setEnabled(False)
        elif err:
            p.set_grouping_status("INVALID", False)
            p.btn_grp_run.setEnabled(False)
            p.lbl_grp_status.setToolTip(err)
        else:
            p.set_grouping_status("OK", True)
            p.btn_grp_run.setEnabled(True)
            p.lbl_grp_status.setToolTip("")

    def _insp_choose_lot_dir(self):
        p = self.inspection_page
        d = QFileDialog.getExistingDirectory(self, "로트 폴더 출력 위치", p.grp_path_edit.text() or "")
        if not d:
            return
        p.grp_path_edit.setText(d)
        from src.core.database import save_setting
        save_setting(self._db_conn, LOT_DIR_KEY, d)
        self._insp_update_grouping()

    def _insp_build_lots(self):
        p = self.inspection_page
        if self._insp_run is None:
            return
        avail = self._insp_available_slots()
        sizes = plan_lot_sizes(p.lot_counts())
        unit_no = p.grp_unit_edit.text().strip()
        out_dir = p.grp_path_edit.text().strip()
        batch = p.grp_batch_edit.text().strip() or default_batch(self._insp_current_tip, self._insp_run.run_id)
        err = validate_plan(sizes, len(avail))
        if err or not unit_no or not out_dir:
            QMessageBox.warning(self, "Grouping", err or "Unit No / 출력 경로를 입력하세요.")
            return
        grade_name = p.grp_grade_combo.currentText()
        if QMessageBox.question(
            self, "로트 생성",
            f"{grade_name} {len(avail)}개 중 {sum(sizes)}개를 {len(sizes)}개 로트"
            f"({' / '.join(f'{s}M' for s in sizes)})로 만듭니다.\n"
            f"시작 Unit No: {unit_no}\n출력: {out_dir}\n\n계속할까요?",
        ) != QMessageBox.Yes:
            return
        try:
            lots, _remaining = build_lots(out_dir, avail, sizes, unit_no, self._insp_current_tip, batch,
                                          self._insp_check_sheet_spec())
        except Exception as e:
            self.logger.error(f"로트 생성 실패: {e}")
            QMessageBox.critical(self, "로트 생성 실패", str(e))
            return
        self.logger.section("로트 생성")
        from src.core.database import save_setting
        self._insp_last_batch = batch
        save_setting(self._db_conn, LAST_BATCH_KEY, batch)
        for lot in lots:
            for code in lot.codes:
                self._insp_grouped[code] = lot.unit_no
            self.logger.ok(f"{Path(lot.folder).name}: {len(lot.codes)}개 → {lot.folder}"
                           + (f" (+ 체크시트 {Path(lot.check_sheet).name})" if lot.check_sheet else ""))
            ms = lot.measurement_set
            if ms is not None:
                ms.production_date = self.date_edit.date().toString("yyyyMMdd")
                self._atx_open_set_in_tab(ms, lot.folder)
                self._add_recent_folder(lot.folder)
        # 다음 로트 Unit No 미리 채움
        from src.core.inspection.lot_builder import next_unit_no
        nxt = unit_no
        for _ in lots:
            nxt = next_unit_no(nxt)
        p.grp_unit_edit.setText(nxt)
        for sp in p.grp_spin.values():
            sp.setValue(0)
        self._insp_refresh_table()
        self._insp_update_grouping()
        self._statusbar.showMessage(f"로트 {len(lots)}개 생성 → ATX 모드 탭으로 열었습니다")
        self._switch_mode("atx")
