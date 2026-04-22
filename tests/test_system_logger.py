"""Phase 6A + 7B 회귀 테스트 — SystemLogger 다중 싱크 + 1000라인 + 레벨 필터."""
from __future__ import annotations

from PySide6.QtWidgets import QTextEdit

from src.ui.widgets.system_logger import (
    LEVEL_PRESETS,
    LEVEL_PRIORITY,
    MAX_LINES,
    SystemLogger,
)


class TestLegacyCompat:
    """Phase 6A 이전 시그니처 호환."""

    def test_single_text_edit_constructor(self, qapp):
        te = QTextEdit()
        logger = SystemLogger(te)
        logger.info("hello")
        assert "hello" in te.toPlainText()

    def test_no_argument_constructor(self, qapp):
        logger = SystemLogger()
        assert len(logger._sinks) == 0
        # sink 없이 _broadcast 호출해도 크래시 없음
        logger.info("void")


class TestMultipleSinks:
    def test_broadcast(self, qapp):
        logger = SystemLogger()
        te1 = QTextEdit()
        te2 = QTextEdit()
        te3 = QTextEdit()
        logger.add_sink(te1)
        logger.add_sink(te2)
        logger.add_sink(te3)

        logger.warn("broadcast-test")
        for te in (te1, te2, te3):
            assert "broadcast-test" in te.toPlainText()

    def test_duplicate_add_ignored(self, qapp):
        logger = SystemLogger()
        te = QTextEdit()
        logger.add_sink(te)
        logger.add_sink(te)  # 중복
        assert len(logger._sinks) == 1

    def test_remove_sink(self, qapp):
        logger = SystemLogger()
        te1 = QTextEdit()
        te2 = QTextEdit()
        logger.add_sink(te1)
        logger.add_sink(te2)
        logger.remove_sink(te2)
        logger.info("after-remove")
        assert "after-remove" in te1.toPlainText()
        assert "after-remove" not in te2.toPlainText()


class TestMaxLines:
    def test_auto_rotation(self, qapp):
        te = QTextEdit()
        logger = SystemLogger(te)
        for i in range(MAX_LINES + 200):
            logger.info(f"line-{i}")
        # setMaximumBlockCount 는 N을 엄격 유지 (+1 잉여 허용)
        assert te.document().blockCount() <= MAX_LINES + 1


class TestLevelFilter:
    """Phase 7B: sink별 독립 레벨 필터."""

    def test_presets_values(self):
        assert LEVEL_PRESETS["All"] == "info"
        assert LEVEL_PRESETS["Warnings+"] == "warn"
        assert LEVEL_PRESETS["Errors only"] == "err"

    def test_priority_order(self):
        assert LEVEL_PRIORITY["info"] == 0
        assert LEVEL_PRIORITY["ok"] == 0
        assert LEVEL_PRIORITY["head"] == 0
        assert LEVEL_PRIORITY["warn"] == 1
        assert LEVEL_PRIORITY["err"] == 2

    def test_warn_level_filters_info_ok(self, qapp):
        logger = SystemLogger()
        te = QTextEdit()
        logger.add_sink(te, min_level="warn")

        logger.info("info-msg")
        logger.ok("ok-msg")
        logger.warn("warn-msg")
        logger.error("err-msg")

        text = te.toPlainText()
        assert "info-msg" not in text
        assert "ok-msg" not in text
        assert "warn-msg" in text
        assert "err-msg" in text

    def test_err_level_filters_all_others(self, qapp):
        logger = SystemLogger()
        te = QTextEdit()
        logger.add_sink(te, min_level="err")

        logger.info("info")
        logger.warn("warn")
        logger.error("err")

        text = te.toPlainText()
        assert "info" not in text
        assert "warn" not in text
        assert "err" in text

    def test_set_sink_level_dynamic(self, qapp):
        logger = SystemLogger()
        te = QTextEdit()
        logger.add_sink(te)  # default info

        logger.set_sink_level(te, "err")
        logger.info("filtered")
        assert "filtered" not in te.toPlainText()

        logger.set_sink_level(te, "info")
        logger.info("unfiltered")
        assert "unfiltered" in te.toPlainText()

    def test_set_unknown_level_ignored(self, qapp):
        logger = SystemLogger()
        te = QTextEdit()
        logger.add_sink(te)
        logger.set_sink_level(te, "unknown-level")
        # 변경되지 않아야 함
        assert logger._sinks[0].min_level == "info"


class TestDeadSinkSelfHeal:
    """``_broadcast`` 는 append RuntimeError 를 감지해 해당 싱크를 제거해야 함.

    ``QTextEdit.deleteLater()`` 는 offscreen 환경에서 타이밍이 비결정적이라,
    RuntimeError 자체를 보장하는 **Mock 싱크** 로 동작을 검증한다.
    """

    def test_sink_raising_runtime_error_is_removed(self, qapp):
        logger = SystemLogger()
        te_good = QTextEdit()

        class _DeadTextEdit:
            """C++ 측이 삭제된 QTextEdit 을 흉내낸 Mock — append에서 RuntimeError."""
            def setReadOnly(self, _b): pass
            def document(self):
                class _Doc:
                    def setMaximumBlockCount(self, _n): pass
                return _Doc()
            def append(self, _msg):
                raise RuntimeError("Internal C++ object already deleted.")

        dead = _DeadTextEdit()
        logger.add_sink(te_good)
        logger.add_sink(dead)  # type: ignore[arg-type]
        assert len(logger._sinks) == 2

        logger.info("probe")

        # dead sink 자동 제거, 살아있는 sink 는 수신
        assert len(logger._sinks) == 1
        assert logger._sinks[0].te is te_good
        assert "probe" in te_good.toPlainText()
