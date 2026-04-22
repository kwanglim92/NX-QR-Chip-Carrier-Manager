"""생산 실적 + 품질 분석 통계 대시보드 — Matplotlib 차트 + 요약 카드."""
from __future__ import annotations

import math
import statistics as st
from collections import defaultdict

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QGridLayout,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from src.ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, ORANGE, PURPLE, RED

# Catppuccin chart palette
CHART_COLORS = [ACCENT, GREEN, ORANGE, PURPLE, RED, "#f5c2e7", "#94e2d5", "#f9e2af"]


class StatsDashboard(QWidget):
    period_changed = Signal()
    probe_filter_changed = Signal()

    PERIODS = ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"]
    PERIOD_MAP = {
        "Daily": "daily",
        "Weekly": "weekly",
        "Monthly": "monthly",
        "Quarterly": "quarterly",
        "Yearly": "yearly",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG}; }}")
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        scroll.setWidget(content)

        # ── Filter row ──
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Period:"))
        self._period_combo = QComboBox()
        self._period_combo.addItems(self.PERIODS)
        self._period_combo.setFixedWidth(140)
        self._period_combo.currentTextChanged.connect(lambda _: self.period_changed.emit())
        filter_row.addWidget(self._period_combo)

        filter_row.addSpacing(16)
        filter_row.addWidget(QLabel("Probe Type:"))
        self._probe_combo = QComboBox()
        self._probe_combo.addItem("All")
        self._probe_combo.setFixedWidth(160)
        self._probe_combo.currentTextChanged.connect(lambda _: self.probe_filter_changed.emit())
        filter_row.addWidget(self._probe_combo)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── Today Summary (3 cards) ──
        layout.addWidget(self._make_section_label("Today"))

        today_row = QHBoxLayout()
        today_row.setSpacing(8)
        self._card_today_sets = self._make_summary_card("Today Sets", "0")
        self._card_today_slots = self._make_summary_card("Today Slots", "0")
        self._card_today_rate = self._make_summary_card("Today Complete %", "-")
        for card in [self._card_today_sets, self._card_today_slots, self._card_today_rate]:
            today_row.addWidget(card)
        # 우측 여백 (5 카드 row와 너비 맞춤)
        today_row.addStretch()
        layout.addLayout(today_row)

        # ── Overall Summary cards (5) ──
        layout.addWidget(self._make_section_label("Overall"))

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self._card_sets = self._make_summary_card("Total Sets", "0")
        self._card_slots = self._make_summary_card("Total Slots", "0")
        self._card_avg_freq = self._make_summary_card("Avg Frequency", "-")
        self._card_avg_q = self._make_summary_card("Avg Q Factor", "-")
        self._card_trend = self._make_summary_card("Trend", "-")

        for card in [self._card_sets, self._card_slots, self._card_avg_freq,
                     self._card_avg_q, self._card_trend]:
            cards_row.addWidget(card)
        layout.addLayout(cards_row)

        # ── Section: Production ──
        layout.addWidget(self._make_section_label("Production"))

        prod_grid = QGridLayout()
        prod_grid.setSpacing(8)

        self._fig_production = Figure(figsize=(5, 3), dpi=100)
        self._canvas_production = FigureCanvasQTAgg(self._fig_production)
        prod_grid.addWidget(self._canvas_production, 0, 0)

        self._fig_stacked = Figure(figsize=(5, 3), dpi=100)
        self._canvas_stacked = FigureCanvasQTAgg(self._fig_stacked)
        prod_grid.addWidget(self._canvas_stacked, 0, 1)

        layout.addLayout(prod_grid)

        # ── Section: Quality Analysis ──
        layout.addWidget(self._make_section_label("Quality Analysis"))

        quality_grid = QGridLayout()
        quality_grid.setSpacing(8)

        self._fig_freq_spc = Figure(figsize=(5, 3), dpi=100)
        self._canvas_freq_spc = FigureCanvasQTAgg(self._fig_freq_spc)
        quality_grid.addWidget(self._canvas_freq_spc, 0, 0)

        self._fig_q_spc = Figure(figsize=(5, 3), dpi=100)
        self._canvas_q_spc = FigureCanvasQTAgg(self._fig_q_spc)
        quality_grid.addWidget(self._canvas_q_spc, 0, 1)

        self._fig_freq_hist = Figure(figsize=(5, 3), dpi=100)
        self._canvas_freq_hist = FigureCanvasQTAgg(self._fig_freq_hist)
        quality_grid.addWidget(self._canvas_freq_hist, 1, 0)

        self._fig_q_hist = Figure(figsize=(5, 3), dpi=100)
        self._canvas_q_hist = FigureCanvasQTAgg(self._fig_q_hist)
        quality_grid.addWidget(self._canvas_q_hist, 1, 1)

        layout.addLayout(quality_grid)

        # ── Stats table ──
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Period", "Probe Type", "Sets", "Slots", "Complete", "Rate"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setMaximumHeight(200)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, 6):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG}; color: {FG}; border: 1px solid {BG3};
                gridline-color: {BG3}; font-size: 13px;
            }}
            QTableWidget::item {{ padding: 4px 8px; }}
            QTableWidget::item:alternate {{ background: {BG2}; }}
            QHeaderView::section {{
                background: {BG2}; color: {ACCENT}; border: 1px solid {BG3};
                padding: 6px; font-weight: bold; font-size: 13px;
            }}
        """)
        layout.addWidget(self._table)

    # ─── Section Label ───

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(f"  {text}")
        lbl.setStyleSheet(
            f"color: {FG2}; font-size: 13px; font-weight: bold; "
            f"border-bottom: 1px solid {BG3}; padding: 4px 0;"
        )
        return lbl

    # ─── Summary Card ───

    def _make_summary_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(80)
        card.setStyleSheet(f"""
            QFrame {{
                background: {BG2}; border: 1px solid {BG3};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 20px; font-weight: bold; border: none;"
        )
        value_label.setObjectName("value")
        card_layout.addWidget(value_label)

        title_label = QLabel(label)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {FG2}; font-size: 11px; border: none;")
        card_layout.addWidget(title_label)

        return card

    def _update_card_value(self, card: QFrame, value: str, color: str | None = None):
        label = card.findChild(QLabel, "value")
        if label:
            label.setText(value)
            c = color or ACCENT
            label.setStyleSheet(
                f"color: {c}; font-size: 20px; font-weight: bold; border: none;"
            )

    # ─── Public API ───

    def get_selected_period(self) -> str:
        return self.PERIOD_MAP.get(self._period_combo.currentText(), "weekly")

    def get_selected_probe_type(self) -> str | None:
        text = self._probe_combo.currentText()
        return None if text == "All" else text

    def set_probe_types(self, probe_types: list[str]):
        current = self._probe_combo.currentText()
        self._probe_combo.blockSignals(True)
        self._probe_combo.clear()
        self._probe_combo.addItem("All")
        for pt in probe_types:
            self._probe_combo.addItem(pt)
        idx = self._probe_combo.findText(current)
        if idx >= 0:
            self._probe_combo.setCurrentIndex(idx)
        self._probe_combo.blockSignals(False)

    def load_stats(self, stats, summary, period_totals, quality_stats, slot_values,
                   today=None):
        """전체 대시보드 갱신.

        Parameters
        ----------
        today
            `get_today_stats()` 결과. None이면 Today 카드는 비움(기본값 표시).
        """
        self._update_today_cards(today)
        self._update_summary_cards(summary, period_totals, slot_values)
        self._draw_production_chart(period_totals)
        self._draw_stacked_chart(stats)
        self._draw_freq_spc_chart(quality_stats)
        self._draw_q_spc_chart(quality_stats)
        self._draw_freq_histogram(slot_values)
        self._draw_q_histogram(slot_values)
        self._update_table(stats)

    # ─── Today Cards ───

    def _update_today_cards(self, today):
        """오늘 요약 카드 3개 갱신."""
        if not today:
            self._update_card_value(self._card_today_sets, "0")
            self._update_card_value(self._card_today_slots, "0")
            self._update_card_value(self._card_today_rate, "-")
            return

        self._update_card_value(self._card_today_sets, str(today.get("total_sets", 0)))
        self._update_card_value(self._card_today_slots, str(today.get("total_slots", 0)))

        rate = today.get("completion_rate", 0)
        total = today.get("total_slots", 0)
        if total == 0:
            self._update_card_value(self._card_today_rate, "-")
        else:
            color = GREEN if rate >= 80 else (ORANGE if rate >= 50 else RED)
            self._update_card_value(self._card_today_rate, f"{rate}%", color)

    # ─── Summary Cards ───

    def _update_summary_cards(self, summary, period_totals, slot_values):
        self._update_card_value(self._card_sets, str(summary["total_sets"]))
        self._update_card_value(self._card_slots, str(summary["total_slots"]))

        # Avg Frequency
        freqs = [v["frequency"] for v in slot_values if v["frequency"] is not None]
        if freqs:
            avg_f = st.mean(freqs)
            self._update_card_value(self._card_avg_freq, f"{avg_f:.1f}", GREEN)
        else:
            self._update_card_value(self._card_avg_freq, "-")

        # Avg Q Factor
        qs = [v["q_factor"] for v in slot_values if v["q_factor"] is not None]
        if qs:
            avg_q = st.mean(qs)
            self._update_card_value(self._card_avg_q, f"{avg_q:.1f}", GREEN)
        else:
            self._update_card_value(self._card_avg_q, "-")

        # Trend
        if len(period_totals) >= 2:
            recent = period_totals[-1]["total_slots"]
            prev = period_totals[-2]["total_slots"]
            if prev > 0:
                change = round((recent - prev) / prev * 100, 1)
                arrow = "\u2191" if change >= 0 else "\u2193"
                color = GREEN if change >= 0 else RED
                self._update_card_value(
                    self._card_trend, f"{arrow}{abs(change)}%", color
                )
            else:
                self._update_card_value(self._card_trend, "NEW", GREEN)
        else:
            self._update_card_value(self._card_trend, "-")

    # ─── Chart: Production Trend (Bar + Line) ───

    def _draw_production_chart(self, period_totals):
        fig = self._fig_production
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        ax.set_title("Production Trend", color=FG, fontsize=12, fontweight="bold")

        if not period_totals:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=FG2, fontsize=14, transform=ax.transAxes)
            self._canvas_production.draw()
            return

        labels = [p["period_label"] for p in period_totals]
        values = [p["total_slots"] for p in period_totals]
        x = range(len(labels))

        ax.bar(x, values, color=ACCENT, alpha=0.7, zorder=2)

        # Moving average (3-period)
        if len(values) >= 3:
            ma = []
            for i in range(len(values)):
                start = max(0, i - 2)
                ma.append(sum(values[start:i + 1]) / (i - start + 1))
            ax.plot(x, ma, color=ORANGE, linewidth=2, marker="o",
                    markersize=4, zorder=3, label="Moving Avg")
            ax.legend(fontsize=9, facecolor=BG2, edgecolor=BG3,
                      labelcolor=FG2, loc="upper left")

        ax.set_xticks(list(x))
        ax.set_xticklabels(self._shorten_labels(labels), rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Slots", color=FG2, fontsize=10)
        fig.tight_layout()
        self._canvas_production.draw()

    # ─── Chart: Stacked Bar by Probe Type ───

    def _draw_stacked_chart(self, stats):
        fig = self._fig_stacked
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        ax.set_title("Production by Probe Type", color=FG, fontsize=12, fontweight="bold")

        if not stats:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=FG2, fontsize=14, transform=ax.transAxes)
            self._canvas_stacked.draw()
            return

        periods_set = []
        probes_set = []
        data = defaultdict(lambda: defaultdict(int))
        for item in stats:
            p, pt = item["period_label"], item["probe_type"]
            data[p][pt] = item["slot_count"]
            if p not in periods_set:
                periods_set.append(p)
            if pt not in probes_set:
                probes_set.append(pt)

        periods_set.sort()
        x = range(len(periods_set))
        bottom = [0] * len(periods_set)

        for i, probe in enumerate(probes_set):
            vals = [data[p][probe] for p in periods_set]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            ax.bar(x, vals, bottom=bottom, color=color, alpha=0.85, label=probe)
            bottom = [b + v for b, v in zip(bottom, vals)]

        ax.set_xticks(list(x))
        ax.set_xticklabels(self._shorten_labels(periods_set), rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Slots", color=FG2, fontsize=10)
        ax.legend(fontsize=7, facecolor=BG2, edgecolor=BG3, labelcolor=FG2,
                  loc="upper center", bbox_to_anchor=(0.5, -0.15),
                  ncol=4, framealpha=0.9)
        fig.tight_layout(rect=[0, 0.08, 1, 1])
        self._canvas_stacked.draw()

    # ─── Chart: Frequency SPC (X-bar) ───

    def _draw_freq_spc_chart(self, quality_stats, spec_upper=None, spec_lower=None):
        fig = self._fig_freq_spc
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        ax.set_title("Frequency SPC (X-bar)", color=FG, fontsize=12, fontweight="bold")

        if not quality_stats:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=FG2, fontsize=14, transform=ax.transAxes)
            self._canvas_freq_spc.draw()
            return

        labels = [q["period_label"] for q in quality_stats]
        means = [q["freq_mean"] for q in quality_stats]
        x = list(range(len(labels)))

        # Overall CL, UCL, LCL (mean ± 3σ of period means)
        cl = st.mean(means)
        if len(means) >= 2:
            sigma = st.stdev(means)
        else:
            sigma = 0
        ucl = cl + 3 * sigma
        lcl = cl - 3 * sigma

        # Data line
        ax.plot(x, means, color=GREEN, linewidth=2, marker="o", markersize=5, zorder=3)

        # Highlight out-of-control points
        for i, m in enumerate(means):
            if m > ucl or m < lcl:
                ax.plot(i, m, "o", color=RED, markersize=8, zorder=4)

        # Control lines
        ax.axhline(y=cl, color=ACCENT, linewidth=1.5, linestyle="-", label=f"CL={cl:.1f}")
        ax.axhline(y=ucl, color=RED, linewidth=1, linestyle="--", alpha=0.8, label=f"UCL={ucl:.1f}")
        ax.axhline(y=lcl, color=RED, linewidth=1, linestyle="--", alpha=0.8, label=f"LCL={lcl:.1f}")

        # Spec limits (future use)
        if spec_upper is not None:
            ax.axhline(y=spec_upper, color=ORANGE, linewidth=1.5, linestyle="-.",
                        label=f"USL={spec_upper}")
        if spec_lower is not None:
            ax.axhline(y=spec_lower, color=ORANGE, linewidth=1.5, linestyle="-.",
                        label=f"LSL={spec_lower}")

        ax.set_xticks(x)
        ax.set_xticklabels(self._shorten_labels(labels), rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Frequency (KHz)", color=FG2, fontsize=10)
        ax.legend(fontsize=7, facecolor=BG2, edgecolor=BG3, labelcolor=FG2,
                  loc="upper right", handlelength=1.5, handletextpad=0.4,
                  borderpad=0.3, labelspacing=0.3)
        fig.tight_layout()
        self._canvas_freq_spc.draw()

    # ─── Chart: Q Factor SPC (X-bar) ───

    def _draw_q_spc_chart(self, quality_stats, spec_upper=None, spec_lower=None):
        fig = self._fig_q_spc
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        ax.set_title("Q Factor SPC (X-bar)", color=FG, fontsize=12, fontweight="bold")

        if not quality_stats:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=FG2, fontsize=14, transform=ax.transAxes)
            self._canvas_q_spc.draw()
            return

        labels = [q["period_label"] for q in quality_stats]
        means = [q["q_mean"] for q in quality_stats]
        x = list(range(len(labels)))

        cl = st.mean(means)
        if len(means) >= 2:
            sigma = st.stdev(means)
        else:
            sigma = 0
        ucl = cl + 3 * sigma
        lcl = cl - 3 * sigma

        ax.plot(x, means, color=GREEN, linewidth=2, marker="o", markersize=5, zorder=3)

        for i, m in enumerate(means):
            if m > ucl or m < lcl:
                ax.plot(i, m, "o", color=RED, markersize=8, zorder=4)

        ax.axhline(y=cl, color=ACCENT, linewidth=1.5, linestyle="-", label=f"CL={cl:.1f}")
        ax.axhline(y=ucl, color=RED, linewidth=1, linestyle="--", alpha=0.8, label=f"UCL={ucl:.1f}")
        ax.axhline(y=lcl, color=RED, linewidth=1, linestyle="--", alpha=0.8, label=f"LCL={lcl:.1f}")

        if spec_upper is not None:
            ax.axhline(y=spec_upper, color=ORANGE, linewidth=1.5, linestyle="-.",
                        label=f"USL={spec_upper}")
        if spec_lower is not None:
            ax.axhline(y=spec_lower, color=ORANGE, linewidth=1.5, linestyle="-.",
                        label=f"LSL={spec_lower}")

        ax.set_xticks(x)
        ax.set_xticklabels(self._shorten_labels(labels), rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Q Factor", color=FG2, fontsize=10)
        ax.legend(fontsize=7, facecolor=BG2, edgecolor=BG3, labelcolor=FG2,
                  loc="upper right", handlelength=1.5, handletextpad=0.4,
                  borderpad=0.3, labelspacing=0.3)
        fig.tight_layout()
        self._canvas_q_spc.draw()

    # ─── Chart: Frequency Histogram ───

    def _draw_freq_histogram(self, slot_values):
        fig = self._fig_freq_hist
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        ax.set_title("Frequency Distribution", color=FG, fontsize=12, fontweight="bold")

        freqs = [v["frequency"] for v in slot_values if v["frequency"] is not None]

        if not freqs:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=FG2, fontsize=14, transform=ax.transAxes)
            self._canvas_freq_hist.draw()
            return

        n, bins, patches = ax.hist(freqs, bins="auto", color=ACCENT, alpha=0.7,
                                    edgecolor=BG, zorder=2)

        # Normal distribution curve
        mu = st.mean(freqs)
        sigma = st.stdev(freqs) if len(freqs) >= 2 else 0
        if sigma > 0:
            bin_width = bins[1] - bins[0]
            x_curve = []
            y_curve = []
            x_min, x_max = min(freqs), max(freqs)
            steps = 100
            for i in range(steps + 1):
                xv = x_min + (x_max - x_min) * i / steps
                x_curve.append(xv)
                yv = (len(freqs) * bin_width /
                      (sigma * math.sqrt(2 * math.pi)) *
                      math.exp(-0.5 * ((xv - mu) / sigma) ** 2))
                y_curve.append(yv)
            ax.plot(x_curve, y_curve, color=ORANGE, linewidth=2, zorder=3)

        # Stats text box
        stats_text = f"\u03bc={mu:.1f}  \u03c3={sigma:.2f}  n={len(freqs)}"
        ax.text(0.97, 0.95, stats_text, transform=ax.transAxes,
                ha="right", va="top", fontsize=9, color=FG2,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=BG2,
                          edgecolor=BG3, alpha=0.9))

        ax.set_xlabel("Frequency (KHz)", color=FG2, fontsize=10)
        ax.set_ylabel("Count", color=FG2, fontsize=10)
        fig.tight_layout()
        self._canvas_freq_hist.draw()

    # ─── Chart: Q Factor Histogram ───

    def _draw_q_histogram(self, slot_values):
        fig = self._fig_q_hist
        fig.clear()
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        ax.set_title("Q Factor Distribution", color=FG, fontsize=12, fontweight="bold")

        qs = [v["q_factor"] for v in slot_values if v["q_factor"] is not None]

        if not qs:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=FG2, fontsize=14, transform=ax.transAxes)
            self._canvas_q_hist.draw()
            return

        n, bins, patches = ax.hist(qs, bins="auto", color=GREEN, alpha=0.7,
                                    edgecolor=BG, zorder=2)

        mu = st.mean(qs)
        sigma = st.stdev(qs) if len(qs) >= 2 else 0
        if sigma > 0:
            bin_width = bins[1] - bins[0]
            x_curve = []
            y_curve = []
            x_min, x_max = min(qs), max(qs)
            steps = 100
            for i in range(steps + 1):
                xv = x_min + (x_max - x_min) * i / steps
                x_curve.append(xv)
                yv = (len(qs) * bin_width /
                      (sigma * math.sqrt(2 * math.pi)) *
                      math.exp(-0.5 * ((xv - mu) / sigma) ** 2))
                y_curve.append(yv)
            ax.plot(x_curve, y_curve, color=ORANGE, linewidth=2, zorder=3)

        stats_text = f"\u03bc={mu:.1f}  \u03c3={sigma:.2f}  n={len(qs)}"
        ax.text(0.97, 0.95, stats_text, transform=ax.transAxes,
                ha="right", va="top", fontsize=9, color=FG2,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=BG2,
                          edgecolor=BG3, alpha=0.9))

        ax.set_xlabel("Q Factor", color=FG2, fontsize=10)
        ax.set_ylabel("Count", color=FG2, fontsize=10)
        fig.tight_layout()
        self._canvas_q_hist.draw()

    # ─── Table ───

    def _update_table(self, stats):
        self._table.setRowCount(len(stats))
        for row, item in enumerate(stats):
            slot_count = item["slot_count"]
            complete = item["complete_slots"]
            rate_val = round(complete / slot_count * 100, 1) if slot_count > 0 else 0

            self._table.setItem(row, 0, QTableWidgetItem(item["period_label"]))
            self._table.setItem(row, 1, QTableWidgetItem(item["probe_type"]))
            self._table.setItem(row, 2, self._numeric_item(item["set_count"]))
            self._table.setItem(row, 3, self._numeric_item(slot_count))
            self._table.setItem(row, 4, self._numeric_item(complete))

            rate_item = QTableWidgetItem(f"{rate_val}%")
            rate_item.setTextAlignment(Qt.AlignCenter)
            rate_item.setForeground(QColor(GREEN if rate_val >= 80 else ORANGE))
            self._table.setItem(row, 5, rate_item)

    # ─── Helpers ───

    def _style_axes(self, ax):
        """Catppuccin Mocha style."""
        ax.set_facecolor(BG)
        ax.figure.patch.set_facecolor(BG)
        ax.tick_params(colors=FG2, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(BG3)
        ax.grid(axis="y", color=BG3, alpha=0.5, linewidth=0.5)

    @staticmethod
    def _shorten_labels(labels: list[str]) -> list[str]:
        """차트 x축 라벨 축약.

        - "2026-W17"   (ISO week)    → "W17"
        - "202604"     (YYYYMM)      → "04/26"
        - "20260421"   (YYYYMMDD)    → "04/21"  (Daily)
        - "2026-Q2"    (quarterly)   → "2026-Q2" (passthrough)
        - "2026"       (yearly)      → "2026" (passthrough)
        """
        result = []
        for lbl in labels:
            if "-W" in lbl:
                result.append(lbl.split("-")[-1])
            elif len(lbl) == 8 and lbl.isdigit():
                # Daily: YYYYMMDD → MM/DD
                result.append(f"{lbl[4:6]}/{lbl[6:8]}")
            elif len(lbl) == 6 and lbl.isdigit():
                # Monthly: YYYYMM → MM/YY
                result.append(f"{lbl[4:6]}/{lbl[2:4]}")
            else:
                result.append(lbl)
        return result

    @staticmethod
    def _numeric_item(value) -> QTableWidgetItem:
        item = QTableWidgetItem(str(value))
        item.setTextAlignment(Qt.AlignCenter)
        return item
