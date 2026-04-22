"""색상 코드가 있는 시스템 로거 위젯.

다중 싱크 + sink별 레벨 필터 + 1000라인 자동 회전.

- 기존 API(``info/ok/warn/error/section``) 전부 호환 유지
- 구형 시그니처 ``SystemLogger(text_edit)`` 도 그대로 사용 가능
- 위젯이 삭제되면 ``RuntimeError`` 를 감지해 자동 제거 (dead sink self-heal)
- 각 sink마다 최소 표시 레벨(``min_level``)을 독립 설정 가능 — Phase 7B
- 각 sink의 ``QTextDocument`` 가 ``MAX_LINES`` 이하 유지 — Qt 내장 기능 사용
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtWidgets import QTextEdit

from src.ui.theme import FG2, ACCENT, GREEN, ORANGE, RED, PURPLE

# 1000라인 이상 누적되지 않도록 자동 회전 (QTextDocument 내장)
MAX_LINES = 1000

# 메시지 우선순위 — 이보다 낮은 priority의 태그는 sink의 min_level 이상이어야 표시
# info/ok/head(section) 은 모두 "일반" 레벨로 묶어서 0
# warn = 1, err = 2
LEVEL_PRIORITY = {"info": 0, "ok": 0, "head": 0, "warn": 1, "err": 2}

# 사용자 UI에 노출되는 레벨 프리셋 이름 → 내부 min_level 태그
LEVEL_PRESETS = {
    "All": "info",
    "Warnings+": "warn",
    "Errors only": "err",
}


@dataclass
class _Sink:
    """로거 싱크 1개분 — QTextEdit + 레벨 필터."""
    te: QTextEdit
    min_level: str = "info"

    @property
    def min_priority(self) -> int:
        return LEVEL_PRIORITY.get(self.min_level, 0)


class SystemLogger:
    COLORS = {"info": FG2, "ok": GREEN, "warn": ORANGE, "err": RED, "head": PURPLE}

    def __init__(self, text_edit: QTextEdit | None = None):
        self._sinks: list[_Sink] = []
        if text_edit is not None:
            self.add_sink(text_edit)

    # ─── 싱크 관리 ───

    def add_sink(self, text_edit: QTextEdit, min_level: str = "info") -> None:
        """로그 메시지를 받을 QTextEdit 를 등록.

        Parameters
        ----------
        text_edit
            메시지를 수신할 위젯.
        min_level
            "info" | "ok" | "warn" | "err" — 이 레벨 미만의 메시지는 필터링.
            기본은 "info" (전체 수신).
        """
        if text_edit is None:
            return
        # 중복 등록 방지
        for s in self._sinks:
            if s.te is text_edit:
                return
        try:
            text_edit.setReadOnly(True)
            # QTextDocument가 자동으로 오래된 블록 회전
            text_edit.document().setMaximumBlockCount(MAX_LINES)
        except RuntimeError:
            return  # 이미 삭제된 위젯이면 무시
        self._sinks.append(_Sink(te=text_edit, min_level=min_level))

    def remove_sink(self, text_edit: QTextEdit) -> None:
        self._sinks = [s for s in self._sinks if s.te is not text_edit]

    def set_sink_level(self, text_edit: QTextEdit, min_level: str) -> None:
        """특정 sink의 최소 표시 레벨 변경.

        UI의 QComboBox.currentTextChanged 시그널에서 호출되도록 설계.
        ``min_level`` 은 ``LEVEL_PRIORITY`` 의 키여야 함. 미지 키면 조용히 무시.
        """
        if min_level not in LEVEL_PRIORITY:
            return
        for s in self._sinks:
            if s.te is text_edit:
                s.min_level = min_level
                return

    # ─── 내부 방송 ───

    def _broadcast(self, html: str, tag: str) -> None:
        """모든 유효한 싱크에 HTML 덩어리를 append. 삭제된 위젯은 자동 제거.

        각 sink의 ``min_level`` 보다 낮은 우선순위의 메시지는 해당 sink에
        표시하지 않음 (다른 sink에는 그대로 표시).
        """
        msg_priority = LEVEL_PRIORITY.get(tag, 0)
        dead: list[_Sink] = []
        for s in self._sinks:
            if msg_priority < s.min_priority:
                continue  # 이 sink는 이 메시지를 필터링
            try:
                s.te.append(html)
            except RuntimeError:
                dead.append(s)
        for s in dead:
            self._sinks.remove(s)

    def _append(self, msg: str, tag: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(tag, FG2)
        self._broadcast(
            f'<span style="color:{ACCENT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>',
            tag,
        )

    # ─── 공개 API ───

    def info(self, msg: str) -> None:
        self._append(msg, "info")

    def ok(self, msg: str) -> None:
        self._append(msg, "ok")

    def warn(self, msg: str) -> None:
        self._append(msg, "warn")

    def error(self, msg: str) -> None:
        self._append(msg, "err")

    def section(self, title: str) -> None:
        self._broadcast(
            f'<br><span style="color:{PURPLE};font-weight:bold">'
            f'{"═" * 40}<br>  {title}<br>{"═" * 40}</span>',
            "head",
        )
