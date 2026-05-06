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
- 검증 완료
  - `python -m py_compile ...` 통과
  - `SlotEditDialog` 원본 미변경 스모크 테스트 통과
  - 전체 테스트: `62 passed, 15 skipped` (`77 collected`)

## 진행중

- Phase 10 변경 파일이 작업트리에 수정 상태로 남아 있음
  - `src/ui/controllers/atx_import_mixin.py`
  - `src/ui/controllers/export_mixin.py`
  - `src/ui/controllers/ui_builder_mixin.py`
  - `src/ui/controllers/upload_mixin.py`
  - `src/ui/main_window.py`
  - `src/ui/widgets/measurement_card.py`
  - `src/ui/widgets/slot_grid_widget.py`
- 신규 파일 `src/ui/dialogs/slot_edit_dialog.py`가 아직 git 추적 대상은 아님
- 커밋 전략은 아직 미결정

## 다음할일

- 실제 GUI에서 ATX 카드 우클릭 `수정...` 다이얼로그 동작 수동 확인
- 실제 GUI에서 Edit 그룹 제거 후 `FreqSweep Image` 영역 확대 상태 확인
- 실제 GUI에서 Export `ATX` / `Manual` 탭 데이터 보존 및 활성 탭 기준 저장/업로드 확인
- 변경 파일 리뷰 후 스테이징/커밋 범위 결정
- 커밋 전략 결정

## 미결이슈

- 실제 GUI 시각 검증은 아직 수행하지 않음
- OCR 실제 샘플 기반 테스트 일부는 샘플/Tesseract 조건에 따라 skip됨
- PySide6/pytest 실행 스크립트 경로가 PATH에 등록되어 있지 않아 `python -m pytest` 방식으로 실행 필요
