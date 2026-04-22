"""Tesseract 포터블 바이너리 경로 설정 (F-14).

프로젝트 루트 하위 ``third_party/tesseract/tesseract.exe`` 가 존재하면
``pytesseract.pytesseract.tesseract_cmd`` 에 해당 절대경로를 바인드한다.
시스템 전역 설치된 Tesseract가 있더라도 포터블 버전이 우선한다.

없으면 조용히 넘어가고(로그만 남김), ``image_parser.extract_measurements`` 가
자연스럽게 ``MeasurementReading(None, None)`` 을 반환 → 수기 입력 폴백.

디렉터리 구조 (권장)
--------------------
::

    third_party/tesseract/
    ├── tesseract.exe
    ├── liblept-5.dll           (혹은 UB Mannheim 빌드 동봉 DLL들)
    ├── libtesseract-5.dll
    ├── LICENSE                 (Apache-2.0)
    └── tessdata/
        └── eng.traineddata
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# 프로젝트 루트 기준 포터블 위치
_PORTABLE_SUBDIR = Path("third_party") / "tesseract"
_EXE_NAME = "tesseract.exe" if os.name == "nt" else "tesseract"

# 포터블 tessdata 경로 — configure_tesseract() 실행 후 설정됨.
# 한글/공백이 포함된 경로 환경에서 ``TESSDATA_PREFIX`` 환경변수가 Tesseract에
# 인식되지 않거나 pytesseract의 ``shlex.split`` 이 따옴표·공백을 오인식하는
# 이슈를 함께 우회하기 위해, Windows에서는 **8.3 short path** 로 변환한 뒤
# OCR 호출 시 ``--tessdata-dir`` 플래그로 직접 전달한다. ``get_tessdata_dir()`` 로 조회.
_tessdata_dir: str | None = None


def _to_short_path(path: Path) -> str:
    """Windows 에서 주어진 경로의 8.3 short path 반환 (ASCII/공백없음 보장 경향).

    non-Windows 이거나 short path 생성 실패 시 원래 문자열 경로 반환.
    """
    if os.name != "nt":
        return str(path)
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        rc = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 260)
        if rc and buf.value:
            return buf.value
    except Exception as e:  # pragma: no cover - ctypes 실패는 드묾
        logger.debug("GetShortPathNameW 실패: %s", e)
    return str(path)


def get_tessdata_dir() -> str | None:
    """``configure_tesseract()`` 가 성공적으로 설정한 tessdata 디렉터리 경로.

    Windows 에서는 short path 이미 적용된 형태로 반환된다 — pytesseract config
    문자열에 공백 없이 안전하게 삽입 가능.
    """
    return _tessdata_dir


def _project_root() -> Path:
    """실행 중인 ``main.py`` 가 위치한 프로젝트 루트 추정.

    - 개발 환경: 이 파일이 ``<root>/src/core/tesseract_setup.py`` 에 있음
    - 패키징 환경(예: PyInstaller 동결): ``sys.executable`` 디렉터리가 루트
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def configure_tesseract() -> bool:
    """포터블 Tesseract를 pytesseract에 연결.

    Returns
    -------
    bool
        성공적으로 포터블 경로를 설정했으면 True.
        ``pytesseract`` 미설치 / 바이너리 미존재면 False (에러 전파 X).
    """
    try:
        import pytesseract  # type: ignore
    except ImportError:
        logger.info("pytesseract 미설치 — OCR 기능 비활성화 (수기 입력만 가능)")
        return False

    root = _project_root()
    portable_exe = root / _PORTABLE_SUBDIR / _EXE_NAME
    tessdata = root / _PORTABLE_SUBDIR / "tessdata"

    if not portable_exe.exists():
        logger.info(
            "포터블 Tesseract 미발견 (%s) — 시스템 PATH의 tesseract 사용 시도",
            portable_exe,
        )
        return False

    pytesseract.pytesseract.tesseract_cmd = str(portable_exe)
    if tessdata.exists():
        # TESSDATA_PREFIX 환경변수: 대부분의 환경에선 이것만으로 충분하지만,
        # Windows + 한글/비-ASCII 경로 조합에서는 Tesseract가 CP949↔UTF-8
        # 변환에 실패해 무시된다. image_parser가 ``--tessdata-dir`` 로 직접
        # 덮어써도 되도록 ``_tessdata_dir`` 모듈 상태를 노출한다.
        os.environ["TESSDATA_PREFIX"] = str(tessdata.parent)
        # Windows에서 pytesseract의 shlex.split 은 공백 포함 경로를 올바르게
        # 처리하지 못하므로 8.3 short path 로 저장 — 한글 문자는 남지만
        # 공백이 제거되어 shlex 토큰화가 깨지지 않는다.
        global _tessdata_dir
        _tessdata_dir = _to_short_path(tessdata)
    logger.info("포터블 Tesseract 설정: %s", portable_exe)
    return True
