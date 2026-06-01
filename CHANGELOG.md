# Changelog

## [2.2.0] - 2026-06-01

### Added
- **품질·수율 분석 (F-20)**: 통계 대시보드에 `In-Spec Yield %` / `Out-of-Spec` 카드, Probe Type별 규격(Spec) 한계 편집 다이얼로그(`⚙ Spec Limits`), 단일 probe 선택 시 SPC·히스토그램 USL/LSL 오버레이(규격 이탈 평균점 ORANGE 강조)
- **PDF 품질 리포트** (`📄 Export Report`): 요약 페이지 + 6개 차트를 matplotlib `PdfPages` 로 내보내기 (추가 의존성 없음)
- `src/core/quality.py` — 규격 평가·In-Spec 수율 계산 순수 함수 (`evaluate_slot`/`compute_yield`/`spec_bounds_for`)
- `src/ui/dialogs/spec_limits_dialog.py`, `tests/test_quality.py` (11건)
- `app_settings.spec_limits` 영속 키 (probe별 freq/q min·max)
- `docs/PRD.md` v2.2.0 전면 개정 + `docs/PRD.html` + `docs/build_prd_html.py` (의존성 0 변환기)

### Changed
- `stats_dashboard.load_stats()`: 수율/규격선 인자 추가(키워드 기본값 — 하위호환). 미사용이던 SPC `spec_upper`/`spec_lower` 정식 배선
- OCR tessdata 경로 전달: 공백 없는 8.3 short path 면 `--tessdata-dir`, 공백 경로면 `TESSDATA_PREFIX` 환경변수에 위임 (pytesseract `shlex.split` 한계 우회)
- Manual 측정 입력 범위 `9999` → `999999` (저장값 클램프 손실 방지)

### Fixed
- 업로드 QThread 재진입/누수 — 재진입 가드 + `deleteLater` 결선 + 업로드 중 버튼 비활성화로 `QThread: Destroyed while running` 크래시·객체 누수 방지
- `update_upload_status`: 실패 재시도가 과거 `uploaded_at` 을 NULL 로 덮어쓰던 문제 (`COALESCE`)
- `ServerUploader.upload`: CSV/이미지 파일 핸들 누수(`finally` close) — Windows 임시파일 잠김 해소
- OCR 풀 drain: `_prepare_manual_reorder`·`closeEvent`·`_on_restore_db` 에서 닫힌 DB 연결 쓰기/결과 유실 방지
- `MeasurementCard` PASS 판정에 Q factor 반영 (`SlotData.is_complete` 와 일치)
- `image_parser`: ROI 필드 독립 판정 + 누락 키 `KeyError` 방지
- `capture_files`: zoom-in/out 짝 파일명 stem 동기화(`final_capture_pair` 공유 카운터)
- `bundle`: overwrite 모드 신규 레코드 `imported` 집계 + 중복탐지 결정화(`ORDER BY`)
- CSV 저장 경로 `.csv` 확장자 보정, 번들 날짜 역순 검증, ATX `ATXNone` 제목 방지, ATX 광범위 `except` 축소, WAL sidecar 파일명(`-wal`/`-shm`) 교정

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
