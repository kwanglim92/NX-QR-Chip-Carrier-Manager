"""색상 코드가 있는 시스템 로거 위젯."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QTextEdit

from src.ui.theme import FG2, ACCENT, GREEN, ORANGE, RED, PURPLE


class SystemLogger:
    COLORS = {"info": FG2, "ok": GREEN, "warn": ORANGE, "err": RED, "head": PURPLE}

    def __init__(self, text_edit: QTextEdit):
        self._te = text_edit
        self._te.setReadOnly(True)

    def _append(self, msg: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(tag, FG2)
        self._te.append(
            f'<span style="color:{ACCENT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )

    def info(self, msg: str):
        self._append(msg, "info")

    def ok(self, msg: str):
        self._append(msg, "ok")

    def warn(self, msg: str):
        self._append(msg, "warn")

    def error(self, msg: str):
        self._append(msg, "err")

    def section(self, title: str):
        self._te.append(
            f'<br><span style="color:{PURPLE};font-weight:bold">'
            f'{"═" * 40}<br>  {title}<br>{"═" * 40}</span>'
        )
