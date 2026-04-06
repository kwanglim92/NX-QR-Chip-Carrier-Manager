---
name: Custom Qt Widgets
description: Reusable PySide6 widgets including stat cards, copyable tables, flow layout, chart containers, and system logger.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [01-pyside6-dark-theme, 12-mvc-mixin-architecture]
---

# SKILL 11 — Custom Qt Widgets

## Overview

A collection of reusable PySide6 widgets designed for dark-themed data analysis applications. Each widget follows a pattern of minimal API surface, safe resource cleanup, and theme integration.

**When to use:** When building custom UI components for data-intensive desktop applications.

## Widgets Catalog

### 1. StatCard — Statistics Summary Card

```python
# Source: ui/widgets/stat_card.py
class StatCard(QFrame):
    def __init__(self, title='X', parent=None):
        # Layout: Title | Avg value | Range/StdDev/Cpk grid | Pass/Fail badge
        # Spec comparison: ▲ exceed / ✓ within spec

    def update_stats(self, mean, range_val, stddev, cpk, passed,
                     spec_r=None, spec_s=None):
        self.avg_label.setText(f"{mean:.4f}")
        # Pass/Fail badge color
        if passed is True:
            self.badge.setStyleSheet(f"background:{GREEN}; color:{BG};")
            self.badge.setText("PASS")
        elif passed is False:
            self.badge.setStyleSheet(f"background:{RED}; color:{BG};")
            self.badge.setText("FAIL")
```

**Key design:** Spec values are displayed alongside measured values with ▲/✓ indicators:
- `Range: 3.45 ✓ (< 4.00)` → within spec
- `StdDev: 0.92 ▲ (> 0.80)` → exceeds spec

### 2. CopyableTable — Ctrl+C Table Copy

```python
# Source: ui/widgets/copyable_table.py
class CopyableTable(QTableWidget):
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            selected = self.selectedRanges()
            text = ''
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                row_data = []
                for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                    item = self.item(row, col)
                    row_data.append(item.text() if item else '')
                text += '\t'.join(row_data) + '\n'
            QApplication.clipboard().setText(text)
```

**Tab-delimited output** pastes correctly into Excel.

### 3. FlowLayout — Auto-Wrapping Layout

```python
# Source: ui/widgets/flow_layout.py
class FlowLayout(QLayout):
    def _do_layout(self, rect, test_only):
        x, y = rect.x(), rect.y()
        line_height = 0
        for item in self._items:
            next_x = x + item.sizeHint().width() + self._spacing
            if next_x > rect.right() and line_height > 0:
                x = rect.x()           # Wrap to next line
                y += line_height + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x += item.sizeHint().width() + self._spacing
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)
```

**Use case:** Die filter checkboxes that automatically wrap when the panel width changes.

### 4. ChartWidget — Matplotlib Container

```python
# Source: ui/widgets/chart_widget.py
class ChartWidget(QWidget):
    def set_figure(self, fig):
        # Safe replacement: remove old canvas, close old figure
        if self._canvas:
            old_fig = self._canvas.figure
            self._layout.removeWidget(self._canvas)
            self._canvas.deleteLater()
            plt.close(old_fig)    # Prevent memory leak
        self._canvas = FigureCanvasQTAgg(fig)
        self._layout.addWidget(self._canvas)
```

### 5. InteractiveChartWidget — PyQtGraph Container

```python
# Source: ui/widgets/chart_widget.py
class InteractiveChartWidget(QWidget):
    def set_widget(self, widget):
        if self._widget:
            self._layout.removeWidget(self._widget)
            self._widget.deleteLater()
        self._widget = widget
        self._layout.addWidget(widget)

    def get_widget(self):
        return self._widget
```

### 6. SystemLogger — Color-Coded Log Output

```python
# Source: ui/widgets/system_logger.py
class SystemLogger:
    COLORS = {'info': FG2, 'ok': GREEN, 'warn': ORANGE, 'err': RED, 'head': PURPLE}

    def _append(self, msg, tag='info'):
        ts = datetime.now().strftime('%H:%M:%S')
        color = self.COLORS.get(tag, FG2)
        self._te.append(f'<span style="color:{ACCENT}">[{ts}]</span> '
                        f'<span style="color:{color}">{msg}</span>')

    def section(self, title):
        self._te.append(f'<br><span style="color:{PURPLE};font-weight:bold">'
                        f'{"═"*50}<br>  {title}<br>{"═"*50}</span>')
```

### 7. Color Helper Functions

```python
# Source: ui/color_helpers.py
_heatmap_diverging(value, abs_max)  # Negative→blue, 0→neutral, Positive→red
_heatmap_single(value, max_val)     # 0→dark, max→steel blue (#4682B4)
_contrast_fg(bg_hex)                # Returns '#000' or '#fff' for readability
```

## Pitfalls & Gotchas

- **Figure Memory:** Always `plt.close(old_fig)` in `ChartWidget.set_figure()`. Omitting this causes unbounded memory growth.
- **FlowLayout heightForWidth:** Must be implemented for QScrollArea to correctly calculate scrollable height.
- **CopyableTable:** `selectedRanges()` may return multiple disjoint ranges. The implementation handles the first range only.
- **SystemLogger HTML:** Uses `append()` which auto-scrolls. Very large logs may slow down the QTextEdit.

## Testing Checklist

- [ ] StatCard correctly shows Pass/Fail badge with spec comparison
- [ ] Ctrl+C copies table data in tab-delimited format
- [ ] FlowLayout wraps items correctly on resize
- [ ] ChartWidget figure replacement doesn't leak memory
- [ ] SystemLogger shows correct timestamps and colors

## Related Files

- `src/ui/widgets/stat_card.py` — StatCard widget
- `src/ui/widgets/copyable_table.py` — CopyableTable widget
- `src/ui/widgets/flow_layout.py` — FlowLayout
- `src/ui/widgets/chart_widget.py` — ChartWidget + InteractiveChartWidget
- `src/ui/widgets/system_logger.py` — SystemLogger
- `src/ui/color_helpers.py` — Color utility functions
