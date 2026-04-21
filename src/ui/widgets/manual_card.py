"""수동 모드 카드 — 썸네일 + 측정값 + QR ID + 상태 뱃지."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy, QMenu,
)

from src.ui.theme import BG2, FG, FG2, ACCENT, GREEN, ORANGE

_FONT_BASE = 12
_FONT_HEADER = 14
_FONT_BADGE = 11
_FONT_QR = 11

MANUAL_CARD_HEIGHT = 140
THUMB_W, THUMB_H = 60, 45


class ManualCard(QFrame):
    clicked = Signal(int)   # slot_index
    removed = Signal(int)   # slot_index

    def __init__(self, slot_index: int, image_path: str, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.image_path = image_path
        self._has_freq = False
        self._has_qr = False

        self.setProperty("card", "true")
        self.setProperty("state", "empty")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(MANUAL_CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(2)

        # 헤더: 카드 번호 + 뱃지
        header = QHBoxLayout()
        self._num_label = QLabel(f"#{slot_index + 1}")
        self._num_label.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; font-size: {_FONT_HEADER}px;"
        )
        header.addWidget(self._num_label)
        header.addStretch()

        self._badge = QLabel("EMPTY")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedSize(70, 20)
        self._badge.setStyleSheet(
            f"background: {FG2}; color: {BG2}; border-radius: 10px; "
            f"font-size: {_FONT_BADGE}px; font-weight: bold;"
        )
        header.addWidget(self._badge)
        root.addLayout(header)

        # 본문: 썸네일 + 측정값
        body = QHBoxLayout()
        body.setSpacing(8)

        self._thumb = QLabel()
        self._thumb.setFixedSize(THUMB_W, THUMB_H)
        self._thumb.setAlignment(Qt.AlignCenter)
        self._thumb.setStyleSheet("border: 1px solid #444; border-radius: 3px;")
        body.addWidget(self._thumb)

        info = QVBoxLayout()
        info.setSpacing(1)
        self._freq_label = QLabel("Freq: -")
        self._freq_label.setStyleSheet(f"color: {FG}; font-size: {_FONT_BASE}px;")
        info.addWidget(self._freq_label)

        self._q_label = QLabel("Q: -")
        self._q_label.setStyleSheet(f"color: {FG}; font-size: {_FONT_BASE}px;")
        info.addWidget(self._q_label)

        body.addLayout(info)
        root.addLayout(body)

        # QR ID
        self._qr_label = QLabel("")
        self._qr_label.setStyleSheet(f"color: {GREEN}; font-size: {_FONT_QR}px;")
        root.addWidget(self._qr_label)

        # 썸네일 로드
        self.set_thumbnail(image_path)

    def set_thumbnail(self, path: str):
        pm = QPixmap(path)
        if not pm.isNull():
            scaled = pm.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._thumb.setPixmap(scaled)

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
            self._num_label.setStyleSheet(
                f"color: #ffffff; font-weight: bold; font-size: {_FONT_HEADER}px;"
            )
        else:
            self._update_state()
            self._num_label.setStyleSheet(
                f"color: {ACCENT}; font-weight: bold; font-size: {_FONT_HEADER}px;"
            )

    def _set_state(self, state: str):
        self.setProperty("state", state)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self.slot_index)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        action = menu.addAction("삭제")
        if menu.exec(self.mapToGlobal(pos)) == action:
            self.removed.emit(self.slot_index)
