---
name: 통계 분석 엔진
description: 순수 Python 통계 — 평균, 표준편차, 이상치, 반복성, Cpk
version: 1.0
---
# SKILL 07 — 통계 분석 엔진
## 함수 목록
| 함수 | 기능 |
|------|------|
| `compute_statistics()` | count, mean, stdev, min, max, range |
| `compute_group_statistics()` | 그룹별 (lot/site/method) 통계 |
| `compute_trend()` | lot_index 순 에이징 트렌드 |
| `detect_outliers()` | IQR / Z-score / 절대범위 3가지 방법 |
| `compute_repeatability()` | Lot간 + Site별 변동 + CV% |
| `compute_cpk()` | min(CPU, CPL) — LSL/USL 기반 |
| `compare_1st_2nd_by_site()` | Site별 1st/2nd 매칭 + diff |
| `filter_by_method()` / `filter_valid_only()` | 데이터 필터링 |
## 주의사항
- **Population stdev** (÷N) 사용 — Excel STDEV (÷N-1)와 다름
- `detect_outliers()`는 in-place 수정 (복사본 아님)
## 관련 파일
`core/statistics.py`
