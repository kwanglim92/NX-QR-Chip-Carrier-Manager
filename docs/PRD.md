# MC QR Code Chip Carrier Manager — Product Requirements Document

| 항목 | 내용 |
|------|------|
| **문서 버전** | 2.2 |
| **작성일** | 2026-05-31 |
| **앱 버전** | 2.2.0 — `main` 기준 (코드 품질 감사 수정 + 품질·수율 분석 기능 반영) |
| **마지막 출시 버전** | 2.2.0 (2026-06-01) — `VERSION`/`CHANGELOG` 기준 |
| **이전 메이저** | 1.0.0 (NX 브랜드) → 2.0.0 (MC 브랜드 전환) |
| **대상 독자** | 개발 / 운영 / QA / 품질관리 |
| **내부 코드명** | `McQrManager` (이전: `NxQrManager`) |
| **저장소** | `main` 브랜치가 단일 기준 (solo 개발) |

> **이 문서의 목적**
> 1. **누가 봐도** 제품의 배경·목적·기능을 이해할 수 있게 한다(운영/QA/신규 합류자).
> 2. **이어서 개발**할 수 있게 아키텍처·확장 패턴·빌드/테스트·로드맵을 한 곳에 정리한다.
> 3. 최근 변경 사항(코드 감사 수정 + 품질·수율 기능)을 추적 가능하게 기록한다.
>
> HTML 버전: [`docs/PRD.html`](./PRD.html) (이 문서를 `docs/build_prd_html.py` 로 변환한 산출물).

---

## 1. 프로젝트 취지 및 배경

### 1.1 문제 정의

반도체 프로브(Probe) 측정 공장에서는 다음 세 가지 데이터 파편화 문제가 반복적으로 발생합니다.

1. **ATX 장비 CSV 파편화** — ATX 측정 장비가 슬롯별로 `summary_*.csv` 파일을 쏟아내지만, PO 번호·QR 코드·생산 날짜가 각 파일에 독립적으로 저장돼 있어 한 로트의 전체 상태를 한눈에 볼 수 없습니다.

2. **Manual 측정의 수기 입력 오류와 캡처 공정 낭비** — 로트카드(Lot Card) 수기 측정은 운영자가 눈으로 값을 읽어 Excel 에 입력하는 방식이라 오탈자가 빈번합니다. 특히 Frequency / Q-factor 같은 값에서 실수가 잦습니다. 기존에는 Windows 캡처 도구로 이미지를 저장한 뒤 다시 앱에 불러오는 공정이 필요했습니다.

3. **이력 분산 + 집계 불가** — 측정 이력이 각 PC 의 로컬 Excel 파일에 흩어져 있어, 일일 생산량·주간 추이·품질 수율을 집계하려면 수작업으로 파일을 모아야 합니다.

### 1.2 해결 방향

- **단일 데스크톱 앱** 으로 ATX 자동 파싱 + Manual Capture/OCR + 이력 DB + 품질 분석을 통합
- **`%LOCALAPPDATA%` SQLite(WAL 모드)** — 오프라인 공장 환경에서도 동작 보장
- **PostgreSQL 이관 친화 스키마** — 향후 중앙 서버 집약 시 수정 최소화 (ON CONFLICT UPSERT, TEXT 날짜, `GROUP_CONCAT` 금지, Python 측 집계)
- **PyInstaller + Inno Setup 단일 설치본** — 사용자 환경에 Python 설치 불필요, Tesseract 포터블 번들

### 1.3 대상 사용자

| 구분 | 역할 | 사용 시나리오 |
|------|------|---------------|
| 1차 | 공장 측정 오퍼레이터 (비개발자) | ATX 결과 Import / Manual 로트카드 캡처·OCR / QR 매칭 / 저장 |
| 2차 | 품질 관리자 | History Statistics 생산량·**품질 수율** 모니터링 / 규격(Spec) 설정 / **PDF 리포트** / CSV Export 검토 |
| 3차 | IT 담당자 | Inno Setup 인스톨러 배포 / PC 간 데이터 이전(Import 번들) / 백업·복원 |

---

## 2. 시스템 아키텍처

### 2.1 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| 런타임 | Python 3.11+ | 표준 라이브러리(`statistics`, `datetime`) 충실 |
| UI | PySide6 (Qt6) `>=6.6` | 공장 Windows 데스크톱 최적, GPL 회피 |
| DB | SQLite 3.24+ (WAL) | 설치형 로컬 앱, PG 이관 친화 |
| OCR | Tesseract 5.x + pytesseract `>=0.3.10` | 숫자 whitelist 로 Manual 카드 Freq/Q 자동 추출 |
| 이미지 | Pillow `>=10.0` | ROI 크롭만 필요, OpenCV 미도입으로 용량 최소화 |
| 차트/리포트 | Matplotlib `>=3.8` | `FigureCanvasQTAgg` 통합, `PdfPages` 로 PDF 리포트(추가 의존성 0) |
| HTTP | requests `>=2.31` + beautifulsoup4 `>=4.12` | 서버 업로드(CSRF/세션 폼 자동화) |
| 빌드 | PyInstaller 6.x (onedir, `contents_directory='.'`) | Tesseract DLL 경로 단순화 |
| 인스톨러 | Inno Setup 6.x | 한/영 다국어, 사용자 권한 설치 |

> 개발 의존성(`requirements-dev.txt`): `pytest>=7.0`, `pytest-qt>=4.4`, `pyinstaller>=6.0`.

### 2.2 레이어 구조 (MVC + Mixin, SKILL 12 패턴)

```
main.py                              ← Entry Point (QApplication 부팅, 테마 적용)
├─ src/core/                         ← 순수 로직 (Qt 의존성 최소, 단위 테스트 용이)
│   ├─ database.py                   — SQLite CRUD + PG 호환 UPSERT + 기간 집계 쿼리
│   ├─ models.py                     — MeasurementSet / SlotData dataclass + is_complete
│   ├─ atx_parser.py                 — summary_*.csv 파싱 → MeasurementSet
│   ├─ csv_exporter.py               — CSV / CSV+Images Export
│   ├─ bundle.py                     — JSONL + ZIP 번들 Export/Import (F-18)
│   ├─ capture_files.py              — Manual 캡처 파일명 / Zoom-In·Out 경로 규칙
│   ├─ image_parser.py               — Tesseract 기반 ROI OCR (F-14)
│   ├─ ocr_worker.py                 — QThreadPool 비동기 OCR (OcrRunnable)
│   ├─ ocr_settings.py               — 해상도별 ROI 프로파일(v2 스키마)
│   ├─ tesseract_setup.py            — 포터블 바이너리 탐색 + 8.3 short path / TESSDATA_PREFIX
│   ├─ slot_mapper.py                — ATX 슬롯코드 ↔ 그리드 위치 매핑
│   ├─ server_uploader.py            — HTTP 멀티파트 업로드
│   ├─ quality.py                    — 규격(Spec) 평가 + In-Spec 수율 (F-20, 순수 함수)
│   └─ qr_reader/                    — ★신규: 키엔스 리더기 (F-21) payload_parser · slot_assigner · keyence_client · settings
├─ src/ui/
│   ├─ theme.py                      — Catppuccin Mocha 색상/QSS
│   ├─ main_window.py                — ChipCarrierManagerApp = 8개 Mixin + QMainWindow 조립
│   ├─ controllers/                  — 페이지별 Mixin (아래 2.3)
│   ├─ widgets/                      — 재사용 위젯 (카드/그리드/테이블/뷰어/대시보드/로거)
│   └─ dialogs/                      — 모달 다이얼로그 (ROI/슬롯편집/번들/규격/탭추가/카탈로그/가이드)
└─ third_party/tesseract/           — 포터블 바이너리 + tessdata (번들, git 비포함)
```

### 2.3 Mixin 조립 순서 & 초기화 시퀀스

`ChipCarrierManagerApp` (`src/ui/main_window.py:17-39`) 은 8개 Mixin + `QMainWindow` 를 다중 상속합니다. **MRO 순서가 메서드 해석에 영향**을 주므로 변경 시 주의.

```python
class ChipCarrierManagerApp(
    UIBuilderMixin,      # UI 위젯 빌드
    ATXImportMixin,      # ATX 폴더 import + 슬롯 편집
    ManualImportMixin,   # Manual 모드 + 비동기 OCR 파이프라인
    QRMatchMixin,        # QR 스캔/매칭
    ExportMixin,         # CSV / CSV+Images / Merge Export
    UploadMixin,         # 서버 업로드(QThread)
    HistoryMixin,        # 이력/통계/번들/백업복원 + 품질·리포트(F-20)
    # … PassPoolMixin, QRReaderMixin(★F-21: 리더기 연결·카세트 스캔·검토·일괄 적용)
    SettingsMixin,       # 설정 저장/복원
    QMainWindow,
):
```

`__init__` 초기화 순서 (`main_window.py:28-39`): `_init_db` → `_init_ocr` → `_init_shared_state` → `_init_settings` → `_build_ui` → `_init_manual_state` → `_init_upload_state` → `_init_history_state` → `_restore_window_geometry` → `_apply_settings_to_ui`.

종료 시 `closeEvent` 는 설정 저장 → **OCR 풀 drain(`_ocr_pool.clear()/waitForDone`) + 배치 무효화** → DB 연결 close 순으로 동작(닫힌 연결에 늦은 OCR 콜백이 쓰는 것을 방지).

### 2.4 데이터 경로 분리

| 경로 | 내용 | 생존 |
|------|------|------|
| `C:\Program Files\McQrManager\` | 실행 파일, DLL, Tesseract | 언인스톨 시 제거 |
| `%LOCALAPPDATA%\MCQRCodeChipCarrier\chip_carrier.db` | 측정 이력 DB (+ `-wal`/`-shm` sidecar) | **언인스톨 해도 보존** |
| `%LOCALAPPDATA%\MCQRCodeChipCarrier\captures\` | Manual 캡처 이미지(Zoom-In/Zoom-Out) | 사용자 데이터로 보존 |
| 사용자 지정 폴더 | ATX summary CSV 원본, Manual 로트카드 이미지 | 사용자 관리 |

### 2.5 데이터 모델

- **`MeasurementSet`** — `po_number`, `quantity`, `probe_type`, `production_date(YYYYMMDD)`, `mode(atx|manual)`, `source_folder`, `slots[]`, `db_id`. 집계 프로퍼티 `matched_count` / `total_count` / `all_complete`.
- **`SlotData`** — `slot_index`, `slot_code`, `frequency`, `drive`, `q_factor`, `qr_id`, `image_path`, `source(summary_csv|manual_entry)`, `probe_type`, `serial_number`, `contact_mode`.
  - **`is_complete`**: 일반 슬롯 = `qr_id AND frequency AND q_factor`; **컨택(contact) 슬롯** = `qr_id` 만.
- 측정값은 정수로 절삭(`truncate_measurement_value`, `int(float(x))`) — 입력 경로(OCR/ATX/수기/슬롯편집) 전반에서 일관 적용.

---

## 3. 기능 명세

> 각 기능의 **진입점(버튼/메뉴/단축키)** 을 함께 표기해 "어떻게 실행하는지"가 분명하도록 했습니다.

### F-14 Manual OCR — 로트카드 자동 입력

| 항목 | 내용 |
|------|------|
| 진입 | 상단 `🎯 Calibrate OCR` (ROI 편집) / Manual 탭 이미지 드롭·캡처 시 자동 OCR |
| 입력 | 로트카드 JPG/PNG, 앱 내 화면 캡처 이미지 |
| 출력 | Frequency / Q-factor 자동 추출 → 입력 폼 pre-fill |
| 실패 대응 | 조용히 수기 입력 모드로 전환 (경고 없음) |
| 구성 파일 | `image_parser.py`, `ocr_worker.py`, `ocr_settings.py`, `tesseract_setup.py`, `roi_calibrator.py`, `roi_canvas.py` |

**핵심 특성**
- **숫자 whitelist OCR** — `--psm 7 -c tessedit_char_whitelist=0123456789.` 로 오탐 원천 차단
- **해상도별 ROI 프로파일** — `ocr_settings` 가 `{resolution_key: {frequency:[x,y,w,h], q_factor:[x,y,w,h]}}` 를 `app_settings.ocr_roi`(v2 스키마)에 저장
- **ROI Calibrator** — `QGraphicsView` 기반 시각 편집기. 신규 해상도는 드래그로 설정 + Test OCR 로 즉시 검증
- **비동기 파이프라인** — `QThreadPool` (최대 4 스레드)로 배치 처리 시 UI freeze 없음. 결과는 `finished` 시그널로 메인 스레드에서 반영
- **필드 독립 판정** — Frequency / Q 각각 독립적으로 성공/실패. 한쪽 ROI 가 범위를 벗어나도 다른 쪽은 읽음
- **범위 검증** — `_FREQ_RANGE=(50,5000) kHz`, `_Q_RANGE=(10,10000)` 벗어나면 추출 실패 처리
- **한글/공백 경로 대응** — Windows 8.3 short path(`get_tessdata_dir`)를 `--tessdata-dir` 로 직접 전달. 경로에 공백이 남으면(8.3 비활성) `--tessdata-dir` 을 생략하고 `TESSDATA_PREFIX` 환경변수에 위임(pytesseract 의 `shlex.split` 한계 우회)

### F-14A Manual Capture-First 워크플로우

| 항목 | 내용 |
|------|------|
| 진입 | Manual Mode `📸 Capture` 메뉴 또는 단축키 |
| Zoom-In 캡처 | **F6** Region / **F7** Window |
| Zoom-Out 캡처 | **F8** Region / **F9** Window |
| 저장 위치 | `captures\{YYYYMMDD}\{serial}\{zoomin,zoomout}\` |
| 파일명 | QR 전 `pending_XXXX.png`, QR 후 `slot_XX_{QRID}.png` (zoom-out 은 stem + `` ` `` 접미사) |

**핵심 특성**
- **Capture-First 공정** — 캡처 후 새 Manual 카드 자동 생성/선택, QR 입력창 자동 포커스
- **Region / Window Capture** — 드래그 영역 또는 Windows 창 클릭 캡처(Sweep 팝업 반복 캡처에 최적)
- **Zoom-In / Zoom-Out 분리** — Zoom-In 은 슬롯 생성 기준, Zoom-Out 은 선택 카드의 sibling 이미지로 첨부
- **순번 안정화** — 카드 삭제 시 남은 카드가 화면 순서 기준 `#1, #2…` 재정렬
- **파일명 짝 동기화** — QR 매칭/재정렬 시 zoom-in·zoom-out 파일명을 **공유 카운터**로 함께 확정해 stem 불일치 방지(`final_capture_pair`)
- **고정 뷰포트 미리보기** — 큰/비정형 캡처도 원본 보존, 화면에서는 Fit 표시로 레이아웃 흔들림 방지

### F-14B ATX 슬롯 다이얼로그 편집

| 항목 | 내용 |
|------|------|
| 진입 | ATX 카드 우클릭 → `수정…` |
| 편집 필드 | Probe Type, Frequency, Q-factor, QR ID, Source |
| 저장 | OK 시 중복 QR 검사 후 DB 자동 저장 |
| 취소 | Cancel 시 원본 `SlotData` 변경 없음 |

### F-15 측정 이력 SQLite (PostgreSQL 이관 친화)

스키마 상세는 **§9.3 DB 스키마** 참조. 핵심:

- **테이블**: `meta`(스키마 버전), `measurement_sets`, `slots`(FK CASCADE), `app_settings`(JSON KV)
- **PG 호환 설계**: `INSERT … ON CONFLICT DO UPDATE` 표준 UPSERT, TEXT `YYYYMMDD` 날짜, `GROUP_CONCAT` 금지(Python `statistics` 대체), `datetime('now')` DEFAULT 제거(호출자가 ISO 주입)
- **증분 마이그레이션**: `_migrate()` 가 `SCHEMA_VERSION` 비교 후 `ALTER TABLE` (멱등 보장). 현재 v3.

### F-16 History 조회

| 필터 | 구현 |
|------|------|
| 주차(ISO Week) | 드롭다운 (`iso_week` 정확 일치) |
| Probe Type | 드롭다운 |
| Upload Status | 드롭다운 (pending/uploaded/failed) |
| 검색 | `po_number`·`probe_type`·`slots.qr_id` LIKE |

- 레코드 클릭 → 상세 패널(슬롯 테이블 + 이미지 미리보기). 더블클릭 상세도 지원
- `Load Record` 로 ATX/Manual 모드에 복원, `Check All`/`Delete` 일괄 처리(체크 선택)
- 업로드 실패 건 재전송(Upload Mixin)

### F-17 History Statistics 생산량 분석

| 기간 | 집계 단위 |
|------|-----------|
| Today | `production_date = today()` |
| Daily / Weekly / Monthly / Quarterly / Yearly | `YYYYMMDD` / ISO 주차 / `YYYYMM` / `YYYY-Q#` / `YYYY` |

**화면 구성** (History → `Statistics` 탭)
- 필터행: Period / Probe Type 콤보 + **⚙ Spec Limits / 📄 Export Report 버튼**(F-20)
- Today KPI 3종 + 기간별 요약 테이블
- Overall KPI 카드: Total Sets / Slots / Avg Freq / Avg Q / Trend + **In-Spec Yield % / Out-of-Spec**(F-20)
- 차트: Production Trend(바+이동평균), Probe Type 누적 바, **Frequency/Q SPC(X-bar, CL/UCL/LCL)**, Frequency/Q 분포 히스토그램(정규곡선)

### F-17A CSV Export / Upload

| 항목 | 내용 |
|------|------|
| 진입 | `Save CSV` 드롭다운(CSV Only / CSV+Images / 머지) · `Upload` 드롭다운(Upload CSV / Upload CSV+Images / 머지 후 업로드 / **Update CSV / Update CSV+Images**) |
| 탭 구조 | `ATX` / `Manual` 2탭 (활성 탭 기준 처리) |
| CSV 컬럼 | `QR ID`, `생산일자[YYYYMMDD]`, `Frequency (KHz)`, `Drive (%)`, `Q`, `Probe Type` |
| 미완성 데이터 정책 | `QR 있는 값만` 또는 `전체 슬롯` 선택 |
| CSV+Images 구조 | `{folder}/{folder}_QR.csv` + `ZOOMIN/` + `ZOOMOUT/` |
| 저장 경로 보정 | 확장자 누락 시 `.csv` 자동 보정 |
| 서버 업로드 대상 | `https://probe-info.parksystems.com` — `POST /accounts/login/` 세션 로그인 후 `POST /chip/login/probe/update/file` (multipart: `test_file` CSV 1개 + `image_files[]` 다수, submit `upload`/`update`) |
| 업로드 이미지 전송명 | CSV+Images 반출과 동일 규격 `{QR ID}{확장자}` (충돌 시 `_1`, `_2`), `csv_exporter.upload_image_files()` |
| 세션·보안 | TLS 검증 활성, 비밀번호 미저장(ID 만 `server_id` 설정), 업로드 전 `is_session_alive()` 확인, 로그인/`?next=` 리다이렉트·`Message` 영역 부재는 실패 처리 |

- `Drive (%)` 는 GUI 입력 항목이 아니라 CSV/Upload 자료구조 유지용 컬럼
- 머지 출고: 여러 시리얼(파트)을 박스 시리얼 이름의 단일 CSV+이미지 폴더로 묶음
- **Update(서버 수정)** 는 서버의 기존 QR 데이터를 덮어쓰므로 실행 전 확인 다이얼로그를 거침. 기본 메뉴는 신규 `upload`

### F-18 Export / Import 번들

| 항목 | 내용 |
|------|------|
| 진입 | History 하단 `Export Bundle` / `Import Bundle` |
| 포맷 | ZIP (`manifest.json` + `data.jsonl` + `images/`) |
| 중복 정책 | `skip`(기본) / `overwrite` / `merge` |
| 스키마 버전 | v1 (`SUPPORTED_SCHEMA_VERSIONS` 호환성 체크) |
| 용도 | PC 간 이전 / 백업 / 중앙 서버 집약 전 단계 |

- 중복 식별은 `qr_id` 오버랩 기준 + (ATX) `source_folder` 보조 매칭. 결정성을 위해 `ORDER BY measurement_set_id LIMIT 1`
- zoom-out 경로는 zoom-in 경로에서 결정적으로 파생(`derive_zoomout_path`)
- 별도 백업: `Quick Backup`(.db 단순 복사) / `Quick Restore`(검증 후 교체, WAL sidecar 정리). 상세 스키마: [`docs/export_schema.md`](./export_schema.md)

### F-19 내장 사용자 가이드

| 항목 | 내용 |
|------|------|
| 진입 | 상단 `📘 설명서` 버튼 |
| 표시 | `QWebEngineView` 다이얼로그, 실패 시 기본 브라우저 fallback |
| 원본 | `docs/user-guide.html` (+ `docs/assets/user-guide/` 스크린샷) |

### ★ F-20 품질·수율 분석 + 규격(Spec) 한계 + PDF 리포트 (신규)

> 품질 관리자 페르소나를 위한 신규 기능. 통계 대시보드가 "생산량/완료율" 위주에서 **품질 적합성(규격 대비 양·불)** 까지 다루도록 확장.

| 항목 | 내용 |
|------|------|
| 진입 | History → `Statistics` 탭 → `⚙ Spec Limits` / `📄 Export Report` 버튼 |
| 저장 | `app_settings.spec_limits` (probe_type 별 JSON, 스키마 마이그레이션 불필요) |
| 구성 파일 | `quality.py`(신규), `spec_limits_dialog.py`(신규), `stats_dashboard.py`, `history_mixin.py`, `settings_mixin.py` |

**핵심 개념**
- **완료율(기존)** = `complete_slots / total_slots` — 입력 진척도
- **In-Spec 수율(신규)** = `in_spec / measured` — 측정된 슬롯(freq·q 보유) 중 규격 내 비율. **완료율과 분모가 다른** 별개 품질 지표
- 규격 미설정 probe 의 측정 슬롯은 `measured` 에 포함하되 in-spec 으로 집계 + `unspecced` 플래그(미정의 규격으로 불합 판정 불가)

**기능**
1. **규격(Spec) 편집** — `⚙ Spec Limits` → Probe Type 별 Frequency/Q 의 min·max 입력(빈칸=무제한, min≤max 검증). `app_settings` 에 영속.
2. **수율 카드** — Overall 영역에 `In-Spec Yield %`(99/95% 임계 색상) + `Out-of-Spec` 카드. 규격 미설정 시 "—".
3. **SPC 규격 오버레이** — 단일 probe 선택 시 Frequency/Q SPC 차트에 USL/LSL 선 표시 + 규격 이탈 기간평균을 **ORANGE**(관리한계 이탈 RED 와 구분). 히스토그램에도 규격 수직선.
4. **PDF 리포트** — `📄 Export Report` → 요약 페이지(메타 + Overall + 수율 overall/per-probe) + 6개 차트를 `PdfPages` 로 PDF 생성(다크 테마 유지, **추가 의존성 0** — 기존 matplotlib).

**설계 노트**: `stats_dashboard` 의 SPC 차트는 원래 `spec_upper/spec_lower` 파라미터를 가졌으나 `load_stats` 가 인자 없이 호출해 **죽은 코드**였음 → F-20 에서 정식 배선. `load_stats` 의 신규 인자(`yield_result`, `spec_lines`)는 키워드 기본값이라 **하위호환**.

### ★ F-21 키엔스 다중 QR 리더기 연동 — 다중 QR 스캔 (신규, Phase 2-B)

> MTC 환경에서 캐리어 카세트(최대 6개 × 12슬롯 = 72칸)를 키엔스 SR-X300W 코드 리더기로 **한 번에 판독**해, 로드된 ATX 폴더 탭 전체에 QR을 일괄 매칭한다. 키보드(HID) 스캐너 입력창은 단일 슬롯 정정·폴백으로 유지. 설계 문서: [`qr-reader-integration-design.md`](./qr-reader-integration-design.md).

| 항목 | 내용 |
|------|------|
| 진입 | 하단 바 [QR 입력] 옆 `다중 QR 스캔` 버튼(**F10**, 연결 시에만 활성) + `판독 검토` 버튼(스캔 후 활성). 상태 바(Theme 왼쪽)의 `● Reader …` 칩(클릭 → 리더기 설정) |
| 통신 | LAN/TCP 9004 단일 소켓, 앱이 클라이언트. 레벨 트리거 `LON` → 판독 시간(기본 6s) → `LOFF` 에서 결과 프레임 확정. AutoID Network Navigator 가 연결돼 있으면 리더기가 모든 명령을 `ER,<cmd>,23` 으로 거부 |
| 프레임 | `code×72` 를 `,` 로, 끝에 `:NNNNms`, 종단 `CR`. 미판독 `ERROR`. 셀 번호 = 인덱스, `port=(cell−1)÷12+1`, `slot=(cell−1)%12+1` (카세트 1 = Port 1) |
| 저장 | `app_settings.qr_reader` (IP·포트·자동 접속·LON/LOFF·판독 시간·기대 코드 수·NG 문자열·셀 재정의 표·미리보기 회전) |
| 구성 파일 | `core/qr_reader/{payload_parser,slot_assigner,keyence_client,settings,boat_layout}.py`, `ui/dialogs/qr_reader_settings_dialog.py`, `ui/dialogs/frame_preview_dialog.py`, `ui/dialogs/batch_read_review_dialog.py`, `ui/controllers/qr_reader_mixin.py`, `scripts/capture_keyence.py`, `scripts/fake_keyence_server.py` |

**기능**
1. **리더기 설정** — 전송 방식(LAN, Serial/Keyboard 는 폴백 자리), IP·포트, 자동 접속, 트리거/종료 명령, 판독 시간, 기대 코드 수, NG 문자열, 셀→Port/Slot 재정의 표(범위·대상 중복 검증). `연결 테스트`(`KEYENCE` 응답)·`테스트 판독`(판독 n/N·NG·스캔타임)은 임시 클라이언트로 수행. **리더기 튜닝** 페이지: 뱅크 1 노출·게인·조명 종류·콘트라스트를 읽고(`RB`) 수정해 `리더기에 쓰기 + 저장`(`WB` → `SAVE` → 재확인), `오토 포커스 실행`(`FTUNE`, 완료 통지 대기). 동작 파라미터(`RP`)는 읽기 전용.
2. **상시 연결·상태 칩** — 앱 시작 시 자동 접속(기본 켜짐, 설정에서 해제 가능), 끊기면 3s→30s 백오프 재접속, 접속 타임아웃 5s. 상태: 미연결/접속 중/연결됨/판독 중/재접속 중.
3. **다중 QR 스캔 → 즉시 적용, 판독 검토는 별도** — 프레임을 로드된 ATX 폴더(탭 순서 ①②③…)에 대응해 셀별 상태를 분류: 적용 / NG(미판독) / 동일 / 중복(프레임 내·로드된 슬롯) / 충돌(기존 다른 QR) / 레코드 없음 / 제외(폴더 미로드). **적용 칸은 검토 창 없이 바로 현재 창에 QR 입력**(슬롯 QR 갱신 → 그리드·탭 라벨·진행률·Pass Pool 갱신 → 폴더별 DB 자동 저장, 기존 단일 QR 경로와 동일 규칙), 나머지는 로그 요약. 레코드 없음은 그 칸만 미적용(차단 아님). `판독 검토` 버튼은 마지막 스캔을 **실물 배치**(보트 2열×3행, 카세트 4열×3행 — 판독 미리보기와 같은 `boat_layout`)로 펼쳐 보여 주고, 충돌 칸 우클릭 덮어쓰기 등을 `적용` 으로 반영.
4. **하드웨어 없는 검증** — `tests/fixtures/qr_reader/*.raw` 실제 캡처 원문을 파서·대응·클라이언트 테스트 입력으로 사용, `scripts/fake_keyence_server.py` 로 앱 전체를 리더기 없이 시험.

**예외 규칙(설계 §5)**: NG 셀은 빈 슬롯 유지 후 키보드 스캔으로 보완 · 레코드 없음 + 코드 있음 → 그 칸만 미적용 + 경고 · 같은 코드 2개(화각 내 어디든) → 양쪽 모두 적용 제외 · 폴더 미로드 포트 → 자동 제외 · 같은 Port 폴더가 2개면 탭 앞쪽 사용(경고 로그) · 개수 불일치·비ASCII 프레임 폐기.

**설계 노트**: 셀 번호와 MTC 물리 슬롯 방향의 대응은 Phase 2 에서 공식으로 고정하고, 지그 → MTC 직접 부착 전환 시 리더기 격자 재번호(또는 재정의 표)로 흡수한다. 좌표(X,Y)·서치 영역 번호 출력은 OFF 로 계약(필요 시 옵션).

### 부가 — SystemLogger 다중 싱크

- ATX / Manual / Export 중심 로그 브로드캐스트, History 는 조회 공간 확보를 위해 전용 로그 박스 미노출
- QTextEdit dead sink 자동 정리(RuntimeError 방어), 레벨 필터(All / Warnings+ / Errors), `MAX_LINES=1000` 자동 트리밍

---

## 4. 비기능 요건

| 항목 | 요건 | 구현 |
|------|------|------|
| 한글/공백 경로 | 사용자 계정명 한글 대응 | 8.3 short path + `TESSDATA_PREFIX` 폴백 |
| 오프라인 작동 | 네트워크 없이 핵심 기능 | 업로드 외 전부 오프라인 |
| 설치 권한 | 관리자 불필요 | `PrivilegesRequired=lowest` (`%LOCALAPPDATA%`) |
| 다국어 | 한/영 | Inno Setup Korean.isl + Default.isl |
| 재설치 보존 | 업그레이드 시 이력 유지 | DB 경로가 설치 경로 외부 |
| 비동기 UI | 다량 OCR 시 freeze 없음 | QThreadPool(4) + 종료 시 drain |
| 동시성 안전 | DB 쓰기 단일 스레드화 | OCR/업로드 워커는 결과만 시그널로 전달, DB 접근은 메인 스레드 |
| 품질 리포트 | 차트 포함 PDF 산출 | matplotlib `PdfPages`(의존성 0) |

---

## 5. 배포 / 빌드

### 5.1 빌드 명령

```powershell
# 1. PyInstaller 빌드 (build.bat 가 산출물 사전검사 포함)
.\build.bat
#   내부: python -m PyInstaller --noconfirm --clean --log-level=INFO McQrManager.spec

# 2. Inno Setup 인스톨러 생성
iscc installer.iss

# 산출물:
#   dist\McQrManager\McQrManager.exe            (onedir 바이너리)
#   Output\McQrManager-Setup-<버전>.exe          (설치 파일)
```

`installer.iss` 는 컴파일 전 필수 산출물(`McQrManager.exe`, `python311.dll`, `third_party\tesseract\tesseract.exe`)을 검사해 중간 산출물 오배포를 방지합니다.

### 5.2 AppId GUID

```
MC 2.x:    {{2991A86F-058F-4349-9F44-1116B5C4F102}   ← 현재
NX 1.0.0:  {{A8F2D4E5-B612-4B19-8C3E-7F5D9A0E4B21}   ← 구버전(별도 제품, 공존 가능)
```

### 5.3 코드 서명

현재 미적용. Windows SmartScreen "알 수 없는 게시자" 경고가 발생할 수 있으며, "추가 정보 → 실행" 으로 우회 가능. EV 인증서 도입은 향후 로드맵.

### 5.4 릴리스 절차(다음 출시 시)

1. `VERSION` 파일을 다음 버전으로 갱신(현재 `2.2.0`).
2. `installer.iss` 의 `MyAppVersion` 동기화.
3. `CHANGELOG.md` 에 변경 이력 추가(**§8 변경 이력** 참조).
4. `build.bat` → `iscc installer.iss` → 산출물 수동 검증(설치/Manual 캡처 단축키/CSV+Images 구조/OCR/History).

---

## 6. 테스트

- **pytest 117건 수집 / 111 passed / 6 skipped** (`main` 기준). 6 skip 은 Tesseract/PIL 의존 OCR 테스트(`ocr` 마커, 바이너리 없으면 graceful skip).
- 실행: `pytest` (기본) · `pytest -m "not slow"` (빠른) · `pytest -m ocr`(Tesseract 필요).
- 픽스처(`tests/conftest.py`): `qapp`(offscreen QApplication), `db_conn`(in-memory SQLite + init_db), `sample_afm_image`, `tesseract_ready`.

| 테스트 파일 | 범위 |
|------------|------|
| `test_database.py` | DB CRUD / UPSERT / 기간 집계 |
| `test_image_parser.py`, `test_ocr_settings.py`, `test_ocr_worker.py` | OCR 파서 / ROI 설정 / 비동기 워커 |
| `test_bundle.py` | 번들 직렬화 / Import 중복 정책 |
| `test_csv_exporter.py` | CSV 컬럼 / 미완성 데이터 정책 |
| `test_capture_files.py` | 캡처 파일명 / Zoom 짝 경로 규칙 |
| `test_manual_slot_order.py` | 카드 삭제 후 순번 안정화 |
| `test_measurement_values.py` | 측정값 절삭 로직 |
| `test_system_logger.py` | 로거 다중 싱크 / dead sink 정리 |
| `test_quality.py` | ★신규: 규격 평가·수율 계산·설정 라운드트립 + 대시보드 스모크(PDF 생성) |
| `test_build_artifacts.py` | 빌드 산출물 구조(`dist/` 존재 시) |

---

## 7. 알려진 제약

| 제약 | 대응 / 비고 |
|------|------|
| 한국어 OCR 미지원 | `eng.traineddata` 만 번들. 필요 시 `kor.traineddata` 추가 |
| 단일 PC DB | 번들 Export/Import 로 PC 간 이전 |
| SmartScreen 경고 | EV 코드 서명 도입 전까지 유지 |
| 서버 업로드 규칙 미확인 | 업로드 폼 구조(필드명·버튼·Message 마크업)는 실서버와 대조 완료. 그러나 서버가 **이미지 파일명을 QR 에 연결하는 규칙**과 **CSV `Probe Type` 문자열을 서버 정식 명칭(`OMCL-AC160TS` 등)에 매칭하는 방식**은 미공개이며, 운영 DB 이므로 실업로드 검증을 수행하지 않음. 앱은 반출 규격(`{QR ID}.png`, 약칭 그대로)을 따름 |
| Window Capture 배율 의존성 | 125%/150% 배율·멀티모니터 실장비 검증 필요 |
| 캡처 파일 정리 | 카드 삭제 시 DB/카드만 제거, 실제 캡처 파일은 보존 |
| Drive 입력 | `Drive (%)` 는 CSV/Upload 컬럼으로만 유지, GUI 입력 미구현 |
| OCR tessdata 경로 + 공백 | 8.3 short path 비활성 + 한글 경로 동시 조합은 `TESSDATA_PREFIX` 환경변수로 대응(완전 해결은 영문 경로 권장) |
| 번들 미포함 설정 | `spec_limits`·`ocr_roi` 등 `app_settings` 는 번들에 포함되지 않음(머신 로컬) |

---

## 8. 변경 이력 (이번 개발 사이클 = 2.2.0 개발본)

> `main` 기준 최근 3개 커밋. 모든 변경은 단위테스트 + 독립 적대적 검증을 거침.

### 8.1 코드 품질 감사 기반 버그 수정 (`82ae960`)

멀티에이전트 코드 감사에서 확정된 18건 + WAL 교정. 주요 항목:

- **[High] 업로드 스레드 재진입/누수** (`upload_mixin.py`) — `isRunning()` 가드 + `deleteLater` 결선 + 업로드 중 버튼 비활성화로 `QThread: Destroyed while running` 크래시·객체 누수 방지.
- **[Med] `uploaded_at` 보존** (`database.py`) — 실패 재시도가 과거 성공 업로드 시각을 NULL 로 덮어쓰지 않도록 `COALESCE`.
- **[Med] CSV 핸들 누수** (`server_uploader.py`) — CSV·이미지 핸들을 `finally` 에서 일괄 close(Windows 임시파일 잠김 해소).
- **[Med] OCR drain** (`manual_import_mixin.py` `_prepare_manual_reorder`) — 대기 전 `pool.clear()` + 타임아웃 경고.
- **[Med] 종료 시 OCR drain** (`main_window.py` `closeEvent`) — 닫힌 DB 연결 쓰기 방지.
- **[Med] PASS 판정 정합성** (`measurement_card.py`) — `_has_q` 추적해 `SlotData.is_complete` 와 일치.
- **[Low] OCR ROI 독립 판정 / KeyError 방지** (`image_parser.py`), **캡처 짝 파일명 동기화**(`capture_files.py`), **번들 imported 집계 + 결정적 dedup**(`bundle.py`), **CSV 확장자 보정**(`export_mixin.py`), **입력 범위 9999→999999**(`ui_builder_mixin.py`), **ATX 광범위 except 축소**(`atx_import_mixin.py`), **`ATXNone` 제목 방지**(`slot_grid_widget.py`), **번들 날짜 역순 검증**(`bundle_dialogs.py`), **WAL sidecar 파일명 `-wal/-shm` 교정**(`database.py`).

### 8.2 OCR tessdata 폴백 정식화 + DB 복원 drain (`1db0dcf`)

- `TESSDATA_PREFIX` 를 8.3 short path 로 설정, `--tessdata-dir` 은 공백 없는 경로에만 사용(공백이면 환경변수 위임). pytesseract 의 `shlex.split(posix=False)` 가 따옴표를 보존해 공백 경로를 깨뜨리는 문제를 우회. *정상(8.3 활성) 경로 동작 불변.*
- `history_mixin._on_restore_db` 가 DB 교체 전 OCR 풀 drain + 배치/활성슬롯/리네임큐 무효화(`closeEvent` 패턴).

### 8.3 품질·수율 분석 + 규격 + PDF 리포트 (`5aab2f3`)

**§3 F-20** 참조. 신규: `core/quality.py`, `dialogs/spec_limits_dialog.py`, `tests/test_quality.py`. 수정: `stats_dashboard.py`, `history_mixin.py`, `settings_mixin.py`.

---

## 9. 개발 가이드 (이어서 개발)

### 9.1 개발 환경 셋업

```powershell
# 1) 가상환경 + 의존성
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# 2) (선택) 포터블 Tesseract 배치 — OCR 사용 시
#    third_party\tesseract\{tesseract.exe, *.dll, tessdata\eng.traineddata}
#    없으면 OCR 만 조용히 비활성화되고 나머지 기능은 정상

# 3) 실행 / 테스트
python main.py
pytest
```

### 9.2 코딩 규칙 (필수)

- 코드 작성·수정 전 **`.agent/rules.md`** 를 읽고 따른다(계획 우선 / 요청 외 기능·추상화 추가 금지 / 수술적 수정 / Skill-First).
- **Skill-First**: `.agent/skills/registry.json` 에서 관련 skill 을 찾아 해당 `SKILL.md` 패턴을 따른다(현 프로젝트와 가장 관련: SKILL 12 Mixin 아키텍처, SKILL 13 백그라운드 스레딩, SKILL 16 검증-QA).
- 사용자 피드백은 `self.logger.section/info/ok/warn/error` 로 통일.

### 9.3 DB 스키마 (current `SCHEMA_VERSION=3`)

| 테이블 | 컬럼(요약) |
|--------|-----------|
| `meta` | `key` PK, `value` |
| `measurement_sets` | `id` PK, `po_number`, `quantity`, `probe_type`, `production_date`, `iso_week`, `source_folder`, `mode`, `created_at`, `updated_at`, `uploaded_at`, `upload_status`, `notes` · 인덱스: `iso_week`, `po_number` |
| `slots` | `id` PK, `measurement_set_id` FK(CASCADE), `slot_index`, `slot_code`, `frequency`, `drive`, `q_factor`, `qr_id`, `image_path`, `source`, `probe_type`, `serial_number`(v2), `contact_mode`(v3) · 인덱스: `measurement_set_id` |
| `app_settings` | `key` PK, `value`(JSON) |

마이그레이션(`database.py:_migrate`): v1→v2 `slots.serial_number`, v2→v3 `slots.contact_mode`. (멱등 — `PRAGMA table_info` 확인 후 `ALTER TABLE`.)

### 9.4 app_settings 키 목록

| 키 | 의미 |
|----|------|
| `window_geometry` | 창 위치/크기 `"x,y,w,h"` |
| `last_mode` | 마지막 모드(atx/manual/export/history) |
| `server_id` | 서버 로그인 사용자명 |
| `manual_columns` | Manual 그리드 열 수(1–8) |
| `last_production_date` | 마지막 생산일자(시작 시 리셋) |
| `recent_folders` | 최근 ATX 폴더 5개 |
| `manual_tip_catalog` | 관리형 Tip 이름 목록 |
| `spec_limits` | ★ probe별 규격 한계 `{pt:{freq_min,freq_max,q_min,q_max}}` |
| `ocr_roi` | 해상도별 ROI 프로파일(v2) |

### 9.5 확장 패턴 (자주 쓰는 작업)

- **새 컨트롤러 Mixin 추가**: `class XxxMixin:` 정의(부모 없음) → `_init_xxx_state()` + 액션 메서드 → `main_window.py` 의 클래스 베이스에 추가 + `__init__` 에서 `_init_xxx_state()` 호출.
- **DB 컬럼 추가**: `SCHEMA_VERSION` +1 → `_migrate` 에 `if current_version < N: … ALTER TABLE`(멱등) 블록 추가 → 초기 `CREATE TABLE` 에도 컬럼 추가.
- **설정 키 추가**: 모듈 상수 `XXX_KEY` 정의 → (전역 머지형이면 `DEFAULT_SETTINGS` 에 추가) → `_load_xxx`/`_save_xxx` 헬퍼(`load_setting`/`save_setting`, `TIP_CATALOG`·`SPEC_LIMITS` 패턴).
- **다이얼로그 추가**: `QDialog` 서브클래스 → `QDialogButtonBox` accept/reject → `result_*()` getter. 호출부 `if dlg.exec() == QDialog.Accepted: dlg.result_*()`.
- **대시보드 차트/카드 추가**: `StatsDashboard` 에 `Figure`+`FigureCanvasQTAgg` 또는 카드 생성 → `load_stats` 에서 갱신(신규 인자는 키워드 기본값으로 하위호환 유지) → 필요 시 시그널 추가 후 `history_mixin._init_history_state` 에서 연결.
- **백그라운드 작업 추가**: 단발 다중 → `QRunnable`+`QThreadPool`(OCR 패턴, `ocr_worker.py`); 단일 장기 → `QObject` 워커 + `moveToThread`(업로드 패턴, `upload_mixin.py`). **결과는 시그널로만 메인 스레드 전달**, DB 접근은 메인 스레드에서.

### 9.6 Git 워크플로우 (`CLAUDE.md` 기준)

- 1커밋 → main 직접 / 2–4커밋 → 로컬 브랜치 + `--ff-only` 머지 / 5+ 또는 실험적 → PR.
- 버그 수정·문서·오타: 규모 무관 main 직접(빠른 반영). 단, 기본 브랜치에서 작업 시 브랜치 먼저 생성 권장.

---

## 10. 로드맵 / 다음 작업

### 10.1 단기(F-20 후속 스트레치)
- **Cp/Cpk 공정능력지수** 계산·표시(규격 + σ 활용).
- **per-probe 수율 미니테이블**을 대시보드에 추가(현재는 Overall 카드 + PDF only).
- 규격 변경 시 **고아 키 prune**, inf/nan 가드.

### 10.2 중기(미완성/제약 해소)
- **Drive (%) 입력 UI** — 현재 컬럼만 존재.
- **`Open Folder` 버튼** — 선택 레코드 원본 폴더 열기(부분 구현, 레코드 선택 전 비활성).
- **업로드 신뢰성** — 재시도(backoff)·배치 큐·업로드 이력/감사·실제 진행률.
- **이력 관리 강화** — 컬럼 정렬·다중선택 일괄 export/upload·현재 필터 결과만 내보내기.
- **OCR tessdata 정식 대응** — 한글+공백+8.3 비활성 동시 조합까지 견고화.

### 10.3 장기(아키텍처 비전)
- **PostgreSQL 중앙 서버 집약** — 스키마는 이미 PG 친화. `database.py` 의 연결/쿼리 계층 교체 + 번들/업로드를 서버 동기화로 전환.
- **서버 수신 엔드포인트** 구축(현재 클라이언트 업로드 프로토콜만 존재).
- **EV 코드 서명** 도입(SmartScreen 경고 제거).
- **한국어 OCR**(`kor.traineddata`) — 로트카드에 한글 항목 인식이 필요해질 경우.

---

## 부록 A. 디렉터리 구조

```
새 폴더/ (프로젝트 루트)
├─ main.py                        ← Entry Point
├─ McQrManager.spec               ← PyInstaller 사양
├─ build.bat / installer.iss      ← 빌드·인스톨러
├─ VERSION / pytest.ini
├─ requirements.txt / requirements-dev.txt
├─ CLAUDE.md / AGENTS.md          ← 개발 규칙
├─ .agent/                        ← rules.md + skills/(registry.json, SKILL.md 19종)
├─ assets/icons/                  ← 앱 아이콘
├─ docs/
│   ├─ PRD.md                     ← 이 문서
│   ├─ PRD.html                   ← 변환 산출물 (build_prd_html.py)
│   ├─ build_prd_html.py          ← PRD.md → PRD.html 변환기(의존성 0)
│   ├─ user-guide.html            ← 앱 내장 가이드 원본
│   ├─ export_schema.md           ← 번들 스키마
│   ├─ DOCUMENTATION_WORKFLOW.md / phase7-deployment-analysis.md / WORKLOG.md
│   └─ assets/user-guide/ · training/
├─ src/
│   ├─ core/  (database, models, atx_parser, csv_exporter, bundle, capture_files,
│   │          image_parser, ocr_worker, ocr_settings, tesseract_setup, slot_mapper,
│   │          server_uploader, quality★)
│   └─ ui/
│       ├─ main_window.py / theme.py
│       ├─ controllers/  (ui_builder, atx_import, manual_import, qr_match,
│       │                 export, upload, history, settings)
│       ├─ widgets/  (manual_card, manual_grid, measurement_card, slot_grid,
│       │             slot_detail_table, history_table, csv_preview_table,
│       │             image_viewer, roi_canvas, screen_capture_overlay,
│       │             qr_input, stats_dashboard, system_logger, login_dialog,
│       │             bundle_dialogs)
│       └─ dialogs/  (roi_calibrator, slot_edit, merge_export, add_tab,
│                     tip_catalog, user_guide, spec_limits★)
├─ tests/                         ← pytest 117건 / 111 passed / 6 skipped
└─ third_party/tesseract/         ← 포터블 바이너리(git 비포함)
```

## 부록 B. 참고 문서

- [`docs/export_schema.md`](./export_schema.md) — Export/Import 번들 JSONL 스키마
- [`docs/user-guide.html`](./user-guide.html) — 운영자용 단계별 사용 가이드
- [`docs/phase7-deployment-analysis.md`](./phase7-deployment-analysis.md) — 배포 분석(당시 NX 명칭)
- `CLAUDE.md` / `.agent/rules.md` — 개발 규칙 / Git 워크플로우 / Skill-First

## 부록 C. 버전 이력

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| 1.0.0 (NX) | 2026-04-23 | F-14~F-18 초기 구현 + 배포 |
| 2.0.0 (MC) | 2026-04-24 | NX→MC 브랜드 전환 / AppId 재발급 / DB 경로 변경 |
| 2.1.0 | 2026-05-14 | ATX 슬롯 다이얼로그 / Export 탭 분리 / CSV 미완성 정책 / Capture-First / Zoom 분리 / History UX / 내장 가이드 |
| 2.2.0 (개발본) | 2026-05-31 | 코드 감사 18건+WAL 수정 / OCR tessdata 폴백·복원 drain / **F-20 품질·수율 분석 + 규격 + PDF 리포트** |
