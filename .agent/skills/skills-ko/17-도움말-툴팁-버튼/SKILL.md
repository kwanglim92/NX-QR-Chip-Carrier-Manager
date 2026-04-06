---
name: PySide6 도움말 툴팁 버튼
description: ℹ️ 아이콘 클릭 → 10초 툴팁 표시 패턴 (PySide6 다크 테마)
version: 1.0
---
# SKILL 17 — PySide6 도움말 툴팁 버튼
## 핵심 패턴
- `SP_MessageBoxInformation` OS 기본 ℹ️ 아이콘 (이미지 파일 불필요)
- 아이콘 16px / 버튼 22px 고정 → 컴팩트 원형
- 투명 배경 + 호버 시 `BG3` 원형 하이라이트
- `WhatsThisCursor` → 물음표 커서
- 클릭 시 `QToolTip.showText()` 10초 유지
## Lambda 캡처 주의
루프 안에서 여러 개 생성 시 **반드시 값 캡처**:
```python
lambda checked=False, b=help_btn, t=_help_text:
    QToolTip.showText(b.mapToGlobal(b.rect().bottomLeft()), t, b, b.rect(), 10000)
```
`checked=False` 필수 — QPushButton.clicked가 bool을 emit하므로 없으면 b에 bool이 들어감
## 프로젝트 내 참조
`ui_builder_mixin.py` L402, L474, L557
