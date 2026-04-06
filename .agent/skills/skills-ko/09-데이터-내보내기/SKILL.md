---
name: 데이터 내보내기 파이프라인
description: CSV/TSV, Excel 멀티시트, PDF 멀티페이지 내보내기 + 스레딩
version: 1.0
---
# SKILL 09 — 데이터 내보내기
## 3가지 형식
- **CSV/TSV**: `utf-8-sig` BOM 인코딩 (한국어 Excel 호환)
- **Excel**: openpyxl 4시트 (Raw/Statistics/Trend/Repeatability) + 헤더 스타일링
- **PDF**: `PdfPages` 멀티페이지 — Summary 테이블 + Recipe별 2×2 차트
## 스레딩 패턴
- PDF: `threading.Thread(daemon=True)` + `QTimer.singleShot(0, callback)` UI 복귀
- openpyxl 미설치 시 CSV 폴백
## 관련 파일
`core/exporter.py`, `core/pdf_generator.py`, `ui/controllers/export_controller.py`
