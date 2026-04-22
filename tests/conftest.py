"""pytest 공용 fixture (Phase 7D).

제공 fixture:
- ``qapp`` : session 스코프의 ``QApplication`` (offscreen)
- ``db_conn`` : function 스코프의 in-memory SQLite connection (init_db 완료)
- ``sample_afm_image`` : AFM 측정 팝업 샘플 이미지의 절대 경로 — 없으면 skip
- ``tesseract_ready`` : Tesseract 바이너리가 설정되면 True, 아니면 False (``ocr`` 마커 skip 조건)

공통 상수:
- ``SAMPLE_FREQ_EXPECTED``, ``SAMPLE_Q_EXPECTED`` — 샘플 이미지의 정답값
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Qt offscreen 강제 — CI/서버/개발 모두 안전
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 프로젝트 루트를 sys.path에 추가 (pytest.ini 의 pythonpath 와 이중 안전망)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ─── 샘플 이미지 + 기대값 상수 ───

SAMPLE_AFM_IMAGE = (
    PROJECT_ROOT
    / "P2602074_CDT-NCHR & AD-42-AS_QR(01.09)"
    / "1.jpg"
)
SAMPLE_FREQ_EXPECTED = 396.04
SAMPLE_Q_EXPECTED = 710.682
SAMPLE_IMAGE_SIZE = (722, 479)


# ─── Fixtures ───


@pytest.fixture(scope="session")
def qapp():
    """세션 단위 QApplication (offscreen). 모든 Qt 위젯 테스트의 기반."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
    # 세션 종료 시 명시적 cleanup 불필요 (pytest가 프로세스 종료 처리)


@pytest.fixture
def db_conn():
    """함수 단위 in-memory SQLite 연결 + init_db 완료."""
    from src.core import database as db
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_afm_image():
    """실제 AFM 팝업 샘플 이미지 경로. 없으면 테스트 skip."""
    if not SAMPLE_AFM_IMAGE.exists():
        pytest.skip(f"샘플 이미지 없음: {SAMPLE_AFM_IMAGE}")
    return str(SAMPLE_AFM_IMAGE)


@pytest.fixture(scope="session")
def tesseract_ready():
    """Tesseract 포터블 바이너리가 설정 가능한지 확인. ocr 테스트의 skip 조건."""
    from src.core.tesseract_setup import configure_tesseract
    return configure_tesseract()


@pytest.fixture
def require_ocr(tesseract_ready):
    """``ocr`` 마커가 붙은 테스트에서 Tesseract 없으면 skip."""
    if not tesseract_ready:
        pytest.skip("Tesseract 바이너리 없음 — OCR 테스트 skip")
