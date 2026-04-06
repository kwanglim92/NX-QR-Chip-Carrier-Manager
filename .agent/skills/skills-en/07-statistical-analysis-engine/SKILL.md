---
name: Statistical Analysis Engine
description: Pure-Python statistical computations for semiconductor measurement data analysis.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [06-csv-raw-data-parser, 08-die-deviation-analysis]
---

# SKILL 07 — Statistical Analysis Engine

## Overview

Provides a complete statistical analysis toolkit for semiconductor positioning measurement data. All functions operate on lists of dicts (output from `batch_load()`) and are dependency-free (pure Python + `math` stdlib only).

**When to use:** When computing summary statistics, trend analysis, outlier detection, repeatability, or process capability (Cpk) from measurement data.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `math` (stdlib) | Square root, infinity |
| `typing` (stdlib) | `Optional` type hints |

No external dependencies — all computations are pure Python.

## Core Patterns

### 1. Basic Statistics

```python
# Source: core/statistics.py → compute_statistics()
def compute_statistics(data: list, metric_key: str = 'value') -> dict:
    values = [r[metric_key] for r in data if isinstance(r.get(metric_key), (int, float))]
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n  # Population stdev
    return {
        'count': n, 'mean': mean,
        'stdev': variance ** 0.5,
        'min': min(values), 'max': max(values),
        'range': max(values) - min(values),
    }
```

**Note:** Uses **population standard deviation** (divides by N, not N-1).

### 2. Group Statistics

Dynamic grouping by any key (lot, site, method):

```python
# Source: core/statistics.py → compute_group_statistics()
compute_group_statistics(data, group_by='lot_name', metric_key='value')
# Returns: [{'group': 'Lot401', 'count': 22, 'mean': ..., 'stdev': ...}, ...]
```

### 3. Lot Trend (Aging Analysis)

Computes per-lot statistics ordered by lot index for temporal trend detection:

```python
# Source: core/statistics.py → compute_trend()
compute_trend(data, metric_key='value')
# Returns: [{'lot_name': 'Lot401', 'lot_index': 1,
#             'count': 22, 'mean': ..., 'stdev': ..., 'min': ..., 'max': ...}, ...]
```

**Key design:** `lot_index` is assigned by order of first appearance in the data, not by parsing the folder name. This ensures consistent ordering even with non-sequential naming.

### 4. Outlier Detection (3 Methods)

```python
# Source: core/statistics.py → detect_outliers()
data = detect_outliers(data, method='iqr', threshold=1.5)
# method='iqr':    outlier if value < Q1 - 1.5*IQR or > Q3 + 1.5*IQR
# method='zscore': outlier if |Z| > threshold (default 3)
# method='range':  outlier if |value - mean| > threshold
```

Adds `'is_outlier': True/False` to each record **in-place** (returns same list).

### 5. Repeatability Analysis

Decomposes variation into lot-level and site-level components:

```python
# Source: core/statistics.py → compute_repeatability()
result = compute_repeatability(data, metric_key='value')
# Returns:
# {
#   'lot_variation': {
#     'count': N_lots, 'mean_of_means': ...,
#     'stdev_of_means': ..., 'range_of_means': ...
#   },
#   'site_variation': [
#     {'site_id': '0001_X000_Y000', 'stdev': ..., 'range': ...}, ...
#   ],
#   'overall': {'mean': ..., 'stdev': ..., 'cv_percent': ...}
# }
```

**CV% (Coefficient of Variation):** `(stdev / |mean|) * 100` — key metric for process stability.

### 6. Process Capability Index (Cpk)

```python
# Source: core/statistics.py → compute_cpk()
cpk = compute_cpk(mean=100.0, stdev=5.0, lsl=-5000.0, usl=5000.0)
# Cpk = min(CPU, CPL) where CPU = (USL - mean) / (3 * stdev)
```

Returns `0.0` if stdev is zero or limits are not provided.

### 7. Data Filtering

```python
# Source: core/statistics.py
x_data = filter_by_method(data, 'X')    # Keep only method='X'
valid  = filter_valid_only(data)          # Keep only valid=True
```

### 8. 1st vs 2nd Round Comparison

```python
# Source: core/statistics.py → compare_1st_2nd_by_site()
diffs = compare_1st_2nd_by_site(data_1st, data_2nd)
# Returns: [{'site_id': ..., 'method': 'X',
#             'val_1st': 123, 'val_2nd': 125, 'diff': -2}, ...]
```

Matches by `(site_id, method)` pair and computes means per site.

## Pitfalls & Gotchas

- **Population vs Sample stdev:** This engine uses population stdev (÷N). Be aware when comparing with Excel STDEV (which uses sample ÷(N-1)).
- **Empty data:** All functions handle empty input gracefully (return zeros/empty lists).
- **In-place mutation:** `detect_outliers()` modifies and returns the same list. Do not assume a copy.
- **CV% edge case:** When mean ≈ 0, CV% can be misleadingly large. Check absolute stdev as well.

## Testing Checklist

- [ ] `compute_statistics([])` returns zeros without error
- [ ] `detect_outliers()` with `method='iqr'` marks known outliers correctly
- [ ] `compute_cpk()` returns correct values for symmetric/asymmetric specs
- [ ] `compute_trend()` produces correct lot ordering
- [ ] `filter_by_method('X')` returns only X-axis records

## Related Files

- `src/core/statistics.py` — All statistical functions (319 lines)
