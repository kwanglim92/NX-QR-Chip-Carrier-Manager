# Export Schema

이 문서는 두 가지 Export 구조를 구분합니다.

- **CSV / CSV+Images Export**: 현장 반출·업로드용 자료 구조
- **Bundle Export / Import**: PC 간 이력 이전·백업용 ZIP 구조

---

## 1. CSV Export

### CSV 컬럼

CSV 헤더는 다음 순서로 고정합니다.

| 순서 | 컬럼명 | 값 규칙 |
|------|--------|---------|
| 1 | `QR ID` | QR 없으면 빈 칸 |
| 2 | `생산일자[YYYYMMDD]` | MeasurementSet 생산일자 |
| 3 | `Frequency (KHz)` | 값 없으면 빈 칸 |
| 4 | `Drive (%)` | `SlotData.drive` 값이 있으면 사용, 없으면 빈 칸 |
| 5 | `Q` | 값 없으면 빈 칸 |
| 6 | `Probe Type` | 슬롯 값 우선, 없으면 세트 기본값, 둘 다 없으면 빈 칸 |

### 미완성 데이터 정책

QR 미입력 또는 측정값 누락 슬롯이 있으면 사용자에게 선택지를 표시합니다.

| 정책 | 동작 |
|------|------|
| `qr_only` | QR ID가 있는 슬롯만 CSV 행으로 생성 |
| `all_slots` | 전체 슬롯을 순서대로 CSV 행으로 생성 |
| `cancel` | 저장 또는 업로드 취소 |

`all_slots` 정책에서는 결측 QR/Frequency/Drive/Q 값을 빈 칸으로 기록합니다.

---

## 2. CSV+Images Export

### 폴더명 기본값

생성 폴더명 기본값은 다음 우선순위로 결정합니다.

1. `MeasurementSet.source_folder`의 마지막 폴더명
2. 이미지들의 공통 부모 폴더명
3. `ms.po_number`
4. `export`

Windows 파일명 금지 문자는 `_`로 치환합니다.

### 출력 구조

예: ATX 원본 폴더가 `P2601002_12M_AC160`인 경우

```text
P2601002_12M_AC160/
├── P2601002_12M_AC160_QR.csv
├── ZOOMIN/
│   ├── QR-001.png
│   ├── QR-002.png
│   └── slot_03.png
└── ZOOMOUT/
    ├── QR-001`.png
    └── QR-002`.png
```

### 이미지 파일명 규칙

| 대상 | 규칙 |
|------|------|
| QR ID가 있는 Zoom-In 이미지 | `{QRID}{원본 확장자}` |
| QR ID가 없는 Zoom-In 이미지 | `slot_XX{원본 확장자}` |
| Zoom-Out 이미지 | Zoom-In 파일명 stem 뒤에 backtick(`) suffix 추가 |
| 이름 충돌 | `_1`, `_2` 접미사 자동 부여 |

Zoom-Out 이미지는 Zoom-In 이미지 경로에서 파생합니다. 앱 내부 캡처 구조에서는 `zoomin/` sibling인 `zoomout/` 폴더를 우선 사용하고, 외부 이미지에서는 같은 폴더의 backtick suffix 파일을 찾습니다.

---

## 3. Bundle Export / Import

### 파일 명명 규칙

```text
chip_carrier_export_YYYYMMDD.zip
```

### ZIP 내부 구조

```text
chip_carrier_export_20260421.zip
├── manifest.json
├── data.jsonl
└── images/                 (옵션; images_included=true인 경우)
    ├── QR-001.png          (Zoom-In)
    ├── QR-001`.png         (Zoom-Out sibling, 있으면 포함)
    ├── QR-002.png
    └── ...
```

Bundle 안에서는 별도 `ZOOMIN/ZOOMOUT` 하위 폴더를 만들지 않고 `images/` 아래에 함께 저장합니다. Zoom-Out 파일은 파일명 stem의 backtick suffix로 구분합니다.

### manifest.json

```json
{
  "schema_version": 1,
  "exported_at": "2026-04-21T10:30:00",
  "record_count": 15,
  "slot_count": 180,
  "image_count": 120,
  "images_included": true,
  "date_range": ["20260415", "20260421"],
  "filter": {
    "date_from": "20260415",
    "date_to": "20260421"
  },
  "producer": "MC QR Code Chip Carrier Manager"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema_version` | integer | 현재 v1. Import는 `SUPPORTED_SCHEMA_VERSIONS`에 정의된 범위만 허용 |
| `exported_at` | ISO-8601 string | 번들 생성 시각(로컬) |
| `record_count` | integer | JSONL 내 MeasurementSet 수 |
| `slot_count` | integer | 전체 슬롯 수 |
| `image_count` | integer | manifest 기준 이미지 카운트. 현재 구현은 slot `image_path` 기준 Zoom-In 카운트 |
| `images_included` | boolean | 이미지 포함 여부 |
| `date_range` | `[min, max]` or `null` | 포함된 `production_date` 범위(YYYYMMDD) |
| `filter` | object | 생성 시 적용된 Export 필터 |
| `producer` | string | 생산 애플리케이션 식별자 |

주의: Zoom-Out sibling 은 best-effort 로 함께 ZIP에 포함되지만, 현재 `image_count`는 Zoom-In 기준 카운트입니다.

### data.jsonl

**1 라인 = 1 JSON 객체 = 1 MeasurementSet (+ nested slots).**

```json
{
  "kind": "measurement_set",
  "po_number": "PO-2026-001",
  "quantity": 12,
  "probe_type": "TypeA",
  "production_date": "20260421",
  "iso_week": "2026-W17",
  "source_folder": "C:/atx/results/PO-2026-001",
  "mode": "atx",
  "upload_status": "uploaded",
  "uploaded_at": "2026-04-21T12:00:00",
  "notes": "",
  "created_at": "2026-04-21 10:00:00",
  "updated_at": "2026-04-21 12:00:00",
  "slots": [ ... ]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `kind` | string | 항상 `"measurement_set"` |
| `po_number` | string | 생산 주문 번호 |
| `quantity` | integer | 주문 수량(M) |
| `probe_type` | string | 세트 기본 프로브 유형 |
| `production_date` | string | `YYYYMMDD` |
| `iso_week` | string | `YYYY-Www` 참고값. Import 시 재계산 가능 |
| `source_folder` | string | ATX 원본 폴더 경로 또는 Manual 원본 참조 |
| `mode` | string | `"atx"` 또는 `"manual"` |
| `upload_status` | string | `"pending"`, `"uploaded"`, `"failed"` |
| `uploaded_at` | string 또는 null | ISO-8601 업로드 완료 시각 |
| `notes` | string | 자유 메모 |
| `created_at` / `updated_at` | string | 로컬 시각 문자열 |
| `slots` | array | Slot 객체 배열 |

### Slot 객체

```json
{
  "slot_index": 0,
  "slot_code": "S01",
  "frequency": 150.12,
  "drive": 1.0,
  "q_factor": 1234.5,
  "qr_id": "QR-001",
  "image_path": "images/QR-001.png",
  "source": "summary_csv",
  "probe_type": "TypeA"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `slot_index` | integer | 세트 내 0-기반 인덱스 |
| `slot_code` | string | 라벨. ATX는 `S01`~`S12`, Manual은 현재 화면 순서 기준 |
| `frequency` | number 또는 null | kHz |
| `drive` | number 또는 null | Drive 값. GUI 입력 항목은 아니지만 Export/Upload 구조 보존용 |
| `q_factor` | number 또는 null | Q-factor |
| `qr_id` | string 또는 null | 외장 리더기로 스캔된 QR ID. 중복 감지 키 |
| `image_path` | string 또는 null | Zoom-In 이미지 참조. 번들 내부면 `images/<파일명>` 상대 경로 |
| `source` | string | `"summary_csv"` 또는 `"manual_entry"` |
| `probe_type` | string 또는 null | 슬롯 단위 프로브 유형 |

Zoom-Out 경로는 `image_path`를 별도 필드로 저장하지 않고, Zoom-In 경로에서 결정적으로 파생합니다.

---

## 4. 중복 정책 (Import)

번들을 Import할 때 동일 QR ID 또는 동일 `source_folder`(ATX 전용)로 중복이 감지되면 다음 정책 중 하나를 적용합니다.

| 정책 | 동작 |
|------|------|
| `skip` | 겹치는 QR이 있으면 해당 세트 전체를 건너뜀. 기본값 |
| `overwrite` | 기존 세트를 삭제하고 번들의 세트로 치환. 슬롯도 모두 교체 |
| `merge` | 기존 세트는 유지하고, 번들에 있는 새로운 QR만 슬롯으로 추가 |

---

## 5. 스키마 호환성

| Bundle v | Current Code | 결과 |
|----------|--------------|------|
| v1 | v1 | 호환 |
| v0 또는 v≥2 | v1 | 비호환. Import 다이얼로그에서 사유 표시 후 OK 비활성화 |

향후 스키마가 진화하면 `SUPPORTED_SCHEMA_VERSIONS`에 호환 범위를 추가하고, 필요 시 레코드 변환 어댑터를 `_apply_record` 호출 전에 삽입합니다.

---

## 6. PostgreSQL 이관 친화성

- DB 벤더 특수 함수(`GROUP_CONCAT`, `datetime()`)를 거치지 않는 순수 Python 직렬화
- `UPSERT`은 표준 `INSERT ... ON CONFLICT` 기반
- 날짜는 문자열(`YYYYMMDD` / ISO-8601)로만 저장
- 이미지는 DB BLOB가 아니라 파일 시스템 참조로 유지
