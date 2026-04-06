---
name: PyQtGraph 인터랙티브 차트
description: 고성능 인터랙티브 차트 — 크로스헤어, 호버, 이중축, 다이별 산점도
version: 1.0
---
# SKILL 03 — PyQtGraph 인터랙티브 차트
## 위젯 목록
| 위젯 | 기능 |
|------|------|
| CrossHairPlotWidget | InfiniteLine + sigMouseMoved → 최근접 데이터 스냅 |
| HoverScatterWidget | Die별 ScatterPlotItem + 호버 라벨 + Die 강조/투명화 |
| Trend | Mean + σ fill_between + Spec InfiniteLine |
| Dual Trend | X/Y 2패널 + setXLink 동기 줌 |
| Scatter | Die별 HSL 색상, Signed Log 모드, Spec 박스 |
| Histogram | BarGraphItem + 정규분포 + σ 수직선 |
| Pareto | 이중축 (ViewBox) — 막대 + 누적%, 80% 기준선 |
| Correlation | 회귀선 + R² + 호버 |
## 관련 파일
`charts/interactive.py`, `charts/interactive_widgets.py`
