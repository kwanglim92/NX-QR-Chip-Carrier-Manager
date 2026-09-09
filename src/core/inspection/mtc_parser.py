"""MTC 런 폴더 파싱 — 6개 탭 구분 txt 를 (ATX, Port, Slot) 키로 병합.

런 폴더(예: ``20260909``) 구성
-------------------------------
- ``PSPD.txt``               : A+B (V), A-B (V), C-D (V)
- ``FreqSweep.txt``          : Frequency (KHz), Set Point (nm), Amplitude (nm), Drive (%), Q
- ``FreqSweep_ZoomOut.txt``  : 위와 같은 열(광대역 200~400 kHz 스윕)
- ``Vision.txt``             : Tip Focus (um), Tip X (pxl), Tip Y (pxl), Match Score (%)
- ``Angle.txt``              : ``CantileverNo Angle`` — CantileverNo = ``{run}_{ATX}{Port}{Slot:02d}``
- ``Exchange.txt``           : Delta Z (um) — 빈 슬롯까지 전부 나열되므로 슬롯 존재 판정에 쓰지 않음
- ``FreqSweep/Repeat{r}/TipExchanger{A}/Port{P}_{S}.jpg|.txt|_ZoomOut.jpg|_ZoomOut.txt``
- ``Vision/Repeat{r}/TipExchanger{A}/Port{P}_{S}_pickUp.png|_putBack.png``

슬롯 존재 = PSPD ∪ FreqSweep ∪ ZoomOut ∪ Vision ∪ Angle 에 한 번이라도 등장.
값은 모두 ``float | None`` (없는 열/행은 None). 슬롯 코드 ``{A}{P}{SS}`` 는 기존
``slot_mapper.parse_slot_code`` 체계와 동일하다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from pathlib import Path

_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "latin-1")

PSPD_FILE = "PSPD.txt"
SWEEP_FILE = "FreqSweep.txt"
ZOOM_FILE = "FreqSweep_ZoomOut.txt"
VISION_FILE = "Vision.txt"
ANGLE_FILE = "Angle.txt"
EXCHANGE_FILE = "Exchange.txt"

# 슬롯 존재를 정의하는 파일(Exchange 제외)
_SLOT_DEFINING_FILES = (PSPD_FILE, SWEEP_FILE, ZOOM_FILE, VISION_FILE, ANGLE_FILE)

_CANTILEVER_RE = re.compile(r"^(?P<run>.+?)_(?P<atx>\d)(?P<port>\d)(?P<slot>\d{2})$")


def read_text_any(path: Path) -> str:
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return path.read_text(encoding="latin-1")


def to_float(value) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize_header(name: str) -> str:
    """열 이름 → snake_case 키. 단위 괄호 제거, ``+``/``-`` 는 plus/minus.

    'A+B (V)' → 'a_plus_b', 'Tip X (pxl)' → 'tip_x', 'Frequency (KHz)' → 'frequency'
    """
    s = re.sub(r"\(.*?\)", "", name).strip()
    s = s.replace("+", " plus ").replace("-", " minus ")
    s = re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_").lower()
    return s


def read_table(path: Path) -> list[dict[str, str]]:
    """탭 구분 표 → [{정규화 헤더: 문자열}]. 행이 헤더보다 짧으면 공백 분리로 재시도.

    (``Angle.txt`` 는 헤더는 탭, 행은 공백으로 구분되어 있다.)
    """
    if not path.exists():
        return []
    lines = [ln for ln in read_text_any(path).splitlines() if ln.strip()]
    if not lines:
        return []
    headers = [normalize_header(h) for h in lines[0].split("\t") if h.strip()]
    rows: list[dict[str, str]] = []
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.split("\t")]
        while cells and cells[-1] == "":
            cells.pop()
        if len(cells) < len(headers):
            cells = ln.split()
        if not cells:
            continue
        rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(headers)})
    return rows


@dataclass
class MtcSlot:
    atx: int
    port: int
    slot: int
    repeat: int = 1
    # PSPD
    a_plus_b: float | None = None
    a_minus_b: float | None = None
    c_minus_d: float | None = None
    # FreqSweep (zoom-in)
    frequency: float | None = None
    set_point: float | None = None
    amplitude: float | None = None
    drive: float | None = None
    q: float | None = None
    # FreqSweep_ZoomOut
    zoom_frequency: float | None = None
    zoom_set_point: float | None = None
    zoom_amplitude: float | None = None
    zoom_drive: float | None = None
    zoom_q: float | None = None
    # Vision
    tip_focus: float | None = None
    tip_x: float | None = None
    tip_y: float | None = None
    match_score: float | None = None
    # Angle / Exchange
    angle: float | None = None
    delta_z: float | None = None
    # 파일 경로 (존재하는 것만, 없으면 None)
    pickup_image: str | None = None
    putback_image: str | None = None
    sweep_image: str | None = None
    zoom_image: str | None = None
    sweep_txt: str | None = None
    zoom_txt: str | None = None

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.atx, self.port, self.slot)

    @property
    def code(self) -> str:
        """슬롯 코드 ``{ATX}{Port}{Slot:02d}`` (예: '1102')."""
        return f"{self.atx}{self.port}{self.slot:02d}"

    @property
    def has_sweep(self) -> bool:
        return self.frequency is not None

    @property
    def has_vision(self) -> bool:
        return self.tip_x is not None and self.tip_y is not None


@dataclass
class MtcRun:
    run_id: str
    folder: str
    slots: list[MtcSlot] = field(default_factory=list)

    def find(self, atx: int, port: int, slot: int) -> MtcSlot | None:
        for s in self.slots:
            if s.key == (atx, port, slot):
                return s
        return None

    def find_code(self, code: str) -> MtcSlot | None:
        for s in self.slots:
            if s.code == code:
                return s
        return None

    def cantilever_no(self, slot: MtcSlot) -> str:
        return f"{self.run_id}_{slot.code}"


def is_mtc_run_folder(folder: str | Path) -> bool:
    p = Path(folder)
    return p.is_dir() and any((p / name).exists() for name in _SLOT_DEFINING_FILES)


_VALUE_FIELDS = {f.name for f in fields(MtcSlot)} - {"atx", "port", "slot", "repeat"}


def _slot_key_of_row(row: dict[str, str]) -> tuple[int, int, int, int] | None:
    try:
        return (
            int(row.get("repeat", "1") or 1),
            int(row["tip_exchanger"]),
            int(row["port"]),
            int(row["slot"]),
        )
    except (KeyError, ValueError):
        return None


def _merge_rows(slots: dict, rows: list[dict[str, str]], mapping: dict[str, str],
                define: bool) -> None:
    """rows 의 열(mapping: 헤더키 → MtcSlot 필드)을 slots 에 병합.

    define=False 면 이미 존재하는 슬롯에만 값을 채운다(Exchange.txt).
    """
    for row in rows:
        k = _slot_key_of_row(row)
        if k is None:
            continue
        repeat, atx, port, slot = k
        key = (atx, port, slot)
        if key not in slots:
            if not define:
                continue
            slots[key] = MtcSlot(atx=atx, port=port, slot=slot, repeat=repeat)
        target = slots[key]
        for src, dst in mapping.items():
            if src in row and dst in _VALUE_FIELDS:
                setattr(target, dst, to_float(row[src]))


_PSPD_MAP = {"a_plus_b": "a_plus_b", "a_minus_b": "a_minus_b", "c_minus_d": "c_minus_d"}
_SWEEP_MAP = {"frequency": "frequency", "set_point": "set_point",
              "amplitude": "amplitude", "drive": "drive", "q": "q"}
_ZOOM_MAP = {"frequency": "zoom_frequency", "set_point": "zoom_set_point",
             "amplitude": "zoom_amplitude", "drive": "zoom_drive", "q": "zoom_q"}
_VISION_MAP = {"tip_focus": "tip_focus", "tip_x": "tip_x", "tip_y": "tip_y",
               "match_score": "match_score"}
_EXCHANGE_MAP = {"delta_z": "delta_z"}


def _merge_angle(slots: dict, rows: list[dict[str, str]]) -> str | None:
    """Angle.txt 병합. CantileverNo 접두(run id)를 반환(첫 행 기준)."""
    run_id: str | None = None
    for row in rows:
        m = _CANTILEVER_RE.match(row.get("cantileverno", ""))
        if not m:
            continue
        if run_id is None:
            run_id = m.group("run")
        key = (int(m.group("atx")), int(m.group("port")), int(m.group("slot")))
        if key not in slots:
            slots[key] = MtcSlot(atx=key[0], port=key[1], slot=key[2])
        slots[key].angle = to_float(row.get("angle"))
    return run_id


def _existing(path: Path) -> str | None:
    return str(path) if path.exists() else None


def _attach_files(folder: Path, s: MtcSlot) -> None:
    sweep_dir = folder / "FreqSweep" / f"Repeat{s.repeat}" / f"TipExchanger{s.atx}"
    vision_dir = folder / "Vision" / f"Repeat{s.repeat}" / f"TipExchanger{s.atx}"
    stem = f"Port{s.port}_{s.slot}"
    s.sweep_image = _existing(sweep_dir / f"{stem}.jpg")
    s.sweep_txt = _existing(sweep_dir / f"{stem}.txt")
    s.zoom_image = _existing(sweep_dir / f"{stem}_ZoomOut.jpg")
    s.zoom_txt = _existing(sweep_dir / f"{stem}_ZoomOut.txt")
    s.pickup_image = _existing(vision_dir / f"{stem}_pickUp.png")
    s.putback_image = _existing(vision_dir / f"{stem}_putBack.png")


def load_mtc_run(folder: str | Path) -> MtcRun:
    """런 폴더를 읽어 ``MtcRun`` 반환. 슬롯은 (ATX, Port, Slot) 오름차순."""
    root = Path(folder)
    slots: dict[tuple[int, int, int], MtcSlot] = {}

    _merge_rows(slots, read_table(root / PSPD_FILE), _PSPD_MAP, define=True)
    _merge_rows(slots, read_table(root / SWEEP_FILE), _SWEEP_MAP, define=True)
    _merge_rows(slots, read_table(root / ZOOM_FILE), _ZOOM_MAP, define=True)
    _merge_rows(slots, read_table(root / VISION_FILE), _VISION_MAP, define=True)
    run_id = _merge_angle(slots, read_table(root / ANGLE_FILE))
    _merge_rows(slots, read_table(root / EXCHANGE_FILE), _EXCHANGE_MAP, define=False)

    ordered = [slots[k] for k in sorted(slots)]
    for s in ordered:
        _attach_files(root, s)

    return MtcRun(run_id=run_id or root.name, folder=str(root), slots=ordered)
