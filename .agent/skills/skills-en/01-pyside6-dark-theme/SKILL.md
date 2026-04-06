---
name: PySide6 Dark Theme GUI Framework
description: Catppuccin Mocha dark theme system with QSS stylesheets, dynamic properties, Fusion style engine, and side panel toggle.
version: 1.1
project_origin: XY Stage Positioning Offset Analysis
related_skills: [11-custom-qt-widgets, 12-mvc-mixin-architecture]
---

# SKILL 01 — PySide6 Dark Theme GUI Framework

## Overview

Implements a sophisticated dark theme system for PySide6 desktop applications using the Catppuccin Mocha color palette. Features f-string-based QSS stylesheets, dynamic property switching, and a centralized color constant system.

**When to use:** When building a professional dark-themed PySide6 desktop application.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `PySide6` | Qt6 Python bindings |
| `PySide6.QtWidgets` | Widget framework |
| `PySide6.QtGui` | QPainter, QColor, QFont |
| `PySide6.QtCore` | Qt, Signal, Slot |

## Core Patterns

### 1. Centralized Color Constants

```python
# Source: ui/theme.py
BG      = '#1e1e2e'    # Base background
BG2     = '#282840'    # Elevated surface
BG3     = '#313244'    # Highest surface
FG      = '#cdd6f4'    # Primary text
FG2     = '#a6adc8'    # Secondary text
ACCENT  = '#89b4fa'    # Accent blue
GREEN   = '#a6e3a1'    # Pass / Success
RED     = '#f38ba8'    # Fail / Error
ORANGE  = '#fab387'    # Warning
PURPLE  = '#cba6f7'    # Headers / Sections
```

### 2. f-String QSS Stylesheet

```python
# Source: ui/theme.py → DARK_STYLE
DARK_STYLE = f"""
QMainWindow, QWidget {{ background: {BG}; color: {FG}; }}
QTabWidget::pane {{ border: 1px solid {BG3}; background: {BG}; }}
QTabBar::tab {{
    background: {BG2}; color: {FG2}; padding: 6px 16px;
    border-top-left-radius: 4px;
}}
QTabBar::tab:selected {{ background: {BG}; color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
QPushButton {{
    background: {BG2}; color: {FG}; border: 1px solid {BG3};
    border-radius: 4px; padding: 6px 12px;
}}
QPushButton:hover {{ background: {BG3}; }}
QPushButton[accent="true"] {{ background: {ACCENT}; color: {BG}; font-weight: bold; }}
"""
```

### 3. Dynamic Property Pattern

State-based styling without changing code:

```python
# Source: main.py / ui/controllers/step_controller.py
btn = QPushButton("Step 1")
btn.setProperty("accent", "true")
btn.style().polish(btn)          # Re-evaluate QSS with new property

# QSS selector:
# QPushButton[accent="true"] { background: #89b4fa; color: #1e1e2e; }
# QPushButton[step_pass="true"] { border-bottom: 3px solid #a6e3a1; }
# QPushButton[step_pass="false"] { border-bottom: 3px solid #f38ba8; }
```

### 4. Fusion Style Engine

```python
# Source: main.py
app = QApplication(sys.argv)
app.setStyle("Fusion")        # Cross-platform consistent rendering
app.setStyleSheet(DARK_STYLE)  # Apply dark theme globally
```

**Rationale:** `Fusion` provides identical widget rendering across Windows, macOS, and Linux, unlike native styles that vary by platform.

### 5. Side Panel Toggle (F11 Shortcut)

```python
# Source: ui/main_window.py
from PySide6.QtGui import QShortcut, QKeySequence

# In _setup_ui():
self._side_panel_visible = True
shortcut = QShortcut(QKeySequence(Qt.Key_F11), self)
shortcut.activated.connect(self._toggle_side_panel)

def _toggle_side_panel(self):
    self._side_panel_visible = not self._side_panel_visible
    self.settings_widget.setVisible(self._side_panel_visible)
    if self._side_panel_visible:
        self.main_splitter.setSizes([260, 1000])
```

**Note:** Use `setMinimumWidth()` + `setMaximumWidth()` instead of `setFixedWidth()` for the panel widget — `setFixedWidth` prevents `setVisible(False)` from fully collapsing the splitter.

### 6. Guide Dialog (In-App Help)

```python
# Source: ui/dialogs/guide_dialog.py → GuideDialog
class GuideDialog(QDialog):
    def __init__(self, parent=None):
        # QSplitter: QListWidget (navigation) | QTextBrowser (content)
        # HTML-based content pages with themed styling
        # Navigation: list click → content switch
```

Structure: Left nav (QListWidget) + Right content (QTextBrowser with HTML).

## Color Helpers

```python
# Source: ui/color_helpers.py
_heatmap_diverging(value, abs_max)   # Negative→blue, Zero→neutral, Positive→red
_heatmap_single(value, max_val)      # 0→dark, max→steel blue
_contrast_fg(bg_hex)                 # Returns '#000' or '#fff' for readability
```

## Pitfalls & Gotchas

- **`style().polish()`:** Required after `setProperty()` for QSS re-evaluation. Without it, the style change won't be visible.
- **QSS specificity:** Property selectors `[prop="val"]` have higher specificity than type selectors. Order matters in the stylesheet.
- **Font rendering:** Korean text requires explicit font setting (`font-family: 'Malgun Gothic'`) in QSS for Labels/Buttons.
- **Memory:** Large QSS strings parsed on every `setStyleSheet()` call. Apply once at app level, use properties for dynamic changes.

## Testing Checklist

- [ ] App launches with full dark theme (no white widget flashes)
- [ ] All button states render correctly (normal, hover, accent, pass, fail)
- [ ] Tab bar shows selected tab with accent underline
- [ ] Table headers use dark background with light text
- [ ] Dynamic property changes are visually reflected after `polish()`

## Related Files

- `src/ui/theme.py` — Color constants + DARK_STYLE QSS
- `src/ui/color_helpers.py` — Heatmap and contrast utilities
- `src/main.py` — App initialization with Fusion + theme
- `src/ui/main_window.py` — Side panel toggle implementation
- `src/ui/dialogs/guide_dialog.py` — Themed help dialog
