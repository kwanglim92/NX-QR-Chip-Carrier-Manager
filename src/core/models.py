from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SlotData:
    slot_index: int
    slot_code: str
    frequency: float | None = None
    drive: float | None = None
    q_factor: float | None = None
    qr_id: str | None = None
    image_path: str | None = None
    source: str = "summary_csv"
    probe_type: str | None = None

    @property
    def is_complete(self) -> bool:
        return all([
            self.qr_id is not None,
            self.frequency is not None,
            self.q_factor is not None,
        ])

    @property
    def grid_position(self) -> tuple[int, int]:
        """슬롯 번호(1-12) → (row, col) 0-indexed."""
        num = int(self.slot_code[-2:])
        row = (num - 1) // 4
        col = (num - 1) % 4
        return row, col

    def format_frequency(self) -> str:
        if self.frequency is None:
            return "-"
        return str(round(self.frequency))

    def format_q(self) -> str:
        if self.q_factor is None:
            return "-"
        return str(round(self.q_factor))


@dataclass
class MeasurementSet:
    po_number: str = ""
    quantity: int = 0
    probe_type: str = ""
    production_date: str = ""
    slots: list[SlotData] = field(default_factory=list)
    source_folder: str = ""
    mode: str = "atx"
    db_id: int | None = None

    @property
    def matched_count(self) -> int:
        return sum(1 for s in self.slots if s.qr_id is not None)

    @property
    def total_count(self) -> int:
        return len(self.slots)

    @property
    def all_complete(self) -> bool:
        return all(s.is_complete for s in self.slots)

    def get_unmatched_slots(self) -> list[SlotData]:
        return [s for s in self.slots if s.qr_id is None]

    def find_slot_by_index(self, index: int) -> SlotData | None:
        for s in self.slots:
            if s.slot_index == index:
                return s
        return None
