---
name: Data Export Pipeline
description: CSV/TSV, Excel (openpyxl multi-sheet), and PDF (matplotlib PdfPages) export with threading.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [07-statistical-analysis-engine, 12-mvc-mixin-architecture]
---

# SKILL 09 — Data Export Pipeline

## Overview

Provides three export formats for analysis results: CSV/TSV plain text, styled Excel workbooks (multi-sheet), and multi-page PDF reports with embedded charts. Includes threaded PDF generation for non-blocking UI.

**When to use:** When implementing data export functionality from analysis applications.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `csv` (stdlib) | CSV/TSV writing |
| `openpyxl` | Excel workbook creation (optional dependency) |
| `matplotlib.backends.backend_pdf` | `PdfPages` multi-page PDF |
| `threading` (stdlib) | Background PDF generation |

## Core Patterns

### 1. CSV/TSV Export

```python
# Source: core/exporter.py → export_combined_csv()
def export_combined_csv(data, output_path, delimiter='\t'):
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(['Lot', 'Site', 'Method', 'Value', ...])
        for row in data:
            writer.writerow([row['lot_name'], row['site_id'], ...])
```

**Note:** `utf-8-sig` encoding adds BOM for Korean Excel compatibility.

### 2. Excel Multi-Sheet Report

```python
# Source: core/exporter.py → export_excel_report()
# Sheet 1: Raw Data — all measurement records
# Sheet 2: Statistics — per-recipe summary stats
# Sheet 3: Trend — lot-by-lot trend data
# Sheet 4: Repeatability — site-level variation

# Styling:
header_fill = PatternFill(start_color='1565C0', fill_type='solid')
header_font = Font(name='맑은 고딕', bold=True, color='FFFFFF')
thin_border = Border(left=Side(style='thin'), ...)
```

### 3. PDF Multi-Page Report

```python
# Source: core/pdf_generator.py → generate_pdf_report()
with PdfPages(output_path) as pdf:
    # Page 1: Summary table (comparison data)
    fig_summary = _create_summary_page(comparison_data, spec_limits)
    pdf.savefig(fig_summary); plt.close(fig_summary)

    # Pages 2+: Per-recipe chart pages (2×2 grid)
    for recipe in results:
        fig = plt.figure(figsize=(16, 12))
        ax1 = fig.add_subplot(2, 2, 1)  # Contour X
        ax2 = fig.add_subplot(2, 2, 2)  # Contour Y
        ax3 = fig.add_subplot(2, 2, 3)  # Vector Map
        ax4 = fig.add_subplot(2, 2, 4)  # Boxplot
        pdf.savefig(fig); plt.close(fig)
```

### 4. Threaded PDF Export

```python
# Source: ui/controllers/export_controller.py → ExportMixin._export_pdf()
def _export_pdf(self):
    def run():
        try:
            results = load_all_recipes(self.path_edit.text())
            generate_pdf_report(path, ...)
            QTimer.singleShot(0, lambda: self.logger.ok(f"PDF 완료"))
            os.startfile(path)  # Auto-open on Windows
        except Exception as e:
            QTimer.singleShot(0, lambda: self.logger.error(str(e)))
    threading.Thread(target=run, daemon=True).start()
```

### 5. Graceful openpyxl Fallback

```python
# Source: core/exporter.py
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side
except ImportError:
    # Fallback: export as CSV instead of Excel
    export_combined_csv(data, path.replace('.xlsx', '.csv'))
```

## Pitfalls & Gotchas

- **BOM for Korean Excel:** Always use `utf-8-sig`, not `utf-8`. Korean Excel opens CSV as garbled text without BOM.
- **openpyxl optional:** Not included in default Python. Handle `ImportError` with CSV fallback.
- **PDF memory:** Large datasets with many recipes can consume significant memory. `plt.close()` after each page is critical.
- **Threading + Qt:** Never call Qt widgets from background thread. Use `QTimer.singleShot(0, callback)` to bounce back to the UI thread.
- **`os.startfile()`:** Windows-only. On macOS use `subprocess.call(['open', path])`, on Linux `xdg-open`.

## Testing Checklist

- [ ] CSV output opens in Excel with correct Korean encoding
- [ ] Excel workbook has all 4 sheets with styled headers
- [ ] PDF generates multi-page output without errors
- [ ] PDF auto-opens after generation
- [ ] UI remains responsive during PDF generation (threading)

## Related Files

- `src/core/exporter.py` — CSV/Excel export (196 lines)
- `src/core/pdf_generator.py` — PDF report generation
- `src/ui/controllers/export_controller.py` — Export button handlers (63 lines)
