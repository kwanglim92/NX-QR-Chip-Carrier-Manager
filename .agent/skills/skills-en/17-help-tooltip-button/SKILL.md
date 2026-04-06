---
name: PySide6 Help Tooltip Button
description: Reusable ℹ️ info button pattern with click-to-show tooltip for PySide6 dark-themed applications.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [01-pyside6-dark-theme, 11-custom-qt-widgets, 12-mvc-mixin-architecture]
---

# SKILL 17 — PySide6 Help Tooltip Button

## Overview

A compact, reusable pattern for adding ℹ️ info buttons next to any widget. Clicking the button shows a persistent tooltip (10 seconds) with help text. Uses the OS system icon — no image assets needed.

**When to use:** When adding contextual help to any UI element (buttons, labels, section headers).

## Tech Stack

| Library | Purpose |
|---------|---------|
| `PySide6.QtWidgets` | `QPushButton`, `QStyle`, `QToolTip` |
| `PySide6.QtCore` | `Qt`, `QSize` |

## Core Pattern

### Complete Implementation (Copy-Paste Ready)

```python
from PySide6.QtWidgets import QPushButton, QStyle, QToolTip
from PySide6.QtCore import Qt, QSize

# 1. Define help text
_help_text = "여기에 도움말 내용 작성 (여러 줄 가능)\n두 번째 줄"

# 2. Create button with system ℹ️ icon
help_btn = QPushButton()
help_btn.setIcon(self.style().standardIcon(
    QStyle.StandardPixmap.SP_MessageBoxInformation))
help_btn.setIconSize(QSize(16, 16))
help_btn.setFixedSize(22, 22)
help_btn.setCursor(Qt.WhatsThisCursor)

# 3. Dark theme styling (transparent + hover highlight)
help_btn.setStyleSheet(f"""
    QPushButton {{ background: transparent; border: none; }}
    QPushButton:hover {{ background: {BG3}; border-radius: 11px; }}
""")

# 4. Register tooltip text
help_btn.setToolTip(_help_text)

# 5. Click → force-show tooltip (10 seconds)
help_btn.clicked.connect(
    lambda checked=False, b=help_btn, t=_help_text:
        QToolTip.showText(b.mapToGlobal(
            b.rect().bottomLeft()), t, b, b.rect(), 10000))

# 6. Add to layout
toolbar_row.addWidget(help_btn)
```

## Key Design Decisions

| Element | Choice | Rationale |
|---------|--------|-----------|
| **Icon** | `SP_MessageBoxInformation` | OS-native ℹ️, no image file needed |
| **Size** | Icon 16px, Button 22px | Compact circular shape |
| **Hover** | Transparent → `BG3` circle | Consistent with dark theme |
| **Cursor** | `WhatsThisCursor` | Visual hint that help is available |
| **Duration** | 10000ms (10 sec) | Default tooltip disappears too fast for reading |

## Lambda Capture Warning

When creating multiple help buttons inside a `for` loop, **always capture by value**:

```python
# ❌ WRONG — all buttons reference the last loop value
help_btn.clicked.connect(lambda: QToolTip.showText(..., _help_text, ...))

# ✅ CORRECT — b and t are captured immediately
help_btn.clicked.connect(
    lambda checked=False, b=help_btn, t=_help_text:
        QToolTip.showText(b.mapToGlobal(
            b.rect().bottomLeft()), t, b, b.rect(), 10000))
```

**Why `checked=False`:** QPushButton.clicked emits a `bool` argument. Without the default parameter, the `bool` would be assigned to `b`, breaking the lambda.

## Helper Function (Optional)

For projects with many help buttons, extract into a reusable function:

```python
def create_help_button(parent, help_text, bg_hover='#313244'):
    btn = QPushButton()
    btn.setIcon(parent.style().standardIcon(
        QStyle.StandardPixmap.SP_MessageBoxInformation))
    btn.setIconSize(QSize(16, 16))
    btn.setFixedSize(22, 22)
    btn.setCursor(Qt.WhatsThisCursor)
    btn.setStyleSheet(f"""
        QPushButton {{ background: transparent; border: none; }}
        QPushButton:hover {{ background: {bg_hover}; border-radius: 11px; }}
    """)
    btn.setToolTip(help_text)
    btn.clicked.connect(
        lambda checked=False, b=btn, t=help_text:
            QToolTip.showText(b.mapToGlobal(
                b.rect().bottomLeft()), t, b, b.rect(), 10000))
    return btn
```

## Pitfalls & Gotchas

- **`BG3` reference:** Import from `ui.theme` or pass as parameter. Don't hardcode.
- **`border-radius: 11px`:** Half of button size (22px) for perfect circle. Adjust if button size changes.
- **Rich text:** `QToolTip` supports basic HTML for styled tooltips: `"<b>Title</b><br>Description"`.
- **Position:** `bottomLeft()` positions tooltip below the button. Use `topRight()` for alternative placement.

## Testing Checklist

- [ ] ℹ️ icon visible next to target widget
- [ ] Hover shows circular highlight (BG3 color)
- [ ] Cursor changes to ? on hover
- [ ] Click shows tooltip text for ~10 seconds
- [ ] Multiple buttons in a loop each show their own text (lambda capture)

## Related Files (Project References)

- `src/ui/controllers/ui_builder_mixin.py` L402–417 (Repeat Contour 도움말)
- `src/ui/controllers/ui_builder_mixin.py` L474–488 (Vector Map 도움말)
- `src/ui/controllers/ui_builder_mixin.py` L557–572 (Lot Trend 도움말)
