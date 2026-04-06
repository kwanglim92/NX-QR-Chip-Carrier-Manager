---
name: MVC Mixin 아키텍처 & UI Builder
description: 12개 Mixin 다중 상속으로 QMainWindow 분할 — 컨트롤러 분리
version: 1.0
---
# SKILL 12 — MVC Mixin 아키텍처
## 클래스 구성
`DataAnalyzerApp(UIBuilderMixin, QMainWindow, ScanMixin, StepMixin, CardMixin, TableMixin, ChartMixin, XYLegendMixin, DieFilterMixin, LotFilterMixin, TiffMixin, ExportMixin)`
## Mixin 역할
| Mixin | 역할 | 라인 |
|-------|------|------|
| UIBuilderMixin | 전체 UI 구성 | 983줄 |
| ScanMixin | 폴더 스캔 + DataLoaderThread | 147줄 |
| StepMixin | Step 네비게이션 + Pass/Fail | 235줄 |
| CardMixin | StatCard 업데이트 | 60줄 |
| TableMixin | 테이블 갱신 + 히트맵 색상 | 236줄 |
| ChartMixin | 차트 렌더링 + QTimer 지연 | 218줄 |
| DieFilterMixin | Die 체크박스 + 미니맵 토글 | 161줄 |
| LotFilterMixin | Lot 체크박스 + 범위 지정 | 144줄 |
| XYLegendMixin | XY Scatter 범례 + Log 스케일 | 135줄 |
| TiffMixin | TIFF 탐색 + 뷰어 | 140줄 |
| ExportMixin | CSV/Excel/PDF 내보내기 | 63줄 |
## 핵심 패턴
- Mixin은 `__init__()` 없음 → `self`를 통한 공유 상태
- `_add_chart(label, type)` 차트 등록 시스템
- `QTimer.singleShot(50, 후속작업)` 지연 렌더링
## 관련 파일
`main.py`, `ui/controllers/*.py`, `ui/dialogs/*.py`
