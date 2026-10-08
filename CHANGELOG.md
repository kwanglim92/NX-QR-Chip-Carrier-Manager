# Changelog

## [Unreleased]

### Added
- **리더기 연결 해제 / 연결 토글**: 리더기 설정 창 `1. 연결` 페이지의 `연결 테스트` 옆 버튼. `연결 해제` 는 접속을 끊고 백오프 재접속을 멈춰 리더기 없이 Inspection 등 다른 기능을 쓸 수 있게 하고, `연결` 은 현재 입력한 설정을 저장한 뒤 접속해 사용을 재개
- **상태 칩 `사용 안함`**: 리더기를 쓰지 않는 상태(연결 해제, 앱 시작 시 자동 접속 꺼짐, 전송 방식이 LAN 이 아님)는 상태 바 `● Reader` 칩에 `미연결`/`재접속 중` 대신 `사용 안함` 으로 표시. `미연결`은 사용 중인데 끊긴 순간에만
- **QR 입력창 영문 고정**: ATX/Manual 모드 하단 QR 입력창과 슬롯 편집 창의 QR ID 필드는 Windows 입력기가 한글이어도 IME 를 끄고 영문으로만 받아 바코드 스캔에 한글이 섞이지 않음 (`force_latin_input`)
- **서버 설정 다이얼로그 + 상태 바 `● Server` 칩**: 업로드 서버 로그인을 리더기와 같은 구조로 분리. 상태 바(Reader 칩 왼쪽) `● Server` 칩이 `미로그인 / 로그인됨 (ID) / 세션 만료 / 업로드 중` 을 보여주고, 클릭하면 서버 설정 창 — `1. 로그인`(ID·비밀번호·[로그인][로그아웃][세션 확인]) · `2. 서버 주소`(읽기 전용: QR 2.0 `probe-info` 현재 대상, QR 2.1 `cantilever-info` 추후 지원). 비밀번호는 보내는 즉시 입력창을 비우고 저장하지 않음. 앱 종료 시 서버 세션 종료
- **QR ID 디코더 + 업로드 버전 게이트** (`src/core/qr_code.py`): 16진수 10자리 QR ID 의 Encoding Major/Minor·생산연도·Probe Type·S/N 을 해독. 업로드 전 행의 QR 버전을 검사해 **2.0 외 버전(2.1 등)이 섞이면 경고창 후 업로드 차단**, 10자리 16진수가 아닌 코드는 경고 로그만 남기고 진행 (Save CSV 에는 적용 안 함)
- **Word 체크시트 자동 생성**: `Save CSV` 의 세 메뉴(CSV Only · CSV + Images · 머지 후 저장) 모두 CSV 옆에 카세트(ATX 폴더)마다 `{PO}_{수량}M_{Type}.docx` 를 생성. 전체(합본) 범위면 원본 폴더별로. 내용 = Unit/Type, Tip 프로필의 SEM 이미지·스펙 표, 1(L)~N(R) Frequency/Q-Factor(10M/12M → 10/12열), `4. Frequency Sweep` Pass/Fail(규격 한계 기준, 없으면 □). 기본 템플릿 `assets/templates/check_sheet_base.docx` 를 zip 수준에서 편집(python-docx 불필요)
- **`Tip 관리…`** (CSV Export 상단, Save CSV 왼쪽): Tip 별 Type 표기명 · SEM 이미지(썸네일, 저장 시 `tip_images/` 로 복사) · 스펙 표(양식 `min/typ/max` 또는 `Nominal Value/Specified Range`, 행 추가·삭제·이동). `app_settings.tip_profiles`. Tip 이름이 ATX 폴더 probe_type 과 같아야 Word 체크시트가 생성되며, 프로필이 없으면 로그 경고 후 생략

### Changed
- 리더기 설정 `저장` 은 사용 중이면 새 설정으로 재접속하고, `사용 안함` 상태에서는 설정만 저장하고 접속하지 않음 (이전: 저장 = 항상 즉시 접속)
- `Upload` 메뉴를 눌렀을 때 미로그인·세션 만료면 서버 설정 창의 로그인 섹션이 열리고, 로그인되면 자동으로 닫힌 뒤 업로드가 이어짐 (이전: 별도 ID/PW 소형 창)

### Removed
- CSV Export 좌하단 `○ Disconnected / Login` 행과 `src/ui/widgets/login_dialog.py` (서버 설정 창으로 대체)

## [2.4.0] - 2026-09-10

### Added
- **MTC Inspection 모드 (F-22)**: 툴바 `Inspection` — MTC 런 폴더(`20260909` 등)를 열어 슬롯별 등급을 **산업용/연구용/재검사/불량 사다리**로 자동 판정. 결과표(등급색)·등급 필터·Fail Item 판정식(`2.91 - 1 < 0.46 < 2.91 + 1`)·Vision/FreqSweep/ZoomOut 이미지·Reference Cantilever·Info, 우클릭 등급 수동 변경/파손 표시/기준 지정/폴더 열기, `Save` 로 검사 리포트 CSV
- **sweep 곡선 형상 자동 판정**: 줌인/ZoomOut txt 수치로 피크 수·Lorentzian R²·비대칭·부피크를 0~100 점수화(템플릿 항목 `Sweep Shape`), 판정 차트에 측정 곡선·피크·피팅·근거 오버레이(Zoom In/Out)
- **Vision 팁 파손 자동 판정**: pickUp 이미지 실루엣 길이/면적을 기준 슬롯 대비 비율로 판정(해상도 무관), 파손은 불량 강제 + 수동 override
- **등급 사다리 템플릿**: Tip ID 별 `Threshold` 폼(등급 탭 × 항목 11종, um/pixel), `New...`(복사)·삭제·Save — Save 시 산업용 Frequency/Q 를 History 의 Spec Limits 에 동기화(`app_settings.inspection_templates`)
- **Grouping → 로트 생성**: 등급·Unit No·Batch·12M/10M/5M 수량·Remain·OK/INVALID, `Run` 으로 `{UnitNo}_{qty}M_{Tip}` 로트 폴더(Summary.csv + FreqSweep/Vision 복사, 기존 ATX 형식) 생성 후 **ATX 모드 탭으로 자동 오픈**(DB 저장), Unit No 자동 +1, 내보낸 슬롯은 표에 `→ Unit No` 표시
- **로트 체크시트 자동 생성**: 템플릿 xlsx(Tip 템플릿의 `체크시트 템플릿` 경로)를 zip 수준에서 복사·편집해 `{Unit}_{qty}M_{정식 모델명}.xlsx` 생성 — Unit·Type(정식 모델명)·1(L)~12(R) Frequency/Q, A+B·Unipeak·Noise·Frequency Sweep Pass/Fail 자동(■/□), SEM/SPEC 이미지·보증 문구는 템플릿 그대로. Batch 는 마지막 입력값 기억
- **레이아웃 보기** (결과표 옆 버튼, 비모달 창): ATX 2×2(1 좌상·2 우상·3 좌하·4 우하) · Port2 위/Port1 아래 · Slot 4열×3행(ATX Mode 그리드 규칙)에 등급 색을 채우고 슬롯 코드(1101·2112 — 폴더/Summary.csv 와 동일)를 표시, 색 기준 콤보(등급 / Sweep 점수 / Frequency / Q), 기준 캔틸레버 굵은 테두리·로트 배지·수동 지정 표시, 클릭/우클릭/더블클릭은 결과표와 동일, 표 선택·등급 필터와 양방향 동기화, 범례 버튼 클릭 = 그 등급만 표시(다시 클릭 = 전체). Inspection 3열·세로 스플리터 비율은 실앱에서 맞춘 값을 기본으로 하고 종료 시 저장·복원(`inspection_splitters`)
- **Sweep Explorer** (판정 차트 더블클릭, pyqtgraph): ZoomOut/줌인 상하 2단 인터랙티브 창 — 휠 확대·드래그 이동·크로스헤어 좌표, 공진 세로선 3종(MTC Frequency·측정 피크·Lorentzian f0), 검출 피크 표(주파수·진폭·prominence·FWHM·Q 추정, 행 클릭 → 확대), 기준 슬롯 오버레이, 메인 표 선택 따라가기, 여러 창 동시. 이미지 뷰어 더블클릭 → 원본 크기 확대 창. `pyqtgraph` 의존성 추가
- `src/core/inspection/`(파서·형상·Vision·기준·템플릿·사다리·로트, 순수 함수) + 실런 발췌 fixture `tests/fixtures/mtc/20260909` + 테스트 59건
- 설계 문서 `docs/inspection-design.md`, PRD F-22, 사용자 가이드 §6.7
- **키엔스 SR-X300W 다중 QR 리더기 연동 — 다중 QR 스캔 (F-21)**: 하단 바 QR 입력 옆 `다중 QR 스캔`(F10) + `판독 검토`, 상태 바(Theme 왼쪽) `● Reader` 상태 칩. LAN/TCP 9004 레벨 트리거(LON → 판독 시간 → LOFF)로 최대 72칸을 한 번에 판독해 **레코드가 있는 칸은 즉시 현재 창에 QR 입력**(검토 창 없이), 나머지는 로그 요약
- **리더기 설정 다이얼로그**: IP·포트·자동 접속·LON/LOFF·판독 시간·기대 코드 수·NG 문자열·셀→Port/Slot 재정의 표, `연결 테스트`·`테스트 판독`·`리더기 값 읽기` (`app_settings.qr_reader`)
- **리더기 튜닝 페이지**: 뱅크 1 노출·게인·조명 종류·콘트라스트를 앱에서 읽고(`RB`) 수정해 `리더기에 쓰기 + 저장`(`WB` → `SAVE` → 재확인), `오토 포커스 실행`(`FTUNE`, 결과 통지 대기) — 실기기 검증 2026-09-09. 동작 파라미터(트리거 등)는 읽기 전용 유지
- **리더기 설정 창 UX 재구성**: 좌측 목록 사이드바(연결 · 판독 · 셀 → Port/Slot · 리더기 현재 값)에서 고른 섹션만 우측에 단독 표시(스크롤 없음), 입력 오류 시 해당 섹션으로 자동 이동, 각 섹션에 관련 버튼(연결 테스트 / 테스트 판독·판독 미리보기 / 리더기 값 읽기) 배치
- **판독 미리보기 실물 배치**: 보트 1장 = 카세트(Port) 6개 2열×3행, 카세트당 4열×3행으로 그리고 보트·카세트 테두리와 Port 라벨 표시. 리더기 화상은 눕혀져 있으므로 기본 270°(반시계) 회전(`preview_rotation`, 설정 창 '미리보기 회전' 또는 창의 `회전` 버튼으로 0/90/180/270 선택·저장)
- **앱 시작 시 리더기 자동 접속 기본 켜짐**: 설정을 저장한 적이 없어도 실행 즉시 리더기(`192.168.100.2:9004`) 연결을 시도하고 상태 칩에 결과 표시, 실패 시 백오프 재접속
- **판독 미리보기 창**: 리더기 서치 영역을 실제 좌표(`RD` 조회)대로 그리고 셀 번호·Port/Slot·판독 코드/NG 표시 — AutoID Network Navigator 없이 번호 배치·판독 결과 확인, `다시 판독`
- **판독 검토 다이얼로그**(`판독 검토` 버튼): 마지막 스캔을 **실물 배치**(보트 2열×3행 · 카세트 4열×3행, 판독 미리보기와 같은 `boat_layout` — 접속 시 읽어 둔 리더기 서치 영역 + 미리보기 회전)로 펼쳐 셀별 적용/NG/동일/중복/충돌/레코드 없음/제외 표시, 레코드 없음은 경고만(차단하지 않음), 충돌 칸 우클릭 덮어쓰기, 이상 칸만 보기
- **판독 미리보기 `적용` 버튼**: 현재 회전을 설정에 바로 저장(설정 창 저장 불필요), 판독 검토 창도 같은 배치를 따름
- `src/core/qr_reader/` (파서·슬롯 대응·QTcpSocket 클라이언트·설정, 순수 함수 + 시그널), `scripts/capture_keyence.py`(원문 캡처), `scripts/fake_keyence_server.py`(fixture 재생 가짜 리더기), 실제 캡처 fixture `tests/fixtures/qr_reader/`
- 테스트 +130건(qr_reader 파서·대응·클라이언트·설정·다이얼로그·믹스인, 실제 네트워크 무접촉)
- **Update(서버 수정) 업로드**: Upload 드롭다운에 `Update CSV (서버 수정)` / `Update CSV + Images (서버 수정)` 추가 — 서버 폼의 `update` 버튼으로 전송, 실행 전 덮어쓰기 확인 다이얼로그
- `csv_exporter.upload_image_files()` — 업로드 이미지 전송명을 CSV+Images 반출과 동일 규격(`{QR ID}.png`, 충돌 시 `_1`)으로 생성
- `ServerUploader.is_session_alive()` — 업로드 페이지를 리다이렉트 없이 GET 해 서버 세션 유효성 확인
- `tests/test_server_uploader.py` (26건, Fake Session — 실제 네트워크 무접촉) + `upload_image_files` 테스트 3건

### Changed
- 사용자 가이드를 2.4.0 실앱 화면과 Inspection·다중 QR 리더기 흐름 기준으로 전면 교체하고 배포용 PDF를 갱신
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
