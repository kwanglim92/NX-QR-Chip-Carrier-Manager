"""4×3 그리드에 표시되는 개별 슬롯 카드.

상태:
  - empty: 데이터 없음
  - loaded: Freq/Q 로드됨 (QR 미입력 → NOT PASS)
  - matched: QR + Freq + Q 모두 완료 → PASS
  - selected: 현재 선택됨
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy, QMenu, QCheckBox,
)

from src.core.models import truncate_measurement_value
from src.core.slot_mapper import parse_slot_code, format_full_label
from src.ui.theme import BADGE_FG, FG, FG2, ACCENT, GREEN, RED, ORANGE, SELECT_FG

# 카드 전용 폰트 (기존 대비 -20%)
_FONT_BASE = 12
_FONT_HEADER = 14
_FONT_BADGE = 11
_FONT_QR = 11

CARD_HEIGHT = 120
CARD_MIN_WIDTH = 150
_UNSET = object()


class MeasurementCard(QFrame):
    clicked = Signal(int)    # slot_index
    reset_qr = Signal(int)   # slot_index
    edit_requested = Signal(int)  # slot_index
    check_toggled = Signal(int, bool)  # slot_index, checked (checkable 카드 전용)

    def __init__(self, slot_index: int, slot_code: str, parent=None, header_label: str | None = None,
                 checkable: bool = False, origin: str | None = None, origin_color: str | None = None,
                 origin_number: str | None = None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.slot_code = slot_code
        self._checkbox: QCheckBox | None = None
        # 출처(PO) 색 — Pass Pool 카드에서만 지정. 헤더 라벨 색이자 선택 해제 시 복귀색.
        self._header_color = origin_color or ACCENT
        self._has_freq = False
        self._has_q = False
        self._has_qr = False
        self._qr_id: str | None = None

        self.setProperty("card", "true")
        self.setProperty("state", "empty")
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setFixedHeight(CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(2)

        # 헤더: (선택 체크박스) + Slot 번호 + 상태 뱃지
        header_layout = QHBoxLayout()
        if checkable:
            self._checkbox = QCheckBox()
            self._checkbox.setToolTip("이 슬롯을 캐리어(12슬롯)에 포함")
            self._checkbox.setCursor(Qt.PointingHandCursor)
            self._checkbox.toggled.connect(
                lambda ch: self.check_toggled.emit(self.slot_index, ch)
            )
            header_layout.addWidget(self._checkbox)
        if header_label is not None:
            header_text = header_label
        else:
            try:
                info = parse_slot_code(slot_code)
                header_text = f"Slot {info['slot']}"
            except (ValueError, IndexError):
                header_text = f"#{slot_index + 1}"
        self._slot_label = QLabel(header_text)
        self._slot_label.setStyleSheet(
            f"color: {self._header_color}; font-weight: bold; font-size: {_FONT_HEADER}px;"
        )
        header_layout.addWidget(self._slot_label)
        header_layout.addStretch()

        # 폴더 순번 뱃지(①②③) — 색만으로는 PASS 상태와 혼동될 수 있어 큰 번호로 명확히 구분
        if origin_number:
            self._origin_num_label = QLabel(origin_number)
            self._origin_num_label.setStyleSheet(
                f"color: {self._header_color}; font-size: {_FONT_HEADER}px; font-weight: bold;"
            )
            header_layout.addWidget(self._origin_num_label)

        # 출처(PO) 라벨 — Pass Pool 단일 스택에서 폴더 구분(폭 좁으면 우측이 잘림)
        if origin:
            self._origin_label = QLabel(origin)
            self._origin_label.setStyleSheet(
                f"color: {self._header_color}; font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
            header_layout.addWidget(self._origin_label)

        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedSize(70, 20)
        self._badge.setStyleSheet(
            f"background: {FG2}; color: {BADGE_FG}; border-radius: 10px; "
            f"font-size: {_FONT_BADGE}px; font-weight: bold;"
        )
        header_layout.addWidget(self._badge)
        layout.addLayout(header_layout)

        # 측정값
        self._freq_label = QLabel("Freq: -")
        self._freq_label.setStyleSheet(f"color: {FG}; font-size: {_FONT_BASE}px;")
        layout.addWidget(self._freq_label)

        self._q_label = QLabel("Q: -")
        self._q_label.setStyleSheet(f"color: {FG}; font-size: {_FONT_BASE}px;")
        layout.addWidget(self._q_label)

        # QR ID
        self._qr_label = QLabel("")
        self._qr_label.setStyleSheet(f"color: {GREEN}; font-size: {_FONT_QR}px;")
        layout.addWidget(self._qr_label)

        self._update_badge()

    def update_data(self, frequency=_UNSET, q_factor=_UNSET, qr_id=_UNSET, **_kwargs):
        if frequency is _UNSET:
            pass
        elif frequency is None:
            self._freq_label.setText("Freq: -")
            self._has_freq = False
        else:
            self._freq_label.setText(
                f"Freq: {truncate_measurement_value(frequency)} kHz"
            )
            self._has_freq = True

        if q_factor is _UNSET:
            pass
        elif q_factor is None:
            self._q_label.setText("Q: -")
            self._has_q = False
        else:
            self._q_label.setText(f"Q: {truncate_measurement_value(q_factor)}")
            self._has_q = True

        if qr_id is _UNSET:
            pass
        elif qr_id:
            self._qr_id = qr_id
            self._qr_label.setText(f"QR: {qr_id}")
            self._has_qr = True
        else:
            self._qr_id = None
            self._qr_label.setText("")
            self._has_qr = False

        self._update_badge()
        self._update_state()

    def _update_badge(self):
        if self._has_freq and self._has_q and self._has_qr:
            self._badge.setText("PASS")
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {GREEN}; color: {BADGE_FG}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
        elif self._has_freq:
            self._badge.setText("QR")
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {ORANGE}; color: {BADGE_FG}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
        else:
            self._badge.setText("EMPTY")
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {FG2}; color: {BADGE_FG}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )

    def _update_state(self):
        if self._has_freq and self._has_q and self._has_qr:
            self._set_state("matched")
        elif self._has_freq:
            self._set_state("loaded")
        else:
            self._set_state("empty")

    def set_selected(self, selected: bool):
        if selected:
            self._set_state("selected")
            # 선택 시 헤더 강조
            self._slot_label.setStyleSheet(
                f"color: {SELECT_FG}; font-weight: bold; font-size: {_FONT_HEADER}px;"
            )
        else:
            self._update_state()
            self._slot_label.setStyleSheet(
                f"color: {self._header_color}; font-weight: bold; font-size: {_FONT_HEADER}px;"
            )

    def _set_state(self, state: str):
        self.setProperty("state", state)
        self.style().polish(self)

    def set_header_label(self, text: str):
        """Override the header text (used by the Pass Pool origin/pick label)."""
        self._slot_label.setText(text)

    def set_checked(self, checked: bool):
        """checkable 카드의 선택 상태를 설정(시그널 억제 — 프로그램적 동기화)."""
        if self._checkbox is not None:
            self._checkbox.blockSignals(True)
            self._checkbox.setChecked(checked)
            self._checkbox.blockSignals(False)

    def is_checked(self) -> bool:
        return self._checkbox is not None and self._checkbox.isChecked()

    def reset_qr_display(self):
        """Clear QR display and revert badge/state."""
        self._qr_id = None
        self._qr_label.setText("")
        self._has_qr = False
        self._update_badge()
        self._update_state()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction("수정…")
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.slot_index))

        if self._has_qr:
            menu.addSeparator()
            reset_action = menu.addAction("Reset QR")
            reset_action.triggered.connect(lambda: self.reset_qr.emit(self.slot_index))

        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        self.clicked.emit(self.slot_index)
        super().mousePressEvent(event)
