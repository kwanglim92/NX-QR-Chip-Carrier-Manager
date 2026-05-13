# WORKLOG

## 완료

- `.agent/rules.md`, `.agent/skills/registry.json`, 관련 Skill 문서 확인 완료
- Phase 10 UX 개선 구현 완료
  - ATX 좌측 `Selected Slot Edit` 그룹과 `Apply Slot Edit` 버튼 제거
  - ATX 슬롯 카드 우클릭 `수정...` 메뉴 및 `SlotEditDialog` 추가
  - 다이얼로그 OK 전 원본 `SlotData` 미변경, OK 후 카드/진행률/DB 자동 저장 반영
  - 기존 QR 중복 검사 유지
- Export 탭 ATX/Manual 분리 구현 완료
  - Export 우측 슬롯 테이블을 `ATX` / `Manual` 2탭 구조로 변경
  - `measurement_sets["atx"|"manual"]` 상태 분리 추가
  - Save CSV, CSV+Images, 이미지 미리보기, 진행률을 활성 Export 탭 기준으로 변경
  - Upload CSV, Upload CSV+Images도 활성 Export 탭 기준으로 변경
  - 업로드 완료 시 시작 시점의 `db_id`를 캡처해 잘못된 레코드 상태 갱신 방지
- OCR 동작 불가 원인 확인 및 브릿지 완료
  - Codex 임시 워크트리에는 `.gitignore` 처리된 `third_party/tesseract` 런타임 파일이 없어 OCR이 실패
  - 메인 워크트리에는 `tesseract.exe`와 `tessdata/eng.traineddata`가 있어 `configure_tesseract()` 정상 확인
  - Phase 10 변경분을 메인 워크트리로 브릿지해 실제 GUI 확인 환경을 메인 기준으로 정리
- CSV Export 미완성 데이터 옵션 및 `Drive (%)` 컬럼 복구 구현 완료
  - CSV 컬럼을 `QR ID`, `생산일자[YYYYMMDD]`, `Frequency (KHz)`, `Drive (%)`, `Q`, `Probe Type` 순서로 변경
  - `Drive (%)`는 GUI 입력/테이블에는 추가하지 않고 CSV/Upload 자료 구조 유지용 열로만 반영
  - 미완성 데이터 경고창을 `QR 있는 값만 반출/업로드`, `전체 슬롯 반출/업로드`, `취소` 선택 구조로 변경
  - `qr_only` 정책은 기존처럼 QR ID가 있는 슬롯만 포함
  - `all_slots` 정책은 전체 슬롯을 포함하고 QR/Frequency/Drive/Q 결측값은 빈 칸으로 반출
  - CSV+Images에서 QR 없는 슬롯 이미지는 `slot_XX` 파일명으로 복사하고 충돌 시 접미사 부여
  - CSV+Images 생성 폴더명 기본값을 ATX 원본 폴더명 우선으로 변경
  - 폴더명 입력 팝업을 긴 이름이 보이는 전용 다이얼로그로 교체
  - 동일 변경을 메인 워크트리에도 브릿지 완료
- History 탭 GUI 개선 구현 완료
  - `History > Records` 하단 전용 `Log` 그룹박스 제거
  - 제거된 공간을 하단 상세 패널에 재배분하고 이미지 미리보기 영역 비중 확대
  - `History > Statistics` 상단을 compact layout으로 재정리
  - `Today` 카드 3개를 좌측 고정 폭 영역으로 정리하고 기간별 리스트를 오른쪽 compact panel로 이동
  - Summary 카드 높이/폰트 크기 축소로 상단 밀도 개선
  - Production/Quality 차트 캔버스 최소 높이 및 Matplotlib 여백을 지정해 제목/축/라벨 잘림 완화
  - History 모드에서만 상단 `Calibrate OCR` 버튼 숨김 처리
- 검증 완료
  - `python -m py_compile ...` 통과
  - `SlotEditDialog` 원본 미변경 스모크 테스트 통과
  - CSV Export 신규 테스트 `tests/test_csv_exporter.py` 추가 및 통과
  - 메인 워크트리 단일 기준 운영 계획 문서화 완료 (`AGENTS.md`)
  - 전체 테스트: `70 passed, 15 skipped` (`85 collected`)
  - `git diff --check` 통과 (CRLF 변환 경고만 발생)

## 진행중

- 메인 워크트리 단일 기준 운영으로 전환 완료
- Codex 임시 워크트리는 최신 메인 변경을 덮는 브릿지 소스로 사용하지 않음
- 메인 워크트리에는 최신 CSV Export 변경과 운영 문서 변경이 미커밋 상태
  - `AGENTS.md`
  - `docs/WORKLOG.md`
  - `src/core/csv_exporter.py`
  - `src/ui/controllers/export_mixin.py`
  - `src/ui/controllers/ui_builder_mixin.py`
  - `src/ui/controllers/upload_mixin.py`
  - `src/ui/widgets/stats_dashboard.py`
  - `tests/test_csv_exporter.py`
- 실제 GUI 수동 검증은 사용자 확인 대기
- CSV Export 및 History GUI 개선 커밋은 GUI 확인 후 진행 예정

## 다음할일

- 실제 GUI에서 ATX 카드 우클릭 `수정...` 다이얼로그 동작 수동 확인
- 실제 GUI에서 Edit 그룹 제거 후 `FreqSweep Image` 영역 확대 상태 확인
- 실제 GUI에서 Export `ATX` / `Manual` 탭 데이터 보존 및 활성 탭 기준 저장/업로드 확인
- CSV Export에서 미완성 데이터 경고창 버튼 3종 동작 확인
  - `QR 있는 값만 반출/업로드`
  - `전체 슬롯 반출/업로드`
  - `취소`
- 저장된 CSV의 최종 열 순서와 빈 칸 처리 확인
  - `QR ID`, `생산일자[YYYYMMDD]`, `Frequency (KHz)`, `Drive (%)`, `Q`, `Probe Type`
  - QR/Frequency/Drive/Q 결측값은 빈 칸
- CSV+Images에서 QR 없는 슬롯 이미지가 `slot_XX` 파일명으로 복사되는지 확인
- CSV+Images 폴더명 팝업 기본값이 ATX 원본 폴더명(`P2601002_12M_AC160`)으로 표시되는지 확인
- 실제 GUI에서 `History > Records` 하단 Log 영역이 제거되었는지 확인
- 실제 GUI에서 `History > Records` 상세 이미지 미리보기 영역이 커졌는지 확인
- 실제 GUI에서 `History > Statistics` 상단 compact layout 확인
  - `Today` 카드와 기간별 리스트가 자연스럽게 붙어 보이는지 확인
  - 리스트가 과도하게 넓지 않고 내부 스크롤이 가능한지 확인
  - Production/Quality 그래프 제목, 축, 범례, 회전 라벨이 잘리지 않는지 확인
- History 탭에서 `Calibrate OCR` 버튼이 숨겨지고 다른 탭에서는 다시 표시되는지 확인
- 다음 작업 시작 전 메인 워크트리에서 `git status --short --branch` 확인
- 새 기능 작업 전 체크포인트 커밋 생성 또는 현재 미커밋 변경의 소유권 확인
- GUI 확인 후 CSV Export 개선과 History GUI 개선 변경을 커밋 단위로 정리

## 미결이슈

- 실제 GUI 시각 검증은 아직 수행하지 않음
- History Statistics 차트의 최종 시각 품질은 사용자 GUI 확인 결과에 따라 추가 조정 가능
- Codex 임시 워크트리(`C:\Users\Spare\.codex\worktrees\5c72\새 폴더`)는 오래된 detached HEAD 기준 변경이 남아 있어 신규 작업 기준으로 사용하지 않음
- OCR 실제 샘플 기반 테스트 일부는 샘플/Tesseract 조건에 따라 skip됨
- `전체 슬롯 업로드` 선택 시 서버가 빈 QR ID 행을 거부할 가능성 있음
  - 현재 앱은 서버 응답을 그대로 성공/실패 로그로 표시하는 정책
- `Drive (%)`는 현재 CSV/Upload 열로만 복구됨
  - 과거/Manual 데이터에 Drive 값이 없으면 빈 칸으로 반출
  - 향후 Drive를 다시 관리 포인트로 복구하면 기존 데이터에 소급 적용 필요
- PySide6/pytest 실행 스크립트 경로가 PATH에 등록되어 있지 않아 `python -m pytest` 방식으로 실행 필요
