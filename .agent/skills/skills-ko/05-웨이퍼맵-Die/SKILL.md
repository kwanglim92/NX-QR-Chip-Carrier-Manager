---
name: 웨이퍼 맵 & Die 포지션 시스템
description: 웨이퍼 컨투어, 벡터맵, Die 위치 시각화, 인터랙티브 미니맵
version: 1.0
---
# SKILL 05 — 웨이퍼 맵 & Die 포지션
## 핵심 시각화
| 차트 | 설명 |
|------|------|
| Wafer Contour | 원형 클리핑 + cKDTree 외곽 보간 + griddata cubic + 50 levels |
| Vector Map | ax.quiver() — 편차 방향/크기 화살표, 스케일 슬라이더 |
| Die Position Map | mpl_connect hover + 측정 순서 화살표 |
| Mini Die Map | 축소판 + picker=True + pick_event 클릭 토글 |
| Repeat Contour | N개 서브플롯 그리드 + 전역 컬러스케일 |
## 주의사항
- cKDTree 최근접 이웃으로 웨이퍼 경계 데이터 외삽 (아티팩트 방지)
- 보간 후 원형 마스킹 (순서 중요!)
## 관련 파일
`charts/wafer.py`, `core/die_analysis.py`, `ui/dialogs/repeat_contour_dialog.py`
