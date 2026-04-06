---
name: TIFF 이미지 로더 & 뷰어
description: PSPylib TIFF 통합 — 메타데이터 추출, 2D 리쉐이프, 인터랙티브 뷰어
version: 1.0
---
# SKILL 10 — TIFF 이미지 로더
## 핵심 흐름
1. `TiffReader.load(path)` → scanHeader + ZData
2. `_extract_metadata()` → channel, mode, width/height, scanSize, zUnit
3. `_reshape_data()` → 1D ZData → 2D numpy (height × width)
4. `TiffViewerWidget` → pg.ImageView + LinearRegionItem ROI + Line Profile
5. `MultiTiffViewerWidget` → QTabWidget 서브탭 (복수 TIFF 비교)
## ASCII 디코딩
uint16 배열 → `chr(v)` 변환 (`_decode_ascii()`)
## 관련 파일
`core/tiff_loader.py`, `charts/interactive_widgets.py`, `ui/controllers/tiff_controller.py`
