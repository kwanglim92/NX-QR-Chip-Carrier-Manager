"""수동 모드 카드 — 썸네일(Zoom-In/Out) + 측정값 + QR ID + 상태 뱃지."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy, QMenu,
)

from src.core.capture_files import derive_zoomout_path
from src.core.models import truncate_measurement_value
from src.ui.theme import BADGE_FG, BG3, FG, FG2, ACCENT, GREEN, ORANGE, SELECT_FG

_FONT_BASE = 12
_FONT_HEADER = 14
_FONT_BADGE = 11
_FONT_QR = 11

MANUAL_CARD_HEIGHT = 140
THUMB_W, THUMB_H = 56, 42
_THUMB_QSS = f"border: 1px solid {BG3}; border-radius: 3px;"
_UNSET = object()


class ManualCard(QFrame):
    clicked = Signal(int)   # slot_index
    removed = Signal(int)   # slot_index

    def __init__(self, slot_index: int, image_path, contact_mode: bool = False, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.image_path = image_path
        self.contact_mode = contact_mode
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
            f"background: {FG2}; color: {BADGE_FG}; border-radius: 10px; "
            f"font-size: {_FONT_BADGE}px; font-weight: bold;"
        )
        header.addWidget(self._badge)
        root.addLayout(header)

        # 본문: 썸네일(Zoom-In | Zoom-Out) + 측정값
        body = QHBoxLayout()
        body.setSpacing(6)

        self._thumb_in = QLabel()
        self._thumb_in.setFixedSize(THUMB_W, THUMB_H)
        self._thumb_in.setAlignment(Qt.AlignCenter)
        self._thumb_in.setStyleSheet(_THUMB_QSS)
        self._thumb_in.setToolTip("Zoom-In")
        body.addWidget(self._thumb_in)

        self._thumb_out = QLabel()
        self._thumb_out.setFixedSize(THUMB_W, THUMB_H)
        self._thumb_out.setAlignment(Qt.AlignCenter)
        self._thumb_out.setStyleSheet(_THUMB_QSS)
        self._thumb_out.setToolTip("Zoom-Out")
        body.addWidget(self._thumb_out)

        info = QVBoxLayout()
        info.setSpacing(1)
        self._freq_label = QLabel("Freq: -")
        self._freq_label.setStyleSheet(f"color: {FG}; font-size: {_FONT_BASE}px;")
        info.addWidget(self._freq_label)

        self._q_label = QLabel("Q: -")
        self._q_label.setStyleSheet(f"color: {FG}; font-size: {_FONT_BASE}px;")
        info.addWidget(self._q_label)

        body.addLayout(info, 1)
        root.addLayout(body)

        # QR ID
        self._qr_label = QLabel("")
        self._qr_label.setStyleSheet(f"color: {GREEN}; font-size: {_FONT_QR}px;")
        root.addWidget(self._qr_label)

        # 컨택 모드: 이미지·측정값 불필요 → 썸네일/Freq/Q 숨김 (QR 중심)
        if self.contact_mode:
            self._thumb_in.setVisible(False)
            self._thumb_out.setVisible(False)
            self._freq_label.setVisible(False)
            self._q_label.setVisible(False)

        # 썸네일 로드 (Zoom-In + Zoom-Out)
        self.set_thumbnail(image_path)
        self.refresh_zoomout()
        self._update_badge()

    def set_thumbnail(self, path):
        self._thumb_in.clear()
        if not path:
            return
        pm = QPixmap(str(path))
        if not pm.isNull():
            scaled = pm.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._thumb_in.setPixmap(scaled)

    def refresh_zoomout(self):
        """Zoom-Out 썸네일 갱신 — 있으면 표시, 없으면 빈 박스(존재 여부 가시화)."""
        self._thumb_out.clear()
        if self.contact_mode or not self.image_path:
            return
        try:
            zo = derive_zoomout_path(self.image_path)
        except (TypeError, ValueError, OSError):
            return
        if zo.exists():
            pm = QPixmap(str(zo))
            if not pm.isNull():
                self._thumb_out.setPixmap(
                    pm.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

    def set_image_path(self, path):
        self.image_path = path
        self.set_thumbnail(path)
        self.refresh_zoomout()

    def set_slot_index(self, slot_index: int):
        self.slot_index = slot_index
        self._num_label.setText(f"#{slot_index + 1}")

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
        else:
            self._q_label.setText(f"Q: {truncate_measurement_value(q_factor)}")

        if qr_id is _UNSET:
            pass
        elif qr_id:
            self._qr_label.setText(f"QR: {qr_id}")
            self._has_qr = True
        else:
            self._qr_label.setText("")
            self._has_qr = False

        self._update_badge()
        self._update_state()

    def _update_badge(self):
        # 컨택 모드: QR 만 있으면 완료(OK)
        if self.contact_mode:
            if self._has_qr:
                text, bg = "OK", GREEN
            else:
                text, bg = "EMPTY", FG2
            self._badge.setText(text)
            self._badge.setFixedWidth(70)
            self._badge.setStyleSheet(
                f"background: {bg}; color: {BADGE_FG}; border-radius: 10px; "
                f"font-size: {_FONT_BADGE}px; font-weight: bold;"
            )
            return

        if self._has_freq and self._has_qr:
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
        if self.contact_mode:
            self._set_state("matched" if self._has_qr else "empty")
            return
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
                f"color: {SELECT_FG}; font-weight: bold; font-size: {_FONT_HEADER}px;"
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
