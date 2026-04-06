---
name: PySide6 다크 테마 GUI 프레임워크
description: Catppuccin Mocha 기반 다크 테마, QSS 스타일시트, Dynamic Property, 패널 토글
version: 1.1
---

# SKILL 01 — PySide6 다크 테마 GUI 프레임워크

## 핵심 요소
- **색상 팔레트**: BG(`#1e1e2e`), FG(`#cdd6f4`), ACCENT(`#89b4fa`), GREEN/RED/ORANGE/PURPLE
- **QSS**: f-string 기반 전체 앱 스타일 (`DARK_STYLE`)
- **Dynamic Property**: `setProperty("accent", "true")` + `style().polish()` → 동적 스타일 전환
- **Fusion 엔진**: 크로스플랫폼 일관된 렌더링
- **Color Helpers**: `_heatmap_diverging()`, `_heatmap_single()`, `_contrast_fg()`

## 사이드 패널 토글 (F11)
- **QShortcut + QKeySequence**: `F11` 키로 좌측 설정 패널 숨기기/보이기
- **패턴**: `QSplitter` + `setVisible(False/True)` + `setSizes()` 복원
- **상태 관리**: `_side_panel_visible` bool 플래그
- **주의**: `setFixedWidth()` 대신 `setMinimumWidth()` + `setMaximumWidth()` 사용 (setVisible 호환)

## 관련 파일
`ui/theme.py`, `ui/color_helpers.py`, `main.py`, `ui/main_window.py`, `ui/dialogs/guide_dialog.py`
