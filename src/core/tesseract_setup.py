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
# tessdata 위치 전달 전략(Windows 한글/공백 경로 대응):
#   1순위: 공백 없는 8.3 short path 면 OCR 호출 시 ``--tessdata-dir`` 로 직접 전달.
#   폴백: 8.3 비활성 등으로 경로에 공백이 남으면 ``--tessdata-dir`` 을 생략하고
#         configure_tesseract 가 설정한 ``TESSDATA_PREFIX`` 환경변수에 위임한다
#         (환경변수는 pytesseract 의 shlex.split 파싱을 거치지 않아 공백에 안전).
# ``get_tessdata_dir()`` 로 short path 를 조회.
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
        # TESSDATA_PREFIX 는 tessdata 의 부모 디렉터리를 가리킨다(Tesseract 가
        # 'tessdata/' 를 덧붙여 탐색). 8.3 short path 로 설정해 공백/비-ASCII
        # 경로에서도 안정적으로 인식되게 한다 — 이는 공백 경로(8.3 비활성)라
        # ``--tessdata-dir`` 을 config 문자열로 전달할 수 없을 때의 신뢰 가능한
        # 폴백 경로다(환경변수는 shlex 파싱을 거치지 않아 공백에 안전).
        os.environ["TESSDATA_PREFIX"] = _to_short_path(tessdata.parent)
        # 공백 없는 short path 면 image_parser 가 ``--tessdata-dir`` 로 직접 전달.
        global _tessdata_dir
        _tessdata_dir = _to_short_path(tessdata)
    logger.info("포터블 Tesseract 설정: %s", portable_exe)
    return True
