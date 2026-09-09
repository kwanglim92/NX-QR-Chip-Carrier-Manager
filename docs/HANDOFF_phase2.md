# Phase 2 핸드오프 — 필드 노트북 새 세션용

| 항목 | 내용 |
|---|---|
| **작성일** | 2026-09-09 (갱신: 2026-09-09 필드 세션 후) |
| **기준 커밋** | `main` (이 문서 커밋 포함) |
| **용도** | 다른 PC(필드 노트북)에서 Claude Code 새 세션을 열어 Phase 2를 이어갈 때, 아래 §4 프롬프트를 그대로 붙여 넣는다 |
| **선행 문서** | [`qr-reader-integration-design.md`](./qr-reader-integration-design.md), [`central-db-aggregation-design.md`](./central-db-aggregation-design.md)(보류), [`PRD.md`](./PRD.md) |

---

## 1. Phase 2 구성과 현재 상태

| 항목 | 상태 | 비고 |
|---|---|---|
| **2-A 서버 업로드 연동** (probe-info.parksystems.com) | **완료 (main 92db21f)** | TLS 검증 활성, 세션 만료 감지·재로그인, Update(서버 수정) 메뉴, 이미지 전송명 `{QR ID}.png`, Fake Session 테스트 26건. **운영 DB이므로 실서버 업로드 검증은 수행하지 않음** — 서버의 이미지↔QR 매핑 규칙·Probe Type 명칭 매칭은 미확인(PRD §7) |
| **2-B 다중 QR 리더기 연동** (키엔스 SR-X300W, LAN) | **A단계 ①·R1·R2·R3 완료, 설계 v0.2, UI 목업 승인** | 프로토콜 확정(설계 §3), 만석 fixture 캡처, `src/core/qr_reader/{payload_parser,slot_assigner,keyence_client}.py` + 테스트 80건, `scripts/fake_keyence_server.py`. 클라이언트 실기기 1회 판독 검증. **다음 = A단계 ②~⑤ 시나리오 캡처 → R4(설정 키·리더기 설정 다이얼로그·상태 칩) → R5(검토 다이얼로그)**. UI 목업: [Keyence Cassette Scan UI](https://claude.ai/code/artifact/868c790f-eef6-4937-ae54-5cbbb723f208) |
| 중앙 DB 취합 | 보류 | 설계 v0.2 문서만 커밋 |
| 릴리스 2.4.0 | 미수행 | `VERSION`=2.3.0, CHANGELOG `[Unreleased]` 누적 중 |

테스트: `pytest -q --ignore=tests/test_server_uploader.py` → 197 passed / 15 skipped (2026-09-09, 필드 노트북 시스템 Python 3.12 기준 — `requests`·`pytesseract`·`pytest-qt` 미설치라 업로더 테스트 제외, Tesseract 없음). `%LOCALAPPDATA%` 를 임시 경로로 리다이렉트하고 실행할 것(실 DB 보호).

> **필드 노트북 주의**: `python` 명령은 Windows Python 관리자 셈이라 `LOCALAPPDATA` 를 바꾸면 새 Python 을 내려받는다. 반드시 절대 경로 인터프리터를 쓸 것:
> `LOCALAPPDATA=<임시경로> C:\Users\Levi.Beak\AppData\Local\Python\pythoncore-3.12-64\python.exe -m pytest -q`

## 2. 확정된 설계 요점 (2-B)

- 통신: **LAN/TCP 9004 단일 소켓, 앱이 클라이언트**. 트리거는 **레벨 방식** `LON` → 대기(6초 캡처 성공) → `LOFF` 에서 결과 출력. 키보드 에뮬레이션은 폴백만.
- 프레임(확정): `code×72` 를 `,` 로, 끝에 `:NNNNms`, 종단 `CR`. 미판독 `ERROR`. 헤더·좌표·영역번호 없음(셀 = 인덱스).
- **AutoID Network Navigator 연결 중이면 모든 명령이 `ER,<cmd>,23`** — 앱 사용 전 Navigator 에서 연결 해제(매뉴얼 10-2 p.59).
- Phase 2 셀 대응: `port=(cell−1)÷12+1, slot=(cell−1)%12+1`, 카세트 1 = Port 1. MTC 물리 방향은 F단계.
- 리더기가 **격자 셀 번호**와 **코드별 X,Y**를 출력. 셀 번호 규약 `cell = (port − 1) × 12 + slot` (1~72).
- 결과 폴더 슬롯 번호 = **분류 후 최종 물리 위치**. 최대 6 포트 × 12 = 72 코드.
- 고정 개수 + **NG 자리표시** 출력(미판독 칸이 밀리지 않게).
- 적용은 **검토 다이얼로그 확인 후 일괄**. 트리거는 앱에서 명령 전송.
- 지그(현재) → MTC 직접 부착(향후) 전환은 리더기 격자 재정의만으로 대응.

## 3. 필드 노트북 준비 체크리스트

- [ ] 저장소 clone 후 `python -m venv .venv` → `pip install -r requirements.txt -r requirements-dev.txt` (Python 3.11+)
- [ ] `pytest -q` 그린 확인 (Tesseract 없으면 6 skip 정상)
- [x] 리더기 IP·포트·트리거 확인 — 192.168.100.2:9004, LON/LOFF (설계 §3.2)
- [x] 노트북 192.168.100.1/24 ↔ 리더기 192.168.100.2 (핑은 막혀 있고 TCP 9004 만 열림)
- [x] 리더기 설정 확인 — 설계 §3.3 설정 시트 (X,Y 는 OFF 로 확정)
- [ ] Pass 카세트 실물 시나리오: [x] 만석(`20260909_132804_full`, 셀 13·14 조명 미판독) [ ] 일부 빈 칸 [ ] 카세트 1개 통째 비움 [ ] 회전 오프셋 [ ] 중복 코드

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

# SR-X300W 확정 절차(레벨 트리거): LON → 6초 → LOFF. 시나리오 태그만 바꿔 반복
python scripts\capture_keyence.py --host 192.168.100.2 --port 9004 --send "LON\r" --then "LOFF\r" --then-after 6 --duration 9 --tag partial
```

산출물은 `tests/fixtures/qr_reader/<시각>_<tag>.raw`(원본 바이트)와 `.txt`(제어문자 표시)로 남는다. `.raw` 는 수정하지 않고 파서 테스트 입력으로 그대로 쓴다.

## 6. 이후 단계 (A 완료 후)

~~R1 파서 → R2 슬롯 대응 → R3 TCP 클라이언트~~(완료, `KeyenceClient` 시그널: state_changed/frame_received/frame_rejected/command_error/response_received/comm_error) → **R4 설정/상태 표시**(`app_settings.qr_reader` 키, 목업의 리더기 설정 다이얼로그, 하단 바 상태 칩 + 카세트 스캔 버튼) → R5 검토 다이얼로그(목업 기준) → R6 카세트 스캔 통합 → R7 문서. 세부는 설계 문서 §11. 참고: 원격 브랜치 `feat/multi-qr-check`(2026-08-18, 미병합)에 SR-X300W 선행 구현(`srx_client.py`, `fake_srx_server.py`)이 있으나 프레임에 셀 상태 분류가 없어 참고용으로만 쓴다. E단계(지그 현장 검증) 후 2.4.0 릴리스에 2-A와 함께 묶는다.
