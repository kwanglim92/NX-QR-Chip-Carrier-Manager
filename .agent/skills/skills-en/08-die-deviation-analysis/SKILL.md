---
name: Die-Level Deviation Analysis
description: Wafer die coordinate system, deviation matrices, affine transform, pareto and correlation analysis.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [07-statistical-analysis-engine, 05-wafer-map-die-system]
---

# SKILL 08 — Die-Level Deviation Analysis

## Overview

Provides die-level analysis for 21-die wafer positioning data: deviation matrix computation, systematic error decomposition via affine transform, outlier pareto analysis, and X/Y correlation. This is the analytical foundation for wafer-level visualizations.

**When to use:** When analyzing positioning accuracy at individual die locations across multiple measurement repeats.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `math` (stdlib) | Mathematical operations |
| `numpy` | Matrix operations (`linalg.lstsq`) |
| `re` (stdlib) | Site ID parsing |

## Core Patterns

### 1. Die Position Coordinate System

21-die wafer layout (hardcoded default + dynamic extraction):

```python
# Source: core/die_analysis.py
DIE_POSITIONS = [
    (0, 0),   (2, 0),   (4, 0),   (6, 0),   (2, 2),
    (4, 4),   (0, 2),   (0, 4),   (0, 6),   (-2, 2),
    (-4, 4),  (-2, 0),  (-4, 0),  (-6, 0),  (-2, -2),
    (-4, -4), (0, -2),  (0, -4),  (0, -6),  (2, -2),
    (4, -4),
]  # Index 0-20, units are relative grid positions
```

Dynamic extraction from measurement data:
```python
# Source: core/die_analysis.py → extract_die_positions()
positions = extract_die_positions(raw_data)
# Returns: {0: (x_mm, y_mm), 1: (x_mm, y_mm), ...}
# Averages x_um/y_um fields per die across all lots
```

### 2. Die Number Extraction from Site ID

```python
# Source: core/die_analysis.py → extract_die_number()
# Pattern: DDDD_XNNN_YNNN where first 2 digits of DDDD = die number (1-based)
extract_die_number('0001_X000_Y000')  # → 0  (Die 1 → index 0)
extract_die_number('0021_X000_Y000')  # → 20 (Die 21 → index 20)
```

### 3. Deviation Matrix (Die × Repeat)

The core data structure for all die-level analysis:

```python
# Source: core/die_analysis.py → compute_deviation_matrix()
result = compute_deviation_matrix(data, method='X', metric_key='value')
# Returns:
# {
#   'die_labels': ['Die1', 'Die2', ...],      # 1-based labels
#   'repeat_labels': ['Lot401', 'Lot402', ...],
#   'matrix': {
#     'Lot401': {'Die1': 2976.0, 'Die2': 2981.5, ...},
#     'Lot402': {...}, ...
#   },
#   'die_stats': [
#     {'die': 'Die1', 'avg': 2978.2, 'range': 12.5, 'stdev': 3.1, 'count': 11},
#   ],
#   'overall_range': 45.2,   # max(die_avg) - min(die_avg)
#   'overall_stddev': 8.7,   # stdev of die averages
# }
```

### 4. Affine Transform (Systematic Error Decomposition)

Decomposes die-level deviations into translation, scale, and rotation components:

```python
# Source: core/die_analysis.py → compute_affine_transform()
# Mathematical model:
#   dx = Tx + Sx * x - θ * y
#   dy = Ty + Sy * y + θ * x
#
# Solved via least squares: np.linalg.lstsq(A, b)

af = compute_affine_transform(x_die_stats, y_die_stats)
# Returns:
# {
#   'tx': 0.1234,       # X Translation (µm)
#   'ty': -0.0567,      # Y Translation (µm)
#   'sx_ppm': 2.5,      # X Scale (ppm)
#   'sy_ppm': -1.8,     # Y Scale (ppm)
#   'theta_deg': 0.001, # Rotation (degrees)
#   'theta_urad': 17.5, # Rotation (microradians)
#   'residual_x': 0.05, # X fitting residual RMS
#   'residual_y': 0.04, # Y fitting residual RMS
# }
```

**Matrix formulation:**
```
A = [[1, x, -y],    b_x = [dx]
     [1, x, -y],    b_y = [dy]
     ...]
[Tx, Sx, θ] = lstsq(A, b_x)
[Ty, Sy, θ] = lstsq(A, b_y)
```

### 5. Pareto Analysis (Outlier Frequency)

```python
# Source: core/die_analysis.py → compute_pareto_data()
pareto = compute_pareto_data(data, group_by='die')  # or 'lot'
# Returns (sorted descending by count):
# [{'label': 'Die5', 'count': 12, 'percent': 30.0, 'cumulative': 30.0},
#  {'label': 'Die8', 'count': 8,  'percent': 20.0, 'cumulative': 50.0}, ...]
```

Requires `is_outlier` field from `detect_outliers()`.

### 6. Pearson Correlation (X vs Y)

```python
# Source: core/die_analysis.py → compute_correlation()
corr = compute_correlation(x_die_stats, y_die_stats)
# Returns:
# {
#   'pearson_r': 0.85,      # Pearson correlation coefficient
#   'r_squared': 0.72,      # Coefficient of determination
#   'slope': 1.23,          # Regression line slope
#   'intercept': -0.45,     # Regression line intercept
#   'points': [(x_avg, y_avg, 'Die1'), ...],
#   'n': 21,
# }
```

### 7. Stabilization Die Filter

```python
# Source: core/die_analysis.py → filter_stabilization_die()
filtered = filter_stabilization_die(data)
# Removes all records belonging to the first-measured die
# (the die that appears first in measurement order)
```

## Pitfalls & Gotchas

- **1-based vs 0-based:** Die labels are 1-based (`Die1`–`Die21`) but `DIE_POSITIONS` uses 0-based indexing. `get_die_position('Die1')` maps to index 0.
- **Dynamic vs static positions:** Always prefer `extract_die_positions()` output over hardcoded `DIE_POSITIONS` — real wafer coordinates may differ from the grid pattern.
- **Affine transform requires ≥3 dies:** With fewer data points, `lstsq` may produce unreliable results.
- **Pareto requires outlier detection first:** Run `detect_outliers()` before `compute_pareto_data()`.

## Testing Checklist

- [ ] `extract_die_number()` correctly parses various site ID formats
- [ ] `compute_deviation_matrix()` returns correct die count and matrix shape
- [ ] `compute_affine_transform()` produces reasonable (small) values for well-calibrated data
- [ ] `compute_correlation()` returns r ≈ 0 for uncorrelated X/Y data
- [ ] `filter_stabilization_die()` removes exactly the first-measured die's records

## Related Files

- `src/core/die_analysis.py` — All die-level analysis (414 lines)
