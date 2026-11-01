"""Data model for GenCAD 1.4 boardviews.

Every field on ``Component`` / ``Pin`` / ``Net`` / ``Shape`` maps 1:1 to a record that was present in the
file. Anything the application derives lives in a separate ``inferred_*`` container so that tool output
can never present an assumption as parsed fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- geometry / pads


@dataclass
class PadGeometry:
    """A primitive (CIRCLE/RECTANGLE/LINE/ARC) inside a PAD definition."""

    kind: str
    params: Tuple[float, ...] = ()


@dataclass
class Pad:
    name: str
    shape_type: str  # ROUND / RECTANGULAR / ... as written in the file
    drill: Optional[float]
    primitives: List[PadGeometry] = field(default_factory=list)


@dataclass
class Padstack:
    name: str
    drill: Optional[float]
    pads: List[Tuple[str, str, float, float]] = field(default_factory=list)
    attributes: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class PinDef:
    """A PIN record inside a SHAPE: footprint-local pin definition."""

    name: str
    padstack: str
    x: float
    y: float
    layer: str
    pad_dx: float = 0.0
    pad_dy: float = 0.0


@dataclass
class Shape:
    name: str
    pins: List[PinDef] = field(default_factory=list)
    inserts: List[str] = field(default_factory=list)


@dataclass
class DeviceDef:
    name: str
    part: Optional[str] = None
    tol: Optional[str] = None


@dataclass
class RouteSummary:
    """Drawing data for a net route. Never part of the connectivity graph."""

    vias: List[Dict[str, object]] = field(default_factory=list)
    track_records: int = 0
    layer_records: int = 0
    geometry_records: int = 0


# --------------------------------------------------------------------------- connectivity records


@dataclass
class Pin:
    name: str
    padstack: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    layer: Optional[str] = None
    pad_dx: Optional[float] = None
    pad_dy: Optional[float] = None
    nets: List[str] = field(default_factory=list)  # exact net names, in file order
    declared_by_shape: bool = False  # True -> came from a SHAPE PIN record
    connected: bool = False  # True -> at least one NODE record referenced it
    node_records: int = 0  # number of NODE lines referencing this pin (>1 == duplicate)


@dataclass
class Component:
    ref: str
    package: Optional[str] = None  # SHAPE name (footprint / "package")
    device: Optional[str] = None  # DEVICE name; viewers show it as the component value
    x: Optional[float] = None
    y: Optional[float] = None
    rotation: Optional[float] = None
    side: Optional[str] = None  # LAYER: TOP / BOTTOM
    pins: Dict[str, Pin] = field(default_factory=dict)
    explicit: Dict[str, bool] = field(default_factory=dict)  # field -> present in file
    inferred: Dict[str, object] = field(default_factory=dict)  # application-derived only


@dataclass
class Net:
    name: str
    members: List[Tuple[str, str]] = field(default_factory=list)  # (component ref, pin name)
    duplicate_members: int = 0  # NODE lines that repeat an existing (ref, pin) pair


@dataclass
class ParseError:
    section: str
    line: int
    message: str


@dataclass
class Board:
    path: str
    format: str = "GENCAD"
    version: str = ""
    header: Dict[str, object] = field(default_factory=dict)
    attributes: List[Dict[str, str]] = field(default_factory=list)
    components: Dict[str, Component] = field(default_factory=dict)
    nets: Dict[str, Net] = field(default_factory=dict)
    shapes: Dict[str, Shape] = field(default_factory=dict)
    padstacks: Dict[str, Padstack] = field(default_factory=dict)
    pads: Dict[str, Pad] = field(default_factory=dict)
    devices: Dict[str, DeviceDef] = field(default_factory=dict)
    layers: Dict[str, str] = field(default_factory=dict)
    tracks: Dict[str, str] = field(default_factory=dict)
    routes: Dict[str, RouteSummary] = field(default_factory=dict)
    sides: List[str] = field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None  # derived from artwork geometry
    bbox_derived: bool = False
    sections_seen: Dict[str, int] = field(default_factory=dict)
    errors: List[ParseError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _as_plain(obj: object) -> object:
    """Recursively convert dataclasses/tuples for JSON serialisation."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _as_plain(v) for k, v in asdict(obj).items()}  # type: ignore[misc]
    if isinstance(obj, tuple):
        return [_as_plain(v) for v in obj]  # type: ignore[misc]
    if isinstance(obj, list):
        return [_as_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _as_plain(v) for k, v in obj.items()}
    return obj
