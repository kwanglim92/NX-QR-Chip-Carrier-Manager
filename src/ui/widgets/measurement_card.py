"""4×3 그리드에 표시되는 개별 슬롯 카드.

상태:
  - empty: 데이터 없음
  - loaded: Freq/Q 로드됨 (QR 미입력 → NOT PASS)
  - matched: QR + Freq + Q 모두 완료 → PASS
  - selected: 현재 선택됨
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy, QMenu

from src.core.slot_mapper import parse_slot_code, format_full_label
from src.ui.theme import BG2, FG, FG2, ACCENT, GREEN, RED, ORANGE

# 카드 전용 폰트 (기존 대비 -20%)
_FONT_BASE = 12
_FONT_HEADER = 14
_FONT_BADGE = 11
_FONT_QR = 11

CARD_HEIGHT = 120
CARD_MIN_WIDTH = 150


class MeasurementCard(QFrame):
    clicked = Signal(int)    # slot_index
    reset_qr = Signal(int)   # slot_index

    def __init__(self, slot_index: int, slot_code: str, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.slot_code = slot_code
        self._has_freq = False
        self._has_qr = False

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

        # 헤더: Slot 번호 + 상태 뱃지
        header_layout = QHBoxLayout()
        try:
            info = parse_slot_code(slot_code)
            header_text = f"Slot {info['slot']}"
        except (ValueError, IndexError):
            header_text = f"#{slot_index + 1}"
        self._slot_label = QLabel(header_text)
        self._slot_label.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; font-size: {_FONT_HEADER}px;"
        )
        header_layout.addWidget(self._slot_label)
        header_layout.addStretch()

        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedSize(70, 20)
        self._badge.setStyleSheet(
            f"background: {FG2}; color: {BG2}; border-radius: 10px; "
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

    def update_data(self, frequency=None, q_factor=None, qr_id=None, **_kwargs):
        if frequency is not None:
            self._freq_label.setText(f"Freq: {round(frequency)} KHz")
            self._has_freq = True
        if q_factor is not None:
            self._q_label.setText(f"Q: {round(q_factor)}")

        if qr_id:
            self._qr_label.setText(f"QR: {qr_id}")
            self._has_qr = True

        self._update_badge()
        self._update_state()

    def _update_badge(self):
        if self._has_freq and self._has_qr:
            self._badge.setText("PASS")
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {GREEN}; color: {BG2}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
        elif self._has_freq:
            self._badge.setText("QR")
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {ORANGE}; color: {BG2}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
        else:
            self._badge.setText("EMPTY")
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {FG2}; color: {BG2}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )

    def _update_state(self):
        if self._has_freq and self._has_qr:
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
                f"color: #ffffff; font-weight: bold; font-size: {_FONT_HEADER}px;"
            )
        else:
            self._update_state()
            self._slot_label.setStyleSheet(
                f"color: {ACCENT}; font-weight: bold; font-size: {_FONT_HEADER}px;"
            )

    def _set_state(self, state: str):
        self.setProperty("state", state)
        self.style().polish(self)

    def reset_qr_display(self):
        """Clear QR display and revert badge/state."""
        self._qr_label.setText("")
        self._has_qr = False
        self._update_badge()
        self._update_state()

    def _show_context_menu(self, pos):
        if not self._has_qr:
            return
        menu = QMenu(self)
        action = menu.addAction("Reset QR")
        if menu.exec(self.mapToGlobal(pos)) == action:
            self.reset_qr.emit(self.slot_index)

    def mousePressEvent(self, event):
        self.clicked.emit(self.slot_index)
        super().mousePressEvent(event)
