# 중앙 DB 생산 데이터 취합 — 설계 문서

| 항목 | 내용 |
|------|------|
| **문서 버전** | 0.2 |
| **작성일 / 개정일** | 2026-07-02 / 2026-08-18 |
| **기준 앱 버전** | 2.3.0 (`main`, 배포됨) |
| **대상 릴리스** | 2.4.0 (0단계) |
| **대상 독자** | 개발 / 운영 / 품질관리 |
| **상태** | **0단계 구현 착수 가능** — 코드 대조 검증 완료, 미결 3건 확정(§9), 작업 분해 §12 |
| **관련 문서** | [`auto-update.md`](./auto-update.md), [`PRD.md`](./PRD.md), [`export_schema.md`](./export_schema.md) |

> **이 문서의 목적**
> 1. 여러 클라이언트 PC의 생산 데이터를 **하나의 중앙 DB로 취합**하는 방식을 확정·기록한다.
> 2. 관리자의 **실시간 생산 모니터링**(작업자·설비별 팁 생산량)의 토대를 정의한다.
> 3. 구현 착수 전 데이터 모델·동기화 프로토콜·단계별 로드맵을 한 곳에 정리한다.
>
> **범위 밖**: 자동 업데이트(`src/updater/`)는 이미 구현되어 있으며 본 건과 **분리·보류**한다. 본 문서는 데이터 취합에 한정한다.

---

## 1. 배경 및 목표

### 1.1 배경
- 제조 엔지니어는 현재 **수작업** 중심이라, 관리자가 "누가 얼마나 팁을 생산 중인지"를 **실시간으로 파악하기 어렵다.**
- 앱은 클라이언트 PC마다 **로컬 SQLite**(`%LOCALAPPDATA%/MCQRCodeChipCarrier/chip_carrier.db`)에 독립적으로 데이터를 쌓는다 → 데이터가 **PC별로 흩어져** 있다.
- 제조 엔지니어의 **저학력 제약이 크다** → 작업자에게 새로운 입력·조작을 요구하면 안 된다.

### 1.2 목표
- 설치형 앱을 **여러 클라이언트 PC에 설치**한 뒤, 각 PC의 생산 데이터가 **중앙 DB 한 곳으로 자동 취합**된다.
- 취합 데이터로 **작업자/설비별 생산량(팁 수) 집계** → (후속) 관리자 실시간 대시보드.
- 작업자는 **아무 새 행동도 하지 않는다**(UUID·동기화·집계 전부 백그라운드 자동). 유일한 1회 설정은 "이 PC의 작업자/설비" 지정뿐.

### 1.3 비목표 (Non-goals)
- 자동 업데이트 재설계 (별도, 보류).
- 이미지의 중앙 취합 (팁 카운트 모니터링에 불필요 — §9 참고).
- 클라이언트 간 양방향 동기화 (단방향: 클라 → 중앙만).

---

## 2. 확정 결정 (AskUserQuestion)

| 결정 항목 | 채택안 | 핵심 이유 |
|---|---|---|
| **취합 방식** | **로컬 우선 + 중앙 API 동기화** | 오프라인 안전(작업 중단 없음), 기존 HTTP 업로드 패턴 재사용, 대시보드 확장 용이 |
| **작업자 식별** | **PC = 작업자/설비 고정** | 저학력 제약 — 매일 로그인 없음. 설치/최초 1회 지정 후 무로그인 |

**탈락안 요약**: ① 중앙 DB 직접 연결 → 네트워크 단절 시 작업 중단·자격증명 노출로 현장 부적합. ② 공유 폴더 파일 드롭 → 준실시간(배치)·중복 관리 부담. ③ 공유 폴더 단일 SQLite → **DB 손상 위험(금지)**.

---

## 3. 핵심 설계 문제 (현 스키마에서 도출)

`src/core/database.py`(SCHEMA_VERSION=3) 확인 결과, 취합 전에 반드시 해결할 2가지:

1. **로컬 PK 충돌** — `measurement_sets.id` / `slots.id` 가 **로컬 AUTOINCREMENT 정수**. PC마다 `id=27`이 서로 다른 데이터 → 중앙에서 합치면 충돌. `source_folder`도 PC별 절대경로라 자연키 불가.
   → **전역 고유 키(UUID)** 를 set 단위로 부여. 중앙은 UUID 기준 upsert.
2. **생산자 식별 부재** — 스키마 어디에도 작업자/PC 컬럼이 없음 → 중앙에 모아도 구분 불가.
   → **`station_id`**(작업자/설비 식별자)를 레코드에 실어야 함.

---

## 4. 전체 아키텍처

```
[클라이언트 앱 ×N]                                  [서버 PC]
 로컬 SQLite (지금 그대로 — 오프라인 안전)
  ├ 최초 실행 1회: "이 PC 작업자/설비" 지정 → app_settings 저장
  ├ 측정 저장 시: set_uuid + station_id 부여, sync_status='pending'
  └ 백그라운드 동기화 워커
       └─ pending 레코드 JSON POST ──►  중앙 API (신규, 토큰 인증)
          (uuid 멱등, 오프라인 큐)             │ set_uuid 기준 upsert
                                              ▼
                                       중앙 DB (PostgreSQL)
                                              │
                                       (2단계) 관리자 대시보드
```

---

## 5. 구성요소

### ① 클라이언트 식별 (PC = 작업자 고정)
- `app_settings` 테이블에 `station_id`(+작업자명) 저장.
- **최초 실행 시 1회** 간단한 선택 다이얼로그: 설비/작업자를 **드롭다운**에서 선택(자유 입력 금지 — 저학력 오타 방지). 이후 무로그인.
- 모든 측정 레코드 생성 시 이 `station_id`를 자동 태깅.

### ② 전역 키 + 동기화 상태 (스키마 v3 → v4)
- `measurement_sets` 컬럼 추가: `set_uuid TEXT UNIQUE`(uuid4), `station_id TEXT`, `sync_status TEXT NOT NULL DEFAULT 'pending'`, `synced_at TEXT`.
- 마이그레이션에서 기존 행에 uuid 백필.
- slots는 `(set_uuid, slot_index)` 로 식별 → 별도 uuid 불필요.
- 저장/수정마다 해당 set을 `sync_status='pending'` + `updated_at` 갱신.
- ⚠️ 기존 `upload_status`/`uploaded_at`(probe-info 업로드용)과 **별도 컬럼** — 두 경로가 섞이지 않게.

### ③ 클라이언트 동기화 워커 (오프라인 안전)
- 백그라운드 스레드/타이머가 주기적으로(또는 저장 직후) `sync_status='pending'` set 조회 → set+slots+station을 JSON POST.
- 성공 시 `synced` + `synced_at`, 실패 시 그대로 pending(다음 재시도).
- **큐 = pending 행 자체** → 네트워크 단절에도 앱 정상, 복구 시 밀린 것 자동 전송.
- 구현은 `src/core/server_uploader.py`의 HTTP 패턴을 응용(단, 대상·인증은 중앙 API용으로 신규).

### ④ 중앙 API + DB (서버 PC에 신규)
- 소형 API 서비스(FastAPI 권장, 또는 기존 Django 확장): `POST /api/v1/measurements` (Bearer 토큰) → **set_uuid 기준 upsert**(재전송/중복 안전, slots는 교체).
- 중앙 **PostgreSQL**(동시 조회·대시보드에 안전).
- 호스팅 후보: 기존 업데이트 서버 PC(`10.4.1.141`) 또는 별도 서버. (§9 미결)

---

## 6. 데이터 모델

### 6.1 클라이언트 스키마 변경 (v4)
```sql
-- ① 컬럼 추가 (SQLite는 ALTER TABLE에 UNIQUE 제약을 붙일 수 없음 → 인덱스로 분리)
ALTER TABLE measurement_sets ADD COLUMN set_uuid    TEXT;
ALTER TABLE measurement_sets ADD COLUMN station_id  TEXT;
ALTER TABLE measurement_sets ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE measurement_sets ADD COLUMN synced_at   TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_ms_set_uuid ON measurement_sets(set_uuid);
CREATE INDEX IF NOT EXISTS idx_ms_sync_status ON measurement_sets(sync_status);

-- ② 삭제 전파용 tombstone (§7.1)
CREATE TABLE IF NOT EXISTS sync_tombstones (
    set_uuid    TEXT PRIMARY KEY,
    deleted_at  TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending'
);

-- app_settings: key='station_id', key='station_name' (최초 1회 설정)
```

> ⚠️ **이중 경로 주의**: `init_db`의 `CREATE TABLE IF NOT EXISTS measurement_sets`(신규 설치)와
> `_migrate`(기존 설치)를 **양쪽 다** 고쳐야 한다. 기존 v2/v3 마이그레이션은 `slots`만 건드려서
> 이 함정이 없었다. 두 경로가 갈라지면 신규 PC와 기존 PC의 스키마가 달라진다 → 회귀 테스트 필수(§12 T5).

> **`set_uuid` 발급 불변식** — `save_measurement_set`(`src/core/database.py:153`)은 분기가 **3개**다:
> (a) `db_id` 기준 UPDATE, (b) ATX `source_folder` 중복 덮어쓰기, (c) INSERT.
> **uuid는 (c)에서만 발급**하고 (a)(b)는 **기존 uuid를 보존**한 채 `sync_status='pending'`으로만 되돌린다.
> (b)에서 uuid를 재발급하면 같은 폴더를 재임포트할 때마다 중앙에 별개 set이 생겨 **생산량이 중복 집계**된다.

### 6.2 중앙 DB 스키마 (PostgreSQL, 개략)
```
stations(station_id PK, name, line, active)
measurement_sets(set_uuid PK, station_id FK, po_number, quantity, probe_type,
                 production_date, iso_week, mode, created_at, updated_at,
                 app_version, received_at)
slots(set_uuid FK, slot_index, slot_code, frequency, drive, q_factor,
      qr_id, probe_type, serial_number, contact_mode,
      PRIMARY KEY(set_uuid, slot_index))
```
- **생산량 집계 (확정)**: 중앙은 slot 원본을 그대로 보관하고 **두 지표를 모두** 집계한다.
  - `tip_count` = `qr_id IS NOT NULL` 인 slots 수 (컨택 모드 QR-only 슬롯 포함)
  - `complete_count` = `qr_id IS NOT NULL AND frequency IS NOT NULL AND q_factor IS NOT NULL`
    — 앱의 기존 `get_production_stats.complete_slots`(`src/core/database.py:406`)와 **동일 정의**
  - 대시보드에서 어느 지표를 볼지 선택. 두 값을 다 보관하므로 나중에 정의를 바꿔도 **재전송이 불필요**하고,
    앱 화면 숫자와 대시보드 숫자를 상시 대조 검증할 수 있다.

### 6.3 동기화 payload (클라 → 중앙, JSON)
```json
{
  "set_uuid": "…", "station_id": "STN-03", "app_version": "2.4.0",
  "po_number": "P2601001", "probe_type": "AC160",
  "production_date": "20260702", "iso_week": "2026-W27", "mode": "atx",
  "created_at": "…", "updated_at": "…",
  "slots": [
    {"slot_index": 0, "slot_code": "_1101", "frequency": 327.6,
     "q_factor": 614.2, "qr_id": "123456", "probe_type": "AC160", "…": "…"}
  ]
}
```

---

## 7. 동기화 프로토콜

- **엔드포인트**: `POST /api/v1/measurements` (Bearer 토큰, LAN 내부).
- **멱등성**: 서버는 `set_uuid` upsert — 같은 set 재전송/수정 재동기화에도 중복 없음(slots는 교체).
- **상태 전이(클라)**: `pending` → (POST 200) → `synced`; 실패 시 `pending` 유지(다음 사이클 재시도).
- **오프라인 큐**: 별도 큐 테이블 불필요 — `sync_status='pending'` 행 집합이 곧 큐.
- **배치 제한**: 한 사이클에 **최대 50건**만 전송(오래된 `updated_at` 순). 마이그레이션 직후 수개월치
  pending이 한꺼번에 나가 서버가 스파이크를 맞는 것을 막는다.
- **시간 기준**: 집계는 `production_date`(작업일), 서버 `received_at`은 감사·지연 진단용.

### 7.1 삭제 전파 (v0.2 추가)

로컬 `delete_measurement_set`(`src/core/database.py:346`)은 로컬 행만 지운다. 그대로 두면 중앙에
**유령 레코드**가 남아 생산량이 과대 집계된다.

- 삭제 시 `sync_tombstones(set_uuid, deleted_at, 'pending')`에 기록한다 (이미 `synced`된 set에 한함 —
  한 번도 전송 안 된 set은 중앙에 없으므로 tombstone 불필요).
- 워커는 pending tombstone을 `DELETE /api/v1/measurements/{set_uuid}` 로 전송하고 성공 시 `synced` 표시.
- **0단계에서 tombstone 기록만은 반드시 넣는다.** 전송 로직은 1단계여도 되지만, 기록이 없으면
  0단계 배포 후 서버 구축 전까지 삭제된 건은 **영원히 중앙에서 지울 수 없다**.

---

## 8. 단계별 로드맵

| 단계 | 내용 | 서버 필요 | 독립 배포 |
|---|---|:---:|:---:|
| **0. 클라 스캐폴딩** | 스키마 v4 + 최초 1회 station 다이얼로그 + 레코드 태깅 + pending 축적 | ❌ | ✅ 앱만 릴리스 가능 |
| **1. 서버 + 동기화 ON** | 중앙 API + PostgreSQL 구축, 클라 워커 활성화(서버 URL 설정) | ✅ | — |
| **2. 관리자 대시보드** | station × 날짜 생산량 실시간 화면 | ✅ | — |

> **핵심**: 0단계는 서버 없이도 **완전히 안전**하다. 서버가 없으면 로컬에 `pending`으로 쌓이기만 하고, 나중에 서버가 서면 그때부터 밀린 것까지 자동 전송된다. → **앱 릴리스와 서버 구축을 분리**할 수 있다.

---

## 9. 미결 사항 / 리스크

### 9.1 확정 (2026-08-18)

| 항목 | 확정 내용 |
|---|---|
| **생산량 정의** | `tip_count`·`complete_count` **둘 다 저장**, 대시보드에서 선택 (§6.2) |
| **과거 데이터 백필** | 전부 uuid 백필 + `pending` → **전송하되 사이클당 50건 배치 제한** (§7) |
| **station 미지정** | **지정 전까지 앱 진입 불가** — 취소 불가 모달. 귀속 불명 데이터를 원천 차단 (§12 T2) |

### 9.2 미결 (1단계 착수 전 확정 필요)

| 항목 | 내용 | 기본 방향 |
|---|---|---|
| **중앙 서버 위치** | `10.4.1.141`(기존 업데이트 서버) 재사용 vs 별도 서버 vs 기존 Django(probe-info) 확장 | 미결 — **0단계는 이 결정 없이 진행 가능** |
| **설비/작업자 목록** | 드롭다운 소스 | 0단계는 앱 설정의 고정 리스트, 1단계에서 중앙 `stations` 동기화로 승격 — 자유 입력 금지 |
| **보안** | LAN 전용이라도 임의 POST 차단 필요 | API 토큰 필수 |
| **이미지** | `image_path`는 로컬 경로 → DB-행 동기화로 안 넘어감 | 팁 카운트엔 불필요 → 로컬 유지(필요 시 기존 probe-info 업로드 활용) |
| **PC 공유** | 한 PC를 여러 작업자가 쓰는 경우 | 현재 결정은 PC 고정 — 필요 시 후속에서 '작업자 전환' 검토 |

---

## 10. 기존 코드와의 관계 (재사용)

- **HTTP 패턴**: `src/core/server_uploader.py`(requests 세션·POST) → 중앙 API 전송에 응용.
- **DB/마이그레이션**: `src/core/database.py`의 `init_db`/`_migrate` 증분 패턴으로 v4 추가.
- **설정 저장**: `app_settings` 테이블(기존)에 `station_id` 보관.
- **서버 PC**: `src/updater/config.py`의 `10.4.1.141` 서버가 중앙 API 호스팅 후보.
- **팁 정의**: `slots.qr_id` 존재 = 팁 1개 → 집계 기준 확정.

---

## 11. 다음 액션

1. **0단계(클라 스캐폴딩)** 구현 — §12 작업 분해. 서버 위치 미확정 상태에서도 진행 가능.
2. 배포된 2.3.0 현장 피드백을 0단계 릴리스(2.4.0)에 함께 반영.
3. §9.2 미결(특히 **중앙 서버 위치**) 확정 → 서버 구축(1단계) → 대시보드(2단계).

---

## 12. 0단계 구현 작업 분해 (2.4.0)

**범위**: 스키마 v4 + station 지정 + 레코드 태깅 + tombstone 기록 + pending 축적.
**범위 밖**: 실제 HTTP 전송 워커(1단계). 0단계 빌드는 **네트워크를 한 번도 건드리지 않는다.**

| ID | 작업 | 대상 파일 | 선행 |
|---|---|---|---|
| **T1** | 스키마 v4 — `SCHEMA_VERSION=4`, `init_db` CREATE 갱신, `_migrate` v4 분기(컬럼 4종 + 인덱스 + `sync_tombstones`), 기존 행 uuid 백필 | `src/core/database.py` | — |
| **T2** | station 최초 1회 지정 — `app_settings` 저장, 취소 불가 모달 다이얼로그(고정 드롭다운), `main.py`의 updater 직후·`MainWindow` 생성 직전 게이트 | `src/ui/`, `main.py:29-33` | T1 |
| **T3** | 레코드 태깅 — `save_measurement_set` 3분기에 uuid 불변식 적용(§6.1), `station_id` 태깅, 저장 시 `sync_status='pending'` 리셋 | `src/core/database.py:153` | T1,T2 |
| **T4** | 삭제 tombstone — `delete_measurement_set`에서 `synced` set에 한해 tombstone 기록 | `src/core/database.py:346` | T1 |
| **T5** | 회귀 테스트 | `tests/test_database.py` | T1–T4 |
| **T6** | 동기화 설정 스텁 — `MCQR_SYNC_SERVER` 기본 `""`. **빈 값이면 워커를 생성조차 하지 않는다**(URL 파싱·소켓 열기 전에 차단) | 신규 `src/core/sync_config.py` | — |

### T5 테스트 항목 (필수)

1. **마이그레이션 멱등성** — v3 DB에 `init_db`를 2회 실행해도 오류·중복 컬럼 없음.
2. **이중 경로 동일성** — 신규 생성 DB와 v3→v4 마이그레이션 DB의 `PRAGMA table_info(measurement_sets)` +
   `PRAGMA index_list`가 **완전히 일치**. (§6.1 ⚠️ 회귀 방지 — 이게 이번 변경의 최대 함정)
3. **uuid 보존** — 같은 `source_folder`로 `save_measurement_set`을 2회 호출 시 `set_uuid`가 동일하고
   `sync_status`가 다시 `pending`이 됨. `db_id` 기준 UPDATE도 동일.
4. **uuid 유일성** — 서로 다른 set 100건 저장 시 `set_uuid` 중복 없음.
5. **백필** — 마이그레이션 후 `set_uuid IS NULL` 인 행이 0건.
6. **tombstone** — `synced` set 삭제 시 tombstone 1건 생성, `pending` set 삭제 시 미생성.
7. **집계 정합** — 같은 데이터에 대해 `complete_count` 산식이 `get_production_stats.complete_slots`와 일치.

> 테스트는 `%LOCALAPPDATA%`를 임시 경로로 리다이렉트한 뒤 실행할 것 — 실제 `chip_carrier.db`를 덮어쓴다.

### 검수 게이트 (구현 세션 → 검토 세션)

0단계 완료 선언 전에 아래가 모두 충족되어야 한다:

- [ ] T5 전 항목 통과 + 기존 `tests/` 전체 그린 (회귀 없음)
- [ ] `git grep -n "MCQR_SYNC_SERVER"` 결과에 실제 `requests`/소켓 호출이 **없음** (0단계 = 네트워크 무접촉)
- [ ] v3 실 DB 사본으로 마이그레이션 후 앱 기동 → 대시보드·이력 화면 숫자가 마이그레이션 전과 동일
- [ ] station 미지정 상태로 기동 시 메인 윈도우 진입 불가 확인
- [ ] TODO/`skip`/미구현 분기 없음
