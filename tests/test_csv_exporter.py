from __future__ import annotations

import csv

from src.core.csv_exporter import (
    CSV_EXPORT_ALL_SLOTS,
    CSV_EXPORT_QR_ONLY,
    export_with_images,
    generate_csv_rows,
)
from src.core.models import MeasurementSet, SlotData
from src.ui.controllers.export_mixin import (
    _default_export_folder_name,
    _sanitize_export_folder_name,
)


CSV_HEADER = ["QR ID", "생산일자[YYYYMMDD]", "Frequency (KHz)", "Drive (%)", "Q", "Probe Type"]


def _make_measurement_set() -> MeasurementSet:
    return MeasurementSet(
        po_number="P2605001",
        production_date="20260506",
        probe_type="DEFAULT",
        slots=[
            SlotData(
                slot_index=0,
                slot_code="1101",
                frequency=396.8,
                drive=0.27,
                q_factor=710.9,
                qr_id="QR-001",
                probe_type="SLOT-PROBE",
            ),
            SlotData(
                slot_index=1,
                slot_code="1102",
                frequency=None,
                drive=None,
                q_factor=92.4,
                qr_id=None,
            ),
            SlotData(
                slot_index=2,
                slot_code="1103",
                frequency=None,
                drive=1.5,
                q_factor=None,
                qr_id=None,
            ),
        ],
    )


def test_generate_csv_rows_qr_only_keeps_existing_export_scope():
    rows = generate_csv_rows(_make_measurement_set(), CSV_EXPORT_QR_ONLY)

    assert rows == [
        CSV_HEADER,
        ["QR-001", "20260506", "396", "0.27", "710", "SLOT-PROBE"],
    ]


def test_generate_csv_rows_all_slots_uses_blank_cells_for_missing_values():
    rows = generate_csv_rows(_make_measurement_set(), CSV_EXPORT_ALL_SLOTS)

    assert rows == [
        CSV_HEADER,
        ["QR-001", "20260506", "396", "0.27", "710", "SLOT-PROBE"],
        ["", "20260506", "", "", "92", "DEFAULT"],
        ["", "20260506", "", "1.5", "", "DEFAULT"],
    ]


def test_export_with_images_uses_slot_name_for_rows_without_qr(tmp_path):
    ms = _make_measurement_set()
    qr_image = tmp_path / "qr.jpg"
    no_qr_image = tmp_path / "no_qr.jpg"
    qr_image.write_bytes(b"qr image")
    no_qr_image.write_bytes(b"no qr image")
    ms.slots[0].image_path = str(qr_image)
    ms.slots[1].image_path = str(no_qr_image)

    result = export_with_images(
        ms,
        str(tmp_path / "export"),
        "result.csv",
        CSV_EXPORT_ALL_SLOTS,
    )

    zoomin_dir = tmp_path / "export" / "ZOOMIN"
    assert result["image_count"] == 2
    assert (zoomin_dir / "QR-001.jpg").read_bytes() == b"qr image"
    assert (zoomin_dir / "slot_02.jpg").read_bytes() == b"no qr image"

    with open(result["csv_path"], encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == CSV_HEADER
    assert len(rows) == 4


def test_default_export_folder_name_uses_source_folder_name(tmp_path):
    ms = _make_measurement_set()
    ms.source_folder = str(tmp_path / "P2601002_12M_AC160")

    assert _default_export_folder_name(ms) == "P2601002_12M_AC160"


def test_default_export_folder_name_uses_common_image_parent(tmp_path):
    image_dir = tmp_path / "ManualLot_20260513"
    image_dir.mkdir()
    ms = MeasurementSet(
        po_number="P2605001",
        slots=[
            SlotData(slot_index=0, slot_code="1", image_path=str(image_dir / "1.jpg")),
            SlotData(slot_index=1, slot_code="2", image_path=str(image_dir / "2.jpg")),
        ],
    )

    assert _default_export_folder_name(ms) == "ManualLot_20260513"


def test_default_export_folder_name_falls_back_to_po_number():
    ms = MeasurementSet(po_number="P2605001")

    assert _default_export_folder_name(ms) == "P2605001"


def test_sanitize_export_folder_name_replaces_windows_forbidden_chars():
    assert _sanitize_export_folder_name(' P2601002:12M/AC160* ') == "P2601002_12M_AC160_"


def test_export_with_images_uses_folder_name_csv_structure(tmp_path):
    ms = _make_measurement_set()
    folder_name = "P2601002_12M_AC160"

    result = export_with_images(
        ms,
        str(tmp_path / folder_name),
        f"{folder_name}_QR.csv",
        CSV_EXPORT_ALL_SLOTS,
    )

    assert result["csv_path"] == str(tmp_path / folder_name / f"{folder_name}_QR.csv")
    assert result["zoomin_dir"] == str(tmp_path / folder_name / "ZOOMIN")
