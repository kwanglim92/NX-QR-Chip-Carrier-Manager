# WORKLOG

## 완료

- 메인 워크트리 단일 기준 운영으로 전환 완료
  - 실제 코드 수정/실행/GUI 확인 기준: `C:\Users\Spare\Desktop\03. Program\새 폴더`
  - Codex 임시 워크트리는 신규 브릿지/구현 기준으로 사용하지 않음
- Phase 10 UX 개선 구현 완료
  - ATX 좌측 `Selected Slot Edit` 그룹과 `Apply Slot Edit` 버튼 제거
  - ATX 슬롯 카드 우클릭 `수정...` 메뉴 및 `SlotEditDialog` 추가
  - Export 우측 슬롯 테이블을 `ATX` / `Manual` 2탭 구조로 변경
  - ATX/Manual MeasurementSet 상태 분리 및 활성 Export 탭 기준 Save/Upload 반영
- OCR 동작 불가 원인 확인 및 메인 기준 정리 완료
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
  - Manual Mode `📸 Capture` 메뉴 버튼 추가
  - Zoom-In 캡처: `F6` Region Capture, `F7` Window Capture
  - Zoom-Out 캡처: `F8` Region Capture, `F9` Window Capture
  - 캡처 이미지 저장 구조: `captures/{YYYYMMDD}/{probe}/{zoomin,zoomout}/`
  - Zoom-In 캡처 직후 Manual 카드 자동 생성/선택 및 QR 입력창 자동 포커스
  - QR 매칭 후 `slot_XX_{QRID}.png` 형식으로 파일명 자동 확정
  - Zoom-Out sibling 파일도 QR 확정 및 Manual 순번 재정렬 시 함께 동기화
- Manual 카드 삭제 후 순번 안정화 구현 완료
  - 삭제 후 남은 카드가 `#1, #2, #3...`으로 재정렬
  - QR ID, Frequency, Q, Probe Type, 이미지 경로는 카드와 함께 유지
  - 앱 내부 캡처 파일은 재정렬된 순번에 맞춰 파일명 재동기화
- Zoom-In / Zoom-Out 분리 캡처 및 반출 구조 구현 완료
  - 폴더 업로드 시 Zoom-Out backtick 접미사 파일 자동 필터
  - 이미지 뷰어 상단 `Zoom-In | Zoom-Out` 토글 추가
  - CSV+Images Export 시 `ZOOMIN/`, `ZOOMOUT/` 두 폴더 동시 출력
  - Bundle Export ZIP `images/`에 zoom-in + zoom-out 양쪽 포함
  - DB 스키마/`SlotData` 변경 없이 zoom-out 경로는 zoom-in 경로에서 파생
- Manual 이미지 표시 안정화 및 Zoom 버튼 개선 완료
  - `ImageViewer`를 고정 뷰포트 기반 paint 방식으로 변경
  - 큰 캡처/비율이 다른 캡처가 들어와도 UI 레이아웃을 밀지 않고 현재 영역 안에 Fit 표시
  - Manual 좌측 패널 최소 폭 및 splitter stretch 조정
  - `Zoom-In` / `Zoom-Out` 버튼 최소 크기 확대로 글자 잘림 개선
- docs 폴더 문서 최신화 완료
  - `docs/PRD.md`: 문서 버전 2.1, Manual Capture/Zoom-In-Out/CSV Export/History Statistics/ImageViewer 안정화 반영
  - `docs/export_schema.md`: CSV, CSV+Images, Bundle Export 구조와 Zoom-Out sibling 규칙 반영
  - `docs/user-guide.html`: 운영자용 가이드를 현재 탭 구조와 Capture-First 흐름 기준으로 업데이트
  - `docs/phase7-deployment-analysis.md`: 이력 보존 문서 상단에 최신 기준 PRD 참조 안내 추가
- 테스트/검증 완료
  - `python -m py_compile src\ui\widgets\image_viewer.py src\ui\controllers\ui_builder_mixin.py` 통과
  - `python -m pytest -q`: 85 passed / 15 skipped
  - `git diff --check` 통과

## 진행중

- 이번 변경분은 메인 워크트리에 미커밋 상태
  - `src/ui/widgets/image_viewer.py`
  - `src/ui/controllers/ui_builder_mixin.py`
  - `docs/WORKLOG.md`
  - `docs/PRD.md`
  - `docs/export_schema.md`
  - `docs/user-guide.html`
  - `docs/phase7-deployment-analysis.md`
- Manual 이미지 표시 안정화 변경에 대한 사용자 GUI 재확인 대기
  - 캡처 이미지 크기/비율이 달라도 Manual 좌우 레이아웃이 흔들리지 않는지 확인 필요
  - Zoom-In / Zoom-Out 버튼 글자 잘림 개선 확인 필요
- 문서 정리 반영 완료, 최종 diff 리뷰 대기

## 다음할일

- GUI 수동 확인
  - 100%, 125%, 150% Windows 배율에서 Zoom 버튼 글자 잘림 여부 확인
  - 작은 캡처, 큰 창 캡처, 가로로 긴 캡처, 세로로 긴 캡처 로드 시 Manual 레이아웃 안정성 확인
  - Zoom-In / Zoom-Out 전환 시 좌측 패널 폭이 바뀌지 않는지 확인
  - splitter 수동 조절 동작 유지 확인
- Manual Capture 흐름 재확인
  - F6/F7로 Zoom-In 캡처 → 새 카드 생성 확인
  - F8/F9로 Zoom-Out 캡처 → 선택 카드 sibling 파일 생성 확인
  - QR 입력 후 zoom-in/zoom-out 파일명이 같은 stem 기준으로 rename 되는지 확인
- Export/Bundle 흐름 재확인
  - CSV+Images Export 시 `ZOOMIN/`, `ZOOMOUT/` 두 폴더 생성 확인
  - QR 없는 슬롯 포함/제외 옵션이 기존 정책대로 동작하는지 확인
  - Bundle Export/Import에서 zoom-in/zoom-out 이미지가 같이 보존되는지 확인
- 최종 확인 후 커밋 및 push
  - `git status --short --branch`
  - `python -m pytest -q`
  - `git diff --check`
  - 기능 단위 커밋 생성 후 `origin/main` push

## 미결이슈

- `Window Capture`는 Windows API 기반이므로 실제 장비/배율/멀티모니터 환경에서 추가 확인 필요
- Windows 배율 125%/150%에서 창 클릭 캡처 좌표가 어긋나는지 최종 확인 필요
- 캡처 파일 삭제 정책은 아직 미구현
  - 현재 카드 삭제 시 DB/카드만 삭제하고 실제 이미지 파일은 보존
  - Zoom-Out sibling도 동일하게 보존
- Zoom-Out 캡처 시 기존 파일 존재하면 확인 다이얼로그 없이 덮어쓰기
  - 실수 방지가 필요하면 별도 옵션화 가능
- `Drive (%)`는 현재 CSV/Upload 열로만 복구됨
  - 과거/Manual 데이터에 Drive 값이 없으면 빈 칸으로 반출
- `전체 슬롯 업로드` 선택 시 서버가 빈 QR ID 행을 거부할 가능성 있음
- OCR 실제 샘플 기반 테스트 일부는 샘플/Tesseract 조건에 따라 skip 됨
- 다른 PC에서 OCR을 이어가려면 `.gitignore` 처리된 `third_party/tesseract` 런타임 또는 시스템 Tesseract 설치가 필요
