"""Pass Pool 뷰어 위젯 — 로드된 폴더들의 규격 통과(pass) 슬롯을 폴더명 섹션으로 묶어
표시한다. 단일 선택으로 하단 QR 바가 대상 슬롯을 지정하며, 카드 형태는 ATX 그리드와
동일하고 헤더 명칭만 연속 Port(Port1~N) 로 바뀐다.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea,
    QPushButton,
)

from src.ui.theme import ACCENT, BG, FG2
from src.ui.widgets.measurement_card import MeasurementCard

_COLUMNS = 4


class PassPoolWidget(QWidget):
    card_clicked = Signal(str)             # 카드 고유 key
    card_checked = Signal(str, bool)       # 카드 key, 체크 여부 (캐리어 선택)
    assemble_requested = Signal()          # '캐리어 확정 → CSV'
    clear_selection_requested = Signal()   # '선택 초기화'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, MeasurementCard] = {}
        self._index_to_key: dict[int, str] = {}
        self._order: list[str] = []
        self._selected_key: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # 헤더 행: 제목 + 캐리어(12) 선택 컨트롤
        header_row = QHBoxLayout()
        self._title = QLabel("Pass Pool")
        self._title.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 15px;")
        header_row.addWidget(self._title)
        header_row.addStretch()

        self._sel_label = QLabel("선택 0/12")
        self._sel_label.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        header_row.addWidget(self._sel_label)

        self.btn_clear_sel = QPushButton("선택 초기화")
        self.btn_clear_sel.clicked.connect(self.clear_selection_requested.emit)
        header_row.addWidget(self.btn_clear_sel)

        self.btn_assemble = QPushButton("캐리어 확정 → CSV")
        self.btn_assemble.setProperty("accent", "true")
        self.btn_assemble.setEnabled(False)
        self.btn_assemble.setToolTip("체크한 pass 슬롯(최대 12)을 한 장의 캐리어 CSV로 내보냅니다.")
        self.btn_assemble.clicked.connect(self.assemble_requested.emit)
        header_row.addWidget(self.btn_assemble)

        outer.addLayout(header_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG}; }}")
        outer.addWidget(scroll, 1)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(10)
        scroll.setWidget(self._content)

        self._empty = QLabel("규격을 통과한 슬롯이 없습니다. 폴더를 불러오세요.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(f"color: {FG2}; font-size: 13px; padding: 24px;")

    @property
    def order(self) -> list[str]:
        return list(self._order)

    def set_passes(self, items: list[dict]):
        """items: 단일 연속 스택으로 이미 (-gport, snum) 정렬되어 들어온 pass 카드 목록.
        [{key,header,tooltip,frequency,q_factor,qr_id,slot_code,origin,origin_color}...]
        (맨 위 = 높은 Port, 맨 아래 = Port1)"""
        self._clear()

        total = len(items)
        if not total:
            self._content_layout.addWidget(self._empty)
            self._title.setText("Pass Pool — 0개")
            return

        grid = QGridLayout()
        grid.setSpacing(6)
        for c in range(_COLUMNS):
            grid.setColumnStretch(c, 1)

        for idx, item in enumerate(items):
            key = item["key"]
            card = MeasurementCard(
                idx, item.get("slot_code", ""), self,
                header_label=item["header"], checkable=True,
                origin=item.get("origin"), origin_color=item.get("origin_color"),
                origin_number=item.get("origin_number"),
            )
            card.update_data(
                frequency=item.get("frequency"),
                q_factor=item.get("q_factor"),
                qr_id=item.get("qr_id"),
            )
            if item.get("tooltip"):
                card.setToolTip(item["tooltip"])
            card.clicked.connect(self._on_card_clicked)
            card.check_toggled.connect(self._on_card_check)
            row, col = divmod(idx, _COLUMNS)
            grid.addWidget(card, row, col)

            self._cards[key] = card
            self._index_to_key[idx] = key
            self._order.append(key)

        self._content_layout.addLayout(grid)
        self._content_layout.addStretch()
        self._title.setText(f"Pass Pool — {total}개")

    def select(self, key: str | None):
        """단일 선택 — 지정 카드만 강조, 나머지 해제."""
        if self._selected_key in self._cards:
            self._cards[self._selected_key].set_selected(False)
        self._selected_key = key
        if key in self._cards:
            self._cards[key].set_selected(True)

    def update_card(self, key: str, frequency=None, q_factor=None, qr_id=None):
        card = self._cards.get(key)
        if card:
            card.update_data(frequency=frequency, q_factor=q_factor, qr_id=qr_id)

    def _on_card_clicked(self, index: int):
        key = self._index_to_key.get(index)
        if key is not None:
            self.card_clicked.emit(key)

    def _on_card_check(self, index: int, checked: bool):
        key = self._index_to_key.get(index)
        if key is not None:
            self.card_checked.emit(key, checked)

    def apply_checks(self, keys):
        """지정 key 집합만 체크 상태로 동기화(프로그램적, 시그널 억제)."""
        keyset = set(keys)
        for key, card in self._cards.items():
            card.set_checked(key in keyset)

    def set_selection_count(self, count: int, cap: int = 12):
        """'선택 N/12' 라벨 갱신 + 확정 버튼 활성화(1~cap)."""
        self._sel_label.setText(f"선택 {count}/{cap}")
        self.btn_assemble.setEnabled(1 <= count <= cap)

    def _clear(self):
        self._cards.clear()
        self._index_to_key.clear()
        self._order.clear()
        self._selected_key = None
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self._empty:
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    child = sub.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
