"""비동기 OCR 실행기 — QThreadPool 기반 (Phase 7C).

Manual 모드에서 이미지를 한 번에 여러 장 드롭할 때 ``extract_measurements`` 를
순차 호출하면 장당 수백 ms × N = UI 동결. ``OcrRunnable`` 을 ``QThreadPool`` 에
넣어 병렬화하고, 결과는 Qt 시그널을 통해 **메인 스레드에서** 수신된다.

스레드 안전성
-------------
- ``extract_measurements`` 내부는 순수 Python + pytesseract subprocess로
  완전 독립. 각 Runnable 은 자신만의 PIL ``Image`` 인스턴스를 생성하고
  별도의 ``tesseract.exe`` 서브프로세스를 스폰한다.
- 결과 시그널 ``finished`` 는 Qt 이벤트 루프를 통해 **메인 스레드** 슬롯으로
  queued delivery 된다. DB 쓰기·QWidget 갱신은 모두 메인 스레드에서 일어난다.

배치 추적
---------
``batch_id`` 로 한 번의 드롭에 해당하는 Runnable 집합을 식별한다. 호출자는
배치별 카운터 (total / done / success) 를 유지해 "N/M 완료" 요약 로그를
최종에만 한 번 찍을 수 있다.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.core.image_parser import MeasurementReading, extract_measurements

logger = logging.getLogger(__name__)


class OcrSignals(QObject):
    """``OcrRunnable`` 이 메인 스레드로 결과를 넘기기 위한 시그널 컨테이너.

    QRunnable 자체는 QObject가 아니라 시그널을 선언할 수 없어 별도 객체에 위임.
    """

    # (slot_index, MeasurementReading, batch_id)
    finished = Signal(int, object, str)


class OcrRunnable(QRunnable):
    """단일 이미지에 대한 OCR 작업을 ``QThreadPool`` 에서 실행.

    Parameters
    ----------
    slot_index
        Manual 모드 카드/슬롯 식별자. 결과가 도착하면 호출자가 이 인덱스로
        카드 UI와 ``SlotData`` 를 매칭한다.
    image_path
        분석할 이미지 파일의 절대 경로.
    roi
        해당 이미지의 해상도에 맞는 ROI dict. None이면 ``extract_measurements``
        의 코드 상수 ``ROI`` fallback.
    batch_id
        한 번의 드롭에 해당하는 Runnable 집합을 묶는 식별자 (UUID 권장).
    """

    def __init__(
        self,
        slot_index: int,
        image_path: str,
        roi: dict | None,
        batch_id: str,
    ):
        super().__init__()
        self.signals = OcrSignals()
        self.slot_index = slot_index
        self.image_path = image_path
        self.roi = roi
        self.batch_id = batch_id
        # QThreadPool이 실행 후 자동 삭제
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """워커 스레드 진입점. ``extract_measurements`` 호출 + 결과 시그널 방출."""
        try:
            reading = extract_measurements(self.image_path, roi=self.roi)
        except Exception as e:
            # 예기치 않은 예외도 조용한 fallback — 메인 스레드로 전파하지 않음
            logger.debug(
                "OcrRunnable: extract_measurements 예외 (slot=%d): %s",
                self.slot_index, e,
            )
            reading = MeasurementReading()
        # 시그널은 Qt가 메인 스레드로 queued delivery 함
        self.signals.finished.emit(self.slot_index, reading, self.batch_id)
