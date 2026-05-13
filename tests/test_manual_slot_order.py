from __future__ import annotations

from src.core.manual_slot_order import renumber_manual_slots
from src.core.models import SlotData


def test_renumber_manual_slots_uses_current_card_order():
    slots = [
        SlotData(slot_index=1, slot_code="2", qr_id="QR2"),
        SlotData(slot_index=3, slot_code="4", qr_id="QR4"),
        SlotData(slot_index=5, slot_code="6", qr_id="QR6"),
    ]

    mapping = renumber_manual_slots(slots, [1, 5])

    assert mapping == {1: 0, 5: 1}
    assert [(s.slot_index, s.slot_code, s.qr_id) for s in slots] == [
        (0, "1", "QR2"),
        (1, "2", "QR6"),
    ]


def test_renumber_manual_slots_keeps_measurement_values_with_slot():
    slots = [
        SlotData(slot_index=0, slot_code="1", frequency=100, q_factor=200),
        SlotData(slot_index=2, slot_code="3", frequency=300, q_factor=400),
    ]

    renumber_manual_slots(slots, [2, 0])

    assert [(s.slot_index, s.frequency, s.q_factor) for s in slots] == [
        (0, 300, 400),
        (1, 100, 200),
    ]
