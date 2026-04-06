---
name: 검증 & QA 스킬
description: 6단계 검증 절차 — 정적분석, 단위, 런타임, 시각, E2E, 회귀
version: 1.0
---
# SKILL 16 — 검증 & QA
## 6단계 검증 레이어
1. **정적 분석**: `python -m py_compile`, import 검증, 스타일 일관성
2. **단위 검증**: compute_statistics, detect_outliers, extract_die_number 등
3. **런타임 테스트**: 앱 실행, 폴더 스캔, Step 네비게이션
4. **시각적 검사**: 컨투어, 벡터, 3D Surface, 히스토그램, Pareto 차트
5. **E2E 파이프라인**: CSV → 파싱 → 통계 → 차트 → 내보내기
6. **회귀 체크**: 변경 전/후 통계값 비교 (±0.001 tolerance)
## 검증 보고서 템플릿
각 레이어 ✅/❌ 상태 + 발견 이슈 + Sign-off 체크리스트
## 스킬 문서 자체 검증
- YAML frontmatter 파싱
- 관련 파일 경로 존재 확인
- 코드 예제 ↔ 소스 코드 일치 (3건 무작위)
