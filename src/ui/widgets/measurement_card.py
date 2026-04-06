"""4×3 그리드에 표시되는 개별 슬롯 카드.

상태:
  - empty: 데이터 없음
  - loaded: Freq/Q 로드됨 (Drive 또는 QR 미입력 → NOT PASS)
  - matched: QR + Drive + Freq + Q 모두 완료 → PASS
  - selected: 현재 선택됨
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout

from src.core.slot_mapper import parse_slot_code, format_full_label
from src.ui.theme import BG2, FG, FG2, ACCENT, GREEN, RED, ORANGE

# 기본 11px 기준 40% 상승 → 15px, 헤더/뱃지도 비례 상승
_FONT_BASE = 15
_FONT_HEADER = 17
_FONT_BADGE = 14
_FONT_QR = 14


class MeasurementCard(QFrame):
    clicked = Signal(int)  # slot_index

    def __init__(self, slot_index: int, slot_code: str, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.slot_code = slot_code
        self._has_freq = False
        self._has_drive = False
        self._has_qr = False

        self.setProperty("card", "true")
        self.setProperty("state", "empty")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(140)
        self.setMinimumWidth(170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        # 헤더: ATX/Port/Slot + 상태 뱃지
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
        self._badge.setFixedSize(80, 22)
        self._badge.setStyleSheet(
            f"background: {FG2}; color: {BG2}; border-radius: 11px; "
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

        self._drive_label = QLabel("Drive: -")
        self._drive_label.setStyleSheet(f"color: {FG2}; font-size: {_FONT_BASE}px;")
        layout.addWidget(self._drive_label)

        # QR ID
        self._qr_label = QLabel("")
        self._qr_label.setStyleSheet(f"color: {GREEN}; font-size: {_FONT_QR}px;")
        layout.addWidget(self._qr_label)

        self._update_badge()

    def update_data(self, frequency=None, q_factor=None, drive=None, qr_id=None):
        if frequency is not None:
            self._freq_label.setText(f"Freq: {round(frequency)} KHz")
            self._has_freq = True
        if q_factor is not None:
            self._q_label.setText(f"Q: {round(q_factor)}")
        if drive is not None:
            self._drive_label.setText(f"Drive: {drive:.2f}%")
            self._has_drive = True

        if qr_id:
            self._qr_label.setText(f"QR: {qr_id}")
            self._has_qr = True

        self._update_badge()
        self._update_state()

    def _update_badge(self):
        if self._has_freq and self._has_drive and self._has_qr:
            self._badge.setText("PASS")
            self._badge.setFixedWidth(80)
            self._badge.setStyleSheet(
                f"background: {GREEN}; color: {BG2}; border-radius: 11px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
        elif self._has_freq:
            missing = []
            if not self._has_drive:
                missing.append("Drive")
            if not self._has_qr:
                missing.append("QR")
            text = ",".join(missing)
            self._badge.setText(text)
            self._badge.setFixedWidth(max(80, len(text) * 9 + 20))
            self._badge.setStyleSheet(
                f"background: {ORANGE}; color: {BG2}; border-radius: 11px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
        else:
            self._badge.setText("EMPTY")
            self._badge.setFixedWidth(80)
            self._badge.setStyleSheet(
                f"background: {FG2}; color: {BG2}; border-radius: 11px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )

    def _update_state(self):
        if self._has_freq and self._has_drive and self._has_qr:
            self._set_state("matched")
        elif self._has_freq:
            self._set_state("loaded")
        else:
            self._set_state("empty")

    def set_selected(self, selected: bool):
        if selected:
            self._set_state("selected")
        else:
            self._update_state()

    def _set_state(self, state: str):
        self.setProperty("state", state)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self.slot_index)
        super().mousePressEvent(event)
