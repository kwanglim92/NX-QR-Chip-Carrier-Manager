"""Transparent drag-selection overlay for one-shot screen captures."""
from __future__ import annotations

import ctypes

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QDialog


def _window_rect_at(point: QPoint) -> QRect | None:
    """Return the native top-level window rect under ``point`` on Windows."""
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        user32.WindowFromPoint.argtypes = [wintypes.POINT]
        user32.WindowFromPoint.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

        hwnd = user32.WindowFromPoint(wintypes.POINT(point.x(), point.y()))
        if not hwnd:
            return None
        hwnd = user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return None

        rect = RECT()
        # DWMWA_EXTENDED_FRAME_BOUNDS includes the visible window frame.
        hr = dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
        )
        if hr != 0 and not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return None
        return QRect(rect.left, rect.top, width, height)
    except (AttributeError, OSError, TypeError):
        return None


class ScreenCaptureOverlay(QDialog):
    """Full-desktop overlay that returns a selected global screen region."""

    MIN_CAPTURE_SIZE = 24

    def __init__(
        self,
        capture_mode: str = "region",
        parent=None,
        label: str = "Sweep Image",
    ) -> None:
        super().__init__(parent)
        self._capture_mode = capture_mode
        self._label = label
        self._start: QPoint | None = None
        self._current: QPoint | None = None
        self._selected_rect: QRect | None = None
        self._selected_screen = None
        self._message = (
            f"Click a {label} window. Esc or right-click to cancel."
            if capture_mode == "window"
            else f"Drag to capture {label}. Esc or right-click to cancel."
        )

        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        cursor = Qt.PointingHandCursor if capture_mode == "window" else Qt.CrossCursor
        self.setCursor(cursor)

        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.geometry())
        if geometry.isNull():
            geometry = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(geometry)

    def selected_region(self):
        """Return ``(QScreen, QRect)`` for the accepted capture region."""
        return self._selected_screen, self._selected_rect

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.RightButton:
            self.reject()
            return
        if self._capture_mode == "window" and event.button() == Qt.LeftButton:
            self._capture_window_at(event.position().toPoint())
            return
        if event.button() == Qt.LeftButton:
            self._start = event.position().toPoint()
            self._current = self._start
            self._message = "Release to capture selected area."
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._capture_mode == "region" and self._start is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._capture_mode != "region":
            return
        if event.button() != Qt.LeftButton or self._start is None:
            return

        self._current = event.position().toPoint()
        local_rect = QRect(self._start, self._current).normalized()
        if (
            local_rect.width() < self.MIN_CAPTURE_SIZE
            or local_rect.height() < self.MIN_CAPTURE_SIZE
        ):
            self._message = (
                f"Selected area is too small. Drag a larger {self._label} area."
            )
            self._start = None
            self._current = None
            self.update()
            return

        top_left = self.mapToGlobal(local_rect.topLeft())
        bottom_right = self.mapToGlobal(local_rect.bottomRight())
        global_rect = QRect(top_left, bottom_right).normalized()
        screen = QGuiApplication.screenAt(global_rect.center()) or QGuiApplication.primaryScreen()
        capture_rect = global_rect.intersected(screen.geometry())

        if (
            capture_rect.width() < self.MIN_CAPTURE_SIZE
            or capture_rect.height() < self.MIN_CAPTURE_SIZE
        ):
            self._message = "Selected area is outside the screen. Try again."
            self._start = None
            self._current = None
            self.update()
            return

        self._selected_screen = screen
        self._selected_rect = capture_rect
        self.accept()

    def _capture_window_at(self, local_pos: QPoint) -> None:
        global_pos = self.mapToGlobal(local_pos)
        self.hide()
        QGuiApplication.processEvents()

        rect = _window_rect_at(global_pos)
        if rect is None:
            self.reject()
            return

        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        capture_rect = rect.intersected(screen.geometry())
        if (
            capture_rect.width() < self.MIN_CAPTURE_SIZE
            or capture_rect.height() < self.MIN_CAPTURE_SIZE
        ):
            self.reject()
            return

        self._selected_screen = screen
        self._selected_rect = capture_rect
        self.accept()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(8, 10, 24, 120))

        painter.setPen(QPen(QColor(180, 205, 255), 1))
        painter.drawText(24, 36, self._message)

        if self._start is None or self._current is None:
            return

        rect = QRect(self._start, self._current).normalized()
        painter.fillRect(rect, QColor(120, 170, 255, 45))
        painter.setPen(QPen(QColor(130, 180, 255), 2))
        painter.drawRect(rect)
