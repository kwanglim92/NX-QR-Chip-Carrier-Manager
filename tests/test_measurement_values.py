from __future__ import annotations

from src.core.atx_parser import load_atx_folder, parse_summary_csv
from src.core.models import MeasurementSet, SlotData, truncate_measurement_value
from src.core.slot_mapper import parse_slot_code
from src.ui.widgets.slot_grid_widget import SlotGridWidget


def test_truncate_measurement_value_discards_fraction():
    assert truncate_measurement_value(327.9) == 327
    assert truncate_measurement_value("420.99") == 420
    assert truncate_measurement_value(None) is None
    assert truncate_measurement_value("bad") is None


def test_slot_formatters_truncate_existing_float_values():
    slot = SlotData(slot_index=0, slot_code="1101", frequency=327.9, q_factor=420.99)
    assert slot.format_frequency() == "327"
    assert slot.format_q() == "420"


def test_parse_summary_csv_truncates_frequency_and_q(tmp_path):
    csv_path = tmp_path / "Summary.csv"
    csv_path.write_text(
        "Batch,ac160(foo)_1101,ac160(foo)_1201\n"
        "Freq,327.6,306.99\n"
        "Q,614.23,420.99\n",
        encoding="utf-8",
    )

    rows = parse_summary_csv(csv_path)

    assert rows[0]["frequency"] == 327
    assert rows[0]["q_factor"] == 614
    assert rows[1]["frequency"] == 306
    assert rows[1]["q_factor"] == 420


def test_load_atx_folder_keeps_port4_slots(tmp_path):
    folder = tmp_path / "P2601001_12M_AC160"
    folder.mkdir()
    (folder / "Summary.csv").write_text(
        "Batch,ac160(foo)_1401\n"
        "Freq,327.6\n"
        "Q,614.23\n",
        encoding="utf-8",
    )

    ms = load_atx_folder(str(folder))

    assert len(ms.slots) == 1
    assert ms.slots[0].slot_code == "1401"
    assert parse_slot_code(ms.slots[0].slot_code) == {"atx": 1, "port": 4, "slot": 1}
    assert ms.slots[0].frequency == 327
    assert ms.slots[0].q_factor == 614


def test_slot_grid_orders_ports_descending(qapp):
    ms = MeasurementSet(po_number="P2601001")
    ms.slots = [
        SlotData(slot_index=0, slot_code="1101", frequency=1, q_factor=1),
        SlotData(slot_index=1, slot_code="1201", frequency=1, q_factor=1),
        SlotData(slot_index=2, slot_code="1401", frequency=1, q_factor=1),
    ]
    grid = SlotGridWidget()

    grid.load_measurement_set(ms)

    headers = []
    for i in range(grid._content_layout.count()):
        widget = grid._content_layout.itemAt(i).widget()
        if widget is not None and hasattr(widget, "text"):
            text = widget.text().strip()
            if text.startswith("Port"):
                headers.append(text)

    assert headers == ["Port 4", "Port 2", "Port 1"]
