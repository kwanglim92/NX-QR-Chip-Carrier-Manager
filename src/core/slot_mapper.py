"""ATX 슬롯 코드 → 그리드 좌표 변환.

슬롯 코드 형식: _XXYY
  XX 앞자리 = ATX 번호, XX 뒷자리 = Port 번호
  YY = 슬롯 번호 (01~12)

물리적 ATX 배치 (좌측 하단 = Slot 1):
  화면 Row 0 (상단): Slot 09, 10, 11, 12
  화면 Row 1 (중간): Slot 05, 06, 07, 08
  화면 Row 2 (하단): Slot 01, 02, 03, 04
"""
from __future__ import annotations

GRID_ROWS = 3


def parse_slot_code(suffix: str) -> dict:
    """슬롯 코드 접미사(예: '1102')를 파싱.

    Returns: {'atx': 1, 'port': 1, 'slot': 2}
    """
    suffix = suffix.strip("_")
    atx = int(suffix[0])
    port = int(suffix[1])
    slot = int(suffix[2:])
    return {"atx": atx, "port": port, "slot": slot}


def slot_to_grid(slot_num: int) -> tuple[int, int]:
    """슬롯 번호(1-12) → (row, col) 0-indexed.

    물리적 배치를 반영: 하단 = Slot 1~4, 상단 = Slot 9~12.
    """
    logical_row = (slot_num - 1) // 4   # 0=Slot1~4, 1=Slot5~8, 2=Slot9~12
    col = (slot_num - 1) % 4
    row = (GRID_ROWS - 1) - logical_row  # 뒤집기: 0→2, 1→1, 2→0
    return row, col


def grid_to_slot(row: int, col: int) -> int:
    """(row, col) 0-indexed → 슬롯 번호(1-12).

    화면 row 2(하단) = Slot 1~4.
    """
    logical_row = (GRID_ROWS - 1) - row
    return logical_row * 4 + col + 1


def format_slot_label(slot_num: int) -> str:
    """슬롯 번호 → 표시용 라벨 (예: '1-1', '2-3')."""
    row = (slot_num - 1) // 4 + 1
    col = (slot_num - 1) % 4 + 1
    return f"{row}-{col}"


def format_full_label(slot_code: str) -> str:
    """슬롯 코드 → 'ATX1 Port1 Slot2' 형식."""
    info = parse_slot_code(slot_code)
    return f"ATX{info['atx']} Port{info['port']} Slot{info['slot']}"
