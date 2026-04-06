---
name: 3D Surface Visualization (OpenGL)
description: OpenGL-based 3D surface rendering with colorbar, Z-scale slider, and polynomial surface fit decomposition.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [05-wafer-map-die-system, 08-die-deviation-analysis]
---

# SKILL 04 — 3D Surface Visualization (OpenGL)

## Overview

Renders 3D surface visualizations of die-level positioning deviations using PyQtGraph's OpenGL backend. Features include a custom QPainter colorbar, interactive Z-axis scale slider, and surface fit decomposition (Tilt/Curve/Residual) using polynomial fitting.

**When to use:** When visualizing spatial data in 3D with interactive rotation, zoom, and surface decomposition.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `pyqtgraph.opengl` | `GLViewWidget`, `GLMeshItem` |
| `scipy.optimize` | `curve_fit` for polynomial fitting |
| `numpy` | Array operations, `meshgrid`, `griddata` |
| `PySide6.QtGui` | `QPainter`, `QLinearGradient` for colorbar |

## Core Patterns

### 1. GLViewWidget Setup

```python
# Source: charts/surface3d.py → SurfaceWidget.__init__()
view = gl.GLViewWidget()
view.setCameraPosition(distance=40, elevation=30, azimuth=-60)
view.setBackgroundColor('#1e1e2e')

# Z=0 reference plane (translucent)
grid = gl.GLMeshItem(...)  # Flat plane at Z=0
grid.setColor((1, 1, 1, 0.08))
view.addItem(grid)
```

### 2. Surface Mesh Construction

```python
# Source: charts/surface3d.py → SurfaceWidget._build_surface()
# 1. Die stats → sparse points (x, y, z_value)
# 2. griddata cubic interpolation → dense grid
# 3. MeshData from grid → GLMeshItem

xi = np.linspace(x_min, x_max, 50)
yi = np.linspace(y_min, y_max, 50)
X, Y = np.meshgrid(xi, yi)
Z = griddata((die_x, die_y), die_z, (X, Y), method='cubic')

# Color mapping: Z value → RGBA
colors = self._z_to_color(Z, vmin, vmax)
mesh = gl.MeshData(vertexes=verts, faces=faces, vertexColors=colors)
surface = gl.GLMeshItem(meshdata=mesh, smooth=True, drawEdges=False)
```

### 3. Custom ColorBar Widget

```python
# Source: charts/surface3d.py → ColorBarWidget
class ColorBarWidget(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        # Vertical gradient bar
        gradient = QLinearGradient(QPointF(x, top), QPointF(x, bottom))
        gradient.setColorStops([
            (0.0, QColor('#f38ba8')),    # Max (red)
            (0.5, QColor('#a6adc8')),    # Mid (neutral)
            (1.0, QColor('#89b4fa')),    # Min (blue)
        ])
        p.fillRect(bar_rect, gradient)
        # Labels: vmax at top, 0 in middle, vmin at bottom
        p.drawText(x, y_top, f"{self.vmax:.2f}")
        p.drawText(x, y_mid, "0.00")
        p.drawText(x, y_bot, f"{self.vmin:.2f}")
```

### 4. Z-Axis Scale Slider

```python
# Source: charts/surface3d.py → SurfaceWidget
scale_slider = QSlider(Qt.Horizontal)
scale_slider.setRange(10, 500)   # 0.1x to 5.0x
scale_slider.setValue(100)       # 1.0x default
scale_slider.valueChanged.connect(self._on_scale_changed)

def _on_scale_changed(self, value):
    scale = value / 100.0
    # Rebuild surface with Z * scale
    self._build_surface(z_scale=scale)
```

### 5. Surface Fit Decomposition

Polynomial fitting to separate systematic and random error:

```python
# Source: charts/surface3d.py
# 1st-order (Tilt/Plane):   z = a*x + b*y + c
def poly1d_2d(xy, a, b, c):
    x, y = xy
    return a * x + b * y + c

# 2nd-order (Curve/Bowl):   z = a*x² + b*y² + c*xy + d*x + e*y + f
def poly2d_2d(xy, a, b, c, d, e, f):
    x, y = xy
    return a*x**2 + b*y**2 + c*x*y + d*x + e*y + f

# Fitting:
popt, _ = curve_fit(poly1d_2d, (die_x, die_y), die_z)
tilt_surface = poly1d_2d((X, Y), *popt)

popt2, _ = curve_fit(poly2d_2d, (die_x, die_y), die_z)
curve_surface = poly2d_2d((X, Y), *popt2) - tilt_surface  # Curve = 2nd - 1st
residual = original - poly2d_2d((X, Y), *popt2)            # Residual = Original - 2nd
```

### 6. Model Selection (RadioButton)

```python
# Source: charts/surface3d.py → SurfaceWidget
# QRadioButton group: Original | Tilt | Curve | Residual
# on_model_changed → rebuild surface with selected component
# Original: raw die averages
# Tilt: 1st-order polynomial (plane)
# Curve: 2nd-order minus 1st-order
# Residual: original minus 2nd-order (random error)
```

## Pitfalls & Gotchas

- **OpenGL compatibility:** Some virtual machines and remote desktops don't support OpenGL. Handle `ImportError` or rendering errors gracefully.
- **Z-scale distortion:** When Z range is much smaller than X/Y range, the surface appears flat. The scale slider addresses this.
- **curve_fit convergence:** `scipy.optimize.curve_fit` may fail with `RuntimeError` if data is insufficient (<4 points for 2nd order). Catch and display fallback.
- **Color mapping direction:** Typically red=positive (shift right/up), blue=negative (shift left/down) for intuitive wafer offset interpretation.

## Testing Checklist

- [ ] Surface renders without OpenGL errors
- [ ] Z-scale slider changes surface exaggeration in real-time
- [ ] Tilt model shows a plane (no curvature)
- [ ] Residual is relatively flat for well-fitting data
- [ ] ColorBar shows correct value range

## Related Files

- `src/charts/surface3d.py` — All 3D surface logic (304 lines)
