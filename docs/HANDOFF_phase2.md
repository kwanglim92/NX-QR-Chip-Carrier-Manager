# Phase 2 핸드오프 — 필드 노트북 새 세션용

| 항목 | 내용 |
|---|---|
| **작성일** | 2026-09-09 |
| **기준 커밋** | `main` (이 문서 커밋 포함) |
| **용도** | 다른 PC(필드 노트북)에서 Claude Code 새 세션을 열어 Phase 2를 이어갈 때, 아래 §4 프롬프트를 그대로 붙여 넣는다 |
| **선행 문서** | [`qr-reader-integration-design.md`](./qr-reader-integration-design.md), [`central-db-aggregation-design.md`](./central-db-aggregation-design.md)(보류), [`PRD.md`](./PRD.md) |

---

## 1. Phase 2 구성과 현재 상태

| 항목 | 상태 | 비고 |
|---|---|---|
| **2-A 서버 업로드 연동** (probe-info.parksystems.com) | **완료 (main 92db21f)** | TLS 검증 활성, 세션 만료 감지·재로그인, Update(서버 수정) 메뉴, 이미지 전송명 `{QR ID}.png`, Fake Session 테스트 26건. **운영 DB이므로 실서버 업로드 검증은 수행하지 않음** — 서버의 이미지↔QR 매핑 규칙·Probe Type 명칭 매칭은 미확인(PRD §7) |
| **2-B 다중 QR 리더기 연동** (키엔스, LAN) | **설계 v0.1 완료, 구현 미착수** | 설계 문서 §2 확정 결정, §10 A단계 확인 목록, §11 작업 분해 R1~R7. **다음 = A단계(리더기 원문 캡처)** |
| 중앙 DB 취합 | 보류 | 설계 v0.2 문서만 커밋 |
| 릴리스 2.4.0 | 미수행 | `VERSION`=2.3.0, CHANGELOG `[Unreleased]` 누적 중 |

테스트: `pytest -q` → 151 passed / 6 skipped (2026-09-08 기준). `%LOCALAPPDATA%` 를 임시 경로로 리다이렉트하고 실행할 것(실 DB 보호).

## 2. 확정된 설계 요점 (2-B)

- 통신: **LAN/TCP, 앱이 클라이언트**로 리더기에 접속. 키보드 에뮬레이션은 폴백만.
- 리더기가 **격자 셀 번호**와 **코드별 X,Y**를 출력. 셀 번호 규약 `cell = (port − 1) × 12 + slot` (1~72).
- 결과 폴더 슬롯 번호 = **분류 후 최종 물리 위치**. 최대 6 포트 × 12 = 72 코드.
- 고정 개수 + **NG 자리표시** 출력(미판독 칸이 밀리지 않게).
- 적용은 **검토 다이얼로그 확인 후 일괄**. 트리거는 앱에서 명령 전송.
- 지그(현재) → MTC 직접 부착(향후) 전환은 리더기 격자 재정의만으로 대응.

## 3. 필드 노트북 준비 체크리스트

- [ ] 저장소 clone 후 `python -m venv .venv` → `pip install -r requirements.txt -r requirements-dev.txt` (Python 3.11+)
- [ ] `pytest -q` 그린 확인 (Tesseract 없으면 6 skip 정상)
- [ ] 리더기 IP·데이터 포트·명령 포트·트리거 명령을 모델 통신 매뉴얼에서 확인 (설계 문서 §10)
- [ ] 노트북과 리더기가 같은 서브넷, 아웃바운드 TCP 허용
- [ ] 리더기 설정: 다중 코드 고정 개수, 격자 번호(§2 규약), X,Y 출력, NG 자리표시, 헤더/구분자/종단자
- [ ] Pass 카세트 실물: 만석 / 일부 빈 칸 / 카세트 1개 통째 비움 / 회전 오프셋 / 중복 코드 시나리오 준비

## 4. 새 세션 프롬프트 (그대로 붙여 넣기)

```text
이 프로젝트(MC QR Code Chip Carrier Manager)의 Phase 2-B "키엔스 다중 QR 리더기 연동"을 이어서 진행한다.
먼저 docs/HANDOFF_phase2.md 와 docs/qr-reader-integration-design.md 를 읽고 현재 상태와 확정 결정을 파악해라.
CLAUDE.md 와 .agent/rules.md 의 개발 규칙(계획 먼저, 요청 범위만, skill-first)을 따른다.

작업 환경: 필드 노트북에 키엔스 QR 리더기가 LAN으로 연결되어 있다. 리더기 모델명과 IP·포트는 내가 알려준다.
제약: probe-info.parksystems.com 은 운영 DB이므로 어떤 쓰기도 하지 말 것. 네트워크 접속은 리더기 IP에만 한다.
테스트 실행 시 %LOCALAPPDATA% 를 임시 경로로 리다이렉트해 실제 chip_carrier.db 를 보호한다.

오늘 목표 = 설계 문서 §10 A단계:
1. scripts/capture_keyence.py 로 리더기 원문 출력을 캡처해 tests/fixtures/qr_reader/ 에 저장한다.
   시나리오: 만석(full) / 일부 빈 칸(partial) / 카세트 1개 통째 비움(empty) / 회전 오프셋(rotated) / 중복 코드(dup).
2. 캡처 결과로 프레임 형식(헤더·구분자·종단자·셀 번호·X,Y·NG 문자열)과 명령(트리거·포트)을 확정해
   설계 문서 §3 "리더기 출력 계약"과 §9 미결을 갱신하고, §10 체크리스트를 채운다.
3. 확정된 형식으로 R1(payload_parser + 테스트)과 R2(slot_assigner + 테스트)를 구현한다. 하드웨어 없이 fixture 로 검증.
4. 시간이 남으면 R3(QTcpSocket 클라이언트 + scripts/fake_keyence_server.py + 인프로세스 테스트)까지.

진행 방식: 단계마다 계획을 먼저 보여주고 승인 후 구현. 커밋은 CLAUDE.md Git 규칙(2~4개면 feat 브랜치 → ff-merge)을 따른다.
완료 시 docs/HANDOFF_phase2.md 의 상태 표를 갱신해 다음 세션이 이어갈 수 있게 한다.
```

## 5. A단계 캡처 도구 사용법

```powershell
# 데이터 포트에 붙어 리더기 트리거(버튼/외부)로 판독한 결과를 60초간 수집
.venv\Scripts\python.exe scripts\capture_keyence.py --host <리더기IP> --port <데이터포트> --duration 60 --tag full

# 접속 직후 트리거 문자열 전송 후 수집 (명령 문자열·포트는 모델 매뉴얼 기준)
.venv\Scripts\python.exe scripts\capture_keyence.py --host <리더기IP> --port <포트> --send "LON\r" --duration 15 --tag partial
```

산출물은 `tests/fixtures/qr_reader/<시각>_<tag>.raw`(원본 바이트)와 `.txt`(제어문자 표시)로 남는다. `.raw` 는 수정하지 않고 파서 테스트 입력으로 그대로 쓴다.

## 6. 이후 단계 (A 완료 후)

R1 파서 → R2 슬롯 대응 → R3 TCP 클라이언트 → R4 설정/상태 표시 → R5 검토 다이얼로그 → R6 카세트 스캔 통합 → R7 문서. 세부는 설계 문서 §11. E단계(지그 현장 검증) 후 2.4.0 릴리스에 2-A와 함께 묶는다.
