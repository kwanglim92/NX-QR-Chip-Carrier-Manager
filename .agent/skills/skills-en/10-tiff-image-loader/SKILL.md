---
name: TIFF Image Loader & Viewer
description: PSPylib TIFF integration with metadata extraction, 2D reshape, and interactive image viewer with line profile.
version: 1.0
project_origin: XY Stage Positioning Offset Analysis
related_skills: [03-pyqtgraph-interactive-charts, 12-mvc-mixin-architecture]
---

# SKILL 10 — TIFF Image Loader & Viewer

## Overview

Loads and visualizes TIFF height map images from semiconductor scan tools using the PSPylib library. Features metadata extraction, 2D array reshaping, interactive image viewing with ROI-based line profiles, and multi-file tabbed comparison.

**When to use:** When integrating proprietary TIFF format reading and interactive image analysis.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `pspylib.tiff.reader` | `TiffReader` — proprietary TIFF format |
| `pyqtgraph` | `ImageView`, `LinearRegionItem` for viewer |
| `numpy` | Array reshape and operations |

## Core Patterns

### 1. TIFF Loading with PSPylib

```python
# Source: core/tiff_loader.py → load_tiff()
from pspylib.tiff.reader import TiffReader

def load_tiff(file_path: str) -> dict:
    reader = TiffReader()
    reader.load(file_path)
    meta = _extract_metadata(reader)     # scanHeader → dict
    data_2d = _reshape_data(reader)       # ZData → 2D numpy
    return {
        'path': file_path,
        'filename': os.path.basename(file_path),
        'metadata': meta,
        'data': data_2d,
    }
```

### 2. Metadata Extraction

```python
# Source: core/tiff_loader.py → _extract_metadata()
def _extract_metadata(reader):
    header = reader.scanHeader
    return {
        'channel': _decode_ascii(header.channelName),
        'mode': _decode_ascii(header.headMode),
        'width': header.pixelWidth,
        'height': header.pixelHeight,
        'scan_size_x': header.scanSizeX,
        'scan_size_y': header.scanSizeY,
        'z_unit': _decode_ascii(header.zUnit),
        'xy_unit': _decode_ascii(header.xyUnit),
    }
```

### 3. 2D Array Reshape

```python
# Source: core/tiff_loader.py → _reshape_data()
def _reshape_data(reader):
    z_data = np.array(reader.ZData)          # 1D array
    height = reader.scanHeader.pixelHeight
    width = reader.scanHeader.pixelWidth
    return z_data.reshape(height, width)      # 2D numpy array
```

### 4. ASCII Decoding (uint16 arrays)

```python
# Source: core/tiff_loader.py → _decode_ascii()
def _decode_ascii(arr):
    if arr is None:
        return ''
    try:
        return ''.join(chr(v) for v in arr if 0 < v < 128)
    except (TypeError, ValueError):
        return str(arr)
```

### 5. TiffViewerWidget (Interactive)

```python
# Source: charts/interactive_widgets.py → TiffViewerWidget
class TiffViewerWidget(QWidget):
    def __init__(self, data_2d, metadata):
        self.image_view = pg.ImageView()
        self.image_view.setImage(data_2d)

        # ROI Line Profile
        self.roi = pg.LinearRegionItem(orientation='vertical')
        self.image_view.addItem(self.roi)
        self.roi.sigRegionChanged.connect(self._update_profile)

        self.profile_plot = pg.PlotWidget()  # Line profile display

    def _update_profile(self):
        region = self.roi.getRegion()
        col_start, col_end = int(region[0]), int(region[1])
        profile = self.data[:, col_start:col_end].mean(axis=1)
        self.profile_plot.plot(profile, clear=True)
```

### 6. MultiTiffViewerWidget (Tabbed)

```python
# Source: charts/interactive_widgets.py → MultiTiffViewerWidget
class MultiTiffViewerWidget(QWidget):
    def set_results(self, results: list):
        # Clear existing tabs
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        # Add one TiffViewerWidget per result
        for result in results:
            viewer = TiffViewerWidget(result['data'], result['metadata'])
            self.tab_widget.addTab(viewer, result['filename'])
```

### 7. Row Double-Click → TIFF Auto-Search

```python
# Source: ui/controllers/tiff_controller.py → TiffMixin._find_tiff_for_row()
# 1. Get lot_name + site_id from clicked table row
# 2. Find TIFF file in lot folder: filename contains site_id
# 3. Exclude Debug/Capture subdirectories
# 4. Fallback: extract numeric part of site_id and match
```

## Pitfalls & Gotchas

- **PSPylib required:** `pspylib` is a proprietary library (`.whl` install). Handle `ImportError` with clear error message.
- **uint16 arrays:** TiffReader's string fields are uint16 arrays, not Python strings. Always use `_decode_ascii()`.
- **Large images:** High-resolution TIFF files (4096×4096+) may cause memory issues. Consider downsampling for display.
- **ROI updates:** `sigRegionChanged` fires on every mouse move. Debounce if profile computation is expensive.

## Testing Checklist

- [ ] `load_tiff()` returns valid 2D array with correct dimensions
- [ ] Metadata fields (channel, mode, scan size) are properly decoded
- [ ] TiffViewerWidget displays image and updates line profile
- [ ] MultiTiffViewerWidget creates correct number of tabs
- [ ] Missing PSPylib shows helpful error, not crash

## Related Files

- `src/core/tiff_loader.py` — TIFF loading logic (171 lines)
- `src/charts/interactive_widgets.py` — TiffViewerWidget, MultiTiffViewerWidget
- `src/ui/controllers/tiff_controller.py` — Row click → TIFF display (140 lines)
