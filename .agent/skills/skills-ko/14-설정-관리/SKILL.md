---
name: 설정 관리 시스템
description: JSON 설정 파일 — 3단계 병합, Spec 구성, 최근 폴더 추적
version: 1.0
---
# SKILL 14 — 설정 관리 시스템
## 3단계 병합
1. `DEFAULT_SETTINGS` 코드 기본값
2. `settings.json` 저장값 병합
3. `_ALWAYS_DEFAULT_KEYS` 강제 적용 / `_RESET_ON_START_KEYS` 리셋
## 주요 설정 구조
- `spec_limits`: Recipe별 X/Y LSL/USL (Cpk 계산용)
- `spec_deviation`: Recipe별 range/stddev 임계값 (Pass/Fail 판정)
- `recent_folders`: 최대 5개 FIFO
- `wafer_size`: 200mm / 300mm
## 관련 파일
`core/settings.py`, `ui/dialogs/spec_config_dialog.py`
