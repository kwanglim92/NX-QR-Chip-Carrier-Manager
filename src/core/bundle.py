"""DB Export/Import 번들 — JSONL + ZIP 포맷 (F-18).

기존 ``export_db``/``import_db``는 SQLite ``.db`` 파일 단순 복사로서
"Quick Backup" 용도로 유지되고, 이 모듈은 **다른 PC 또는 다른 DB 엔진**으로
이식 가능한 가독성 있는 번들 포맷을 제공한다 (PostgreSQL 이관 친화).

번들 구조
---------
::

    chip_carrier_export_YYYYMMDD.zip
    ├── manifest.json    메타데이터 (스키마 버전, 레코드 수 등)
    ├── data.jsonl       1라인 = 1 MeasurementSet (nested slots 포함)
    └── images/          이미지 포함 옵션 시 QR_ID 기반 파일명

중복 정책 (Import 시)
---------------------
QR ID 오버랩을 기준으로 판정:

- ``skip``      : 겹치는 QR이 있으면 세트 전체 건너뛰기
- ``overwrite`` : 기존 세트를 삭제하고 새 세트로 치환
- ``merge``     : 기존 세트에 새 QR만 추가 (기존 QR 유지)
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.database import (
    _compute_iso_week,
    save_measurement_set,
    delete_measurement_set,
)
from src.core.models import MeasurementSet, SlotData

BUNDLE_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1,)  # Import 허용 범위

MANIFEST_NAME = "manifest.json"
DATA_NAME = "data.jsonl"
IMAGES_DIR = "images"


# ─── 공통 타입 ───


@dataclass
class BundlePreview:
    """Import 전 미리보기."""
    schema_version: int
    record_count: int
    exported_at: str
    date_range: tuple[str, str] | None  # (min, max) production_date
    images_included: bool
    compatible: bool
    incompatible_reason: str | None = None


@dataclass
class ImportResult:
    """Import 결과 요약."""
    imported: int = 0     # 신규 세트
    skipped: int = 0      # 중복 정책 skip
    overwritten: int = 0  # overwrite
    merged: int = 0       # merge 발생
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# ─── Export ───


def export_bundle(
    conn: sqlite3.Connection,
    dest_zip: str | Path,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    include_images: bool = True,
) -> dict[str, Any]:
    """측정 세트 + 슬롯(+옵션 이미지) 번들 생성.

    Parameters
    ----------
    conn
        DB 연결.
    dest_zip
        생성할 ZIP 경로. 확장자 ``.zip`` 자동 보정.
    date_from / date_to
        "YYYYMMDD" 범위 필터. None이면 양쪽 모두 해당 방향 무제한.
        둘 다 None이면 전체 Export.
    include_images
        True면 슬롯의 ``image_path``가 가리키는 실제 파일도 ``images/`` 하위로
        복사. 원본 파일이 없으면 건너뜀 (에러 아님).

    Returns
    -------
    dict
        {"record_count", "slot_count", "image_count", "zip_path"}.
    """
    dest = Path(dest_zip)
    if dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(".zip")

    # 1) 대상 세트 조회 (기간 필터)
    conditions: list[str] = []
    params: list = []
    if date_from:
        conditions.append("ms.production_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("ms.production_date <= ?")
        params.append(date_to)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(f"""
        SELECT * FROM measurement_sets ms {where}
        ORDER BY ms.production_date ASC, ms.id ASC
    """, params).fetchall()

    ms_ids = [r["id"] for r in rows]

    # 2) 각 세트의 슬롯을 dict로 그룹핑
    slots_by_ms: dict[int, list[dict]] = {mid: [] for mid in ms_ids}
    if ms_ids:
        placeholders = ",".join(["?"] * len(ms_ids))
        slot_rows = conn.execute(
            f"SELECT * FROM slots WHERE measurement_set_id IN ({placeholders}) "
            f"ORDER BY measurement_set_id, slot_index",
            ms_ids,
        ).fetchall()
        for sr in slot_rows:
            slots_by_ms[sr["measurement_set_id"]].append({
                "slot_index": sr["slot_index"],
                "slot_code": sr["slot_code"],
                "frequency": sr["frequency"],
                "drive": sr["drive"],
                "q_factor": sr["q_factor"],
                "qr_id": sr["qr_id"],
                "image_path": sr["image_path"],
                "source": sr["source"],
                "probe_type": sr["probe_type"],
            })

    # 3) 임시 디렉토리에 번들 조립 후 ZIP 압축
    image_count = 0
    slot_count = 0
    min_date: str | None = None
    max_date: str | None = None

    with tempfile.TemporaryDirectory(prefix="chip_bundle_") as tmp:
        tmp_path = Path(tmp)
        images_dir = tmp_path / IMAGES_DIR
        if include_images:
            images_dir.mkdir(exist_ok=True)

        # data.jsonl 기록
        with (tmp_path / DATA_NAME).open("w", encoding="utf-8") as jf:
            for r in rows:
                ms_id = r["id"]
                pd = r["production_date"] or ""
                if pd:
                    min_date = pd if min_date is None else min(min_date, pd)
                    max_date = pd if max_date is None else max(max_date, pd)

                slot_dicts = slots_by_ms[ms_id]

                # 이미지 포함 옵션: 슬롯의 image_path 원본을 images/로 복사하고
                # 번들 내부 상대 경로로 치환. QR ID가 있으면 QR 기반, 없으면
                # ms_id+slot_index 기반의 고유 파일명을 사용 (충돌 방지).
                if include_images:
                    for s in slot_dicts:
                        src = s.get("image_path")
                        if not src:
                            continue
                        src_p = Path(src)
                        if not src_p.exists() or not src_p.is_file():
                            # 원본 이미지 소실: 경로 참조는 남기되 파일 복사는 생략
                            continue
                        ext = src_p.suffix or ".png"
                        qr = s.get("qr_id")
                        base = qr if qr else f"ms{ms_id}_s{s['slot_index']}"
                        # 동일 QR 충돌 방지 (_1, _2)
                        dest_name = f"{base}{ext}"
                        i = 1
                        while (images_dir / dest_name).exists():
                            dest_name = f"{base}_{i}{ext}"
                            i += 1
                        shutil.copy2(str(src_p), str(images_dir / dest_name))
                        s["image_path"] = f"{IMAGES_DIR}/{dest_name}"
                        image_count += 1
                else:
                    # 이미지 미포함: image_path는 원본 경로 그대로 (재매칭용 참조)
                    pass

                record = {
                    "kind": "measurement_set",
                    "po_number": r["po_number"],
                    "quantity": r["quantity"],
                    "probe_type": r["probe_type"],
                    "production_date": r["production_date"],
                    "iso_week": r["iso_week"],
                    "source_folder": r["source_folder"],
                    "mode": r["mode"],
                    "upload_status": r["upload_status"],
                    "uploaded_at": r["uploaded_at"],
                    "notes": r["notes"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "slots": slot_dicts,
                }
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                slot_count += len(slot_dicts)

        # manifest.json
        manifest = {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "record_count": len(rows),
            "slot_count": slot_count,
            "image_count": image_count,
            "images_included": include_images,
            "date_range": [min_date, max_date] if min_date and max_date else None,
            "filter": {
                "date_from": date_from,
                "date_to": date_to,
            },
            "producer": "NX QR Chip Carrier Manager",
        }
        (tmp_path / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # ZIP으로 압축
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_path / MANIFEST_NAME, MANIFEST_NAME)
            zf.write(tmp_path / DATA_NAME, DATA_NAME)
            if include_images:
                for img in sorted(images_dir.iterdir()):
                    zf.write(img, f"{IMAGES_DIR}/{img.name}")

    return {
        "record_count": len(rows),
        "slot_count": slot_count,
        "image_count": image_count,
        "zip_path": str(dest),
    }


# ─── Import: Preview ───


def preview_bundle(zip_path: str | Path) -> BundlePreview:
    """번들 파일을 열지 않고 manifest만 읽어 미리보기 정보 반환."""
    try:
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            if MANIFEST_NAME not in zf.namelist():
                return BundlePreview(
                    schema_version=-1,
                    record_count=0,
                    exported_at="",
                    date_range=None,
                    images_included=False,
                    compatible=False,
                    incompatible_reason="manifest.json 없음",
                )
            with zf.open(MANIFEST_NAME) as mf:
                manifest = json.loads(mf.read().decode("utf-8"))
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError) as e:
        return BundlePreview(
            schema_version=-1, record_count=0, exported_at="",
            date_range=None, images_included=False,
            compatible=False, incompatible_reason=f"번들 파싱 실패: {e}",
        )

    sv = int(manifest.get("schema_version", -1))
    compatible = sv in SUPPORTED_SCHEMA_VERSIONS
    reason = None
    if not compatible:
        reason = (
            f"schema_version={sv}은 지원되지 않음 "
            f"(허용: {SUPPORTED_SCHEMA_VERSIONS})"
        )

    dr = manifest.get("date_range") or None
    date_range = (dr[0], dr[1]) if dr and len(dr) == 2 and all(dr) else None

    return BundlePreview(
        schema_version=sv,
        record_count=int(manifest.get("record_count", 0)),
        exported_at=manifest.get("exported_at", ""),
        date_range=date_range,
        images_included=bool(manifest.get("images_included", False)),
        compatible=compatible,
        incompatible_reason=reason,
    )


# ─── Import ───


def import_bundle(
    conn: sqlite3.Connection,
    zip_path: str | Path,
    *,
    on_duplicate: str = "skip",
    images_extract_dir: str | Path | None = None,
) -> ImportResult:
    """번들 파일을 DB로 가져오기.

    Parameters
    ----------
    on_duplicate
        "skip" | "overwrite" | "merge". 기본 "skip".
    images_extract_dir
        이미지가 포함된 번들일 때 이미지를 풀 경로. None이면 추출하지 않음
        (``image_path``는 번들 내부 상대 경로가 그대로 저장됨).
    """
    if on_duplicate not in ("skip", "overwrite", "merge"):
        raise ValueError(f"invalid on_duplicate: {on_duplicate!r}")

    result = ImportResult()

    # 호환성 선검증
    preview = preview_bundle(zip_path)
    if not preview.compatible:
        result.errors.append(preview.incompatible_reason or "incompatible bundle")
        return result

    extract_base: Path | None = None
    if images_extract_dir:
        extract_base = Path(images_extract_dir)
        extract_base.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            names = zf.namelist()

            # 이미지 추출 (요청 시)
            if extract_base is not None and preview.images_included:
                for name in names:
                    if name.startswith(f"{IMAGES_DIR}/") and not name.endswith("/"):
                        rel = name[len(IMAGES_DIR) + 1:]
                        out = extract_base / rel
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, out.open("wb") as dst:
                            shutil.copyfileobj(src, dst)

            # data.jsonl 처리
            if DATA_NAME not in names:
                result.errors.append(f"{DATA_NAME} 없음")
                return result

            with zf.open(DATA_NAME) as df:
                for raw in df:
                    line = raw.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        result.errors.append(f"data.jsonl 파싱 오류: {e}")
                        continue

                    if record.get("kind") != "measurement_set":
                        continue

                    _apply_record(
                        conn, record, on_duplicate=on_duplicate,
                        images_base=extract_base, result=result,
                    )
    except (zipfile.BadZipFile, OSError) as e:
        result.errors.append(f"번들 읽기 실패: {e}")
        return result

    conn.commit()
    return result


def _apply_record(
    conn: sqlite3.Connection,
    record: dict,
    *,
    on_duplicate: str,
    images_base: Path | None,
    result: ImportResult,
) -> None:
    """단일 measurement_set 레코드를 DB에 적용 (중복 정책 포함)."""
    slots_in = record.get("slots") or []
    qr_ids_in = {s.get("qr_id") for s in slots_in if s.get("qr_id")}

    # 중복 세트 식별: QR ID 오버랩을 기준
    existing_ms_id: int | None = None
    if qr_ids_in:
        placeholders = ",".join(["?"] * len(qr_ids_in))
        row = conn.execute(
            f"SELECT DISTINCT measurement_set_id FROM slots "
            f"WHERE qr_id IN ({placeholders}) LIMIT 1",
            list(qr_ids_in),
        ).fetchone()
        if row:
            existing_ms_id = row["measurement_set_id"]

    # ATX 모드 source_folder 기반 보조 매칭 (QR 없는 세트용)
    if existing_ms_id is None and record.get("mode") == "atx":
        sf = record.get("source_folder") or ""
        if sf:
            row = conn.execute(
                "SELECT id FROM measurement_sets WHERE source_folder=? AND mode='atx'",
                (sf,),
            ).fetchone()
            if row:
                existing_ms_id = row["id"]

    # ── 정책 분기 ──
    if existing_ms_id is not None:
        if on_duplicate == "skip":
            result.skipped += 1
            return
        if on_duplicate == "overwrite":
            delete_measurement_set(conn, existing_ms_id)
            existing_ms_id = None  # 아래 신규 삽입 경로
            result.overwritten += 1
        elif on_duplicate == "merge":
            _merge_into_existing(conn, existing_ms_id, slots_in, images_base)
            result.merged += 1
            return

    # ── 신규 세트 생성 ──
    ms = _record_to_measurement_set(record, images_base)
    save_measurement_set(conn, ms)
    if existing_ms_id is None and on_duplicate != "overwrite":
        result.imported += 1


def _merge_into_existing(
    conn: sqlite3.Connection,
    ms_id: int,
    incoming_slots: list[dict],
    images_base: Path | None,
) -> None:
    """기존 세트에 신규 슬롯만 추가 (QR ID 오버랩은 건너뛰기)."""
    existing_qrs_rows = conn.execute(
        "SELECT qr_id FROM slots WHERE measurement_set_id=? AND qr_id IS NOT NULL",
        (ms_id,),
    ).fetchall()
    existing_qrs = {r["qr_id"] for r in existing_qrs_rows}

    # 기존 slot_index max 확인 → 신규 슬롯은 그 뒤로 추가
    row = conn.execute(
        "SELECT COALESCE(MAX(slot_index), -1) AS mx FROM slots WHERE measurement_set_id=?",
        (ms_id,),
    ).fetchone()
    next_idx = int(row["mx"]) + 1

    for s in incoming_slots:
        qr = s.get("qr_id")
        if qr and qr in existing_qrs:
            continue  # 이미 있는 QR은 보존

        img = s.get("image_path") or None
        if img and images_base and not Path(img).is_absolute():
            img = str(images_base / Path(img).name)

        conn.execute("""
            INSERT INTO slots
                (measurement_set_id, slot_index, slot_code, frequency, drive,
                 q_factor, qr_id, image_path, source, probe_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ms_id, next_idx, str(s.get("slot_code") or next_idx + 1),
            s.get("frequency"), s.get("drive"), s.get("q_factor"),
            qr, img, s.get("source") or "summary_csv", s.get("probe_type"),
        ))
        next_idx += 1

    # updated_at 갱신
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE measurement_sets SET updated_at=? WHERE id=?",
        (now, ms_id),
    )


def _record_to_measurement_set(
    record: dict, images_base: Path | None
) -> MeasurementSet:
    """JSONL 레코드 → ``MeasurementSet`` 객체 변환."""
    ms = MeasurementSet(
        po_number=record.get("po_number") or "",
        quantity=int(record.get("quantity") or 0),
        probe_type=record.get("probe_type") or "",
        production_date=record.get("production_date") or "",
        source_folder=record.get("source_folder") or "",
        mode=record.get("mode") or "atx",
    )
    # iso_week는 save_measurement_set에서 재계산되므로 무시

    for s in record.get("slots") or []:
        img = s.get("image_path") or None
        if img and images_base and not Path(img).is_absolute():
            # 번들 내부 상대 경로 → 추출된 절대 경로로 교체
            img = str(images_base / Path(img).name)

        ms.slots.append(SlotData(
            slot_index=int(s.get("slot_index") or 0),
            slot_code=str(s.get("slot_code") or ""),
            frequency=s.get("frequency"),
            drive=s.get("drive"),
            q_factor=s.get("q_factor"),
            qr_id=s.get("qr_id"),
            image_path=img,
            source=s.get("source") or "summary_csv",
            probe_type=s.get("probe_type"),
        ))
    return ms


def default_export_filename(now: datetime | None = None) -> str:
    """사용자에게 제안할 기본 파일명."""
    now = now or datetime.now()
    return f"chip_carrier_export_{now.strftime('%Y%m%d')}.zip"
