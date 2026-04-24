# MC QR Code Chip Carrier Manager — Product Requirements Document

| 항목 | 내용 |
|------|------|
| **문서 버전** | 2.0 |
| **작성일** | 2026-04-24 |
| **앱 버전** | 2.0.0 (MC 브랜드) |
| **이전 버전** | 1.0.0 (NX 브랜드) |
| **대상 독자** | 개발 / 운영 / QA / 품질관리 |
| **내부 코드명** | `McQrManager` (이전: `NxQrManager`) |

---

## 1. 프로젝트 취지 및 배경

### 1.1 문제 정의

반도체 측정 공장에서는 다음 세 가지 데이터 파편화 문제가 반복적으로 발생합니다.

1. **ATX 장비 CSV 파편화**  
   ATX 측정 장비가 슬롯별로 `summary_*.csv` 파일을 쏟아내지만, PO 번호·QR 코드·생산 날짜가 각 파일에 독립적으로 저장돼 있어 한 로트의 전체 상태를 한눈에 볼 수 없습니다.

2. **Manual 측정의 수기 입력 오류**  
   로트카드(Lot Card) 수기 측정은 운영자가 눈으로 값을 읽어 Excel 에 입력하는 방식이라 오탈자가 빈번하게 발생합니다. 특히 Frequency / Q-factor 같은 소수점 값에서 실수가 잦습니다.

3. **이력 분산 + 집계 불가**  
   측정 이력이 각 PC 의 로컬 Excel 파일에 흩어져 있어, 일일 생산량이나 주간 추이를 집계하려면 수작업으로 파일을 모아 통계를 내야 합니다.

### 1.2 해결 방향

- **단일 데스크톱 앱** 으로 ATX 자동 파싱 + Manual OCR + 이력 DB 를 통합
- **`%LOCALAPPDATA%` SQLite(WAL 모드)** — 오프라인 공장 환경에서도 동작 보장
- **PostgreSQL 이관 친화 스키마** — 향후 중앙 서버 집약 시 수정 최소화 (ON CONFLICT UPSERT, TEXT 날짜, GROUP_CONCAT 금지)
- **PyInstaller + Inno Setup 단일 설치본** — 사용자 환경에 Python 설치 불필요, Tesseract 포터블 번들

### 1.3 대상 사용자

| 구분 | 역할 | 사용 시나리오 |
|------|------|---------------|
| 1차 | 공장 측정 오퍼레이터 (비개발자) | ATX 결과 Import / Manual 로트카드 OCR / 저장 |
| 2차 | 품질 관리자 | Dashboard 생산량 모니터링 / Export 번들 배포 / History 필터 조회 |
| 3차 | IT 담당자 | Inno Setup 인스톨러 배포 / PC 간 데이터 이전 (Import 번들) |

---

## 2. 시스템 아키텍처

### 2.1 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| 런타임 | Python 3.11+ | 표준 라이브러리(`statistics`, `datetime`) 충실 |
| UI | PySide6 (Qt6) | 공장 환경 Windows 데스크톱 최적, GPL 회피 |
| DB | SQLite 3.24+ | 설치형 로컬 앱, WAL 모드, PG 이관 친화 |
| OCR | Tesseract 5.x + pytesseract | 숫자 whitelist 로 Manual 카드 Freq/Q 자동 추출 |
| 이미지 | Pillow (PIL) | ROI 크롭만 필요, OpenCV 미도입으로 용량 최소화 |
| 차트 | Matplotlib 3.8+ | PySide6 `FigureCanvasQTAgg` 통합, Catppuccin Mocha 테마 |
| 빌드 | PyInstaller 6.x (onedir) | contents_directory='.' 로 Tesseract DLL 경로 단순화 |
| 인스톨러 | Inno Setup 6.x | 한/영 다국어, 사용자 권한 설치, UPX 오탐 회피 |

### 2.2 레이어 구조

```
main.py                           ← Entry Point (QApplication 부팅)
├─ src/core/                      ← 순수 로직 (Qt 의존성 최소)
│   ├─ database.py                — SQLite CRUD + PG 호환 UPSERT
│   ├─ models.py                  — MeasurementSet / SlotData dataclass
│   ├─ atx_parser.py              — summary_*.csv 파싱
│   ├─ csv_exporter.py            — Quick Backup CSV
│   ├─ bundle.py                  — JSONL + ZIP 번들 (F-18)
│   ├─ image_parser.py            — Tesseract 기반 OCR (F-14)
│   ├─ ocr_worker.py              — QThread 비동기 OCR
│   ├─ ocr_settings.py            — 해상도별 ROI 프로파일
│   ├─ tesseract_setup.py         — 포터블 바이너리 탐색 + 8.3 short path
│   ├─ slot_mapper.py             — QR ↔ 슬롯 매핑
│   └─ server_uploader.py         — HTTP 멀티파트 업로드
├─ src/ui/
│   ├─ theme.py                   — Catppuccin Mocha QSS
│   ├─ main_window.py             — Qt 메인 윈도우 + Mixin 조립
│   ├─ widgets/                   — 재사용 위젯 (카드, 테이블, 그리드, 차트)
│   ├─ controllers/               — 페이지별 Mixin (ATX/Manual/History/Export/Upload/UI Builder)
│   └─ dialogs/
│       └─ roi_calibrator.py      — ROI 시각적 편집기 (QGraphicsView)
└─ third_party/tesseract/         — 포터블 바이너리 + tessdata (번들)
```

### 2.3 데이터 경로 분리

| 경로 | 내용 | 생존 |
|------|------|------|
| `C:\Program Files\McQrManager\` | 실행 파일, DLL, Tesseract | 언인스톨 시 제거 |
| `%LOCALAPPDATA%\MCQRCodeChipCarrier\chip_carrier.db` | 측정 이력 DB | **언인스톨 해도 보존** |
| 사용자 지정 폴더 | ATX summary CSV 원본, Manual 로트카드 이미지 | 사용자 관리 |

### 2.4 배포 토폴로지

- **단일 PC 설치형** — 네트워크 없이 모든 핵심 기능 동작
- **Tesseract 포터블 번들** — 시스템 설치 불필요, 버전 고정
- **다중 PC 공유** — Export 번들(ZIP) 을 USB/공유 드라이브로 전달 → Import 로 병합

---

## 3. 기능 명세

### F-14 Manual OCR — 로트카드 자동 입력

| 항목 | 내용 |
|------|------|
| 입력 | 로트카드 JPG/PNG 이미지 |
| 출력 | Frequency / Q-factor 자동 추출, UI pre-fill |
| 실패 대응 | 조용히 수기 입력 모드로 전환 (경고 없음) |
| 구성 파일 | `image_parser.py`, `ocr_worker.py`, `ocr_settings.py`, `tesseract_setup.py`, `roi_calibrator.py` |

**핵심 특성**
- **숫자 whitelist OCR** — `--psm 7 -c tessedit_char_whitelist=0123456789.` 로 오탐 원천 차단
- **해상도별 ROI 프로파일** — 720×480, 1920×1080 등 여러 프로파일을 DB 에 저장
- **ROI Calibrator** — QGraphicsView 기반 시각 편집기. 신규 해상도 추가 시 드래그로 설정
- **비동기 파이프라인** — QThreadPool (4 스레드) 로 20장 배치 처리 시 UI freeze 없음
- **범위 검증** — `_FREQ_RANGE = (50.0, 5000.0)`, `_Q_RANGE = (10.0, 10000.0)` 벗어나면 추출 실패 처리
- **한글/공백 경로 대응** — Windows 8.3 short path 자동 변환 (`tesseract_setup.py`)

### F-15 측정 이력 SQLite (PostgreSQL 이관 친화)

| 테이블 | 용도 |
|--------|------|
| `measurement_sets` | PO, quantity, probe_type, production_date, mode(atx/manual), upload_status |
| `slots` | FK → measurement_sets, slot_index, qr_id UNIQUE, frequency/drive/q |
| `app_settings` | ocr_roi JSON, window_geometry 등 key-value 저장 |

**PG 호환 설계 (Phase 0 리팩터 결과)**
- `INSERT ... ON CONFLICT(key) DO UPDATE SET value=excluded.value` 표준 UPSERT (SQLite 3.24+ / PG 9.5+ 공통)
- 날짜는 TEXT `YYYYMMDD` 고정 → PG `DATE` 캐스팅 가능
- `GROUP_CONCAT` 등 SQLite 전용 함수 제거 → Python `statistics` 모듈로 대체
- `datetime('now','localtime')` DEFAULT 제거 → 호출자가 ISO 문자열 주입

### F-16 History 조회

| 필터 | 구현 |
|------|------|
| 날짜 범위 | `production_date` BETWEEN |
| PO 번호 | LIKE %keyword% |
| Probe Type | 드롭다운 |
| Upload Status | 드롭다운 (pending/uploaded/failed) |
| QR 코드 | `slots.qr_id` LIKE |

- 더블 클릭 → SlotDetailTable (12슬롯 상세) 팝업
- 업로드 실패 건 재전송 (Upload Mixin)

### F-17 생산량 대시보드

| 기간 | 집계 단위 |
|------|-----------|
| Today | `production_date = today()` 단일 |
| Daily | `YYYY-MM-DD` 일자별 |
| Weekly | ISO 주차 (YYYY-W##) |
| Monthly | `YYYY-MM` |
| Quarterly | `YYYY-Q#` |
| Yearly | `YYYY` |

**차트 4종**
1. 시계열 바 차트 — 기간별 생산 세트 수
2. 업로드 상태 파이 — `pending/uploaded/failed` 비율
3. 프로브 유형별 누적 바 — Probe Type 별 슬롯 합계
4. 주간 히트맵 — 요일 × 시간 생산량

**Today 카드 (상단)**
- 오늘 측정 세트 수 / 총 슬롯 수 / QR 성공률 / 업로드 대기 건

### F-18 Export / Import 번들

| 항목 | 내용 |
|------|------|
| 포맷 | ZIP (`manifest.json` + `data.jsonl` + `images/`) |
| 중복 정책 | `skip` (기본) / `overwrite` / `merge` |
| 스키마 버전 | v1 — `SUPPORTED_SCHEMA_VERSIONS` 로 호환성 체크 |
| 용도 | PC 간 이전 / 백업 / 중앙 서버 집약 전 단계 |

상세 스키마는 [`docs/export_schema.md`](./export_schema.md) 참조.

### 부가 — SystemLogger 다중 싱크

- ATX / Manual / Export / History 4 페이지에 로그 브로드캐스트
- QTextEdit dead sink 자동 정리 (RuntimeError 방어)
- 레벨 필터: All / Warnings+ / Errors only (페이지별 콤보박스)
- `MAX_LINES = 1000` (자동 트리밍)

---

## 4. 비기능 요건

| 항목 | 요건 | 구현 |
|------|------|------|
| 한글/공백 경로 | 사용자 계정명 한글 대응 | Windows 8.3 short path 자동 변환 |
| 오프라인 작동 | 네트워크 없이 핵심 기능 동작 | 업로드 외 전부 오프라인 |
| 설치 권한 | 관리자 불필요 | `PrivilegesRequired=lowest` (`%LOCALAPPDATA%` 사용) |
| 다국어 | 한/영 선택 가능 | Inno Setup Korean.isl + Default.isl |
| 재설치 보존 | 업그레이드 시 이력 유지 | DB 경로가 설치 경로 외부 |
| 비동기 UI | 20장 OCR 시에도 UI freeze 없음 | QThreadPool (4 스레드) |
| 로그 | 사용자 피드백 | SystemLogger 4페이지 브로드캐스트 |

---

## 5. 배포 / 빌드

### 5.1 빌드 명령

```powershell
# 1. PyInstaller 빌드
.\build.bat

# 2. Inno Setup 인스톨러 생성
iscc installer.iss

# 산출물:
#   dist\McQrManager\McQrManager.exe            (onedir 바이너리)
#   Output\McQrManager-Setup-2.0.0.exe          (설치 파일)
```

### 5.2 AppId GUID

```
MC 2.0.0: {{2991A86F-058F-4349-9F44-1116B5C4F102}   ← 현재
NX 1.0.0: {{A8F2D4E5-B612-4B19-8C3E-7F5D9A0E4B21}   ← 구버전 (별도 제품)
```

두 제품은 별도의 설치·언인스톨 단위. AppId 가 다르므로 **동일 PC 에 공존 가능**.

### 5.3 코드 서명

현재 미적용. Windows SmartScreen "알 수 없는 게시자" 경고가 발생할 수 있음.  
사용자는 "추가 정보" → "실행" 클릭으로 우회 가능. EV 인증서 도입은 2.1+ 로드맵.

---

## 6. 테스트 커버리지

- **pytest 72건 회귀 테스트**
- 범위:
  - DB CRUD / UPSERT / 기간 집계 (`test_database.py`)
  - OCR 파서 / ROI 설정 / 비동기 워커 (`test_image_parser.py`, `test_ocr_settings.py`, `test_ocr_worker.py`)
  - 번들 직렬화 / Import 중복 정책 (`test_bundle.py`)
  - 로거 다중 싱크 / dead sink 정리 (`test_system_logger.py`)
  - 빌드 산출물 구조 (`test_build_artifacts.py` — 선택적, `dist/` 존재 시만)
- 실행: `pytest` (기본) / `pytest -m "not slow"` (빠른 실행)

---

## 7. 알려진 제약

| 제약 | 대응 |
|------|------|
| 한국어 OCR 미지원 | 현재 `eng.traineddata` 만 번들. 필요 시 `kor.traineddata` 추가 |
| 단일 PC DB | 번들 Export/Import 로 PC 간 이전 가능 |
| SmartScreen 경고 | EV 코드 서명 인증서 도입 전까지 유지 |
| 서버 업로더 | HTTP 멀티파트. 엔드포인트는 별도 구축 필요 |

---

## 8. 1.0.0 (NX) → 2.0.0 (MC) 마이그레이션 가이드

**배경**: 2.0.0 은 AppId GUID 가 새로 발급되었고, DB 경로가 `NXQRChipCarrierManager` → `MCQRCodeChipCarrier` 로 변경됨. 자동 이관되지 **않으므로** 수동 번들 전송이 필요합니다.

**절차**:

1. **NX 1.0.0 에서**:
   - History 페이지 → 전체 선택
   - Export → Bundle (`.zip`) 생성
   - `%LOCALAPPDATA%\NXQRChipCarrierManager\` 를 별도 경로에 백업 (선택)
2. **MC 2.0.0 설치**:
   - `McQrManager-Setup-2.0.0.exe` 실행
   - 기본 경로(`C:\Program Files\McQrManager\`) 설치
3. **MC 2.0.0 에서**:
   - Import → 번들 `.zip` 선택
   - 정책: `overwrite` (신규 설치이므로 충돌 없음)
   - History 에서 이관된 데이터 확인
4. **NX 1.0.0 언인스톨** (선택):
   - 제어판에서 제거. DB(`%LOCALAPPDATA%\NXQRChipCarrierManager\`) 는 수동 삭제.

---

## 부록 A. 디렉터리 구조 (2.0.0 기준)

```
MC QR Code Chip Carrier/                  ← 프로젝트 루트
├─ main.py
├─ McQrManager.spec                       ← PyInstaller 빌드 사양
├─ build.bat
├─ installer.iss                          ← Inno Setup 스크립트
├─ pytest.ini
├─ requirements.txt
├─ requirements-dev.txt
├─ CLAUDE.md                              ← 개발 규칙 (Claude Code용)
├─ .gitignore
├─ assets/
│   └─ icons/
│       ├─ icon_lotcard_ref.ico           ← 실제 앱 아이콘
│       └─ image.png                      ← 원본 소스 이미지
├─ docs/
│   ├─ PRD.md                             ← 이 문서
│   ├─ user-guide.html                    ← 사용자 가이드 (Phase 9)
│   ├─ export_schema.md                   ← 번들 스키마
│   └─ phase7-deployment-analysis.md      ← 배포 분석 (이력 보존)
├─ src/
│   ├─ core/
│   └─ ui/
│       ├─ controllers/
│       ├─ widgets/
│       └─ dialogs/
├─ tests/                                 ← pytest 72건
└─ third_party/
    └─ tesseract/                         ← 포터블 바이너리 (.exe + DLLs + tessdata/)
```

---

## 부록 B. 참고 문서

- [`docs/export_schema.md`](./export_schema.md) — Export/Import 번들 JSONL 스키마
- [`docs/phase7-deployment-analysis.md`](./phase7-deployment-analysis.md) — 배포 분석 (당시 NX 명칭)
- [`docs/user-guide.html`](./user-guide.html) — 공장 운영자용 단계별 사용 가이드
- `CLAUDE.md` — 개발 규칙 / Git 워크플로우

---

## 부록 C. 버전 이력

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| 1.0.0 (NX) | 2026-04-23 | F-14~F-18 초기 구현 + 배포 |
| 2.0.0 (MC) | 2026-04-24 | NX→MC 브랜드 전환 / AppId 재발급 / DB 경로 변경 / 유지보수 구조 정리 |
