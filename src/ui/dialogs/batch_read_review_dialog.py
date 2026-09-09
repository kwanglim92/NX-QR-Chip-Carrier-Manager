"""카세트 판독 검토 다이얼로그 (설계 §4·§5, 승인 목업 "카세트 판독 검토").

입력: ``AssignPlan`` (R2 ``build_plan`` 결과) + 로드된 세트 목록(패널 제목의 PO 표시용) + 스캔타임.
- 상단 요약 칩 / "이상 칸만 보기" / 범례
- 리더기 격자 순서대로 Port 패널(각 3열 × 4행 셀), 폴더 미로드 포트는 "자동 제외"로 흐리게
- 충돌 칸은 우클릭 → "덮어쓰기" 토글 (계획은 불변, 다이얼로그가 강제 적용 셀 집합을 따로 보관)
- 하단: 차단 사유 + [재판독][취소][적용 (n)]. 레코드 없음이 1칸이라도 있으면 적용 불가.

결과: ``selected_items()`` = APPLY 항목 + 덮어쓰기로 선택된 CONFLICT 항목. 실제 적용은 호출자(R6).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.models import MeasurementSet
from src.core.qr_reader.slot_assigner import SLOTS_PER_PORT, AssignItem, AssignPlan, AssignStatus
from src.core.slot_mapper import circled_number
from src.ui.theme import BG, BG2, BG3, BG4, FG, FG2, FG3, GREEN, ORANGE, RED, TEAL, YELLOW

# 상태 → (테두리 색, 굵기, 배지 배경, 배지 글자, 코드 색)
_STYLE: dict[AssignStatus, tuple[str, int, str, str, str]] = {
    AssignStatus.APPLY: (GREEN, 2, GREEN, "적용", GREEN),
    AssignStatus.NG: (BG3, 1, FG2, "NG", FG3),
    AssignStatus.SAME: (TEAL, 1, TEAL, "동일", TEAL),
    AssignStatus.CONFLICT: (RED, 2, RED, "충돌", RED),
    AssignStatus.DUP_FRAME: (ORANGE, 2, ORANGE, "중복", ORANGE),
    AssignStatus.DUP_LOADED: (ORANGE, 2, ORANGE, "중복", ORANGE),
    AssignStatus.NO_RECORD: (RED, 2, RED, "레코드없음", RED),
    AssignStatus.EXCLUDED: (BG3, 1, FG3, "제외", FG3),
}
_FORCED_STYLE = (YELLOW, 2, YELLOW, "덮어씀", YELLOW)
_DIMMED_STYLE = (BG3, 1, BG3, "", FG3)
# "이상 칸만 보기" 에서 흐리게 처리하는(확인이 필요 없는) 상태. 숨기지 않고 흐리게 해 격자 위치를 유지한다.
_NORMAL_STATUSES = {AssignStatus.APPLY, AssignStatus.SAME, AssignStatus.EXCLUDED}
_COLS = 3


class _CellCard(QFrame):
    force_toggled = Signal(int)   # cell

    def __init__(self, item: AssignItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self.forced = False
        self.dimmed = False
        self.setFixedHeight(58)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self._pos = QLabel(f"{item.cell} · S{item.slot}")
        self._pos.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedHeight(18)
        head.addWidget(self._pos)
        head.addStretch()
        head.addWidget(self._badge)
        layout.addLayout(head)

        self._code = QLabel("")
        self._note = QLabel("")
        self._note.setStyleSheet(f"color: {FG2}; font-size: 10px;")
        # 라벨이 카드 폭을 밀어내지 않게(3열 × 3패널이 1180px 안에 들어가도록) 가로 최소 폭을 무시
        for lab in (self._pos, self._code, self._note):
            lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(96)
        layout.addWidget(self._code)
        layout.addWidget(self._note)

        if item.status is AssignStatus.CONFLICT:
            self.setContextMenuPolicy(Qt.CustomContextMenu)
            self.customContextMenuRequested.connect(self._menu)
            self.setCursor(Qt.PointingHandCursor)
        self.refresh()

    def _menu(self, pos) -> None:
        menu = QMenu(self)
        act = menu.addAction("덮어쓰기 해제" if self.forced else "덮어쓰기 (기존 QR 교체)")
        act.triggered.connect(lambda: self.force_toggled.emit(self.item.cell))
        menu.exec(self.mapToGlobal(pos))

    def refresh(self) -> None:
        it = self.item
        if self.dimmed:
            border, width, bbg, btext, ccolor = _DIMMED_STYLE
        elif self.forced:
            border, width, bbg, btext, ccolor = _FORCED_STYLE
        else:
            border, width, bbg, btext, ccolor = _STYLE[it.status]
        self.setStyleSheet(
            f"_CellCard {{ background: {BG2}; border: {width}px solid {border}; border-radius: 6px; }}"
        )
        self._badge.setText(btext)
        self._badge.setVisible(bool(btext))
        self._badge.setStyleSheet(
            f"background: {bbg}; color: {BG}; border-radius: 9px; padding: 0 6px; font-size: 10px; font-weight: bold;"
        )
        if it.status is AssignStatus.NG:
            self._code.setText("미판독")
            self._code.setStyleSheet(f"color: {FG3}; font-size: 12px;")
        elif it.status is AssignStatus.EXCLUDED or self.dimmed:
            self._code.setText(it.code or "")
            self._code.setStyleSheet(f"color: {FG3}; font-size: 12px;")
        else:
            self._code.setText(it.code or "")
            self._code.setStyleSheet(f"color: {ccolor}; font-size: 12px; font-weight: bold;")
        note = it.note
        if it.status is AssignStatus.NG and it.target is not None:
            note = "키보드 스캔으로 보완"
        elif it.status is AssignStatus.APPLY:
            note = "Freq/Q 있음" if it.target is not None and it.target.frequency is not None else "레코드 있음"
        if self.forced:
            note = f"{it.note} → 교체"
        self._note.setText(note)
        status_text = _STYLE[it.status][3] if not self.forced else "덮어쓰기"
        self.setToolTip(
            f"셀 {it.cell} → Port {it.port} Slot {it.slot}\n"
            f"코드: {it.code or '(미판독)'}\n{status_text}: {note}"
        )

    def set_dimmed(self, dimmed: bool) -> None:
        if dimmed != self.dimmed:
            self.dimmed = dimmed
            self.refresh()


class BatchReadReviewDialog(QDialog):
    rescan_requested = Signal()

    def __init__(self, plan: AssignPlan, sets: list[MeasurementSet], scan_time_ms: int | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("카세트 판독 검토 — SR-X300W")
        self.setModal(True)
        self.resize(1180, 790)
        self._plan = plan
        self._sets = sets
        self._cards: dict[int, _CellCard] = {}
        self._forced: set[int] = set()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # ── 요약 칩 ──
        counts = plan.counts()
        n = len(plan.items)
        unread = sum(1 for it in plan.items if it.code is None)   # NG + 미로드 포트의 미판독 칸
        chips = QHBoxLayout()
        self._chip_labels: dict[str, QLabel] = {}
        for key, label, value, color in (
            ("read", "판독", f"{n - unread} / {n}", FG),
            ("apply", "적용 가능", counts[AssignStatus.APPLY], GREEN),
            ("ng", "NG", counts[AssignStatus.NG], FG2),
            ("same", "동일", counts[AssignStatus.SAME], TEAL),
            ("dup", "중복", counts[AssignStatus.DUP_FRAME] + counts[AssignStatus.DUP_LOADED], ORANGE),
            ("conflict", "충돌", counts[AssignStatus.CONFLICT], RED),
            ("norec", "레코드 없음", counts[AssignStatus.NO_RECORD], RED),
            ("excluded", "제외", counts[AssignStatus.EXCLUDED], YELLOW),
        ):
            chips.addWidget(self._chip(key, label, value, color))
        chips.addStretch()
        self._scan_label = QLabel(f"스캔 {scan_time_ms} ms" if scan_time_ms is not None else "")
        self._scan_label.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        chips.addWidget(self._scan_label)
        outer.addLayout(chips)

        # ── 필터 + 범례 ──
        bar = QHBoxLayout()
        self.chk_issues_only = QCheckBox("이상 칸만 보기")
        self.chk_issues_only.setToolTip("적용·동일·제외 칸을 흐리게 표시하고 확인이 필요한 칸만 강조합니다.")
        self.chk_issues_only.toggled.connect(self._apply_filter)
        bar.addWidget(self.chk_issues_only)
        for color, text, thick in ((GREEN, "적용", True), (BG3, "NG", False), (TEAL, "동일", False),
                                   (ORANGE, "중복", True), (RED, "충돌/레코드없음", True), (YELLOW, "덮어쓰기", True)):
            bar.addWidget(self._legend(color, text, thick))
        bar.addStretch()
        hint = QLabel("충돌 칸 우클릭 → 덮어쓰기")
        hint.setStyleSheet(f"color: {FG3}; font-size: 12px;")
        hint.setToolTip("셀 번호 = 리더기 격자 순서 · Port = (셀−1)÷12+1, Slot = (셀−1)%12+1")
        bar.addWidget(hint)
        outer.addLayout(bar)
        self.setMinimumWidth(960)

        # ── 패널 (스크롤) ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG}; }}")
        body = QWidget()
        grid = QGridLayout(body)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(16)
        by_port: dict[int, list[AssignItem]] = {}
        for it in plan.items:
            by_port.setdefault(it.port, []).append(it)
        for i, port in enumerate(sorted(by_port)):
            grid.addWidget(self._panel(port, by_port[port]), i // _COLS, i % _COLS)
        for c in range(_COLS):
            grid.setColumnStretch(c, 1)          # 패널 3열을 뷰포트 폭에 균등 분배 (가로 스크롤 없음)
        grid.setRowStretch(grid.rowCount(), 1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # ── 하단 ──
        footer = QHBoxLayout()
        self._block_label = QLabel("")
        self._block_label.setWordWrap(True)
        footer.addWidget(self._block_label, 1)
        self.btn_rescan = QPushButton("재판독")
        self.btn_rescan.clicked.connect(self.rescan_requested.emit)
        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton("적용")
        self.btn_apply.setProperty("accent", "true")
        self.btn_apply.clicked.connect(self.accept)
        for b in (self.btn_rescan, self.btn_cancel, self.btn_apply):
            footer.addWidget(b)
        outer.addLayout(footer)
        self._refresh_footer()

    # ─── 구성 요소 ───

    def _chip(self, key: str, label: str, value, color: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f"QFrame {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 4px; }}")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(6)
        lab = QLabel(label)
        lab.setStyleSheet(f"color: {FG2}; font-size: 12px; border: none;")
        val = QLabel(str(value))
        val.setStyleSheet(f"color: {color}; font-weight: bold; border: none;")
        lay.addWidget(lab)
        lay.addWidget(val)
        self._chip_labels[key] = val
        return w

    @staticmethod
    def _legend(color: str, text: str, thick: bool) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        sw = QFrame()
        sw.setFixedSize(14, 14)
        sw.setStyleSheet(f"background: {BG2}; border: {2 if thick else 1}px solid {color}; border-radius: 3px;")
        lab = QLabel(text)
        lab.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        lay.addWidget(sw)
        lay.addWidget(lab)
        return w

    def _panel(self, port: int, items: list[AssignItem]) -> QGroupBox:
        # 포트가 로드됐는지는 EXCLUDED 여부로 판단 (NO_RECORD 칸만 있는 포트도 "로드됨")
        loaded = any(it.status is not AssignStatus.EXCLUDED for it in items)
        set_idx = next((it.set_index for it in items if it.set_index is not None), None)
        if loaded and set_idx is not None and set_idx < len(self._sets):
            title = f"Port {port} · {circled_number(set_idx + 1)} {self._sets[set_idx].po_number}"
        elif loaded:
            title = f"Port {port} · 레코드 없음"
        else:
            title = f"Port {port} · 폴더 미로드"
        box = QGroupBox(title)
        # 제목·카드 내용이 패널 최소 폭을 밀어 올리지 않게 (3패널 × 3카드가 1180px 안에 들어가야 함)
        box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        box.setToolTip(title)
        if not loaded:
            box.setStyleSheet(f"QGroupBox {{ color: {FG2}; }}")
        lay = QVBoxLayout(box)
        head = QHBoxLayout()
        head.addStretch()
        n_apply = sum(1 for it in items if it.status is AssignStatus.APPLY)
        head_lab = QLabel(f"적용 {n_apply}/{len(items)}" if loaded else "자동 제외")
        head_lab.setStyleSheet(f"color: {FG2 if loaded else YELLOW}; font-size: 12px;")
        head.addWidget(head_lab)
        lay.addLayout(head)
        cells = QGridLayout()
        cells.setSpacing(6)
        for i, it in enumerate(sorted(items, key=lambda x: x.cell)):
            card = _CellCard(it)
            card.force_toggled.connect(self._toggle_force)
            self._cards[it.cell] = card
            cells.addWidget(card, i // _COLS, i % _COLS)
        lay.addLayout(cells)
        if not loaded:
            box.setEnabled(False)
        return box

    # ─── 상호작용 ───

    def _toggle_force(self, cell: int) -> None:
        card = self._cards.get(cell)
        if card is None or card.item.status is not AssignStatus.CONFLICT:
            return
        if cell in self._forced:
            self._forced.discard(cell)
            card.forced = False
        else:
            self._forced.add(cell)
            card.forced = True
        card.refresh()
        self._refresh_footer()

    def _apply_filter(self, issues_only: bool) -> None:
        for card in self._cards.values():
            card.set_dimmed(issues_only and card.item.status in _NORMAL_STATUSES)

    def _refresh_footer(self) -> None:
        counts = self._plan.counts()
        n_apply = len(self.selected_items())
        blocked = counts[AssignStatus.NO_RECORD] > 0
        if blocked:
            cells = [it for it in self._plan.items if it.status is AssignStatus.NO_RECORD]
            where = ", ".join(f"Port {it.port} · S{it.slot}" for it in cells[:4]) + ("…" if len(cells) > 4 else "")
            self._block_label.setText(
                f"⚠ 적용 차단 — 레코드 없음 {len(cells)}칸 ({where}). MTC 결과와 실물이 다릅니다. "
                "카세트를 확인하거나 해당 폴더를 로드한 뒤 재판독하세요."
            )
            self._block_label.setStyleSheet(f"color: {RED}; font-weight: bold; font-size: 13px;")
        else:
            parts = []
            if counts[AssignStatus.CONFLICT]:
                forced = len(self._forced)
                parts.append(f"충돌 {counts[AssignStatus.CONFLICT]}칸 중 {forced}칸 덮어쓰기 선택" if forced
                             else f"충돌 {counts[AssignStatus.CONFLICT]}칸은 적용에서 제외됩니다 (우클릭으로 덮어쓰기)")
            dup = counts[AssignStatus.DUP_FRAME] + counts[AssignStatus.DUP_LOADED]
            if dup:
                parts.append(f"중복 {dup}칸 제외")
            if counts[AssignStatus.NG]:
                parts.append(f"NG {counts[AssignStatus.NG]}칸은 적용 후 키보드 스캔으로 보완")
            if n_apply == 0:
                parts.append("적용할 칸이 없습니다")
            self._block_label.setText(" · ".join(parts))
            self._block_label.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        self.btn_apply.setText(f"적용 ({n_apply})")
        self.btn_apply.setEnabled(not blocked and n_apply > 0)

    # ─── 결과 ───

    @property
    def forced_cells(self) -> set[int]:
        return set(self._forced)

    def selected_items(self) -> list[AssignItem]:
        """적용할 항목: APPLY 전부 + 덮어쓰기로 고른 CONFLICT."""
        return [it for it in self._plan.items
                if it.status is AssignStatus.APPLY
                or (it.status is AssignStatus.CONFLICT and it.cell in self._forced)]
