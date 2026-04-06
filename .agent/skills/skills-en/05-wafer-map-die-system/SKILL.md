---
name: Wafer Map & Die Position System
description: Wafer-level contour maps, vector maps, die position visualization, and interactive wafer navigation.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [08-die-deviation-analysis, 02-matplotlib-static-charts]
---

# SKILL 05 — Wafer Map & Die Position System

## Overview

Renders wafer-level visualizations for semiconductor positioning analysis: contour heatmaps with circular clipping, vector maps showing deviation direction/magnitude, die position maps with measurement order, and interactive mini-maps for die filtering.

**When to use:** When visualizing spatial data across a wafer die layout.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `matplotlib` | Figure, axes, contourf, quiver, scatter |
| `scipy.interpolate` | `griddata` for cubic interpolation |
| `scipy.spatial` | `cKDTree` for boundary extrapolation |
| `numpy` | Array operations |

## Core Patterns

### 1. Wafer Contour Map (Circular Clipping)

```python
# Source: charts/wafer.py → plot_wafer_contour()
# Step 1: Extrapolate boundary points using cKDTree nearest-neighbor
tree = cKDTree(np.column_stack([xs, ys]))
angles = np.linspace(0, 2 * np.pi, 36, endpoint=False)
bx = data_r * np.cos(angles)
by = data_r * np.sin(angles)
_, nearest_idx = tree.query(np.column_stack([bx, by]))
bz = zs[nearest_idx]  # Extend data to wafer edge

# Step 2: Interpolate onto dense grid
xs_ext = np.concatenate([xs, bx])
ys_ext = np.concatenate([ys, by])
zs_ext = np.concatenate([zs, bz])
zi = griddata((xs_ext, ys_ext), zs_ext, (xi, yi), method='cubic')

# Step 3: Circular mask
zi[np.sqrt(xi**2 + yi**2) > data_r] = np.nan

# Step 4: Contour fill
norm = Normalize(vmin=-vmax, vmax=vmax)
ax.contourf(xi, yi, zi, levels=50, cmap='RdYlGn', norm=norm, extend='both')
```

**Key insight:** `cKDTree` nearest-neighbor is used to extrapolate die values to the wafer boundary, preventing contour artifacts at the edge.

### 2. Vector Map (Quiver)

```python
# Source: charts/wafer.py → plot_vector_map()
# Arrow direction = (x_offset, y_offset)
# Arrow magnitude scaled by slider (scale_pct)
scale = scale_pct / 100.0

ax.quiver(die_x, die_y, dx_values, dy_values,
          angles='xy', scale_units='xy', scale=1.0/scale,
          color=arrow_colors, width=0.15, headwidth=3)

# Value labels next to arrows (optional)
if show_values:
    for i, (x, y, dx, dy) in enumerate(zip(die_x, die_y, dx_vals, dy_vals)):
        mag = math.sqrt(dx**2 + dy**2)
        ax.text(x, y - 0.8, f'{mag:.2f}', ha='center', fontsize=7, color='#cdd6f4')
```

### 3. Die Position Map (Interactive Hover)

```python
# Source: charts/wafer.py → plot_die_position_map()
# Static scatter of die positions with measurement order arrows
scatter = ax.scatter(die_x, die_y, c=colors, s=200, zorder=5)

# Measurement order arrows
for i in range(len(die_x) - 1):
    ax.annotate('', xy=(die_x[i+1], die_y[i+1]),
                xytext=(die_x[i], die_y[i]),
                arrowprops=dict(arrowstyle='->', color='#89b4fa', lw=1.5))

# Interactive hover via mpl_connect
def on_move(event):
    # Find nearest die, show tooltip with die info
    ...
fig.canvas.mpl_connect('motion_notify_event', on_move)
```

### 4. Mini Die Map (Click Toggle)

```python
# Source: charts/wafer.py → plot_die_position_map_mini()
# Compact version for die filter panel
# picker=True enables click events
scatter_map = {}
for i, (x, y, die_idx) in enumerate(dies):
    color = active_color if die_idx not in excluded else dimmed_color
    sc = ax.scatter([x], [y], c=[color], s=80, picker=True, zorder=5)
    scatter_map[die_idx] = sc
return fig, scatter_map

# Click handler in controller:
# canvas.mpl_connect('pick_event', self._on_mini_map_pick)
```

### 5. Repeat Contour Dialog

```python
# Source: ui/dialogs/repeat_contour_dialog.py → RepeatContourDialog
# N subplots (one per repeat/lot), arranged in grid
# Shared colorscale (vmax_global) across all subplots
# patheffects.withStroke for text outline on contour labels
```

### 6. HSL Color Generation for Dies

```python
# Source: charts/wafer.py → _color_from_die_hex()
def _hsl_to_rgb(h, s, l):
    # Standard HSL → RGB conversion
    ...

def _color_from_die_hex(die_index, total_dies=21):
    hue = (die_index * 360.0 / total_dies) % 360
    return _hsl_to_rgb(hue, 0.7, 0.6)  # Returns hex color
```

## Pitfalls & Gotchas

- **griddata extrapolation:** `cubic` method returns NaN outside convex hull. The `cKDTree` boundary extrapolation prevents edge artifacts.
- **Contour levels:** Too few levels (<20) → visible banding. Too many (>100) → slow rendering. 50 is the sweet spot.
- **Quiver scaling:** `scale_units='xy'` makes arrow length proportional to data units, not pixels. Adjust `scale` parameter for visibility.
- **Circular mask:** Must be applied AFTER interpolation, not before, to get smooth edge contours.
- **patheffects import:** `from matplotlib.patheffects import withStroke` for text outline on dark contour background.

## Testing Checklist

- [ ] Contour map shows circular wafer shape (no square artifacts)
- [ ] Vector arrows point in correct X/Y direction
- [ ] Die position map shows correct measurement order
- [ ] Mini map click toggles die filter correctly
- [ ] Global color scale is consistent across repeat contours

## Related Files

- `src/charts/wafer.py` — All wafer visualization functions (598 lines)
- `src/core/die_analysis.py` — Die position data (`DIE_POSITIONS`, `get_die_position()`)
- `src/ui/dialogs/repeat_contour_dialog.py` — Repeat contour popup (118 lines)
