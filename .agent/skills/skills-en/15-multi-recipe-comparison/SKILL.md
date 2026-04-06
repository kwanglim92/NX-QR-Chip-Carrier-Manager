---
name: Multi-Recipe Comparison System
description: Automatic recipe detection, batch loading, cross-recipe comparison tables, and comparison chart generation.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [06-csv-raw-data-parser, 07-statistical-analysis-engine, 02-matplotlib-static-charts]
---

# SKILL 15 — Multi-Recipe Comparison System

## Overview

Automatically detects multiple measurement recipes from a hierarchical folder structure, batch-loads all data, computes cross-recipe statistics, and generates comparison visualizations. Handles both flat (direct lot folders) and layered (1st/2nd round) directory structures.

**When to use:** When analyzing data from multiple measurement steps/recipes that need cross-comparison.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `os`, `re` (stdlib) | Directory traversal, name parsing |
| Core modules | `csv_loader`, `statistics`, `die_analysis` |
| Chart modules | `comparison.py` for cross-recipe charts |

## Core Patterns

### 1. Two-Level Folder Detection

```python
# Source: core/recipe_scanner.py → scan_recipes()
# Level 1 — Flat structure:
#   data/
#   ├── 1. Vision Pattern/
#   │   ├── Lot401/
#   │   └── Lot402/
#   └── 2. In-Die Align/
#       ├── Lot401/
#       └── Lot402/

# Level 2 — Round structure:
#   data/
#   ├── 1. Vision Pattern/
#   │   ├── 1st/
#   │   │   ├── Lot401/
#   │   │   └── Lot402/
#   │   └── 2nd/
#   └── 2. In-Die Align/
#       ├── 1st/
#       └── 2nd/

def scan_recipes(root_path):
    recipes = []
    for folder in sorted(os.listdir(root_path)):
        full = os.path.join(root_path, folder)
        if not os.path.isdir(full): continue
        # Check for round subdirectories (1st, 2nd)
        rounds = _find_rounds(full)
        if rounds:
            recipes.append({'name': folder, 'rounds': rounds, ...})
        elif _has_data_folders(full):
            recipes.append({'name': folder, 'rounds': {'1st': full}, ...})
    return recipes
```

### 2. Short Name Generation

```python
# Source: core/recipe_scanner.py
# "1. Vision Pattern Recognize" → "Vision Pattern Recognize"
short_name = re.sub(r'^\d+\.\s*', '', folder_name)
```

Used for matching against `settings.json` spec keys.

### 3. Batch Loading All Recipes

```python
# Source: core/recipe_scanner.py → load_all_recipes()
def load_all_recipes(root_path, round_name='1st', axis='both'):
    recipes = scan_recipes(root_path)
    results = []
    for recipe in recipes:
        round_path = recipe['rounds'].get(round_name, '')
        raw_data = batch_load(round_path, axis=axis)
        stats = compute_statistics(raw_data)
        outliers = detect_outliers(raw_data)
        trend = compute_trend(raw_data)
        results.append({
            'name': recipe['name'],
            'short_name': recipe['short_name'],
            'raw_data': raw_data,
            'statistics': stats,
            'trend': trend,
            'round_path': round_path,
        })
    return results
```

### 4. Cross-Recipe Comparison Table

```python
# Source: core/recipe_scanner.py → compare_recipes()
def compare_recipes(results):
    comparison = []
    for r in results:
        x_data = filter_by_method(r['raw_data'], 'X')
        y_data = filter_by_method(r['raw_data'], 'Y')
        comparison.append({
            'name': r['short_name'],
            'x_mean': compute_statistics(x_data)['mean'],
            'y_mean': compute_statistics(y_data)['mean'],
            'x_stdev': ..., 'y_stdev': ...,
            'x_range': ..., 'y_range': ...,
            'outlier_count': sum(1 for d in r['raw_data'] if d.get('is_outlier')),
        })
    return comparison
```

### 5. Comparison Charts

```python
# Source: charts/comparison.py
# Boxplot: 2-row grid (X and Y), one column per recipe
plot_recipe_comparison_boxplot(results)

# Trend: Overlay all recipe trends on shared axes
plot_recipe_comparison_trend(results)

# Heatmap: 2×N grid of contour heatmaps
plot_recipe_comparison_heatmap(results)
```

### 6. Recipe Name Validation

```python
# Source: ui/controllers/scan_controller.py → ScanMixin._scan_folder()
# Compare detected recipe names against spec settings
spec_dev = self.settings.get('spec_deviation', {})
std_names = list(spec_dev.keys())
for r in recipes:
    if r['short_name'] not in std_names:
        # Show error dialog, block analysis
        QMessageBox.critical(self, "❌ 폴더명 불일치", msg)
        return
```

## Pitfalls & Gotchas

- **Folder naming matters:** Recipe folders must follow `N. RecipeName` pattern for automatic detection and spec matching.
- **Round detection:** Only checks for `1st`, `2nd` subdirectories by default. Custom round names aren't supported.
- **short_name matching:** Case-insensitive comparison with trimming. Whitespace differences between spec keys and folder names cause matching failures.
- **Large datasets:** Loading all recipes at once may consume significant memory. The DataLoaderThread handles this in background.

## Testing Checklist

- [ ] `scan_recipes()` detects both flat and round folder structures
- [ ] `short_name` correctly strips leading numbers
- [ ] `load_all_recipes()` returns complete results with stats
- [ ] `compare_recipes()` produces comparison table for all recipes
- [ ] Recipe name validation catches mismatches

## Related Files

- `src/core/recipe_scanner.py` — Recipe detection + batch load (190 lines)
- `src/charts/comparison.py` — Comparison chart functions (164 lines)
- `src/ui/workers/data_loader_thread.py` — Background loading integration
