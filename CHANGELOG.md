# Changelog

## [0.1.0] - 2026-05-01

### Added
- `truncate_measurement_value()` — 측정값(frequency/Q)을 소수점 버림 정수화하는 핵심 함수
- ATX 선택 슬롯 편집 패널 (`Selected Slot Edit`): Probe Type, Frequency, Q, QR ID, Source 수정 지원
- QR ID 중복 검사 — 편집 적용 시 동일 QR 중복 차단
- `tests/test_measurement_values.py` — 정수화 로직·Port 정렬 검증 테스트 5건 추가

### Changed
- ATX Summary CSV 파싱: `float()` → `truncate_measurement_value()` (정수 저장)
- OCR 추출값: `float()` → `truncate_measurement_value()` (정수 반환)
- Manual 입력 적용값: `truncate_measurement_value()` 적용
- `SlotData.format_frequency()` / `format_q()`: `round()` → `truncate_measurement_value()` (소수점 버림)
- `manual_freq_input` / `manual_q_input`: `setDecimals(0)` — 정수 입력 UI
- Port 섹션 표시 순서: 오름차순 → 내림차순 (Port 4 → Port 2 → Port 1)
- `ManualCard.update_data()` / `MeasurementCard.update_data()`: sentinel 패턴 도입 (`_UNSET`) — `None` 명시 전달과 미전달 구분

### Fixed
- `image_parser.py`: dead `except ValueError` 제거 (truncate_measurement_value 내부 처리)
- `atx_import_mixin.py`: `freq and freq > 0` → `freq is not None and freq > 0` (0값 None 오해석 방지)
