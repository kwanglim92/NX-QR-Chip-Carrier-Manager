"""sweep 판정 미니 차트 — 측정 곡선 + 피크 마커 + Lorentzian 피팅 + Set Point 선 + 근거 텍스트.

SKILL 02 (matplotlib Qt 임베드, 앱 테마 색) 패턴. ``show(shape, freqs, amps, set_point)``
로 그리고 ``clear()`` 로 비운다. Zoom In(줌인 100점) / Out(ZoomOut 500점) 데이터는
호출자가 골라 넘긴다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget  # noqa: E402

from src.core.inspection.sweep_shape import SweepShape, lorentzian_curve  # noqa: E402
from src.ui.theme import ACCENT, BG, BG3, FG, FG2, ORANGE, RED, TEAL  # noqa: E402


class SweepVerdictChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._fig = Figure(figsize=(4, 2.4), dpi=100)
        self._fig.patch.set_facecolor(BG)
        self._canvas = FigureCanvasQTAgg(self._fig)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)
        self._ax = self._fig.add_subplot(111)
        self.clear()

    def _style(self, ax):
        ax.set_facecolor(BG)
        ax.tick_params(colors=FG2, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(BG3)
        ax.grid(color=BG3, alpha=0.5, linewidth=0.5)
        ax.set_xlabel("kHz", color=FG2, fontsize=8)
        ax.set_ylabel("nm", color=FG2, fontsize=8)

    def clear(self, message: str = "no sweep data"):
        self._ax.clear()
        self._style(self._ax)
        self._ax.text(0.5, 0.5, message, transform=self._ax.transAxes,
                      ha="center", va="center", color=FG2, fontsize=9)
        self._fig.tight_layout()
        self._canvas.draw_idle()

    def show(self, shape: SweepShape | None, freqs: list[float], amps: list[float],
             set_point: float | None = None, zoomed_out: bool = False):
        if not freqs:
            self.clear()
            return
        ax = self._ax
        ax.clear()
        self._style(ax)
        ax.plot(freqs, amps, color=ACCENT, linewidth=1.6, label="measured")

        if shape is not None and shape.available and not zoomed_out:
            if shape.fit_params:
                ax.plot(freqs, lorentzian_curve(freqs, shape.fit_params), color=TEAL,
                        linewidth=1.0, linestyle="--", label=f"Lorentz R²={shape.fit_r2:.2f}")
            for i in shape.peak_indices:
                if 0 <= i < len(freqs):
                    ax.plot(freqs[i], amps[i], marker="v", color=RED, markersize=8,
                            markerfacecolor="none")
        if shape is not None and shape.available and zoomed_out and shape.side_peak_freq is not None \
                and shape.side_peak_ratio is not None and shape.side_peak_ratio > 0.5:
            ax.axvline(shape.side_peak_freq, color=ORANGE, linewidth=0.8, linestyle=":")
            ax.text(shape.side_peak_freq, max(amps) * 0.95, f"side {shape.side_peak_ratio:.2f}×",
                    color=ORANGE, fontsize=7, ha="left", va="top")
        if set_point is not None:
            ax.axhline(set_point, color=RED, linewidth=0.8)

        if shape is not None and shape.available:
            color = TEAL if shape.score >= 70 else ORANGE if shape.score >= 30 else RED
            text = f"Sweep score {shape.score:.0f}"
            if shape.reasons:
                text += "\n" + "\n".join(shape.reasons)
            ax.text(0.02, 0.97, text, transform=ax.transAxes, ha="left", va="top",
                    color=color, fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor=color, alpha=0.85))
        ax.legend(fontsize=7, loc="upper right", facecolor=BG, edgecolor=BG3, labelcolor=FG)
        self._fig.tight_layout()
        self._canvas.draw_idle()
