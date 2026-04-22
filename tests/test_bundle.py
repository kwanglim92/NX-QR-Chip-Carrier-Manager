"""Phase 4 회귀 테스트 — bundle.py 의 Export/Import + 3가지 중복 정책."""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

import sqlite3

import pytest

from src.core import bundle as b
from src.core import database as db
from src.core.models import MeasurementSet, SlotData


def _mk_ms(po, date, qr_prefix, *, source_folder=None, n_slots=3, probe="TypeA"):
    ms = MeasurementSet(
        po_number=po, probe_type=probe, production_date=date, mode="atx",
        source_folder=source_folder or f"/data/{po}",
    )
    for i in range(1, n_slots + 1):
        ms.slots.append(SlotData(
            slot_index=i - 1, slot_code=f"S{i:02d}",
            frequency=150.0 + i * 0.1, drive=1.0,
            q_factor=1200.0 + i,
            qr_id=f"{qr_prefix}-{i:03d}", image_path=None,
            source="summary_csv", probe_type=probe,
        ))
    return ms


@pytest.fixture
def tmpdir_path(tmp_path):
    return tmp_path


def _make_fresh_conn():
    """Import 정책 테스트용 빈 DB 생성 (src와 dst가 독립해야 함)."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    return c


@pytest.fixture
def seeded_src_db():
    """3개 세트가 저장된 독립 DB 반환 (fixture db_conn 과 분리)."""
    conn = _make_fresh_conn()
    db.save_measurement_set(conn, _mk_ms("PO-ALPHA", "20260420", "ALPHA"))
    db.save_measurement_set(conn, _mk_ms("PO-BRAVO", "20260421", "BRAVO"))
    db.save_measurement_set(conn, _mk_ms("PO-CHARLIE", "20260422", "CHARLIE"))
    yield conn
    conn.close()


@pytest.fixture
def fresh_dst_db():
    """Import 대상 빈 DB."""
    conn = _make_fresh_conn()
    yield conn
    conn.close()


class TestExport:
    def test_export_all(self, seeded_src_db, tmpdir_path):
        zip_path = tmpdir_path / "full.zip"
        result = b.export_bundle(seeded_src_db, zip_path, include_images=False)

        assert result["record_count"] == 3
        assert result["slot_count"] == 9
        assert zip_path.exists()

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert "manifest.json" in names
            assert "data.jsonl" in names
            manifest = json.loads(zf.read("manifest.json").decode())
            assert manifest["schema_version"] == 1
            assert manifest["record_count"] == 3
            assert manifest["date_range"] == ["20260420", "20260422"]

    def test_export_date_filter(self, seeded_src_db, tmpdir_path):
        zip_path = tmpdir_path / "filter.zip"
        result = b.export_bundle(
            seeded_src_db, zip_path,
            date_from="20260421", date_to="20260421",
            include_images=False,
        )
        assert result["record_count"] == 1


class TestPreview:
    def test_preview_valid(self, seeded_src_db, tmpdir_path):
        zip_path = tmpdir_path / "preview.zip"
        b.export_bundle(seeded_src_db, zip_path, include_images=False)
        preview = b.preview_bundle(zip_path)
        assert preview.compatible is True
        assert preview.schema_version == 1
        assert preview.record_count == 3

    def test_preview_corrupted(self, tmpdir_path):
        bad = tmpdir_path / "bad.zip"
        bad.write_bytes(b"not a zip")
        preview = b.preview_bundle(bad)
        assert preview.compatible is False
        assert preview.incompatible_reason


class TestImportPolicies:
    def _export(self, src_conn, tmpdir):
        zip_path = Path(tmpdir) / "bundle.zip"
        b.export_bundle(src_conn, zip_path, include_images=False)
        return zip_path

    def test_import_skip_policy(self, seeded_src_db, fresh_dst_db, tmpdir_path):
        zip_path = self._export(seeded_src_db, tmpdir_path)

        # 빈 DB → 3개 신규
        r1 = b.import_bundle(fresh_dst_db, zip_path, on_duplicate="skip")
        assert r1.imported == 3
        assert r1.skipped == 0

        # 재임포트 → 3개 skip
        r2 = b.import_bundle(fresh_dst_db, zip_path, on_duplicate="skip")
        assert r2.imported == 0
        assert r2.skipped == 3

    def test_import_overwrite_policy(self, seeded_src_db, fresh_dst_db, tmpdir_path):
        zip_path = self._export(seeded_src_db, tmpdir_path)
        b.import_bundle(fresh_dst_db, zip_path, on_duplicate="skip")

        # 한 세트의 probe_type 조작 후 overwrite
        fresh_dst_db.execute(
            "UPDATE measurement_sets SET probe_type='MODIFIED' WHERE po_number='PO-ALPHA'"
        )
        fresh_dst_db.commit()
        r = b.import_bundle(fresh_dst_db, zip_path, on_duplicate="overwrite")
        assert r.overwritten == 3

        row = fresh_dst_db.execute(
            "SELECT probe_type FROM measurement_sets WHERE po_number='PO-ALPHA'"
        ).fetchone()
        assert row["probe_type"] == "TypeA"  # 원복 확인

    def test_import_merge_policy(self, seeded_src_db, fresh_dst_db, tmpdir_path):
        zip_path = self._export(seeded_src_db, tmpdir_path)

        # dst DB에 PO-ALPHA의 1번 슬롯만 먼저 존재 (QR=ALPHA-001만)
        partial = _mk_ms("PO-ALPHA", "20260420", "ALPHA", n_slots=1)
        db.save_measurement_set(fresh_dst_db, partial)
        existing_id = partial.db_id

        r = b.import_bundle(fresh_dst_db, zip_path, on_duplicate="merge")
        assert r.merged == 1
        assert r.imported == 2  # BRAVO, CHARLIE는 신규

        # PO-ALPHA의 슬롯이 1 + 2 = 3개
        qrs = fresh_dst_db.execute(
            "SELECT qr_id FROM slots WHERE measurement_set_id=? ORDER BY slot_index",
            (existing_id,),
        ).fetchall()
        qr_set = {r["qr_id"] for r in qrs}
        assert qr_set == {"ALPHA-001", "ALPHA-002", "ALPHA-003"}


class TestImageRoundtrip:
    def test_image_bundle_and_extract(self, tmpdir_path):
        img_dir = tmpdir_path / "imgs"
        img_dir.mkdir()
        img1 = img_dir / "A.png"
        img1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"A" * 100)
        img2 = img_dir / "B.png"
        img2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"B" * 100)

        src = _make_fresh_conn()
        try:
            # 이미지 경로를 가진 세트 저장
            ms = _mk_ms("PO-IMG", "20260423", "IMG", n_slots=2)
            ms.slots[0].image_path = str(img1)
            ms.slots[1].image_path = str(img2)
            db.save_measurement_set(src, ms)

            zip_path = tmpdir_path / "img_bundle.zip"
            r_exp = b.export_bundle(src, zip_path, include_images=True)
            assert r_exp["image_count"] == 2
        finally:
            src.close()

        # 새 DB로 import + 이미지 추출
        dst = _make_fresh_conn()
        try:
            extract_dir = tmpdir_path / "extracted"
            r_imp = b.import_bundle(dst, zip_path, on_duplicate="skip",
                                     images_extract_dir=extract_dir)
            assert r_imp.imported == 1
            assert len(list(extract_dir.iterdir())) == 2

            # image_path 재바인딩 검증
            loaded = db.load_measurement_set(dst, 1)
            for slot in loaded.slots:
                assert slot.image_path and Path(slot.image_path).exists()
        finally:
            dst.close()


def test_default_filename_format():
    fn = b.default_export_filename()
    assert fn.startswith("chip_carrier_export_")
    assert fn.endswith(".zip")
