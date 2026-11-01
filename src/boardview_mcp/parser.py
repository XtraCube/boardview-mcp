"""GenCAD 1.4 boardview parser (strictly read-only).

A field exists on the returned model **only if the file asserted it**. Anything the application
derives lives in ``inferred_*`` containers, which the tool layer always labels as inferred.

The record subset understood here is exactly what was observed in
``MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad`` (CAMCAD Professional "RSI-TRANSLATOR" output) and in
other GenCAD 1.x translators of the same family:

    $HEADER $BOARD $PADS $PADSTACKS $ARTWORKS $SHAPES $COMPONENTS $DEVICES
    $SIGNALS $TRACKS $LAYERS $ROUTES $MECH $TESTPINS $POWERPINS

$BOARD / $ARTWORKS / $ROUTES are drawing data. $ROUTES VIA records name pads a net's *drawing*
passes over; they are deliberately **not** merged into net membership (see :func:`_parse_routes`).
Unknown sections and unknown records inside known sections are counted and reported instead of
being dropped silently, so a future dialect fails loudly rather than quietly losing connectivity.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .models import (
    Board,
    Component,
    DeviceDef,
    Net,
    Pad,
    PadGeometry,
    Padstack,
    ParseError,
    Pin,
    PinDef,
    RouteSummary,
    Shape,
)

GENCAD_SECTIONS: tuple[str, ...] = (
    "HEADER",
    "BOARD",
    "PADS",
    "PADSTACKS",
    "ARTWORKS",
    "SHAPES",
    "COMPONENTS",
    "DEVICES",
    "SIGNALS",
    "TRACKS",
    "LAYERS",
    "ROUTES",
    "MECH",
    "TESTPINS",
    "POWERPINS",
)

_SECTION_RE = re.compile(r"^\$([A-Z][A-Z0-9_]*)$")
_END_RE = re.compile(r"^\$END([A-Z][A-Z0-9_]*)$")
_NUMBER_RE = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)$")
_GEOMETRY_RECORDS = frozenset({"LINE", "ARC", "CIRCLE", "RECTANGLE"})


class GenCadError(Exception):
    """Raised when the input is not a parseable GenCAD file at all."""


class Validation:
    """Structural problems found while parsing; reported on the Board, never raised mid-parse."""

    def __init__(self) -> None:
        self.errors: list[ParseError] = []
        self.warnings: list[str] = []
        self._once: set[str] = set()

    def error(self, section: str, line: int, message: str) -> None:
        self.errors.append(ParseError(section=section, line=line, message=message))

    def warn_once(self, key: str, message: str) -> None:
        if key in self._once:
            return
        self._once.add(key)
        self.warnings.append(message)


def tokenize(line: str) -> list[str]:
    """Split one GenCAD record into values, honouring ``"quoted strings"`` with ``\\\\"`` escapes."""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            buf: list[str] = []
            j = i + 1
            closed = False
            while j < n:
                c = line[j]
                if c == "\\" and j + 1 < n:
                    buf.append(line[j + 1])
                    j += 2
                    continue
                if c == '"':
                    closed = True
                    break
                buf.append(c)
                j += 1
            out.append("".join(buf))
            i = j + 1 if closed else j
            continue
        j = i
        while j < n and not line[j].isspace():
            j += 1
        out.append(line[i:j])
        i = j
    return out


def logical_lines(text: str) -> list[tuple[int, str]]:
    """Join GenCAD ``\\`` end-of-line continuations -> ``[(first_physical_line_no, record), ...]``."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0
    for idx, raw in enumerate(text.splitlines(), start=1):
        if not buf:
            start = idx
        if raw.endswith("\\") and not raw.endswith("\\\\"):
            buf.append(raw[:-1])
            continue
        out.append((start, "".join(buf) + raw if buf else raw))
        buf = []
    if buf:
        out.append((start, "".join(buf)))
    return out


def split_sections(lines: Sequence[tuple[int, str]]) -> list[tuple[str, int, list[tuple[int, str]]]]:
    """Group logical lines into ``[(SECTION, opening_line_no, records), ...]``."""
    out: list[tuple[str, int, list[tuple[int, str]]]] = []
    name, opened, records = "", 0, []

    def close() -> None:
        nonlocal name, opened, records
        if name:
            out.append((name, opened, records))
        name, opened, records = "", 0, []

    for line_no, line in lines:
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped.startswith("$"):
            end = _END_RE.match(stripped)
            start = _SECTION_RE.match(stripped)
            if end:
                if not name or end.group(1) != name:
                    close()
                    out.append(("(unbalanced-marker)", line_no, [(line_no, stripped)]))
                else:
                    close()
                continue
            if start:
                close()
                name, opened, records = start.group(1), line_no, []
                continue
            close()
            out.append(("(stray-dollar)", line_no, [(line_no, stripped)]))
            continue
        if name:
            records.append((line_no, stripped))
        else:
            out.append(("(outside-section)", line_no, [(line_no, stripped)]))
    close()
    return out


def _numbers(tokens: Sequence[str]) -> Optional[Tuple[float, ...]]:
    """All tokens numeric -> tuple of floats, else None."""
    vals: list[float] = []
    for tok in tokens:
        if not _NUMBER_RE.match(tok):
            return None
        vals.append(float(tok))
    return tuple(vals)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="cp1252", errors="replace") as fh:
            return fh.read()


def sniff(path: str) -> tuple[str, str]:
    """Return ``(format, version)`` for GenCAD input, else raise :class:`GenCadError` with a hint."""
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if not head.strip():
        raise GenCadError(f"{path}: file is empty.")
    if b"\x00" in head:
        raise GenCadError(f"{path}: contains NUL bytes - not a text GenCAD 1.4 file.")
    sample = head.decode("utf-8", errors="replace")
    if "GENCAD" not in sample.upper():
        first = sample.splitlines()[0].strip() if sample.splitlines() else "<empty>"
        raise GenCadError(
            f"{path}: no GENCAD marker in the first 4 KiB (first line {first[:72]!r}). "
            "Only GenCAD 1.x boardviews are supported; a '.cad' extension alone does not imply GenCAD."
        )
    for line in sample.splitlines():
        m = re.match(r"^\s*GENCAD\s+([0-9][0-9.]*)\s*$", line, flags=re.IGNORECASE)
        if m:
            return "GENCAD", m.group(1)
    return "GENCAD", "unknown"


# --------------------------------------------------------------------------- section parsers


def _parse_header(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "GENCAD":
            if not args or not re.match(r"^[0-9][0-9.]*$", args[0]):
                v.error("HEADER", line_no, f"bad version token: {line!r}")
            else:
                board.version = args[0]
        elif rec in ("USER", "DRAWING", "REVISION"):
            board.header[rec] = " ".join(args)
        elif rec in ("UNITS", "ORIGIN", "INTERTRACK"):
            board.header[rec] = _numbers(args) or args
        elif rec == "ATTRIBUTE":
            if len(args) >= 3:
                board.attributes.append({"id": args[0], "key": args[1], "value": args[2]})
            else:
                v.error("HEADER", line_no, f"ATTRIBUTE needs id/key/value: {line!r}")
        else:
            v.warn_once(f"header:{rec}", f"header record {rec} not understood (ignored).")


def _parse_geometry_section(section: str, records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    """$BOARD / $ARTWORKS: drawing primitives. Only the extent is kept, flagged as derived."""
    xs: list[float] = []
    ys: list[float] = []
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec in _GEOMETRY_RECORDS:
            pts = _numbers(args)
            if pts is None:
                v.error(section, line_no, f"non-numeric geometry parameters: {line!r}")
                continue
            xs += pts[0::2]
            ys += pts[1::2]
        elif rec == "ARTWORK":
            continue
        else:
            v.warn_once(f"{section}:{rec}", f"{section} record {rec} not understood (ignored).")
    if xs and ys:
        board.bbox = (min(xs), min(ys), max(xs), max(ys))
        board.bbox_derived = True


def _parse_pads(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    cur: Pad | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "PAD":
            if len(args) < 2:
                v.error("PADS", line_no, f"PAD needs at least a name and a shape type: {line!r}")
                cur = None
                continue
            cur = Pad(name=args[0], shape_type=args[1], drill=_first_number(args[2:]))
            board.pads[cur.name] = cur
        elif rec in _GEOMETRY_RECORDS and cur is not None:
            pts = _numbers(args)
            if pts is None:
                v.error("PADS", line_no, f"non-numeric pad geometry parameters: {line!r}")
                continue
            cur.primitives.append(PadGeometry(kind=rec, params=pts))
        else:
            v.warn_once(f"PADS:{rec}", f"PADS record {rec} not understood (ignored).")


def _parse_padstacks(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    cur: Padstack | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "PADSTACK":
            if len(args) < 1:
                v.error("PADSTACKS", line_no, f"PADSTACK without a name: {line!r}")
                cur = None
                continue
            cur = Padstack(name=args[0], drill=_first_number(args[1:]))
            board.padstacks[cur.name] = cur
        elif rec == "PAD" and cur is not None:
            if len(args) < 4:
                v.error("PADSTACKS", line_no, f"PAD inside PADSTACK needs name/layer/dx/dy: {line!r}")
                continue
            cur.pads.append((args[0], args[1], float(args[2]), float(args[3])))
        elif rec == "ATTRIBUTE" and len(args) >= 3:
            cur.attributes.append({"id": args[0], "key": args[1], "value": args[2]})
        elif rec == "ATTRIBUTE":
            v.error("PADSTACKS", line_no, f"ATTRIBUTE needs id/key/value: {line!r}")
        else:
            v.warn_once(f"PADSTACKS:{rec}", f"PADSTACKS record {rec} not understood (ignored).")


def _parse_shapes(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    cur: Shape | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "SHAPE":
            if not args:
                v.error("SHAPES", line_no, f"SHAPE without a name: {line!r}")
                cur = None
                continue
            cur = Shape(name=args[0])
            board.shapes[cur.name] = cur
        elif rec == "PIN" and cur is not None:
            # PIN <pin-name> <padstack> <x> <y> <layer> <pad-dx> <pad-dy>
            if len(args) < 7:
                v.error("SHAPES", line_no, f"PIN needs name/padstack/x/y/layer/dx/dy: {line!r}")
                continue
            coords = _numbers(args[2:4])
            offsets = _numbers(args[5:7])
            if coords is None or offsets is None:
                v.error("SHAPES", line_no, f"non-numeric PIN coordinates/offsets: {line!r}")
                continue
            if args[0] in {p.name for p in cur.pins}:
                v.error("SHAPES", line_no, f"duplicate PIN {args[0]!r} in shape {cur.name}: {line!r}")
                continue
            cur.pins.append(
                PinDef(name=args[0], padstack=args[1], x=coords[0], y=coords[1], layer=args[4], pad_dx=offsets[0], pad_dy=offsets[1])
            )
        elif rec == "INSERT" and cur is not None and args:
            cur.inserts.append(args[0])
        else:
            v.warn_once(f"SHAPES:{rec}", f"SHAPES record {rec} not understood (ignored).")


def _parse_components(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    cur: Component | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "COMPONENT":
            if not args:
                v.error("COMPONENTS", line_no, f"COMPONENT without a reference: {line!r}")
                cur = None
                continue
            ref = args[0]
            if ref in board.components:
                v.error("COMPONENTS", line_no, f"duplicate component reference {ref}: {line!r}")
                cur = None
                continue
            cur = Component(ref=ref)
            board.components[ref] = cur
        elif cur is None:
            v.error("COMPONENTS", line_no, f"record {rec} outside a COMPONENT block: {line!r}")
        elif rec == "PLACE":
            pts = _numbers(args)
            if pts is None or len(pts) != 2:
                v.error("COMPONENTS", line_no, f"PLACE needs exactly two numbers: {line!r}")
            else:
                cur.x, cur.y = pts
                cur.explicit["position"] = True
        elif rec == "LAYER":
            if not args:
                v.error("COMPONENTS", line_no, f"LAYER without a value: {line!r}")
            else:
                cur.side = args[0]
                cur.explicit["side"] = True
        elif rec == "ROTATION":
            pts = _numbers(args)
            if pts is None or len(pts) != 1:
                v.error("COMPONENTS", line_no, f"ROTATION needs exactly one number: {line!r}")
            else:
                cur.rotation = pts[0]
                cur.explicit["rotation"] = True
        elif rec == "SHAPE":
            if not args:
                v.error("COMPONENTS", line_no, f"SHAPE without a name: {line!r}")
            else:
                cur.package = args[0]
                cur.explicit["package"] = True
                off = _numbers(args[1:])
                if off and len(off) == 2:
                    cur.inferred["package_offset"] = {"dx": off[0], "dy": off[1], "basis": "SHAPE <name> <dx> <dy>"}
                elif off is not None:
                    v.error("COMPONENTS", line_no, f"SHAPE offset needs two numbers: {line!r}")
        elif rec == "DEVICE":
            if not args:
                v.error("COMPONENTS", line_no, f"DEVICE without a name: {line!r}")
            else:
                cur.device = args[0]
                cur.explicit["device"] = True
        elif rec == "e":
            cur.inferred["annotations"] = args
        else:
            v.warn_once(f"COMPONENTS:{rec}", f"COMPONENTS record {rec} not understood (ignored).")


def _parse_devices(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    cur: DeviceDef | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "DEVICE":
            if not args:
                v.error("DEVICES", line_no, f"DEVICE without a name: {line!r}")
                cur = None
                continue
            cur = DeviceDef(name=args[0])
            board.devices[cur.name] = cur
        elif cur is None:
            v.error("DEVICES", line_no, f"record {rec} outside a DEVICE block: {line!r}")
        elif rec in ("PART", "TOL"):
            if rec == "PART":
                cur.part = " ".join(args)
            else:
                cur.tol = " ".join(args)
        else:
            v.warn_once(f"DEVICES:{rec}", f"DEVICES record {rec} not understood (ignored).")


def _parse_signals(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    cur: Net | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "SIGNAL":
            if len(args) != 1:
                v.error("SIGNALS", line_no, f"SIGNAL needs exactly one name: {line!r}")
                cur = None
                continue
            name = args[0]
            if name in board.nets:
                v.error("SIGNALS", line_no, f"duplicate SIGNAL {name}: later members appended to the first")
                cur = board.nets[name]
                continue
            cur = Net(name=name, members=[])
            board.nets[name] = cur
        elif rec == "NODE":
            if len(args) != 2:
                v.error("SIGNALS", line_no, f"NODE needs exactly component-ref pin-name: {line!r}")
                continue
            if cur is None:
                v.error("SIGNALS", line_no, f"NODE {args[0]} {args[1]} appears outside any SIGNAL")
                continue
            pair = (args[0], args[1])
            if pair in cur.members:
                cur.duplicate_members += 1
                v.warn_once(
                    f"dup_node:{cur.name}:{args[0]}:{args[1]}",
                    f"NODE {args[0]} {args[1]} repeated inside SIGNAL {cur.name} (kept once)",
                )
                continue
            cur.members.append(pair)
        else:
            v.warn_once(f"SIGNALS:{rec}", f"SIGNALS record {rec} not understood (ignored).")


def _parse_tracks(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    for line_no, line in records:
        toks = tokenize(line)
        if toks[0] == "TRACK" and len(toks) >= 2:
            board.tracks[toks[1]] = toks[2:]
        else:
            v.warn_once("TRACKS:other", "TRACKS contains unrecognised records (ignored).")


def _parse_layers(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    for line_no, line in records:
        toks = tokenize(line)
        if toks[0] == "DEFINE" and len(toks) >= 3:
            board.layers[toks[1]] = toks[2]
        else:
            v.warn_once("LAYERS:other", "LAYERS contains unrecognised records (ignored).")


def _parse_routes(records: list[tuple[int, str]], board: Board, v: Validation) -> None:
    """$ROUTES is drawing data. VIA waypoints are NOT electrical members - they are counted only."""
    cur: RouteSummary | None = None
    for line_no, line in records:
        toks = tokenize(line)
        rec, args = toks[0], toks[1:]
        if rec == "ROUTE":
            if not args:
                v.error("ROUTES", line_no, f"ROUTE without a net name: {line!r}")
                cur = None
                continue
            cur = RouteSummary()
            board.routes[args[0]] = cur
        elif cur is None:
            v.error("ROUTES", line_no, f"{rec} record outside a ROUTE block: {line!r}")
        elif rec == "VIA":
            # VIA <padstack> <x> <y> <layer> <track> <label> - drawing waypoints over pads, NOT members
            if len(args) < 3:
                v.error("ROUTES", line_no, f"VIA needs padstack/x/y: {line!r}")
                continue
            pts = _numbers(args[1:3])
            if pts is None:
                v.error("ROUTES", line_no, f"non-numeric VIA coordinates: {line!r}")
            else:
                cur.vias.append({"padstack": args[0], "x": pts[0], "y": pts[1], "rest": args[3:]})
        elif rec == "TRACK":
            cur.track_records += 1
        elif rec == "LAYER":
            cur.layer_records += 1
        elif rec in _GEOMETRY_RECORDS:
            cur.geometry_records += 1
        else:
            v.warn_once(f"ROUTES:{rec}", f"ROUTES record {rec} not understood (ignored).")


# --------------------------------------------------------------------------- driver


def parse_file(path: str, *, max_bytes: int = 128 * 1024 * 1024) -> Board:
    """Parse a GenCAD 1.x boardview file. Read-only; nothing from the file is ever executed."""
    fmt, version = sniff(path)
    if os.path.getsize(path) > max_bytes:
        raise GenCadError(f"{path}: {os.path.getsize(path)} bytes exceeds max_bytes={max_bytes}; refusing to parse.")

    board = Board(path=path, format=fmt, version=version)
    v = Validation()

    geometry_sections = {"BOARD", "ARTWORKS"}
    handlers = {
        "HEADER": _parse_header,
        "PADS": _parse_pads,
        "PADSTACKS": _parse_padstacks,
        "SHAPES": _parse_shapes,
        "COMPONENTS": _parse_components,
        "DEVICES": _parse_devices,
        "SIGNALS": _parse_signals,
        "TRACKS": _parse_tracks,
        "LAYERS": _parse_layers,
        "ROUTES": _parse_routes,
    }

    for name, _opened, records in split_sections(logical_lines(text := _read_text(path))):
        board.sections_seen[name] = len(records)
        if name in geometry_sections:
            _parse_geometry_section(name, records, board, v)
        elif name in handlers:
            handlers[name](records, board, v)
        elif name not in GENCAD_SECTIONS:
            v.warn_once(f"section:{name}", f"unknown section {name}: {len(records)} records counted, not parsed.")

    for marker in ("(outside-section)", "(unbalanced-marker)", "(stray-dollar)"):
        if marker in board.sections_seen:
            v.error("(file)", 0, f"file contains {board.sections_seen[marker]} stray marker(s) outside sections")

    if board.version not in ("1.4",):
        v.warn_once(
            "version",
            f"file declares GENCAD {board.version}; the parser targets GenCAD 1.4. "
            "Records that were understood are reported; check sections_seen for anything unmapped.",
        )
    if not board.components:
        v.error("(file)", 0, "no COMPONENT records found: this GenCAD file carries no board components")

    _cross_validate(board, v)
    _attach_pins(board, v)
    board.sides = sorted({c.side for c in board.components.values() if c.side})
    board.errors, board.warnings = v.errors, v.warnings
    return board


def _first_number(tokens: Sequence[str]) -> Optional[float]:
    for tok in tokens:
        if _NUMBER_RE.match(tok):
            return float(tok)
    return None


def _cross_validate(board: Board, v: Validation) -> None:
    for net_name, net in board.nets.items():
        for ref, _pin in net.members:
            if ref not in board.components:
                v.error("SIGNALS", 0, f"SIGNAL {net_name} references unknown component {ref}")
    for ref, comp in board.components.items():
        if comp.package and comp.package not in board.shapes:
            v.error("COMPONENTS", 0, f"component {ref} references SHAPE {comp.package} with no SHAPE record")
        if comp.device and comp.device not in board.devices:
            v.error("DEVICES", 0, f"component {ref} references DEVICE {comp.device} with no DEVICE record")
    if (only_routes := set(board.routes) - set(board.nets)):
        v.warn_once("routes/orphan", f"{len(only_routes)} ROUTE records have no SIGNAL of that name (kept separate).")
    if (only_signals := set(board.nets) - set(board.routes)):
        v.warn_once("signals/noroute", f"{len(only_signals)} SIGNAL nets have no ROUTE drawing record.")
    empty = [n for n, net in board.nets.items() if not net.members]
    if empty:
        v.warn_once("signals/empty", f"{len(empty)} SIGNAL records have no NODE members (kept as empty nets).")
    dup_total = sum(net.duplicate_members for net in board.nets.values())
    if dup_total:
        v.warn_once("signals/dup", f"{dup_total} repeated NODE lines were collapsed to single memberships.")


def _attach_pins(board: Board, v: Validation) -> None:
    """Footprint pins come from the component's SHAPE; net memberships come from SIGNALS/NODE."""
    for comp in board.components.values():
        shape = board.shapes.get(comp.package or "")
        if shape is None:
            continue
        for pd in shape.pins:
            comp.pins[pd.name] = Pin(
                name=pd.name,
                padstack=pd.padstack,
                x=pd.x,
                y=pd.y,
                layer=pd.layer,
                pad_dx=pd.pad_dx,
                pad_dy=pd.pad_dy,
                declared_by_shape=True,
            )
    for net_name, net in board.nets.items():
        for ref, pin_name in net.members:
            comp = board.components.get(ref)
            if comp is None:
                continue
            p = comp.pins.get(pin_name)
            if p is None:
                p = Pin(name=pin_name, declared_by_shape=False)
                comp.pins[pin_name] = p
                v.warn_once(
                    "node/undeclared-pin",
                    "some NODE records name a pin absent from the component's SHAPE; "
                    "those pins are kept with declared_by_shape=False.",
                )
            p.nets.append(net_name)
            p.node_records += 1
            p.connected = True


def load_board(path: str) -> Board:
    """Parse a boardview once (the server calls this at startup; tools never reparse)."""
    return parse_file(path)
