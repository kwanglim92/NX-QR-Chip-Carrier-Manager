# Export Bundle Schema (F-18)

## 파일 명명 규칙

`chip_carrier_export_YYYYMMDD.zip`

## ZIP 내부 구조

```
chip_carrier_export_20260421.zip
├── manifest.json
├── data.jsonl
└── images/          (옵션; images_included=true인 경우)
    ├── QR-001.png
    ├── QR-002.png
    └── ...
```

## manifest.json

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
  "producer": "NX QR Chip Carrier Manager"
}
```

필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema_version` | integer | 현재 v1. Import는 `SUPPORTED_SCHEMA_VERSIONS`에 정의된 범위만 허용. |
| `exported_at` | ISO-8601 string | 번들 생성 시각(로컬). |
| `record_count` | integer | JSONL 내 MeasurementSet 수. |
| `slot_count` | integer | 전체 슬롯 수. |
| `image_count` | integer | `images/` 내 실제 파일 수. |
| `images_included` | boolean | 이미지 포함 여부. |
| `date_range` | `[min, max]` or `null` | 포함된 `production_date` 범위(YYYYMMDD). |
| `filter` | object | 생성 시 적용된 Export 필터. |
| `producer` | string | 생산 애플리케이션 식별자. |

## data.jsonl

**1 라인 = 1 JSON 객체 = 1 MeasurementSet (+ nested slots).**

JSON Lines 포맷이므로 라인 단위 스트리밍 파싱이 가능합니다.

### MeasurementSet 레코드

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
| `kind` | string | 항상 `"measurement_set"` (미래 확장 대비). |
| `po_number` | string | 생산 주문 번호. |
| `quantity` | integer | 주문 수량(M). |
| `probe_type` | string | 프로브 유형. |
| `production_date` | string | "YYYYMMDD". |
| `iso_week` | string | "YYYY-Www" (참고용; Import 시 재계산됨). |
| `source_folder` | string | ATX 원본 폴더 경로(ATX 중복 감지용). |
| `mode` | string | `"atx"` \| `"manual"`. |
| `upload_status` | string | `"pending"` \| `"uploaded"` \| `"failed"`. |
| `uploaded_at` | string \| null | ISO-8601 업로드 완료 시각. |
| `notes` | string | 자유 메모. |
| `created_at` / `updated_at` | string | "YYYY-MM-DD HH:MM:SS" 로컬 시각. |
| `slots` | array | Slot 객체 배열(아래 참조). |

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
| `slot_index` | integer | 세트 내 0-기반 인덱스. |
| `slot_code` | string | 라벨(ATX는 `"S01"~"S12"`, Manual은 자유). |
| `frequency` | number \| null | kHz. |
| `drive` | number \| null | 드라이브 값. |
| `q_factor` | number \| null | Q-factor. |
| `qr_id` | string \| null | 외장 리더기로 스캔된 QR ID. **중복 감지 키.** |
| `image_path` | string \| null | 이미지 참조. 번들 내부면 `"images/<파일명>"` 상대 경로. |
| `source` | string | `"summary_csv"` (ATX) \| `"manual_entry"`. |
| `probe_type` | string \| null | 슬롯 단위 프로브 유형(Manual 탭별). |

## 중복 정책 (Import)

번들을 Import할 때 동일 QR ID 또는 동일 `source_folder`(ATX 전용)로 중복이 감지되면
다음 세 정책 중 하나를 적용합니다.

| 정책 | 동작 |
|------|------|
| `skip` | 겹치는 QR이 있으면 해당 세트 전체를 건너뜁니다. **기본값.** |
| `overwrite` | 기존 세트를 삭제하고 번들의 세트로 치환합니다. 슬롯도 모두 교체됩니다. |
| `merge` | 기존 세트는 유지하고, 번들에 있는 **새로운 QR만** 슬롯으로 추가합니다. |

## 스키마 호환성 매트릭스

| Bundle v | Current Code | 결과 |
|----------|--------------|------|
| v1 | v1 | ✅ 완전 호환 |
| v0 또는 v≥2 | v1 | ❌ 비호환 — Import 다이얼로그에서 사유 표시 후 OK 비활성화 |

향후 스키마가 진화하면 `SUPPORTED_SCHEMA_VERSIONS`에 호환 범위를 추가하고,
필요 시 레코드 변환 어댑터를 `_apply_record` 호출 전에 삽입합니다.

## 이미지 파일명 규칙

`images/` 하위 파일명:
- QR ID가 있는 슬롯: `{qr_id}{원본 확장자}` (예: `QR-001.png`)
- QR ID가 없는 슬롯: `ms{ms_id}_s{slot_index}{원본 확장자}`
- 동일 이름 충돌 시 `_1`, `_2` 접미사 자동 부여.

## PostgreSQL 이관 친화성

- 모든 DB 벤더 특수 함수(`GROUP_CONCAT`, `datetime()`)를 거치지 않는 순수 Python 직렬화.
- `UPSERT`은 표준 `INSERT ... ON CONFLICT`만 사용 (Phase 0 기반).
- 날짜는 문자열(`"YYYYMMDD"` / ISO-8601)로만 저장 → PG `TEXT` 또는 `DATE`/`TIMESTAMP` 캐스팅 용이.
- `image_path`는 DB에 BLOB 저장하지 않고 파일 시스템 참조만 유지.
