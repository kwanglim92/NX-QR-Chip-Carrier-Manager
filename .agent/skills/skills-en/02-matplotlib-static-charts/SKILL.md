---
name: Matplotlib Static Charts
description: Publication-quality static charts with Korean font support, Qt embedding, and memory-safe figure management.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [03-pyqtgraph-interactive-charts, 05-wafer-map-die-system]
---

# SKILL 02 — Matplotlib Static Charts

## Overview

Creates static, publication-quality charts for semiconductor measurement analysis. Covers trend charts, heatmaps, boxplots, and histograms with Korean font support, dark-themed styling, and safe Qt widget embedding.

**When to use:** When generating non-interactive charts for display or PDF/image export.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `matplotlib` | Chart rendering |
| `matplotlib.backends.backend_qtagg` | `FigureCanvasQTAgg`, `NavigationToolbar2QT` |
| `scipy.interpolate` | `griddata` for contour interpolation |
| `numpy` | Numerical operations |

## Core Patterns

### 1. Korean Font Setup (Cross-Platform)

```python
# Source: charts/basic.py (top-level)
import platform
if platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
elif platform.system() == 'Darwin':
    plt.rcParams['font.family'] = 'AppleGothic'
else:
    plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False  # Prevent minus sign rendering issue
```

### 2. Dark-Themed Figure Creation

```python
# Source: charts/basic.py
fig, ax = plt.subplots(figsize=(10, 5), dpi=110)
fig.patch.set_facecolor('#1e1e2e')   # Match app background
ax.set_facecolor('#1e1e2e')
ax.tick_params(colors='#a6adc8')
for spine in ax.spines.values():
    spine.set_color('#313244')
```

### 3. Trend Chart (Mean ± σ Band)

```python
# Source: charts/basic.py → plot_trend_chart()
ax.plot(indices, means, 'o-', color='#89b4fa', label='Mean')
ax.fill_between(indices, lower_1σ, upper_1σ, alpha=0.2, color='#89b4fa')
ax.axhline(overall_mean, color='#cba6f7', ls='--', label='Overall Mean')
ax.plot(indices, mins, '--', color='#a6e3a1', alpha=0.5, label='Min')
ax.plot(indices, maxs, '--', color='#f38ba8', alpha=0.5, label='Max')
```

### 4. Figure-to-PNG Conversion

```python
# Source: charts/basic.py → _fig_to_png()
def _fig_to_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)  # Critical: prevent memory leak
    return buf.getvalue()
```

### 5. Qt Widget Embedding

```python
# Source: ui/widgets/chart_widget.py → ChartWidget.set_figure()
canvas = FigureCanvasQTAgg(fig)
toolbar = NavigationToolbar2QT(canvas, self)
# Old figure cleanup:
if self._canvas:
    old_fig = self._canvas.figure
    self._canvas.deleteLater()
    plt.close(old_fig)
```

### 6. Recipe Color Palette

```python
# Source: charts/basic.py
RECIPE_COLORS = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63',
                 '#9C27B0', '#00BCD4', '#795548', '#607D8B']
```

### 7. Multi-Recipe Comparison Charts

```python
# Source: charts/comparison.py
plot_recipe_comparison_boxplot(recipe_results)   # 2×N grid
plot_recipe_comparison_trend(recipe_results)      # Overlaid trend lines
plot_recipe_comparison_heatmap(recipe_results)    # 2×2 grid per recipe
```

## Pitfalls & Gotchas

- **Memory leaks:** Always call `plt.close(fig)` after embedding. Matplotlib keeps internal references to all figures.
- **Korean minus sign:** Without `axes.unicode_minus = False`, negative values display as □ on Korean font.
- **Thread safety:** Matplotlib is NOT thread-safe. Create figures in the main thread or use `Agg` backend in workers.
- **DPI scaling:** Use `dpi=110` for display, `dpi=150` for export. High DPI increases memory usage.

## Testing Checklist

- [ ] Korean labels render correctly on all axes
- [ ] `_fig_to_png()` produces valid PNG bytes
- [ ] Figure memory is released after `set_figure()` replacement
- [ ] Trend chart shows σ band and overall mean line
- [ ] Boxplot displays outlier fliers correctly

## Related Files

- `src/charts/basic.py` — Trend, heatmap, boxplot, histogram (234 lines)
- `src/charts/comparison.py` — Multi-recipe comparison charts (164 lines)
- `src/charts/wafer.py` — Wafer contour/vector (also uses matplotlib)
- `src/ui/widgets/chart_widget.py` — Qt embedding container
