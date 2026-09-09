"""Vision 파손 자동 판정 — pickUp 이미지 실루엣 + Vision.txt Match Score.

이미지(그레이, 밝은 배경 위 어두운 칩 몸체가 상단에, 캔틸레버가 아래로 매달림)에서
1. 어두운 픽셀 비율이 ``BODY_ROW_FRAC`` 이상인 마지막 행 = 칩 몸체 하단 기준선
2. 기준선 아래 외곽선 구간(``ROOT_SKIP_FRAC``)을 건너뛴 뒤 ``ROOT_ROWS_FRAC`` 까지의 행에서
   어두운 열 범위 = 캔틸레버 밴드
3. 밴드(±여유) 안 마지막 어두운 행 − 기준선 = **팁 길이(px)**, 밴드 안 어두운 픽셀 수 = 면적
을 구한다. 판정은 기준 슬롯 대비 **비율**(길이·면적)로 하므로 해상도에 무관하다.
기준 슬롯이 없으면 이미지 높이 대비 길이(``MIN_LENGTH_FRAC``)로 대신 판정한다.

의존성: Pillow + numpy (둘 다 기존 requirements 에 포함).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DARK_THRESHOLD = 110        # 0~255, 이보다 어두우면 '몸체/캔틸레버'
BODY_ROW_FRAC = 0.5         # 행의 어두운 비율이 이 이상이면 몸체 행
ROOT_SKIP_FRAC = 0.03       # 기준선 직하 이 비율(높이 대비)은 칩 하단 외곽선이라 건너뜀
ROOT_ROWS_FRAC = 0.10       # 그 다음 이 비율까지의 행에서 캔틸레버 뿌리 열을 찾음
BAND_MARGIN_FRAC = 0.02     # 밴드 좌우 여유(폭 대비)
MIN_ROW_DARK_PX = 2         # 행을 '캔틸레버 있음' 으로 볼 최소 어두운 픽셀 수
MIN_LENGTH_RATIO = 0.7      # 기준 대비 길이 비율 미만 → 파손
MIN_AREA_RATIO = 0.6        # 기준 대비 면적 비율 미만 → 파손
MIN_LENGTH_FRAC = 0.15      # 기준 없음: 이미지 높이 대비 길이 미만 → 파손


@dataclass
class TipMeasure:
    image_height: int
    image_width: int
    baseline_row: int
    band: tuple[int, int]
    length_px: int
    area_px: int

    @property
    def length_frac(self) -> float:
        return self.length_px / self.image_height if self.image_height else 0.0


@dataclass
class VisionCheck:
    available: bool = False
    broken: bool = False
    length_px: int | None = None
    length_ratio: float | None = None     # 기준 대비 (기준 없으면 None)
    area_ratio: float | None = None
    match_score: float | None = None
    match_ok: bool | None = None          # min_match 미지정이면 None
    reasons: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.available:
            return "vision 없음"
        head = "BROKEN" if self.broken else "OK"
        return f"{head} ({', '.join(self.reasons)})" if self.reasons else head


def load_gray(path: str | Path) -> np.ndarray | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return np.asarray(im.convert("L"), dtype=np.uint8)
    except Exception:
        return None


def measure_tip(image: np.ndarray | str | Path | None,
                dark_threshold: int = DARK_THRESHOLD) -> TipMeasure | None:
    """이미지에서 팁(캔틸레버) 길이·면적 측정. 몸체 기준선을 못 찾으면 None."""
    if image is None:
        return None
    arr = image if isinstance(image, np.ndarray) else load_gray(image)
    if arr is None or arr.ndim != 2 or arr.size == 0:
        return None
    h, w = arr.shape
    dark = arr < dark_threshold
    row_frac = dark.mean(axis=1)
    body_rows = np.flatnonzero(row_frac >= BODY_ROW_FRAC)
    if body_rows.size == 0:
        return None
    baseline = int(body_rows.max())
    below = dark[baseline + 1:]
    if below.shape[0] == 0:
        return TipMeasure(h, w, baseline, (0, w - 1), 0, 0)

    skip = int(h * ROOT_SKIP_FRAC)
    root_rows = max(skip + 1, int(h * ROOT_ROWS_FRAC))
    root_cols = np.flatnonzero(below[skip:root_rows].any(axis=0))
    if root_cols.size == 0:
        return TipMeasure(h, w, baseline, (0, w - 1), 0, 0)
    margin = max(1, int(w * BAND_MARGIN_FRAC))
    c0 = max(0, int(root_cols.min()) - margin)
    c1 = min(w - 1, int(root_cols.max()) + margin)
    band = below[:, c0:c1 + 1]
    row_counts = band.sum(axis=1)
    rows_with_tip = np.flatnonzero(row_counts >= MIN_ROW_DARK_PX)
    length = int(rows_with_tip.max()) + 1 if rows_with_tip.size else 0
    area = int(band.sum())
    return TipMeasure(h, w, baseline, (c0, c1), length, area)


def check_vision(pickup_image: str | Path | None, match_score: float | None,
                 reference: TipMeasure | None = None,
                 min_match: float | None = None,
                 min_length_ratio: float = MIN_LENGTH_RATIO,
                 min_area_ratio: float = MIN_AREA_RATIO) -> VisionCheck:
    """pickUp 이미지 + Match Score → VisionCheck.

    ``reference`` 는 기준 슬롯의 ``measure_tip`` 결과. 없으면 이미지 높이 대비로 판정.
    ``min_match`` 를 주면 Match Score 미달을 reasons 에 남기고 ``match_ok`` 를 채운다
    (파손 판정과는 별개 — 등급 사다리의 ``vision_match`` 항목이 사용).
    """
    vc = VisionCheck(match_score=match_score)
    if min_match is not None and match_score is not None:
        vc.match_ok = match_score >= min_match
        if not vc.match_ok:
            vc.reasons.append(f"match {match_score:.1f}%")

    if not pickup_image or not Path(pickup_image).exists():
        vc.reasons.append("no image")
        return vc
    m = measure_tip(pickup_image)
    if m is None:
        vc.reasons.append("body not found")
        return vc

    vc.available = True
    vc.length_px = m.length_px
    if reference is not None and reference.length_px > 0:
        vc.length_ratio = m.length_px / reference.length_px
        vc.area_ratio = (m.area_px / reference.area_px) if reference.area_px else None
        if vc.length_ratio < min_length_ratio:
            vc.broken = True
            vc.reasons.append(f"tip length {vc.length_ratio:.0%} of ref")
        elif vc.area_ratio is not None and vc.area_ratio < min_area_ratio:
            vc.broken = True
            vc.reasons.append(f"tip area {vc.area_ratio:.0%} of ref")
    else:
        if m.length_frac < MIN_LENGTH_FRAC:
            vc.broken = True
            vc.reasons.append(f"tip length {m.length_frac:.0%} of image")
    return vc
