---
name: Matplotlib 정적 차트
description: 한국어 폰트, Qt 임베딩, Figure 메모리 관리를 포함한 정적 차트 생성
version: 1.0
---
# SKILL 02 — Matplotlib 정적 차트
## 핵심 차트
- **Trend**: Mean ± 1σ 밴드, Min/Max, Overall Mean
- **Heatmap/Contour**: griddata cubic 보간, RdYlGn 컬러맵
- **Boxplot**: 그룹별 분산 + 이상치 flier
- **Histogram**: density + 정규분포 곡선 오버레이
- **Recipe 비교**: 2×N boxplot, 오버레이 trend, 2×2 heatmap
## 핵심 패턴
- OS별 한국어 폰트 분기 (Malgun Gothic / AppleGothic / NanumGothic)
- `axes.unicode_minus = False` (마이너스 기호 깨짐 방지)
- `_fig_to_png()` + `plt.close(fig)` 메모리 관리
- `FigureCanvasQTAgg` + `NavigationToolbar2QT` Qt 임베딩
## 관련 파일
`charts/basic.py`, `charts/comparison.py`, `charts/wafer.py`, `ui/widgets/chart_widget.py`
