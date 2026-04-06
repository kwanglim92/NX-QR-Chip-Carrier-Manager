---
name: Settings Persistence System
description: JSON-based application settings with 3-stage merge, spec configuration, and recent folder tracking.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [12-mvc-mixin-architecture]
---

# SKILL 14 — Settings Persistence System

## Overview

Manages persistent application settings via JSON, with a sophisticated 3-stage merge strategy that balances user preferences with code-level defaults. Includes spec limit configuration per recipe and recent folder history.

**When to use:** When implementing app settings that survive restarts, with some keys always resetting and others always using code defaults.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `json` (stdlib) | Read/write settings file |
| `os` (stdlib) | File path resolution |

## Core Patterns

### 1. Three-Stage Settings Merge

```python
# Source: core/settings.py → load_settings()
def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()              # Stage 1: Code defaults
    if os.path.exists(SETTINGS_FILE):
        saved = json.load(open(SETTINGS_FILE))
        for k, v in saved.items():
            if k not in _ALWAYS_DEFAULT_KEYS         # Stage 2: Merge saved
               and k not in _RESET_ON_START_KEYS:
                settings[k] = v
    # Stage 3: _ALWAYS_DEFAULT_KEYS → forced to code default
    # Stage 4: _RESET_ON_START_KEYS → reset on every launch
    return settings
```

**Key categories:**

| Category | Behavior | Example |
|----------|----------|---------|
| Normal keys | Persisted across sessions | `spec_limits`, `outlier_method` |
| `_ALWAYS_DEFAULT_KEYS` | Code default always wins (auto-update) | `standard_recipe_names` |
| `_RESET_ON_START_KEYS` | Reset to default on every launch | `last_folder` |

### 2. Default Settings Structure

```python
# Source: core/settings.py
DEFAULT_SETTINGS = {
    'last_folder': '',
    'last_axis': 'both',
    'use_all_range': True,
    'outlier_method': 'iqr',
    'outlier_threshold': 1.5,
    'export_delimiter': '\t',
    'window_geometry': '',
    'recent_folders': [],
    'spec_limits': {                    # Cpk calculation limits
        'Vision Pattern Recognize': {
            'X': {'lsl': -5000.0, 'usl': 5000.0},
            'Y': {'lsl': -5000.0, 'usl': 5000.0}
        },
        # ... per recipe
    },
    'spec_deviation': {                 # Pass/Fail thresholds
        'Vision Pattern Rec…': {'spec_range': 4.0, 'spec_stddev': 0.8},
        'In-Die Align':       {'spec_range': 4.0, 'spec_stddev': 0.8},
        'Global Align':       {'spec_range': 7.5, 'spec_stddev': 2.2},
    },
    'standard_recipe_names': ['Vision Pattern', 'In-Die Align', ...],
    'wafer_size': 300,  # mm: 200 or 300
}
```

### 3. Recent Folder Tracking

```python
# Source: core/settings.py → add_recent_folder()
def add_recent_folder(settings, folder_path):
    recents = settings.get('recent_folders', [])
    if folder_path in recents:
        recents.remove(folder_path)    # Remove duplicate
    recents.insert(0, folder_path)     # Add to front
    settings['recent_folders'] = recents[:5]  # Keep max 5
    return settings
```

### 4. Settings File Location

```python
# Source: core/settings.py
SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))  # Same as core/
SETTINGS_FILE = os.path.join(SETTINGS_DIR, 'settings.json')
```

Settings file lives alongside the source code in the `core/` directory.

### 5. Window Geometry Save/Restore

```python
# Source: main.py
def _save_settings(self):
    geom = self.geometry()
    self.settings['window_geometry'] = f"{geom.width()}x{geom.height()}+{geom.x()}+{geom.y()}"

def _restore_settings(self):
    if self.folder_path and os.path.isdir(self.folder_path):
        self.path_edit.setText(self.folder_path)
        QTimer.singleShot(100, self._scan_folder)  # Auto-load on launch
```

## Pitfalls & Gotchas

- **File path:** Settings are saved in the `core/` source directory, not user's app data. This means settings are project-specific, not user-specific.
- **JSON encoding:** Uses `ensure_ascii=False` for Korean recipe names in spec_limits.
- **IOError suppression:** Both `load_settings()` and `save_settings()` silently catch IO errors. Check for corruption manually.
- **Spec key matching:** Recipe names in `spec_deviation` must match the `short_name` from `scan_recipes()` — see `ScanMixin._scan_folder()` for validation logic.

## Testing Checklist

- [ ] `load_settings()` returns complete defaults when no file exists
- [ ] Saved settings persist after `save_settings()` →  `load_settings()` cycle
- [ ] `_ALWAYS_DEFAULT_KEYS` are not overwritten by saved values
- [ ] `_RESET_ON_START_KEYS` are reset on every load
- [ ] `add_recent_folder()` maintains 5-item limit with FIFO order
- [ ] Malformed `settings.json` doesn't crash `load_settings()`

## Related Files

- `src/core/settings.py` — Settings logic (96 lines)
- `src/ui/dialogs/spec_config_dialog.py` — Settings viewer dialog
