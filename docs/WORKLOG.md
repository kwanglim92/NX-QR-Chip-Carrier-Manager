# WORKLOG

## 완료

- 메인 워크트리 단일 기준 운영 유지
  - 실제 코드 수정/실행/GUI 확인 기준: `C:\Users\Spare\Desktop\03. Program\새 폴더`
  - Codex 임시 워크트리는 신규 브릿지/구현 기준으로 사용하지 않음
- Phase 10 UX 개선 구현 및 문서화 완료
  - ATX 슬롯 편집 다이얼로그화
  - Export `ATX` / `Manual` 탭 분리
  - CSV 미완성 데이터 옵션 및 `Drive (%)` 컬럼 복구
  - History Records/Statistics 레이아웃 개선
  - Manual Capture-First, Zoom-In/Zoom-Out 분리 캡처, 캡처 파일명 자동 확정
  - Manual 삭제 후 순번 안정화 및 ImageViewer 고정 뷰포트 표시
- 배포 버전 표기 2.1.0 정리 완료
  - `installer.iss` `MyAppVersion=2.1.0`
  - `VERSION=2.1.0`
  - `docs/PRD.md` 배포 산출물/버전 이력/사전검사 설명 업데이트
  - `docs/user-guide.html` 설치 파일명을 `McQrManager-Setup-x.y.z.exe` 기준으로 정리
- 사용자 가이드 실무 운영 구조 반영 완료
  - `docs/user-guide.html`을 현장 오퍼레이터 중심 상세 매뉴얼로 개편
  - 문서 대상에서 품질 관리자/IT 담당자 제외
  - NX 1.0.0 -> MC 2.x 마이그레이션 안내 제거
  - 하단 개발자 정보 추가: Levi.Beak / `levi.beak@parksystems.com`
  - `docs/assets/user-guide/` 스크린샷 자산 폴더와 촬영 목록 추가
  - `docs/DOCUMENTATION_WORKFLOW.md`에 HTML 원본 -> PDF 배포본 -> PPT 교육본 흐름 정리
  - `docs/MC_QR_Manager_User_Guide_v2.1.0.pdf` 배포 초안 생성
- 앱 내장 설명서 창 구현 완료
  - 상단 `📘 설명서` 버튼 추가
  - `QWebEngineView` 기반 사용자 가이드 다이얼로그 추가
  - `QWebEngineView` 사용 불가 시 외부 브라우저 fallback 제공
  - 개발 실행/배포 실행 모두에서 `docs/user-guide.html` 경로를 찾도록 처리
  - PyInstaller 배포 산출물에 `docs/user-guide.html`과 `docs/assets/user-guide/` 포함
  - `build.bat`에서 사용자 가이드 번들 여부 검증
- 빌드/검증 완료
  - `python -m py_compile src\ui\dialogs\user_guide_dialog.py src\ui\controllers\ui_builder_mixin.py` 통과
  - `python -m pytest -q`: 94 passed / 6 skipped
  - `git diff --check` 통과
  - `build.bat` 통과
  - `dist\McQrManager\docs\user-guide.html` 포함 확인
  - `dist\McQrManager\docs\assets\user-guide\README.md` 포함 확인
  - `dist\McQrManager\PySide6\QtWebEngineProcess.exe` 포함 확인

## 진행중

- 내장 설명서 기능의 설치본 기준 최종 수동 확인 대기
  - 소스 실행 및 `dist\McQrManager\McQrManager.exe` 기준 번들 검증은 완료
  - `iscc installer.iss`로 설치 파일 재생성 후 설치본에서 설명서 버튼 동작 확인 필요

## 다음할일

- 설치본 재생성 및 수동 확인
  - `iscc installer.iss` 실행
  - `Output\McQrManager-Setup-2.1.0.exe` 재생성 확인
  - 기존 설치본 업그레이드 감지 확인
  - 설치 후 시작 메뉴/바탕화면 바로가기 실행 확인
  - 설치 경로의 `McQrManager.exe` 정상 실행 확인
  - `📘 설명서` 버튼으로 앱 내부 사용자 가이드 창 로드 확인
  - `브라우저에서 열기` fallback 확인
- 배포 전 최종 운영 확인
  - Manual Capture F6/F7/F8/F9 동작
  - CSV+Images `ZOOMIN/`, `ZOOMOUT/` 반출 구조
  - Export 미완성 데이터 옵션
  - OCR/Tesseract 동작
  - History Records/Statistics 화면
- 사용자 가이드 스크린샷 보강
  - `docs/assets/user-guide/`의 placeholder 목록 기준으로 실제 PNG 촬영
  - 민감 QR/PO/고객 정보가 보이지 않는 샘플 화면 사용
  - HTML/PDF의 그림 설명과 실제 화면 일치 여부 확인

## 미결이슈

- Windows SmartScreen 코드 서명은 아직 미적용
  - 설치 시 "알 수 없는 게시자" 경고가 발생할 수 있음
- Qt WebEngine 포함으로 설치본 용량 증가 가능
- 실제 사용자 가이드 스크린샷 PNG는 아직 placeholder 상태
- 설치본 실행 확인은 사용자 PC에서 최종 수동 확인 필요
- `Window Capture`는 실제 장비/배율/멀티모니터 환경에서 추가 확인 필요
- 캡처 파일 삭제 정책은 아직 미구현
  - 카드 삭제 시 DB/카드만 삭제하고 실제 이미지 파일은 보존
- `Drive (%)`는 CSV/Upload 열로만 복구됨
  - 과거/Manual 데이터에 Drive 값이 없으면 빈 칸으로 반출
- `전체 슬롯 업로드` 선택 시 서버가 빈 QR ID 행을 거부할 가능성 있음
