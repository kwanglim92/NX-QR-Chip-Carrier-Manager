"""업로드 전 QR 버전 게이트 — 2.0 외 버전이 섞이면 차단, 해독 불가는 경고 1회 후 진행 (실서버 호출 없음)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.ui.controllers import upload_mixin as mod
from tests.test_upload_mixin import _NoSig, _ms, host  # noqa: F401 — host fixture 재사용


class _FakeThread:
    started_count = 0

    def __init__(self):
        self.started = _NoSig()
        self.finished = _NoSig()

    def isRunning(self): return False
    def start(self): _FakeThread.started_count += 1
    def quit(self): pass
    def deleteLater(self): pass


@pytest.fixture
def no_thread(monkeypatch):
    _FakeThread.started_count = 0
    monkeypatch.setattr(mod, "QThread", _FakeThread)
    monkeypatch.setattr(mod._UploadWorker, "moveToThread", lambda self, t: None)
    return _FakeThread


def _temp_csvs() -> set[str]:
    return {p.name for p in Path(tempfile.gettempdir()).glob("*.csv")}


def test_start_upload_blocked_when_any_qr21(host, no_thread, monkeypatch):
    warnings = []
    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: warnings.append((a[1], a[2])))
    before = _temp_csvs()
    host.measurement_set = _ms("2680002971", "2684080D7C", "2684080D7D")
    host._start_upload(with_images=False)
    assert no_thread.started_count == 0
    assert len(warnings) == 1 and warnings[0][0] == "업로드 차단" and "QR 2.1: 2건" in warnings[0][1]
    assert host.logger.lines[-1][0] == "error" and "QR 2.1: 2건" in host.logger.lines[-1][1]
    assert _temp_csvs() == before                 # 임시 CSV 를 만들지 않았다
    assert host.btn_server_status.text() == "● Server 미로그인"


def test_start_upload_warns_once_for_undecodable_and_proceeds(host, no_thread, monkeypatch):
    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: pytest.fail("경고창이 뜨면 안 된다"))
    host.measurement_set = _ms("2680002971", "QR-001", "ABC")
    host._start_upload(with_images=False)
    assert no_thread.started_count == 1
    warns = [m for k, m in host.logger.lines if k == "warn" and "해독 불가" in m]
    assert warns == ["QR 형식 해독 불가 2건 (10자리 16진수 아님) — 그대로 업로드합니다"]
    assert host.btn_server_status.text() == "● Server 업로드 중"
    os.unlink(host._upload_worker._csv_path)


def test_start_upload_all_qr20_has_no_warning(host, no_thread, monkeypatch):
    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: pytest.fail("경고창이 뜨면 안 된다"))
    host.measurement_set = _ms("2680002971", "2680086CB6")
    host._start_upload(with_images=False)
    assert no_thread.started_count == 1
    assert not any(k in ("warn", "error") for k, _ in host.logger.lines)
    os.unlink(host._upload_worker._csv_path)
