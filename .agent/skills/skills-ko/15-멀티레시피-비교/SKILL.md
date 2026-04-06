---
name: 멀티 레시피 비교 시스템
description: Recipe 자동 탐지, 일괄 로드, 교차 비교 통계, 비교 차트
version: 1.0
---
# SKILL 15 — 멀티 레시피 비교
## 핵심 흐름
1. `scan_recipes()` — 2단계 구조 탐지 (플랫/라운드)
2. `short_name` 생성 — `re.sub(r'^\d+\.\s*', '', name)` 번호 제거
3. `load_all_recipes()` — 전 Recipe 데이터 + 통계 + 이상치 일괄 산출
4. `compare_recipes()` — mean, stdev, CV%, outlier 교차 비교 테이블
5. 비교 차트: Boxplot (2×N), Trend 오버레이, Heatmap 그리드
## 폴더 구조
- **플랫**: `data/Recipe명/Lot들`
- **라운드**: `data/Recipe명/1st/Lot들` + `2nd/Lot들`
## 네이밍 검증
ScanMixin이 Spec 설정 키와 폴더명 일치 여부 검증 → 불일치 시 차단
## 관련 파일
`core/recipe_scanner.py`, `charts/comparison.py`, `ui/workers/data_loader_thread.py`
