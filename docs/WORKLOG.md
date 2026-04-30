# WORKLOG

## 완료

- `.agent/rules.md`와 `.agent/skills/registry.json` 확인 완료
- 현재 브랜치 및 git 상태 확인 완료
- `docs/WORKLOG.md` 부재 확인 완료
- `docs/WORKLOG.md` 생성 완료
- Frequency/Q 측정값 소수점 버림 정수화 구현 완료
  - ATX `Summary.csv` 파싱값 정수화
  - OCR 추출값 정수화
  - Manual 입력 적용값 정수화
  - 기존 소수 저장값도 화면/CSV 표시 시 버림 처리
- ATX 선택 슬롯 편집 패널 구현 완료
  - Probe Type, Frequency, Q, QR ID, Source 수정 지원
  - QR ID 중복 검사 적용
  - 수정 후 카드 갱신, 진행률 갱신, DB 자동 저장 연결
- Port 섹션 표시 순서 변경 완료
  - Port 내림차순 표시 적용
  - Port4 파싱 유지 확인
- 테스트/검증 환경 구성 완료
  - `pytest`, `pytest-qt`, `PySide6` 및 프로젝트 의존성 설치 완료
  - 관련 테스트: `16 passed, 6 skipped`
  - 전체 테스트: `62 passed, 15 skipped`

## 진행중

- `AGENTS.md`가 새 파일로 추가되어 있으나 아직 git 추적 대상은 아님
- 측정값 정수화/ATX 편집/Port 배치 변경 코드가 작업트리에 수정 상태로 남아 있음
- 신규 테스트 파일 `tests/test_measurement_values.py`가 아직 git 추적 대상은 아님

## 다음할일

- 필요 시 `AGENTS.md`를 스테이징/커밋 대상으로 포함할지 결정
- `docs/WORKLOG.md`를 스테이징/커밋 대상으로 포함할지 결정
- 이번 기능 변경 파일들을 리뷰 후 스테이징/커밋할지 결정
- 실제 GUI에서 ATX 폴더 로드 후 선택 슬롯 편집 패널 동작을 수동 확인
- 실제 ATX 데이터에서 Port2가 Port1 위에 표시되는지 화면 확인

## 미결이슈

- `AGENTS.md`의 프로젝트명 placeholder `[Project Name]`이 아직 실제 프로젝트명으로 치환되지 않음
- `.agent/skills/registry.json`의 `"project"` 값이 아직 `"Master Skills Template"`로 남아 있음
- OCR 실제 샘플 기반 테스트 일부는 샘플/Tesseract 조건에 따라 skip됨
- PySide6/pytest 실행 스크립트 경로가 PATH에 등록되어 있지 않아 번들 Python의 `-m pytest` 방식으로 실행 필요
