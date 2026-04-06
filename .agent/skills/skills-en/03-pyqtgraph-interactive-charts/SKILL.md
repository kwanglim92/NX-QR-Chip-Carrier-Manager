---
name: PyQtGraph Interactive Charts
description: High-performance interactive charts with crosshair, hover, dual-axis, and die-level scatter visualization.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [02-matplotlib-static-charts, 11-custom-qt-widgets]
---

# SKILL 03 — PyQtGraph Interactive Charts

## Overview

Implements high-performance interactive charts using PyQtGraph for real-time data exploration. Features include crosshair cursor tracking, hover tooltips, dual-trend panels with synchronized zoom, die-level scatter plots, Pareto charts with dual axes, and correlation analysis.

**When to use:** When users need to explore data interactively (zoom, pan, hover) rather than viewing static images.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `pyqtgraph` | Fast OpenGL-accelerated 2D plotting |
| `numpy` | Array operations |
| `PySide6` | Qt widget framework |

## Core Patterns

### 1. Global Configuration

```python
# Source: charts/interactive.py
BG = '#1e1e2e'; FG = '#cdd6f4'
pg.setConfigOptions(background=BG, foreground=FG, antialias=True)
```

### 2. CrossHairPlotWidget (Cursor Snap)

```python
# Source: charts/interactive_widgets.py → CrossHairPlotWidget
class CrossHairPlotWidget(QWidget):
    def __init__(self):
        self.vline = pg.InfiniteLine(angle=90, pen=crosshair_pen)
        self.hline = pg.InfiniteLine(angle=0, pen=crosshair_pen)
        self.plot.addItem(self.vline); self.plot.addItem(self.hline)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, pos):
        mouse_pt = self.plot.vb.mapSceneToView(pos)
        # Snap to nearest data point
        idx = np.argmin(np.abs(self.x_data - mouse_pt.x()))
        self.vline.setPos(self.x_data[idx])
        self.hline.setPos(self.y_data[idx])
        self.label.setText(f"X={self.x_data[idx]:.2f}  Y={self.y_data[idx]:.4f}")
```

### 3. HoverScatterWidget (Die Highlight)

```python
# Source: charts/interactive_widgets.py → HoverScatterWidget
class HoverScatterWidget(QWidget):
    # Per-die ScatterPlotItem with unique colors
    # hover events show data point label
    # highlight_die(die_label) → dim other dies, emphasize selected
    # _restore_all() → reset all to normal opacity
```

### 4. Trend Widget (Mean + σ Band)

```python
# Source: charts/interactive.py → create_trend_widget()
plot.plot(x, means, pen=mean_pen)
fill = pg.FillBetweenItem(mean_curve, sigma_upper, brush=(137,180,250,40))
plot.addItem(fill)
if spec:
    plot.addItem(pg.InfiniteLine(pos=spec['lsl'], pen=spec_pen, label='LSL'))
    plot.addItem(pg.InfiniteLine(pos=spec['usl'], pen=spec_pen, label='USL'))
```

### 5. Dual Trend Widget (X/Y Synchronized)

```python
# Source: charts/interactive.py → create_dual_trend_widget()
# Two CrossHairPlotWidgets stacked vertically in QSplitter
# X-axes linked: plot_y.setXLink(plot_x)
# Zoom in one panel → both panels zoom together
```

### 6. Scatter Widget (Signed Log Mode)

```python
# Source: charts/interactive.py → create_scatter_widget()
# Die-level scatter with HSL-based color assignment
# log_mode: sign(value) * log10(1 + |value|)  — preserves sign with log scale
# Spec range box: pg.LinearRegionItem [horizontal + vertical]
```

### 7. Histogram Widget

```python
# Source: charts/interactive.py → create_histogram_widget()
# BarGraphItem + Normal distribution curve overlay
# σ lines: ±1σ, ±2σ, ±3σ vertical InfiniteLines
bg = pg.BarGraphItem(x=bin_centers, height=counts, width=bin_width,
                     brush=(137,180,250,180))
```

### 8. Pareto Widget (Dual Axis)

```python
# Source: charts/interactive.py → create_pareto_widget()
# Left axis: BarGraphItem (counts, descending)
# Right axis: cumulative % line (ViewBox overlay)
# 80% threshold line: InfiniteLine
# ViewBox synchronization for zoom:
vb_right = pg.ViewBox()
plot.scene().addItem(vb_right)
plot.getAxis('right').linkToView(vb_right)
vb_right.setXLink(plot)  # Sync X-axis zoom
```

### 9. Die Color Generation

```python
# Source: charts/interactive.py → _gen_die_colors()
def _gen_die_colors(n=21):
    colors = []
    for i in range(n):
        hue = (i * 360.0 / n) % 360
        # HSL → hex, with fixed saturation=70%, lightness=60%
        colors.append(hsl_to_hex(hue, 0.7, 0.6))
    return colors
```

## Pitfalls & Gotchas

- **ViewBox sync:** Pareto's dual-axis requires manual `sigRangeChanged` connection and axis sync. Without it, right-axis doesn't zoom with the chart.
- **Signed Log:** `log_mode` transform must preserve the sign: `sign(v) * log10(1 + |v|)`. Pure log fails on negative values.
- **Die colors:** `_DIE_COLORS` is module-level and lazily initialized. Access after first import.
- **Memory:** Replace widget via `InteractiveChartWidget.set_widget()` — it handles `deleteLater()` and old widget cleanup.

## Testing Checklist

- [ ] CrossHair snaps to nearest data point (not arbitrary position)
- [ ] Hover label shows correct value for the data point
- [ ] Dual trend zoom synchronization works in both panels
- [ ] Die scatter colors are distinct and consistent
- [ ] Pareto cumulative line reaches 100% at rightmost bar

## Related Files

- `src/charts/interactive.py` — All chart creation functions (635 lines)
- `src/charts/interactive_widgets.py` — Widget classes (402 lines)
