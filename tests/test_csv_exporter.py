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


def test_generate_csv_rows_includes_contact_slot_with_blank_freq_q():
    """컨택 슬롯(QR-only)도 QR 반출에 포함되며 Freq/Q는 빈칸으로 출력."""
    ms = MeasurementSet(
        po_number="P1", production_date="20260530",
        slots=[
            SlotData(
                slot_index=0, slot_code="1", qr_id="C-1",
                probe_type="ContactTip", serial_number="S1", contact_mode=True,
            ),
        ],
    )
    rows = generate_csv_rows(ms, CSV_EXPORT_QR_ONLY)
    assert rows[0] == CSV_HEADER
    assert rows[1] == ["C-1", "20260530", "", "", "", "ContactTip"]


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


# ─── 서버 업로드용 이미지 전송명 (upload_image_files) ───


def test_upload_image_files_renames_to_qr_id_like_export(tmp_path):
    from src.core.csv_exporter import upload_image_files

    a = tmp_path / "slot_01_1234567890.png"
    b = tmp_path / "slot_02_2222222222.jpg"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    ms = MeasurementSet(
        slots=[
            SlotData(slot_index=0, slot_code="1", qr_id="1234567890", image_path=str(a)),
            SlotData(slot_index=1, slot_code="2", qr_id="2222222222", image_path=str(b)),
            SlotData(slot_index=2, slot_code="3", qr_id="3333333333", image_path=str(tmp_path / "missing.png")),
            SlotData(slot_index=3, slot_code="4", qr_id="4444444444", image_path=None),
        ]
    )
    assert upload_image_files(ms) == [
        (str(a), "1234567890.png"),
        (str(b), "2222222222.jpg"),
    ]


def test_upload_image_files_dedupes_same_send_name(tmp_path):
    from src.core.csv_exporter import upload_image_files

    a = tmp_path / "x.png"
    b = tmp_path / "y.png"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    ms = MeasurementSet(
        slots=[
            SlotData(slot_index=0, slot_code="1", qr_id="1234567890", image_path=str(a)),
            SlotData(slot_index=1, slot_code="2", qr_id="1234567890", image_path=str(b)),
        ]
    )
    assert [n for _, n in upload_image_files(ms)] == ["1234567890.png", "1234567890_1.png"]


def test_upload_image_files_policy_qr_only_skips_unmatched_and_all_slots_uses_slot_name(tmp_path):
    from src.core.csv_exporter import (
        CSV_EXPORT_ALL_SLOTS,
        CSV_EXPORT_QR_ONLY,
        upload_image_files,
    )

    a = tmp_path / "pending_0001.png"
    a.write_bytes(b"a")
    ms = MeasurementSet(slots=[SlotData(slot_index=4, slot_code="5", qr_id=None, image_path=str(a))])
    assert upload_image_files(ms, CSV_EXPORT_QR_ONLY) == []
    assert upload_image_files(ms, CSV_EXPORT_ALL_SLOTS) == [(str(a), "slot_05.png")]
