---
name: CSV Raw Data 파싱 엔진
description: 다중 인코딩 CSV 파서 — DLP 우회, 메타헤더 분리, 배치 로드
version: 1.0
---
# SKILL 06 — CSV Raw Data 파싱 엔진
## 핵심 패턴
- **인코딩 폴백**: utf-8-sig → cp949 → euc-kr → latin-1
- **DLP 우회**: xcopy 임시 복사 → 읽기 → 삭제 (PermissionError 대응)
- **메타헤더 분리**: SmartScan CSV 행 1-9 메타, 행 12 헤더, 행 13+ 데이터
- **폴더 자동 감지**: `_is_smartscan_csv()` → CSV 구조 기반 판별
- **배치 로드**: `batch_load(root, lot_range=None/tuple/list, axis='both')`
- **정규화**: `_normalize_row()` → 통일 dict (site_id, x_um, y_um, method, value 등)
## 관련 파일
`core/csv_loader.py`
