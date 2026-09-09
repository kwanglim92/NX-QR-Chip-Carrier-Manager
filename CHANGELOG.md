# Changelog

## [Unreleased]

### Added
- **키엔스 SR-X300W 다중 QR 리더기 연동 — 카세트 스캔 (F-21)**: 하단 바 `● Reader` 상태 칩 + `카세트 스캔`(F10). LAN/TCP 9004 레벨 트리거(LON → 판독 시간 → LOFF)로 최대 72칸을 한 번에 판독해 로드된 ATX 폴더 탭 전체에 일괄 매칭
- **리더기 설정 다이얼로그**: IP·포트·자동 접속·LON/LOFF·판독 시간·기대 코드 수·NG 문자열·셀→Port/Slot 재정의 표, `연결 테스트`·`테스트 판독`·`리더기 값 읽기`(노출·게인·조명·트리거 방식 등 읽기 전용) (`app_settings.qr_reader`)
- **리더기 설정 창 UX 재구성**: 좌측 목차 사이드바(연결 · 판독 · 셀 → Port/Slot · 리더기 현재 값) + 우측 본문 스크롤 구조, 목차 클릭 → 섹션 이동 · 스크롤 → 현재 섹션 강조, 입력 오류 시 해당 섹션으로 자동 이동, 각 섹션에 관련 버튼(연결 테스트 / 테스트 판독·판독 미리보기 / 리더기 값 읽기) 배치
- **앱 시작 시 리더기 자동 접속 기본 켜짐**: 설정을 저장한 적이 없어도 실행 즉시 리더기(`192.168.100.2:9004`) 연결을 시도하고 상태 칩에 결과 표시, 실패 시 백오프 재접속
- **판독 미리보기 창**: 리더기 서치 영역을 실제 좌표(`RD` 조회)대로 그리고 셀 번호·Port/Slot·판독 코드/NG 표시 — AutoID Network Navigator 없이 번호 배치·판독 결과 확인, `다시 판독`
- **카세트 판독 검토 다이얼로그**: 셀별 적용/NG/동일/중복/충돌/레코드 없음/제외 분류, 레코드 없음 시 적용 차단, 충돌 칸 우클릭 덮어쓰기, 이상 칸만 보기
- `src/core/qr_reader/` (파서·슬롯 대응·QTcpSocket 클라이언트·설정, 순수 함수 + 시그널), `scripts/capture_keyence.py`(원문 캡처), `scripts/fake_keyence_server.py`(fixture 재생 가짜 리더기), 실제 캡처 fixture `tests/fixtures/qr_reader/`
- 테스트 +130건(qr_reader 파서·대응·클라이언트·설정·다이얼로그·믹스인, 실제 네트워크 무접촉)
- **Update(서버 수정) 업로드**: Upload 드롭다운에 `Update CSV (서버 수정)` / `Update CSV + Images (서버 수정)` 추가 — 서버 폼의 `update` 버튼으로 전송, 실행 전 덮어쓰기 확인 다이얼로그
- `csv_exporter.upload_image_files()` — 업로드 이미지 전송명을 CSV+Images 반출과 동일 규격(`{QR ID}.png`, 충돌 시 `_1`)으로 생성
- `ServerUploader.is_session_alive()` — 업로드 페이지를 리다이렉트 없이 GET 해 서버 세션 유효성 확인
- `tests/test_server_uploader.py` (26건, Fake Session — 실제 네트워크 무접촉) + `upload_image_files` 테스트 3건

### Changed
- accent 버튼 비활성(`:disabled`) 스타일 추가 — 비활성인데 활성처럼 보이던 문제
- **TLS 인증서 검증 활성화**: `verify=False`·`urllib3` 경고 억제 제거 (서버 인증서 유효 확인)
- 로그인 성공 판정 강화: `sessionid` 쿠키 **및** 응답이 로그인 폼이 아님
- 업로드 전 세션 유효성 확인, GET/POST 응답이 로그인/`?next=` 리다이렉트면 실패 처리 → UI 상태 Disconnected 로 동기화
- 서버 `Message :` 영역이 없으면 성공으로 간주하지 않음 (`응답 형식 불일치`)
- 업로드 POST 타임아웃을 이미지 수에 비례(60 + 10/장, 최대 600초)
- 로그인 다이얼로그 비밀번호는 로그인 호출 직후 참조 해제, 로그아웃 시 로컬 쿠키 폐기
- `ServerUploader.upload()` 이미지 인자를 `(로컬 경로, 전송 파일명)` 목록으로 변경

### Fixed
- 서버 세션이 만료된 상태에서 업로드하면 `/chip/?next=` 페이지의 CSRF 토큰으로 POST 한 뒤 "응답 확인 불가"를 **성공으로 오판**하던 문제

## [2.3.0] - 2026-07-02

### Added
- **Pass Pool 단일 연속 스택**: 전 폴더의 규격 통과(pass) 슬롯을 하나의 스택으로 표시(맨 아래 Port1, 위로 갈수록 Port 증가), 폴더 순번 뱃지(①②③)·폴더색으로 출처를 명확히 구분
- **상단 고정 Pass Pool 토글**: 폴더 그리드 ↔ 풀 전환(실시간 매칭 N/M 배지)
- **드래그 폴더 칩 스트립**: Pass Pool 을 벗어나지 않고 폴더 순서 변경(색·번호 범례 겸용)
- **Cassette(12) 명시적 선택 조립 → CSV**: 카드 체크박스로 최대 12개 선택 후 한 장의 Cassette CSV 반출(부분 Cassette 허용)
- **CSV Export 다중 폴더**: 전체(합본) + 폴더 선택 스코프, 표에 PO(출처) 열
- `slot_mapper.circled_number()` — 원형 순번(①②③) 헬퍼

### Changed
- 폴더 탭 드래그 재정렬 지원 + 탭/칩 재정렬을 단일 funnel 로 통일해 순번·연속 Port 를 실시간 재부여
- 폴더 탭 라벨에 순번 프리픽스(`① P2601001 …`)
- '캐리어 확정' UI 용어를 **Cassette** 로 통일(버튼·툴팁·안내 메시지·저장 파일명 `cassette_QR.csv`)
- 합본 Export: 슬롯 재인덱싱·유효 probe 스탬프, 날짜 변경 시 합본 throwaway 레코드 미저장(각 폴더 set 만 저장)

### Fixed
- `PoolFolderStrip`: `QListWidget::item` 스타일시트가 item `setBackground`/`setForeground` 역할을 무시시켜 폴더 칩 색이 표시되지 않던 문제 수정
- 폴더 재정렬/닫힘 시 위치 종속 Pass Pool 선택 키를 무효화(Cassette 선택 초기화)

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
