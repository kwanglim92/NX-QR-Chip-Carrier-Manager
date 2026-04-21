"""로컬 SQLite DB — 측정 이력 + 설정 저장."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from src.core.models import MeasurementSet, SlotData

SCHEMA_VERSION = 1
DB_FILENAME = "chip_carrier.db"
APP_DIR_NAME = "NXQRChipCarrierManager"


def get_db_dir() -> Path:
    """DB 디렉토리 경로 반환 (%LOCALAPPDATA%/NXQRChipCarrierManager/)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / ".local" / "share"
    db_dir = base / APP_DIR_NAME
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def get_db_path() -> Path:
    return get_db_dir() / DB_FILENAME


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """SQLite 연결 생성 (WAL mode, foreign keys ON)."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ─── 스키마 초기화 / 마이그레이션 ───


def init_db(conn: sqlite3.Connection):
    """테이블 생성 + 스키마 마이그레이션."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS measurement_sets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number       TEXT NOT NULL DEFAULT '',
            quantity        INTEGER NOT NULL DEFAULT 0,
            probe_type      TEXT NOT NULL DEFAULT '',
            production_date TEXT NOT NULL DEFAULT '',
            iso_week        TEXT NOT NULL DEFAULT '',
            source_folder   TEXT NOT NULL DEFAULT '',
            mode            TEXT NOT NULL DEFAULT 'atx',
            created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            uploaded_at     TEXT,
            upload_status   TEXT NOT NULL DEFAULT 'pending',
            notes           TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_ms_iso_week ON measurement_sets(iso_week);
        CREATE INDEX IF NOT EXISTS idx_ms_po_number ON measurement_sets(po_number);

        CREATE TABLE IF NOT EXISTS slots (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_set_id INTEGER NOT NULL REFERENCES measurement_sets(id) ON DELETE CASCADE,
            slot_index         INTEGER NOT NULL,
            slot_code          TEXT NOT NULL,
            frequency          REAL,
            drive              REAL,
            q_factor           REAL,
            qr_id              TEXT,
            image_path         TEXT,
            source             TEXT NOT NULL DEFAULT 'summary_csv',
            probe_type         TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_slots_ms_id ON slots(measurement_set_id);

        CREATE TABLE IF NOT EXISTS app_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    # 스키마 버전 초기화
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
    else:
        current = int(row["value"])
        if current < SCHEMA_VERSION:
            _migrate(conn, current)


def _migrate(conn: sqlite3.Connection, current_version: int):
    """증분 스키마 마이그레이션."""
    # 향후 버전 업그레이드 시 여기에 추가
    # if current_version < 2:
    #     conn.execute("ALTER TABLE ...")
    conn.execute(
        "UPDATE meta SET value=? WHERE key='schema_version'",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


# ─── 주차 계산 ───


def _compute_iso_week(production_date: str) -> str:
    """YYYYMMDD → '2026-W15' 형식."""
    if not production_date or len(production_date) != 8:
        return ""
    try:
        dt = datetime.strptime(production_date, "%Y%m%d")
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except ValueError:
        return ""


# ─── MeasurementSet CRUD ───


def save_measurement_set(conn: sqlite3.Connection, ms: MeasurementSet) -> int:
    """MeasurementSet 저장 (INSERT or UPDATE). 반환: DB row id."""
    iso_week = _compute_iso_week(ms.production_date)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if ms.db_id is not None:
        # UPDATE
        conn.execute("""
            UPDATE measurement_sets SET
                po_number=?, quantity=?, probe_type=?, production_date=?,
                iso_week=?, source_folder=?, mode=?, updated_at=?
            WHERE id=?
        """, (
            ms.po_number, ms.quantity, ms.probe_type, ms.production_date,
            iso_week, ms.source_folder, ms.mode, now, ms.db_id,
        ))
        ms_id = ms.db_id

        # 기존 슬롯 삭제 후 재삽입
        conn.execute("DELETE FROM slots WHERE measurement_set_id=?", (ms_id,))
    else:
        # ATX 모드: source_folder로 중복 감지
        existing_id = None
        if ms.mode == "atx" and ms.source_folder:
            row = conn.execute(
                "SELECT id FROM measurement_sets WHERE source_folder=? AND mode='atx'",
                (ms.source_folder,),
            ).fetchone()
            if row:
                existing_id = row["id"]

        if existing_id:
            # 덮어쓰기
            conn.execute("""
                UPDATE measurement_sets SET
                    po_number=?, quantity=?, probe_type=?, production_date=?,
                    iso_week=?, mode=?, updated_at=?
                WHERE id=?
            """, (
                ms.po_number, ms.quantity, ms.probe_type, ms.production_date,
                iso_week, ms.mode, now, existing_id,
            ))
            conn.execute("DELETE FROM slots WHERE measurement_set_id=?", (existing_id,))
            ms_id = existing_id
        else:
            # INSERT
            cursor = conn.execute("""
                INSERT INTO measurement_sets
                    (po_number, quantity, probe_type, production_date,
                     iso_week, source_folder, mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ms.po_number, ms.quantity, ms.probe_type, ms.production_date,
                iso_week, ms.source_folder, ms.mode, now, now,
            ))
            ms_id = cursor.lastrowid

    # 슬롯 삽입
    for slot in ms.slots:
        conn.execute("""
            INSERT INTO slots
                (measurement_set_id, slot_index, slot_code, frequency, drive,
                 q_factor, qr_id, image_path, source, probe_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ms_id, slot.slot_index, slot.slot_code, slot.frequency, slot.drive,
            slot.q_factor, slot.qr_id, slot.image_path, slot.source, slot.probe_type,
        ))

    conn.commit()
    ms.db_id = ms_id
    return ms_id


def load_measurement_set(conn: sqlite3.Connection, ms_id: int) -> MeasurementSet | None:
    """DB에서 MeasurementSet 로드."""
    row = conn.execute("SELECT * FROM measurement_sets WHERE id=?", (ms_id,)).fetchone()
    if not row:
        return None

    ms = MeasurementSet(
        po_number=row["po_number"],
        quantity=row["quantity"],
        probe_type=row["probe_type"],
        production_date=row["production_date"],
        source_folder=row["source_folder"],
        mode=row["mode"],
        db_id=row["id"],
    )

    slot_rows = conn.execute(
        "SELECT * FROM slots WHERE measurement_set_id=? ORDER BY slot_index",
        (ms_id,),
    ).fetchall()

    for sr in slot_rows:
        slot = SlotData(
            slot_index=sr["slot_index"],
            slot_code=sr["slot_code"],
            frequency=sr["frequency"],
            drive=sr["drive"],
            q_factor=sr["q_factor"],
            qr_id=sr["qr_id"],
            image_path=sr["image_path"],
            source=sr["source"],
            probe_type=sr["probe_type"],
        )
        ms.slots.append(slot)

    return ms


def list_measurement_sets(
    conn: sqlite3.Connection,
    week: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """측정 세트 요약 목록 조회."""
    query = """
        SELECT ms.*,
               COUNT(s.id) AS total_slots,
               SUM(CASE WHEN s.qr_id IS NOT NULL AND s.frequency IS NOT NULL
                         AND s.q_factor IS NOT NULL
                    THEN 1 ELSE 0 END) AS complete_slots
        FROM measurement_sets ms
        LEFT JOIN slots s ON s.measurement_set_id = ms.id
    """
    conditions = []
    params = []

    if week and week != "All":
        conditions.append("ms.iso_week = ?")
        params.append(week)

    if search:
        conditions.append(
            "(ms.po_number LIKE ? OR ms.probe_type LIKE ?)"
        )
        params.extend([f"%{search}%", f"%{search}%"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY ms.id ORDER BY ms.production_date DESC, ms.updated_at DESC"

    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "po_number": r["po_number"],
            "probe_type": r["probe_type"],
            "production_date": r["production_date"],
            "iso_week": r["iso_week"],
            "mode": r["mode"],
            "total_slots": r["total_slots"],
            "complete_slots": r["complete_slots"],
            "upload_status": r["upload_status"],
            "updated_at": r["updated_at"],
        })
    return results


def delete_measurement_set(conn: sqlite3.Connection, ms_id: int):
    """측정 세트 삭제 (CASCADE로 슬롯도 삭제)."""
    conn.execute("DELETE FROM measurement_sets WHERE id=?", (ms_id,))
    conn.commit()


def list_weeks(conn: sqlite3.Connection) -> list[str]:
    """고유 iso_week 목록 (최신 순)."""
    rows = conn.execute(
        "SELECT DISTINCT iso_week FROM measurement_sets "
        "WHERE iso_week != '' ORDER BY iso_week DESC"
    ).fetchall()
    return [r["iso_week"] for r in rows]


# ─── 생산 통계 ───


def get_production_stats(
    conn: sqlite3.Connection,
    period: str = "weekly",
) -> list[dict]:
    """Probe Type별 생산 통계.

    period: "weekly" | "monthly" | "quarterly" | "yearly"
    반환: [{period_label, probe_type, set_count, slot_count, complete_slots}]
    """
    period_exprs = {
        "weekly": "ms.iso_week",
        "monthly": "SUBSTR(ms.production_date, 1, 6)",
        "quarterly": (
            "SUBSTR(ms.production_date, 1, 4) || '-Q' || "
            "CASE "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 3 THEN '1' "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 6 THEN '2' "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 9 THEN '3' "
            "  ELSE '4' "
            "END"
        ),
        "yearly": "SUBSTR(ms.production_date, 1, 4)",
    }
    period_expr = period_exprs.get(period, period_exprs["weekly"])

    query = f"""
        SELECT
            {period_expr} AS period_label,
            ms.probe_type,
            COUNT(DISTINCT ms.id) AS set_count,
            COUNT(s.id) AS slot_count,
            SUM(CASE WHEN s.qr_id IS NOT NULL AND s.frequency IS NOT NULL
                      AND s.q_factor IS NOT NULL
                 THEN 1 ELSE 0 END) AS complete_slots
        FROM measurement_sets ms
        LEFT JOIN slots s ON s.measurement_set_id = ms.id
        WHERE ms.production_date != ''
        GROUP BY period_label, ms.probe_type
        ORDER BY period_label DESC, ms.probe_type
    """
    rows = conn.execute(query).fetchall()
    return [
        {
            "period_label": r["period_label"],
            "probe_type": r["probe_type"],
            "set_count": r["set_count"],
            "slot_count": r["slot_count"],
            "complete_slots": r["complete_slots"] or 0,
        }
        for r in rows
    ]


def get_overall_stats(conn: sqlite3.Connection) -> dict:
    """전체 요약 통계."""
    row = conn.execute("""
        SELECT
            COUNT(DISTINCT ms.id) AS total_sets,
            COUNT(s.id) AS total_slots,
            SUM(CASE WHEN s.qr_id IS NOT NULL AND s.frequency IS NOT NULL
                      AND s.q_factor IS NOT NULL
                 THEN 1 ELSE 0 END) AS complete_slots
        FROM measurement_sets ms
        LEFT JOIN slots s ON s.measurement_set_id = ms.id
    """).fetchone()
    total_slots = row["total_slots"] or 0
    complete = row["complete_slots"] or 0
    return {
        "total_sets": row["total_sets"] or 0,
        "total_slots": total_slots,
        "complete_slots": complete,
        "completion_rate": round(complete / total_slots * 100, 1) if total_slots > 0 else 0,
    }


def get_period_totals(
    conn: sqlite3.Connection,
    period: str = "weekly",
) -> list[dict]:
    """기간별 전체 합산 (Probe Type 무관). 추세선/Peak/Trend용."""
    period_exprs = {
        "weekly": "ms.iso_week",
        "monthly": "SUBSTR(ms.production_date, 1, 6)",
        "quarterly": (
            "SUBSTR(ms.production_date, 1, 4) || '-Q' || "
            "CASE "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 3 THEN '1' "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 6 THEN '2' "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 9 THEN '3' "
            "  ELSE '4' "
            "END"
        ),
        "yearly": "SUBSTR(ms.production_date, 1, 4)",
    }
    period_expr = period_exprs.get(period, period_exprs["weekly"])

    query = f"""
        SELECT
            {period_expr} AS period_label,
            COUNT(s.id) AS total_slots,
            SUM(CASE WHEN s.qr_id IS NOT NULL AND s.frequency IS NOT NULL
                      AND s.q_factor IS NOT NULL
                 THEN 1 ELSE 0 END) AS complete_slots
        FROM measurement_sets ms
        LEFT JOIN slots s ON s.measurement_set_id = ms.id
        WHERE ms.production_date != ''
        GROUP BY period_label
        ORDER BY period_label ASC
    """
    rows = conn.execute(query).fetchall()
    return [
        {
            "period_label": r["period_label"],
            "total_slots": r["total_slots"] or 0,
            "complete_slots": r["complete_slots"] or 0,
        }
        for r in rows
    ]


def get_probe_type_list(conn: sqlite3.Connection) -> list[str]:
    """등록된 Probe Type 목록."""
    rows = conn.execute(
        "SELECT DISTINCT probe_type FROM measurement_sets "
        "WHERE probe_type != '' ORDER BY probe_type"
    ).fetchall()
    return [r["probe_type"] for r in rows]


def get_slot_values(
    conn: sqlite3.Connection,
    probe_type: str | None = None,
) -> list[dict]:
    """완료 슬롯의 frequency, q_factor 원시값 목록. Histogram + 통계 계산용."""
    query = """
        SELECT s.frequency, s.q_factor, ms.probe_type
        FROM slots s
        JOIN measurement_sets ms ON ms.id = s.measurement_set_id
        WHERE s.frequency IS NOT NULL AND s.q_factor IS NOT NULL
    """
    params: list = []
    if probe_type:
        query += " AND ms.probe_type = ?"
        params.append(probe_type)

    rows = conn.execute(query, params).fetchall()
    return [
        {"frequency": r["frequency"], "q_factor": r["q_factor"],
         "probe_type": r["probe_type"]}
        for r in rows
    ]


def get_period_quality_stats(
    conn: sqlite3.Connection,
    period: str = "weekly",
    probe_type: str | None = None,
) -> list[dict]:
    """기간별 Frequency/Q Factor 평균 및 표준편차. SPC 차트용.

    SQLite에 STDEV가 없으므로 GROUP_CONCAT로 수집 후 Python에서 계산.
    반환: [{period_label, freq_mean, freq_std, q_mean, q_std, sample_count}]
    """
    import statistics as _st

    period_exprs = {
        "weekly": "ms.iso_week",
        "monthly": "SUBSTR(ms.production_date, 1, 6)",
        "quarterly": (
            "SUBSTR(ms.production_date, 1, 4) || '-Q' || "
            "CASE "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 3 THEN '1' "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 6 THEN '2' "
            "  WHEN CAST(SUBSTR(ms.production_date, 5, 2) AS INTEGER) <= 9 THEN '3' "
            "  ELSE '4' "
            "END"
        ),
        "yearly": "SUBSTR(ms.production_date, 1, 4)",
    }
    period_expr = period_exprs.get(period, period_exprs["weekly"])

    query = f"""
        SELECT
            {period_expr} AS period_label,
            COUNT(s.id) AS sample_count,
            GROUP_CONCAT(s.frequency) AS freq_values,
            GROUP_CONCAT(s.q_factor) AS q_values
        FROM measurement_sets ms
        JOIN slots s ON s.measurement_set_id = ms.id
        WHERE s.frequency IS NOT NULL AND s.q_factor IS NOT NULL
          AND ms.production_date != ''
    """
    params: list = []
    if probe_type:
        query += " AND ms.probe_type = ?"
        params.append(probe_type)

    query += " GROUP BY period_label ORDER BY period_label ASC"

    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        freq_vals = [float(v) for v in r["freq_values"].split(",")]
        q_vals = [float(v) for v in r["q_values"].split(",")]

        freq_mean = _st.mean(freq_vals)
        q_mean = _st.mean(q_vals)
        freq_std = _st.stdev(freq_vals) if len(freq_vals) >= 2 else 0.0
        q_std = _st.stdev(q_vals) if len(q_vals) >= 2 else 0.0

        results.append({
            "period_label": r["period_label"],
            "freq_mean": round(freq_mean, 3),
            "freq_std": round(freq_std, 3),
            "q_mean": round(q_mean, 3),
            "q_std": round(q_std, 3),
            "sample_count": r["sample_count"],
        })
    return results


# ─── 업로드 상태 ───


def update_upload_status(
    conn: sqlite3.Connection, ms_id: int, status: str, timestamp: str | None = None
):
    conn.execute(
        "UPDATE measurement_sets SET upload_status=?, uploaded_at=? WHERE id=?",
        (status, timestamp, ms_id),
    )
    conn.commit()


# ─── 설정 CRUD ───


def save_setting(conn: sqlite3.Connection, key: str, value):
    """설정 저장 (JSON 인코딩)."""
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    conn.commit()


def save_all_settings(conn: sqlite3.Connection, settings: dict):
    """모든 설정 일괄 저장."""
    for key, value in settings.items():
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
    conn.commit()


def load_setting(conn: sqlite3.Connection, key: str, default=None):
    """설정 로드 (JSON 디코딩)."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return default


def load_all_settings(conn: sqlite3.Connection) -> dict:
    """모든 설정 로드."""
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    result = {}
    for r in rows:
        try:
            result[r["key"]] = json.loads(r["value"])
        except (json.JSONDecodeError, TypeError):
            result[r["key"]] = r["value"]
    return result


# ─── 백업 / 복원 ───


def export_db(conn: sqlite3.Connection, dest_path: str):
    """DB 백업 (WAL checkpoint 후 파일 복사)."""
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db_path = get_db_path()
    shutil.copy2(str(db_path), dest_path)


def import_db(source_path: str) -> bool:
    """DB 복원. 유효성 검증 후 교체. 성공 시 True."""
    # 유효성 검증
    try:
        test_conn = sqlite3.connect(source_path)
        test_conn.execute("SELECT value FROM meta WHERE key='schema_version'")
        test_conn.close()
    except Exception:
        return False

    db_path = get_db_path()
    shutil.copy2(source_path, str(db_path))

    # WAL/SHM 파일 제거 (새 연결에서 재생성됨)
    for ext in (".wal", ".shm"):
        p = db_path.with_suffix(db_path.suffix + ext)
        if p.exists():
            p.unlink()

    return True
