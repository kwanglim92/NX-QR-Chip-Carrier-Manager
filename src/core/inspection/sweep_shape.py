"""sweep 곡선 형상 자동 판정 — 수치(txt) 기반, 이미지 비교 아님.

입력: ``Port{P}_{S}.txt``(줌인 100점) 과 ``Port{P}_{S}_ZoomOut.txt``(광대역 500점)의
(Frequency, Amplitude) 열. 아래 네 지표를 0~100 점수로 합산하고, 감점 근거를
``reasons`` 로 남긴다(UI 의 Error 열·차트 오버레이용).

1. **피크 수**      : 최대 진폭의 ``PEAK_MIN_REL`` 이상이고 prominence 가 ``PEAK_PROM_REL``
                       이상인 국소 최대의 개수 (2개 이상 = 이중 피크/어깨)
2. **Lorentzian R²**: ``A(f) = b + (A0-b) / (1 + ((f-f0)/γ)²)`` 를 f0(피크 ±3점)·b·A0·γ
                       격자 탐색(numpy 벡터화)으로 맞춘 결정계수 — 정상 곡선 ≈ 0.97, 어깨/왜곡 < 0.9
3. **비대칭**       : 반높이 교차점까지의 좌/우 거리비 (max/min ≥ 1)
4. **ZoomOut 부피크**: 주피크 ±``SIDE_WINDOW_KHZ`` 밖 최대 진폭 / 주피크 진폭

의존성: numpy (matplotlib 의존성으로 이미 포함). scipy 불필요.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PEAK_MIN_REL = 0.30       # 최대 진폭 대비 국소 최대 최소 높이
PEAK_PROM_REL = 0.08      # 최대 진폭 대비 최소 prominence
SIDE_WINDOW_KHZ = 10.0    # ZoomOut 에서 주피크로 간주하는 반폭
SMOOTH_WINDOW = 3         # 피크 검출 전 이동평균 창(홀수)

# 감점 가중치 (합계 최대 100 초과 → 0 으로 클램프)
PENALTY_EXTRA_PEAK = 35.0
PENALTY_EXTRA_PEAK_MAX = 70.0
PENALTY_FIT_SCALE = 300.0   # (1 - R²) × scale  (0.97→9, 0.90→30, ≤0.85→45)
PENALTY_FIT_MAX = 45.0
ASYM_FREE = 1.15            # 이 비율까지는 감점 없음
PENALTY_ASYM_SCALE = 40.0   # (asym - free) × scale
PENALTY_ASYM_MAX = 20.0
SIDE_PEAK_FREE = 0.5        # 이 비율까지는 감점 없음
PENALTY_SIDE_SCALE = 40.0   # (ratio - free) × scale
PENALTY_SIDE_MAX = 30.0


@dataclass
class SweepShape:
    available: bool = False
    score: float = 0.0
    n_peaks: int = 0
    peak_freq: float | None = None
    peak_amp: float | None = None
    fit_r2: float | None = None
    fit_gamma: float | None = None
    fit_params: dict | None = None        # {f0, a0, base, gamma} — 차트 오버레이용
    asymmetry: float | None = None
    side_peak_ratio: float | None = None
    side_peak_freq: float | None = None
    peak_indices: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.available:
            return "sweep 없음"
        base = f"score {self.score:.0f}"
        return f"{base} ({', '.join(self.reasons)})" if self.reasons else base


def read_sweep_txt(path: str | Path | None) -> tuple[list[float], list[float]]:
    """``Frequency (KHz)\\tAmplitude (nm)`` 표 → (freqs, amps). 없거나 비면 ([], [])."""
    if not path:
        return [], []
    p = Path(path)
    if not p.exists():
        return [], []
    freqs: list[float] = []
    amps: list[float] = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = ln.split()
        if len(parts) < 2:
            continue
        try:
            f, a = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        freqs.append(f)
        amps.append(a)
    return freqs, amps


def _smooth(values: list[float], window: int = SMOOTH_WINDOW) -> list[float]:
    if window <= 1 or len(values) < window:
        return list(values)
    half = window // 2
    out = []
    n = len(values)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        seg = values[lo:hi]
        out.append(sum(seg) / len(seg))
    return out


def _prominence(amps: list[float], i: int) -> float:
    """i 번째 국소 최대의 prominence: 좌/우로 더 높은 점을 만날 때까지의 최저값 중 큰 쪽과의 차."""
    peak = amps[i]
    left_min = peak
    j = i - 1
    while j >= 0 and amps[j] <= peak:
        left_min = min(left_min, amps[j])
        j -= 1
    right_min = peak
    j = i + 1
    while j < len(amps) and amps[j] <= peak:
        right_min = min(right_min, amps[j])
        j += 1
    return peak - max(left_min, right_min)


def find_peaks(amps: list[float], min_rel: float = PEAK_MIN_REL,
               prom_rel: float = PEAK_PROM_REL) -> list[int]:
    """조건을 만족하는 국소 최대 인덱스(평활 후). 평탄 정점은 첫 점 하나만 센다."""
    if len(amps) < 3:
        return []
    sm = _smooth(amps)
    top = max(sm)
    if top <= 0:
        return []
    peaks: list[int] = []
    for i in range(1, len(sm) - 1):
        if sm[i] > sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] >= top * min_rel:
            if _prominence(sm, i) >= top * prom_rel:
                peaks.append(i)
    return peaks


def lorentzian_curve(freqs, params: dict) -> list[float]:
    """``fit_params`` 로 모델 곡선 재생성(차트 오버레이)."""
    f = np.asarray(freqs, dtype=float)
    x = (f - params["f0"]) / params["gamma"]
    return (params["base"] + (params["a0"] - params["base"]) / (1.0 + x * x)).tolist()


def lorentzian_fit(freqs: list[float], amps: list[float]) -> tuple[float | None, float | None, dict | None]:
    """(R², γ, params) — ``A(f) = b + (A0-b) / (1 + ((f-f0)/γ)²)`` 를 격자 탐색으로 맞춘다.

    f0 = 피크 ±3 샘플, b ∈ {0, min/2, min}, A0 = 피크 × {0.95, 1, 1.05}, γ = 로그 격자 49단계.
    점이 5개 미만이거나 진폭이 평탄하면 (None, None, None).
    """
    n = len(freqs)
    if n < 5:
        return None, None, None
    f = np.asarray(freqs, dtype=float)
    a = np.asarray(amps, dtype=float)
    i0 = int(a.argmax())
    a_min = float(a.min())
    if a[i0] - a_min <= 0:
        return None, None, None
    span = float(abs(f[-1] - f[0]))
    if span <= 0:
        return None, None, None
    ss_tot = float(((a - a.mean()) ** 2).sum()) or 1e-12

    f0s = f[max(0, i0 - 3): i0 + 4]
    bases = np.array([0.0, a_min * 0.5, a_min])
    a0s = a[i0] * np.array([0.95, 1.0, 1.05])
    gammas = (span / 8.0) * (1.25 ** (np.arange(-24, 25) / 4.0))

    # broadcasting: (f0, base, a0, gamma, sample)
    F0 = f0s[:, None, None, None, None]
    B = bases[None, :, None, None, None]
    A0 = a0s[None, None, :, None, None]
    G = gammas[None, None, None, :, None]
    x = (f[None, None, None, None, :] - F0) / G
    model = B + (A0 - B) / (1.0 + x * x)
    ss_res = ((a[None, None, None, None, :] - model) ** 2).sum(axis=-1)
    idx = np.unravel_index(int(ss_res.argmin()), ss_res.shape)
    r2 = 1.0 - float(ss_res[idx]) / ss_tot
    params = {"f0": float(f0s[idx[0]]), "base": float(bases[idx[1]]),
              "a0": float(a0s[idx[2]]), "gamma": float(gammas[idx[3]])}
    return r2, params["gamma"], params


def half_width_asymmetry(freqs: list[float], amps: list[float]) -> float | None:
    """반높이 교차점까지 좌/우 거리의 비(max/min). 한쪽이라도 창 안에서 못 찾으면 None."""
    n = len(freqs)
    if n < 5:
        return None
    i0 = max(range(n), key=lambda i: amps[i])
    base = min(amps)
    level = base + (amps[i0] - base) / 2.0
    dists = []
    for step in (-1, 1):
        j = i0
        while 0 <= j + step < n and amps[j + step] > level:
            j += step
        if not (0 <= j + step < n):
            return None
        # 선형 보간
        f1, a1, f2, a2 = freqs[j], amps[j], freqs[j + step], amps[j + step]
        t = (a1 - level) / (a1 - a2) if a1 != a2 else 0.0
        dists.append(abs((f1 + (f2 - f1) * t) - freqs[i0]))
    if min(dists) <= 0:
        return None
    return max(dists) / min(dists)


def side_peak_ratio(freqs: list[float], amps: list[float], main_freq: float | None,
                    window: float = SIDE_WINDOW_KHZ) -> tuple[float | None, float | None]:
    """주피크 ±window 밖 최대 진폭 / 주피크 진폭, 그 주파수. 데이터 없으면 (None, None)."""
    if len(freqs) < 5:
        return None, None
    if main_freq is None:
        i0 = max(range(len(freqs)), key=lambda i: amps[i])
        main_freq = freqs[i0]
    inside = [a for f, a in zip(freqs, amps) if abs(f - main_freq) <= window]
    outside = [(a, f) for f, a in zip(freqs, amps) if abs(f - main_freq) > window]
    if not inside or not outside:
        return None, None
    main_amp = max(inside)
    if main_amp <= 0:
        return None, None
    amp, f = max(outside)
    return amp / main_amp, f


def analyze_sweep(sweep_txt: str | Path | None, zoom_txt: str | Path | None) -> SweepShape:
    """줌인 + ZoomOut txt → SweepShape. 줌인이 없으면 available=False(점수 0)."""
    freqs, amps = read_sweep_txt(sweep_txt)
    shape = SweepShape()
    if len(freqs) < 5:
        return shape

    shape.available = True
    i0 = max(range(len(amps)), key=lambda i: amps[i])
    shape.peak_freq, shape.peak_amp = freqs[i0], amps[i0]
    shape.peak_indices = find_peaks(amps)
    shape.n_peaks = max(1, len(shape.peak_indices))
    shape.fit_r2, shape.fit_gamma, shape.fit_params = lorentzian_fit(freqs, amps)
    shape.asymmetry = half_width_asymmetry(freqs, amps)

    zf, za = read_sweep_txt(zoom_txt)
    shape.side_peak_ratio, shape.side_peak_freq = side_peak_ratio(zf, za, shape.peak_freq)

    penalty = 0.0
    if shape.n_peaks > 1:
        p = min(PENALTY_EXTRA_PEAK * (shape.n_peaks - 1), PENALTY_EXTRA_PEAK_MAX)
        penalty += p
        shape.reasons.append(f"{shape.n_peaks} peaks")
    if shape.fit_r2 is not None:
        p = min((1.0 - shape.fit_r2) * PENALTY_FIT_SCALE, PENALTY_FIT_MAX)
        if p >= 5.0:
            shape.reasons.append(f"fit R2 {shape.fit_r2:.2f}")
        penalty += max(0.0, p)
    if shape.asymmetry is not None:
        p = min(max(0.0, shape.asymmetry - ASYM_FREE) * PENALTY_ASYM_SCALE, PENALTY_ASYM_MAX)
        if p >= 5.0:
            shape.reasons.append(f"asym {shape.asymmetry:.2f}")
        penalty += p
    if shape.side_peak_ratio is not None and shape.side_peak_ratio > SIDE_PEAK_FREE:
        p = min((shape.side_peak_ratio - SIDE_PEAK_FREE) * PENALTY_SIDE_SCALE, PENALTY_SIDE_MAX)
        if p >= 5.0:
            shape.reasons.append(
                f"side peak {shape.side_peak_ratio:.2f}× @{shape.side_peak_freq:.0f}kHz")
        penalty += p

    shape.score = max(0.0, min(100.0, 100.0 - penalty))
    return shape
