---
name: Die 편차 분석
description: 편차 행렬, Affine Transform, Pareto, 상관 분석, 안정화 Die 필터
version: 1.0
---
# SKILL 08 — Die 편차 분석
## 핵심 함수
| 함수 | 기능 |
|------|------|
| `compute_deviation_matrix()` | Die × Repeat 행렬 + die_stats 집계 |
| `compute_affine_transform()` | Translation, Scale(ppm), Rotation(µrad) 분리 — lstsq |
| `compute_pareto_data()` | 이상치 빈도 내림차순 + 누적% |
| `compute_correlation()` | X/Y 피어슨 상관 + 회귀선 |
| `filter_stabilization_die()` | 첫 측정 Die 제외 |
| `extract_die_positions()` | 동적 Die 좌표 추출 |
## Affine Transform 수학 모델
- `dx = Tx + Sx·x − θ·y`, `dy = Ty + Sy·y + θ·x`
- `np.linalg.lstsq(A, b)` 최소자승법
## 관련 파일
`core/die_analysis.py`
