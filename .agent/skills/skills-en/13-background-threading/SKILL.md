---
name: Background Threading & Data Pipeline
description: QThread subclass with Signal/Slot pattern for non-blocking data loading and UI-safe updates.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [12-mvc-mixin-architecture, 06-csv-raw-data-parser]
---

# SKILL 13 — Background Threading & Data Pipeline

## Overview

Implements background data loading using QThread to keep the UI responsive during long-running data parsing operations. Uses Qt's Signal/Slot mechanism for thread-safe UI updates.

**When to use:** When loading or processing data that takes >100ms and would otherwise freeze the UI.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `PySide6.QtCore` | `QThread`, `Signal`, `QTimer` |
| `threading` (stdlib) | Daemon threads for fire-and-forget jobs |

## Core Patterns

### 1. QThread Subclass

```python
# Source: ui/workers/data_loader_thread.py
from PySide6.QtCore import QThread, Signal

class DataLoaderThread(QThread):
    finished = Signal(object, object, float)  # results, comparison, elapsed_sec
    error = Signal(str)                        # error message

    def __init__(self, root_path, round_name='1st'):
        super().__init__()
        self.root_path = root_path
        self.round_name = round_name

    def run(self):
        import time
        t0 = time.time()
        try:
            from core.recipe_scanner import load_all_recipes, compare_recipes
            results = load_all_recipes(self.root_path,
                                       round_name=self.round_name,
                                       axis='both')
            comparison = compare_recipes(results)
            elapsed = time.time() - t0
            self.finished.emit(results, comparison, elapsed)
        except Exception as e:
            self.error.emit(str(e))
```

### 2. Signal Connection in Controller

```python
# Source: ui/controllers/scan_controller.py → ScanMixin._scan_folder()
self._loader_thread = DataLoaderThread(folder)
self._loader_thread.finished.connect(self._on_scan_complete)
self._loader_thread.error.connect(
    lambda e: (self.logger.error(f"로드 오류: {e}"),
               QMessageBox.critical(self, "오류", e)))
self._loader_thread.start()
```

### 3. UI-Thread-Safe Callback

**From QThread Signal (auto-marshalled):**
```python
# QThread signals are automatically dispatched to the receiver's thread
# If receiver is a QObject in the main thread, slot runs in main thread
self._loader_thread.finished.connect(self._on_scan_complete)
```

**From stdlib Thread (manual marshalling):**
```python
# Source: ui/controllers/export_controller.py → ExportMixin._export_pdf()
def run():
    try:
        generate_pdf_report(...)
        # Must bounce back to UI thread:
        QTimer.singleShot(0, lambda: self.logger.ok("PDF 완료"))
    except Exception as e:
        QTimer.singleShot(0, lambda: self.logger.error(str(e)))

threading.Thread(target=run, daemon=True).start()
```

### 4. Thread Lifecycle Management

```python
# Source: ui/controllers/scan_controller.py
# Store reference to prevent garbage collection:
self._loader_thread = DataLoaderThread(folder)

# The thread is stored as an instance attribute
# When a new scan starts, the old thread (if finished) is replaced
# QThread.finished signal is auto-emitted when run() returns
```

### 5. Progress Callback Pattern

```python
# Source: core/recipe_scanner.py → load_all_recipes()
def load_all_recipes(root_path, progress_cb=None, ...):
    recipes = scan_recipes(root_path)
    for i, recipe in enumerate(recipes):
        if progress_cb:
            progress_cb(i, len(recipes), recipe['name'])
        # ... load data ...

# Usage in DataLoaderThread:
# results = load_all_recipes(path, progress_cb=self._on_progress)
```

## Pitfalls & Gotchas

- **QThread vs threading.Thread:** Use `QThread` when you need signals. Use `threading.Thread(daemon=True)` for fire-and-forget jobs.
- **Never access widgets from worker thread.** Use `QTimer.singleShot(0, callback)` or Qt Signals.
- **Lambda capture:** In `QTimer.singleShot(0, lambda: ...)`, variables are captured by reference. Use `lambda e=e: ...` for value capture.
- **Thread reference:** Keep a reference (`self._loader_thread = ...`). Without it, Python garbage-collects the thread.
- **Multiple scans:** If user clicks "Scan" while a scan is running, the old thread completes and its signals are still connected. Guard against stale results.

## Testing Checklist

- [ ] UI remains responsive during data loading
- [ ] `finished` signal delivers correct results to main thread
- [ ] `error` signal shows error dialog without crash
- [ ] PDF export runs in background, shows success on completion
- [ ] No "QObject: Cannot create children for a parent in different thread" warnings

## Related Files

- `src/ui/workers/data_loader_thread.py` — QThread subclass
- `src/ui/controllers/scan_controller.py` — Thread launch + result handling
- `src/ui/controllers/export_controller.py` — daemon thread for PDF
