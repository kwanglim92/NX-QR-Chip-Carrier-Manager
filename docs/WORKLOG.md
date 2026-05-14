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
- Inno Setup 인스톨러 사전검사 추가 완료
  - `dist\McQrManager\McQrManager.exe` 누락 시 컴파일 중단
  - `dist\McQrManager\python311.dll` 누락 시 컴파일 중단
  - `dist\McQrManager\third_party\tesseract\tesseract.exe` 누락 시 컴파일 중단
  - `build\McQrManager\McQrManager.exe` 중간 산출물 오실행/오배포 방지
- 2.1.0 설치 파일 생성 확인
  - `Output\McQrManager-Setup-2.1.0.exe`
  - 크기 약 150.5 MB
- 최근 검증 완료
  - `python -m pytest -q`: 85 passed / 15 skipped
  - `git diff --check` 통과
  - Inno Setup 산출물 생성 확인

## 진행중

- 없음
  - 기능/문서 변경은 2.1.0 배포 정리 기준으로 마무리
  - 남은 작업은 설치본 수동 확인과 운영 환경 검증

## 다음할일

- 설치본 수동 확인
  - `Output\McQrManager-Setup-2.1.0.exe` 실행
  - 기존 설치본 업그레이드 감지 확인
  - 설치 후 시작 메뉴/바탕화면 바로가기 실행 확인
  - 설치 경로의 `McQrManager.exe`가 정상 실행되는지 확인
  - OCR/Tesseract 동작 확인
- 배포 전 최종 운영 확인
  - Manual Capture F6/F7/F8/F9 동작
  - CSV+Images `ZOOMIN/`, `ZOOMOUT/` 반출 구조
  - Export 미완성 데이터 옵션
  - History Records/Statistics 화면

## 미결이슈

- Windows SmartScreen 코드 서명은 아직 미적용
  - 설치 시 "알 수 없는 게시자" 경고가 발생할 수 있음
- 설치본 실행 확인은 사용자 PC에서 최종 수동 확인 필요
- `Window Capture`는 실제 장비/배율/멀티모니터 환경에서 추가 확인 필요
- 캡처 파일 삭제 정책은 아직 미구현
  - 카드 삭제 시 DB/카드만 삭제하고 실제 이미지 파일은 보존
- `Drive (%)`는 CSV/Upload 열로만 복구됨
  - 과거/Manual 데이터에 Drive 값이 없으면 빈 칸으로 반출
- `전체 슬롯 업로드` 선택 시 서버가 빈 QR ID 행을 거부할 가능성 있음
