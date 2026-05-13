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
  - `Period` 필터 아래 구분선 추가
  - `Today` 영역과 `Period Summary` 리스트를 좌우 5:5 비율로 확장
  - `Today` 영역과 리스트 사이에 세로 구분선 추가
  - 고정폭 기반 리스트 배치를 제거해 상단 공간 낭비 축소
- Manual Capture-First 자동화 기능 구현 완료
  - Manual Mode에 `📸 Capture` 메뉴 버튼 추가
  - `Region Capture`와 `Window Capture` 모드 추가
  - `Region Capture`: 드래그 영역 캡처
  - `Window Capture`: 클릭한 Windows 창 전체 캡처
  - 캡처 이미지는 앱 데이터 폴더의 `captures/{YYYYMMDD}/{probe_type}/pending_XXXX.png`로 저장
  - 캡처 직후 Manual 카드 자동 생성/선택, QR 입력창 자동 포커스
  - QR 매칭 후 `slot_XX_{QRID}.png` 형식으로 캡처 파일명 자동 확정
  - OCR 진행 중 QR을 먼저 찍어도 OCR 완료 후 안전하게 파일명 확정
- Manual 카드 삭제 후 순번 안정화 구현 완료
  - 잘못 캡처한 카드를 삭제하면 남은 카드가 `#1, #2, #3...`으로 재정렬
  - `SlotData.slot_index`, `slot_code`, `ManualCard.slot_index`, grid key, 선택 상태, `_manual_slot_counter` 동기화
  - 앱 내부 캡처 파일은 재정렬된 순번에 맞춰 `slot_XX_{QRID}.png`로 파일명 재동기화
  - 외부 Load/drag & drop 이미지 파일명은 변경하지 않음
- Capture 단축키 구현 완료
  - `F6`: `Region Capture`
  - `F7`: `Window Capture`
  - `QAction`/`QShortcut` 중복 등록 문제 제거
  - `QAction::event: Ambiguous shortcut overload` 경고 해결
  - Manual Mode가 아닐 때는 단축키로 캡처가 시작되지 않도록 guard 추가
- 테스트/검증 완료
  - `python -m py_compile ...` 통과
  - `python -m pytest -q` 통과: `78 passed, 15 skipped` (`93 collected`)
  - `git diff --check` 통과 (CRLF 변환 경고만 발생)
  - 신규 테스트 추가
    - `tests/test_capture_files.py`
    - `tests/test_manual_slot_order.py`

## 진행중

- 현재 변경분은 메인 워크트리에 미커밋 상태
  - `src/core/capture_files.py`
  - `src/core/manual_slot_order.py`
  - `src/ui/widgets/screen_capture_overlay.py`
  - `src/ui/widgets/stats_dashboard.py`
  - `src/ui/widgets/manual_card.py`
  - `src/ui/widgets/manual_grid_widget.py`
  - `src/ui/controllers/manual_import_mixin.py`
  - `src/ui/controllers/qr_match_mixin.py`
  - `src/ui/controllers/ui_builder_mixin.py`
  - `src/ui/controllers/history_mixin.py`
  - `tests/test_capture_files.py`
  - `tests/test_manual_slot_order.py`
  - `docs/WORKLOG.md`
- Capture 기능은 사용자 GUI 확인을 거쳐 기본 동작 확인 완료
- `History > Statistics` 5:5 레이아웃 및 구분선 변경은 방금 반영되어 GUI 최종 확인 대기
- 현재 작업 범위는 “Manual Capture 자동화 + History Statistics 레이아웃 후속 개선”으로 묶여 있음

## 다음할일

- 실제 GUI에서 `History > Statistics` 상단이 좌우 5:5 비율로 자연스럽게 확장되는지 확인
- `Period` 필터 아래 가로 구분선과 Today/List 사이 세로 구분선이 과하지 않게 보이는지 확인
- 1920x1080 기준으로 상단 Today 카드와 `Period Summary` 리스트가 화면 폭을 균형 있게 쓰는지 확인
- 그래프 영역이 이전보다 더 잘리거나 밀리지 않는지 확인
- Manual Mode에서 `F6` / `F7` 단축키 최종 동작 재확인
- `Window Capture`가 실제 Sweep 팝업 창을 동일 크기로 안정적으로 캡처하는지 반복 확인
- 잘못 캡처한 카드 삭제 후 다음 항목들이 `#1`부터 재정렬되고 Export Manual 탭도 같은 순서로 표시되는지 확인
- GUI 확인 완료 후 현재 미커밋 변경을 하나의 기능 커밋으로 정리
- 커밋 전 최종 확인
  - `git status --short --branch`
  - `python -m pytest -q`
  - `git diff --check`

## 미결이슈

- `Window Capture`는 Windows API 기반이므로 실제 장비/배율/멀티모니터 환경에서 추가 확인 필요
- Windows 배율 125%/150%에서 창 클릭 캡처 좌표가 어긋나는지 최종 확인 필요
- 캡처 파일 삭제 정책은 아직 미구현
  - 현재 카드 삭제 시 DB/카드만 삭제하고 실제 이미지 파일은 보존
  - 필요 시 앱 내부 `pending_*.png` 또는 QR 확정 캡처 파일 삭제 옵션을 별도 설계 가능
- `Drive (%)`는 현재 CSV/Upload 열로만 복구됨
  - 과거/Manual 데이터에 Drive 값이 없으면 빈 칸으로 반출
  - 향후 Drive를 다시 관리 포인트로 복구하면 기존 데이터에 소급 적용 필요
- `전체 슬롯 업로드` 선택 시 서버가 빈 QR ID 행을 거부할 가능성 있음
  - 현재 앱은 서버 응답을 그대로 성공/실패 로그로 표시하는 정책
- OCR 실제 샘플 기반 테스트 일부는 샘플/Tesseract 조건에 따라 skip됨
- PySide6/pytest 실행 스크립트 경로가 PATH에 등록되어 있지 않아 `python -m pytest` 방식으로 실행 필요
