"""Manual-mode slot ordering helpers."""
from __future__ import annotations

from src.core.models import SlotData


def renumber_manual_slots(
    slots: list[SlotData], ordered_indices: list[int]
) -> dict[int, int]:
    """Renumber ``slots`` according to the current Manual card order.

    Returns a mapping of old slot_index to new slot_index for retained slots.
    Slots not present in ``ordered_indices`` are dropped from the list.
    """
    by_index = {slot.slot_index: slot for slot in slots}
    ordered_slots = [
        by_index[old_index]
        for old_index in ordered_indices
        if old_index in by_index
    ]

    mapping: dict[int, int] = {}
    for new_index, slot in enumerate(ordered_slots):
        old_index = slot.slot_index
        mapping[old_index] = new_index
        slot.slot_index = new_index
        slot.slot_code = str(new_index + 1)

    slots[:] = ordered_slots
    return mapping
