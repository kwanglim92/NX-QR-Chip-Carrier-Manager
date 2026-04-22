"""Manual 모드 이미지 OCR — Frequency / Q-factor 자동 추출 (F-14).

AFM 측정 결과 팝업의 스크린샷(고정 레이아웃) 우측 패널에서 ``Frequency`` 와
``Q`` 숫자 값을 Tesseract OCR로 읽어 Manual 모드 입력 폼에 pre-fill 한다.

이 모듈은 **조용한 fallback** 정책을 따른다:

- Tesseract 바이너리 미설치 / ``pytesseract`` 미설치 / Pillow 미설치 /
  이미지 로드 실패 / OCR 결과 파싱 실패 → 예외를 전파하지 않고
  ``MeasurementReading(None, None)`` 을 반환한다.
- 호출자(manual_import_mixin)는 None 값이면 기존 수기 입력 흐름을 그대로
  유지하면 된다.

ROI 좌표
--------
샘플 이미지 2장 기준의 **플레이스홀더 좌표**가 ``ROI`` 딕셔너리에 선언되어
있다. 실측이 완료되면 해당 dict 만 갱신하면 된다 — 다른 코드는 변경 불필요.

OCR 설정
--------
``--psm 7`` (단일 텍스트 라인) + ``tessedit_char_whitelist=0123456789.`` 로
숫자와 소수점만 인식 대상으로 제한해 오인식 가능성을 원천 차단한다.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MeasurementReading:
    """이미지에서 추출한 측정값.

    두 필드 모두 None이면 "추출 실패 → 수기 입력 폴백" 신호.
    """
    frequency: float | None = None   # kHz
    q_factor: float | None = None


# ─── ROI (픽셀 좌표) ─────────────────────────────────────────────────────────
# 실측 기준 — **722 × 479** 해상도 AFM 측정 팝업 스크린샷 (2026-04-22 샘플 기준).
# 우측 결과 패널의 "Frequency (kHz)" / "Q" 값 박스 위치.
#
# 형식: {"frequency": (x, y, w, h), "q_factor": (x, y, w, h)}
#   x, y: 좌상단 기준 픽셀
#   w, h: 박스 너비/높이
#
# 해상도가 다른 이미지가 들어오면 ``_ocr_single_roi`` 가 ROI 범위 초과를 감지해
# UI 로그에 경고 메시지를 남긴다. 새 해상도 대응이 필요하면 이 dict만 갱신.
ROI: dict[str, tuple[int, int, int, int]] = {
    # (x, y, width, height)
    "frequency": (595, 95, 120, 30),
    "q_factor":  (595, 175, 120, 30),
}

# Tesseract 설정: 단일 텍스트 라인 + 숫자/소수점 화이트리스트
_OCR_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789."

# OCR 결과에서 숫자 하나만 정확히 뽑기 위한 패턴
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Phase 7A-A3: OCR 결과 범위 검증 — AFM 프로브 측정의 일반적 범위를
# 벗어나는 값은 ROI 오차로 인한 오인식(예: 두 박스 경계가 겹쳐 합쳐진
# 숫자)으로 간주하고 None으로 폐기. 그러면 Manual 흐름은 자연스럽게
# 수기 입력 fallback으로 전환된다.
_FREQ_RANGE = (50.0, 5000.0)   # kHz (10 kHz 이하/5 MHz 이상은 AFM 범위 밖)
_Q_RANGE = (10.0, 10000.0)


def _in_range(value: float | None, lo: float, hi: float) -> bool:
    return value is not None and lo <= value <= hi


def extract_measurements(
    image_path: str,
    roi: dict[str, tuple[int, int, int, int]] | None = None,
) -> MeasurementReading:
    """이미지에서 Frequency/Q 값을 추출.

    Parameters
    ----------
    image_path
        분석할 이미지 파일의 절대 경로.
    roi
        사용자가 Calibrator로 조정한 ROI dict. None이면 모듈 상수 ``ROI`` 를
        fallback으로 사용. Manual 모드는 ``ocr_settings.load_roi(conn)`` 결과를
        주입한다 (DB 없으면 None → 코드 기본값).

    Returns
    -------
    MeasurementReading
        성공 시 각 필드에 float 값을, 실패 시 None.
        **두 필드 모두 독립적으로** 성공/실패 판정되므로, 한쪽만 성공하면
        그 쪽만 pre-fill 할 수 있다.
    """
    active_roi = roi if roi else ROI

    # 지연 임포트 — 의존성 미설치 환경에서도 모듈 임포트 가능하게
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        logger.debug("Pillow 미설치 — OCR 비활성화")
        return MeasurementReading()

    try:
        import pytesseract  # type: ignore
    except ImportError:
        logger.debug("pytesseract 미설치 — OCR 비활성화")
        return MeasurementReading()

    try:
        img = Image.open(image_path)
    except (FileNotFoundError, OSError) as e:
        logger.debug("OCR: 이미지 로드 실패 %r: %s", image_path, e)
        return MeasurementReading()

    # ROI 범위 사전 체크 — 해상도가 ROI 가정과 다르면 UI 수준 경고
    W, H = img.size
    for name, (x, y, w, h) in active_roi.items():
        if x + w > W or y + h > H:
            logger.warning(
                "OCR: ROI %s=%s 가 이미지 범위 초과 (이미지 %dx%d). "
                "Manual 탭의 'Calibrate ROI…' 버튼으로 좌표를 재조정하세요.",
                name, (x, y, w, h), W, H,
            )
            return MeasurementReading()

    freq = _ocr_single_roi(img, active_roi["frequency"], pytesseract)
    q = _ocr_single_roi(img, active_roi["q_factor"], pytesseract)

    # Phase 7A-A3: 범위 검증 — 오인식으로 인한 비상식적 값 폐기
    if not _in_range(freq, *_FREQ_RANGE):
        if freq is not None:
            logger.debug("OCR: Frequency %s가 허용 범위 %s 밖 — 폐기", freq, _FREQ_RANGE)
        freq = None
    if not _in_range(q, *_Q_RANGE):
        if q is not None:
            logger.debug("OCR: Q %s가 허용 범위 %s 밖 — 폐기", q, _Q_RANGE)
        q = None

    if freq is None and q is None:
        logger.debug("OCR: 두 ROI 모두 숫자 추출 실패 — 수기 입력 폴백")
    elif freq is None:
        logger.debug("OCR: Frequency 추출 실패 (Q만 성공)")
    elif q is None:
        logger.debug("OCR: Q 추출 실패 (Frequency만 성공)")
    else:
        logger.debug("OCR: Freq=%s, Q=%s", freq, q)

    return MeasurementReading(frequency=freq, q_factor=q)


def _ocr_single_roi(img, roi: tuple[int, int, int, int], pytesseract) -> float | None:
    """단일 ROI를 크롭하고 OCR로 숫자 추출. 실패 시 None (예외 전파 X)."""
    try:
        x, y, w, h = roi
        crop = img.crop((x, y, x + w, y + h))

        # 한글/공백 포함 경로 환경에서도 안전하도록 ``--tessdata-dir`` 로 직접 전달.
        # ``tesseract_setup.get_tessdata_dir()`` 는 Windows에서 8.3 short path로
        # 반환하므로 공백이 없어 따옴표/이스케이프가 필요 없다. pytesseract의
        # shlex.split 파싱이 안전하게 토큰화한다.
        config = _OCR_CONFIG
        try:
            from src.core.tesseract_setup import get_tessdata_dir
            td = get_tessdata_dir()
            if td:
                config = f"--tessdata-dir {td} {_OCR_CONFIG}"
        except ImportError:
            pass

        raw = pytesseract.image_to_string(crop, config=config)
    except Exception as e:  # pytesseract.TesseractNotFoundError 등 포함
        logger.debug("OCR 실행 실패 (ROI=%s): %s", roi, e)
        return None

    # 숫자 패턴만 정확히 1개 추출 — 여러 개 있으면 첫 번째 사용
    matches = _NUMBER_RE.findall(raw)
    if not matches:
        return None
    try:
        return float(matches[0])
    except ValueError:
        return None
