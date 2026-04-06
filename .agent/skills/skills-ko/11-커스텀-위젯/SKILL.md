---
name: 커스텀 Qt 위젯
description: StatCard, CopyableTable, FlowLayout, ChartWidget, SystemLogger, Color Helpers
version: 1.0
---
# SKILL 11 — 커스텀 Qt 위젯
## 위젯 카탈로그
| 위젯 | 역할 |
|------|------|
| **StatCard** | Avg/Range/StdDev/Cpk + Pass/Fail 배지 + Spec 대비 ▲/✓ |
| **CopyableTable** | Ctrl+C → 탭 구분 클립보드 복사 |
| **FlowLayout** | heightForWidth 기반 가로 줄바꿈 레이아웃 |
| **ChartWidget** | Matplotlib Figure 안전 교체 + `plt.close()` |
| **InteractiveChartWidget** | PyQtGraph 위젯 안전 교체 + `deleteLater()` |
| **SystemLogger** | timestamp + 색상별 HTML 로그, section 구분선 |
| **Color Helpers** | 양극 발산/단색 히트맵, 자동 전경색 |
## 관련 파일
`ui/widgets/*.py`, `ui/color_helpers.py`
