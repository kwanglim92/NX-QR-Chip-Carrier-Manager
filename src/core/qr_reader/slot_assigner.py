"""셀 번호 → (Port, Slot) 대응 + 로드된 세트 기준 적용 계획 (설계 문서 §2, §5).

Phase 2 규약: ``port = (cell−1)÷12+1``, ``slot = (cell−1)%12+1`` (카세트 1 = Port 1).
특수 배치는 ``override`` 표(``{cell: (port, slot)}``)로 셀 단위 재정의.

적용 계획 상태 (§5):
- APPLY       : 대상 레코드 있음 + 코드 있음 + 충돌/중복 없음
- NG          : 미판독(빈 슬롯 유지, 키보드 스캔으로 보완)
- SAME        : 대상에 이미 같은 QR (변경 없음)
- CONFLICT    : 대상에 다른 QR 있음 (적용 제외, 덮어쓰기는 명시적 선택)
- DUP_FRAME   : 같은 프레임 안에 같은 코드 2개 이상
- DUP_LOADED  : 로드된 다른 슬롯에 이미 같은 QR
- NO_RECORD   : 포트는 로드됐으나 슬롯 레코드 없음 → **전체 적용 차단**
- EXCLUDED    : 포트 폴더 미로드 → 자동 제외

주의:
- DUP_FRAME 은 미로드(EXCLUDED) 포트의 셀까지 포함해 센다 — 같은 코드가 화각 어디에든 2개 있으면
  오판독·중복 캐리어 신호이므로 로드된 쪽도 적용하지 않는다.
- 같은 ATX+Port 를 가진 세트가 2개 이상 로드되면(다른 PO 의 같은 포트) ``set_for_port={port: set_index}``
  로 대상 세트를 지정해야 한다. 지정이 없으면 ``AssignError``.
- override 표는 ``{cell: (port, slot)}``. 셀·포트·슬롯 범위와 대상 중복을 ``build_plan`` 진입 시 검증한다.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from src.core.models import MeasurementSet, SlotData
from src.core.qr_reader.payload_parser import ParsedFrame
from src.core.slot_mapper import parse_slot_code

SLOTS_PER_PORT = 12


class AssignStatus(str, Enum):
    APPLY = "apply"
    NG = "ng"
    SAME = "same"
    CONFLICT = "conflict"
    DUP_FRAME = "dup_frame"
    DUP_LOADED = "dup_loaded"
    NO_RECORD = "no_record"
    EXCLUDED = "excluded"


BLOCKING_STATUSES = frozenset({AssignStatus.NO_RECORD})


class AssignError(ValueError):
    """세트/override 구성 문제로 계획을 세울 수 없음 (프레임 자체의 문제는 FrameError)."""


@dataclass(frozen=True)
class AssignItem:
    cell: int
    port: int
    slot: int
    code: str | None
    status: AssignStatus
    set_index: int | None = None     # sets 목록 내 인덱스
    target: SlotData | None = None
    note: str = ""


@dataclass
class AssignPlan:
    items: list[AssignItem] = field(default_factory=list)

    @property
    def can_apply(self) -> bool:
        """차단 상태가 없고 적용할 칸이 1개 이상일 때만 True."""
        if any(i.status in BLOCKING_STATUSES for i in self.items):
            return False
        return any(i.status is AssignStatus.APPLY for i in self.items)

    @property
    def applicable(self) -> list[AssignItem]:
        return [i for i in self.items if i.status is AssignStatus.APPLY]

    def counts(self) -> dict[AssignStatus, int]:
        c = Counter(i.status for i in self.items)
        return {s: c.get(s, 0) for s in AssignStatus}


def cell_to_port_slot(cell: int, override: Mapping[int, tuple[int, int]] | None = None) -> tuple[int, int]:
    """셀 번호 → (port, slot). override 가 있으면 우선. 범위를 벗어나면 ``ValueError``."""
    if cell < 1:
        raise ValueError(f"셀 번호는 1 이상: {cell}")
    if override and cell in override:
        port, slot = (int(v) for v in override[cell])
        if port < 1 or not 1 <= slot <= SLOTS_PER_PORT:
            raise ValueError(f"override 범위 오류: 셀 {cell} → (port {port}, slot {slot})")
        return port, slot
    return (cell - 1) // SLOTS_PER_PORT + 1, (cell - 1) % SLOTS_PER_PORT + 1


def _validate_override(override: Mapping[int, tuple[int, int]] | None, cells: Sequence[int]) -> None:
    """override 를 적용한 뒤 두 셀이 같은 (port, slot) 을 가리키면 AssignError."""
    seen: dict[tuple[int, int], int] = {}
    for cell in cells:
        try:
            key = cell_to_port_slot(cell, override)
        except ValueError as e:
            raise AssignError(str(e)) from None
        if key in seen:
            raise AssignError(f"override 대상 중복: 셀 {seen[key]} 와 셀 {cell} 이 모두 Port {key[0]} Slot {key[1]}")
        seen[key] = cell


def _index_sets(
    sets: Sequence[MeasurementSet],
    atx: int | None,
    set_for_port: Mapping[int, int] | None,
) -> tuple[dict[tuple[int, int], tuple[int, SlotData]], dict[str, list[tuple[int, SlotData]]], set[int]]:
    """(port, slot) → (set_index, SlotData), qr_id → [(set_index, SlotData)...], 로드된 port 집합.

    같은 (port, slot) 이 두 세트에 있으면 ``set_for_port[port]`` 로 대상 세트를 고르고, 없으면 AssignError.
    ``by_qr`` 는 atx/set_for_port 필터와 무관하게 **로드된 세트 전체**의 기존 QR 을 모은다(§5 "로드된 폴더 전체에서 QR 중복").
    """
    by_pos: dict[tuple[int, int], tuple[int, SlotData]] = {}
    by_qr: dict[str, list[tuple[int, SlotData]]] = {}
    ports: set[int] = set()
    for si, ms in enumerate(sets):
        for sd in ms.slots:
            try:
                info = parse_slot_code(sd.slot_code)
            except (ValueError, IndexError):
                raise AssignError(
                    f"세트 {si}({ms.po_number}) 의 슬롯 코드를 해석할 수 없습니다: {sd.slot_code!r}"
                ) from None
            if sd.qr_id:
                by_qr.setdefault(sd.qr_id, []).append((si, sd))
            if atx is not None and info["atx"] != atx:
                continue
            port = info["port"]
            if set_for_port and port in set_for_port and set_for_port[port] != si:
                continue
            key = (port, info["slot"])
            if key in by_pos:
                other = by_pos[key][0]
                raise AssignError(
                    f"Port {port} Slot {info['slot']} 이 세트 {other}({sets[other].po_number}) 와 "
                    f"세트 {si}({ms.po_number}) 에 모두 있습니다 — set_for_port 로 대상 세트를 지정하세요"
                )
            by_pos[key] = (si, sd)
            ports.add(port)
    return by_pos, by_qr, ports


def build_plan(
    frame: ParsedFrame,
    sets: Sequence[MeasurementSet],
    atx: int | None = None,
    override: Mapping[int, tuple[int, int]] | None = None,
    set_for_port: Mapping[int, int] | None = None,
) -> AssignPlan:
    """판독 프레임을 로드된 세트에 대응시켜 셀별 상태를 분류한다. 아무것도 변경하지 않는다.

    - ``atx``: 여러 ATX 가 로드됐을 때 대상 ATX 번호
    - ``set_for_port``: ``{port: set_index}`` — 같은 포트를 가진 세트가 여럿일 때 대상 세트
    - ``override``: ``{cell: (port, slot)}`` 셀 재정의
    구성 문제는 ``AssignError``.
    """
    _validate_override(override, [r.cell for r in frame.reads])
    by_pos, by_qr, loaded_ports = _index_sets(sets, atx, set_for_port)
    code_counts = Counter(r.code for r in frame.reads if r.code is not None)

    items: list[AssignItem] = []
    for read in frame.reads:
        port, slot = cell_to_port_slot(read.cell, override)
        found = by_pos.get((port, slot))
        set_index, target = found if found else (None, None)
        code = read.code

        if port not in loaded_ports:
            status, note = AssignStatus.EXCLUDED, "폴더 미로드"
        elif code is None:
            status, note = AssignStatus.NG, "미판독" if target else "미판독 (레코드 없음)"
        elif target is None:
            status, note = AssignStatus.NO_RECORD, "MTC 결과 없음"
        elif code_counts[code] > 1:
            others = [r.cell for r in frame.reads if r.code == code and r.cell != read.cell]
            status, note = AssignStatus.DUP_FRAME, f"셀 {', '.join(map(str, others))} 과 동일"
        elif target.qr_id == code:
            status, note = AssignStatus.SAME, "이미 매칭됨"
        elif target.qr_id:
            status, note = AssignStatus.CONFLICT, f"기존 QR {target.qr_id}"
        elif code in by_qr:
            where = ", ".join(sd.slot_code for _, sd in by_qr[code])
            status, note = AssignStatus.DUP_LOADED, f"{where} 에 이미 있음"
        else:
            status, note = AssignStatus.APPLY, ""

        items.append(AssignItem(
            cell=read.cell, port=port, slot=slot, code=code, status=status,
            set_index=set_index, target=target, note=note,
        ))
    return AssignPlan(items=items)
