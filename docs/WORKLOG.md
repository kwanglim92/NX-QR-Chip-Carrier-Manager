# WORKLOG

## 완료

- 메인 워크트리 단일 기준 운영으로 전환 완료
  - 실제 코드 수정/실행/GUI 확인 기준: `C:\Users\Spare\Desktop\03. Program\새 폴더`
  - Codex 임시 워크트리는 신규 브릿지 소스로 사용하지 않음
- Phase 10 UX 개선 구현 완료
  - ATX 좌측 `Selected Slot Edit` 그룹과 `Apply Slot Edit` 버튼 제거
  - ATX 슬롯 카드 우클릭 `수정...` 메뉴 및 `SlotEditDialog` 추가
  - Export 우측 슬롯 테이블을 `ATX` / `Manual` 2탭 구조로 변경
  - ATX/Manual MeasurementSet 상태 분리 및 활성 Export 탭 기준 저장/업로드 반영
- OCR 동작 불가 원인 확인 및 메인 브릿지 완료
  - Codex 임시 워크트리에는 `.gitignore` 처리된 `third_party/tesseract` 런타임 파일이 없어 OCR 실패
  - 메인 워크트리 기준으로 `tesseract.exe`와 `tessdata/eng.traineddata` 정상 확인
- CSV Export 미완성 데이터 옵션 및 `Drive (%)` 컬럼 복구 구현 완료
  - CSV 컬럼 순서: `QR ID`, `생산일자[YYYYMMDD]`, `Frequency (KHz)`, `Drive (%)`, `Q`, `Probe Type`
  - `qr_only` / `all_slots` 반출 정책 추가
  - 미완성 데이터 경고창을 `QR 있는 값만 반출/업로드`, `전체 슬롯 반출/업로드`, `취소` 선택 구조로 변경
  - CSV+Images 폴더명 기본값을 ATX 원본 폴더명 우선으로 변경
- History 탭 GUI 개선 구현 완료
  - `History > Records` 하단 전용 `Log` 그룹박스 제거
  - 상세 패널과 이미지 미리보기 영역 확대
  - History 모드에서만 상단 `Calibrate OCR` 버튼 숨김 처리
  - `History > Statistics` 상단 KPI/리스트/차트 레이아웃 최적화
- Manual Capture-First 자동화 기능 구현 완료
  - Manual Mode `📸 Capture` 메뉴 버튼 (Region/Window)
  - 캡처 이미지 `captures/{YYYYMMDD}/{probe_type}/pending_XXXX.png` 저장
  - 캡처 직후 Manual 카드 자동 생성/선택, QR 입력창 자동 포커스
  - QR 매칭 후 `slot_XX_{QRID}.png` 형식으로 파일명 자동 확정
  - OCR 진행 중 QR을 먼저 찍어도 OCR 완료 후 안전하게 파일명 확정
- Manual 카드 삭제 후 순번 안정화 구현 완료
  - 삭제 후 남은 카드가 `#1, #2, #3...`으로 재정렬
  - 앱 내부 캡처 파일은 재정렬된 순번에 맞춰 `slot_XX_{QRID}.png`로 파일명 재동기화
- Capture 단축키 구현 완료 (`F6`: Region, `F7`: Window)
- **Zoom-In / Zoom-Out 분리 캡처 기능 구현 완료 (이번 작업)**
  - `src/core/capture_files.py`에 헬퍼 6개 + 상수 3개 추가
    - `ZOOMIN_SUBDIR`, `ZOOMOUT_SUBDIR`, `ZOOMOUT_SUFFIX = "` "`
    - `zoom_dir`, `zoom_filename`, `is_zoomout_filename`
    - `next_pending_capture_pair`, `final_capture_pair`, `derive_zoomout_path`
  - 저장 구조: `captures/{YYYYMMDD}/{probe}/{zoomin,zoomout}/`
    - Zoom-In: `slot_NN_QR.png`
    - Zoom-Out: `slot_NN_QR` `.png` (stem에 backtick suffix)
  - 캡처 워크플로우 분리 (probe SW에서 Zoom-Out 모드 전환 시간 확보)
    - `_capture_manual_image()` → Zoom-In 단일 캡처, 새 슬롯 생성
    - 신규 `_capture_manual_image_zoomout()` → 현재 선택된 카드에 Zoom-Out 첨부
    - 단축키: `F6` Zoom-In Region, `F7` Zoom-In Window, `F8` Zoom-Out Region, `F9` Zoom-Out Window
    - 📸 Capture 드롭다운 4항목으로 재구성
  - 폴더 업로드 시 backtick 접미사 파일 자동 필터 (zoom-out 중복 슬롯 방지)
  - QR 확정 시 zoom-out sibling도 동시 rename
  - 이미지 뷰어 상단 `Zoom-In | Zoom-Out` 토글 버튼 추가
    - `_apply_zoom_toggle_visual(level)` 헬퍼: `accent` 동적 프로퍼티를 활성 버튼으로 옮기고 `style().unpolish/polish` 호출하여 즉시 repaint (초기 토글 색상 stuck 버그 해결)
    - Zoom-Out 이미지 없는 카드 선택 시 자동으로 Zoom-In 복귀 + 안내 로그
    - 카드 전환 시 토글 항상 Zoom-In으로 reset
  - CSV Export 확장: `ZOOMIN/` + `ZOOMOUT/` 두 폴더 동시 출력
  - Bundle Export 확장: ZIP `images/` 안에 zoom-in + zoom-out 양쪽 포함
  - DB 스키마/`SlotData` 변경 없음 (zoom-out 경로는 zoom-in에서 결정적으로 파생)
- 테스트/검증 완료
  - `tests/test_capture_files.py`에 zoom 헬퍼 단위 테스트 7개 추가
  - `python -m pytest`: 85 passed / 15 skipped
  - offscreen smoke test: MainWindow 빌드, 토글 위젯/핸들러/단축키 wiring 확인
  - E2E smoke: 가짜 zoom-in/zoom-out 쌍 → CSV Export (ZOOMIN+ZOOMOUT) / Bundle ZIP 검증 통과

## 진행중

- 이번 변경분은 메인 워크트리에 미커밋 상태
  - `src/core/capture_files.py`
  - `src/core/csv_exporter.py`
  - `src/core/bundle.py`
  - `src/ui/controllers/manual_import_mixin.py`
  - `src/ui/controllers/qr_match_mixin.py`
  - `src/ui/controllers/ui_builder_mixin.py`
  - `src/ui/controllers/export_mixin.py`
  - `src/ui/widgets/screen_capture_overlay.py`
  - `tests/test_capture_files.py`
  - `docs/WORKLOG.md`
- Zoom-In/Zoom-Out 토글 색상 stuck 버그 수정 완료, 사용자 GUI 재확인 대기
- 캡처 워크플로우 분리 (Zoom-In→슬롯 생성, Zoom-Out→선택 카드 첨부) 구현 완료, 사용자 GUI 재확인 대기

## 다음할일

- 실제 GUI에서 Zoom-In 캡처 → probe SW에서 Zoom-Out 모드 전환 → Zoom-Out 캡처 흐름 검증
  - F6/F7 단축키로 Zoom-In 캡처 → 새 카드 생성 확인
  - F8/F9 단축키로 Zoom-Out 캡처 → 선택된 카드에 sibling 파일 생성 확인
  - `captures/YYYYMMDD/probe/zoomin/`, `.../zoomout/` 두 폴더에 파일이 정상 저장되는지 확인
- 이미지 뷰어 토글 동작 재확인
  - Zoom-In/Zoom-Out 토글 시 파란색 accent가 활성 버튼으로 옮겨가는지
  - 카드 전환 시 토글이 Zoom-In으로 자동 reset 되는지
  - Zoom-Out 없는 레거시 카드 선택 후 Zoom-Out 클릭 시 안내 로그 후 Zoom-In 복귀하는지
- QR 입력 후 zoom-in/zoom-out 양쪽 파일이 동일 stem으로 rename 되는지 확인
- 폴더 업로드 시 backtick (`) 접미사 파일이 슬롯에 추가되지 않는지 확인
  - 4 파일 (`chip1.png`, `chip1` `.png`, `chip2.png`, `chip2` `.png`) → 2 슬롯
- CSV + Images Export 시 `ZOOMIN/`, `ZOOMOUT/` 두 폴더가 모두 생성되고 QR로 정렬되는지 확인
- 이번 변경분을 하나의 기능 커밋으로 정리 후 push
  - `git status --short --branch`
  - `python -m pytest`
  - `git diff --check`

## 미결이슈

- `Window Capture`는 Windows API 기반이므로 실제 장비/배율/멀티모니터 환경에서 추가 확인 필요
- Windows 배율 125%/150%에서 창 클릭 캡처 좌표가 어긋나는지 최종 확인 필요
- 캡처 파일 삭제 정책은 아직 미구현
  - 현재 카드 삭제 시 DB/카드만 삭제하고 실제 이미지 파일은 보존
  - Zoom-Out sibling도 동일하게 보존 (수동 정리 필요 시 별도 설계)
- Zoom-Out 캡처 시 기존 파일 존재하면 덮어쓰기 정책
  - 사용자가 명시적으로 재캡처 의도라고 가정하여 확인 다이얼로그 없이 overwrite
  - 실수 방지가 필요하면 별도 옵션화 가능
- `Drive (%)`는 현재 CSV/Upload 열로만 복구됨
  - 과거/Manual 데이터에 Drive 값이 없으면 빈 칸으로 반출
- `전체 슬롯 업로드` 선택 시 서버가 빈 QR ID 행을 거부할 가능성 있음
- OCR 실제 샘플 기반 테스트 일부는 샘플/Tesseract 조건에 따라 skip 됨
- Backtick (`) 파일명은 Windows에서 합법이지만 shell 명령 노출 시 command substitution 위험
  - 본 앱은 `Path`/`shutil`로만 다루므로 안전, 외부 도구 연계 시 escape 유의
