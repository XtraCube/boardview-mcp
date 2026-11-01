"""Labelled component classification from what the file *names*, never from board-specific knowledge.

Everything here is an attempt at naming a physical kind; results are always returned with
``inferred: True`` and the ``basis`` list that produced them, so tool output can never read as fact.
"""

import re

# Generic GenCAD/CAMCAD device-name vocabulary. These are *name patterns*, not board component
# names: nothing here mentions J15/RS1/L45 or any other specific reference.

_UNIT_F = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*([pnumk]?)\s*[fF](?![A-Za-z0-9])")  # farads
_UNIT_H = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*([pnumk]?)\s*[hH](?![A-Za-z0-9])")  # henries
_UNIT_OHM = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*(?:[km]?)\s*(?:ohm|ohms|\u03a9)(?![A-Za-z0-9])", re.IGNORECASE)
_SHORTHAND_OHM = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*k(?![A-Za-z0-9])")  # `100k` style resistor value
_PLAIN_OHM = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)R(?![A-Za-z0-9])")  # `0R` style resistor value
_MEGA_HZ = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*([km])?hz", re.IGNORECASE)
_VOLT_VALUE = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*[vV](?![A-Za-z0-9])")

_EXPLICIT_TOKENS = {
    "capacitor": ("cap", "caps"),
    "inductor": ("ind", "inductor", "chk"),
    "ferrite": ("fet", "fnp", "npn", "sot"),
    "fuse": ("fuse",),
    "shunt": ("shunt", "vsc", "vs"),
    "connector": ("conn", "pwrconn", "hdmi", "displayport", "pci"),
    "test_point": ("testpoint", "labtestpoint", "tp"),
    "mounting": ("mounting", "hole"),
    "optical/unpopulated": ("opt",),
    "gpu": ("gpu",),
    "memory": ("mem",),
    "voltage regulator": ("vrm", "pwrmtr"),
    "sense": ("sense", "rdsense", "rsense"),
    # the file's own SHAPE/DEVICE names use the word VIRTUAL for placeholders: RS1 SHAPE
    # RSENSE_VIRTUAL_04_SMD_2512, VS501 SHAPE VIRTUAL_SHORT. That word is file data; what the
    # placeholder stands in for is not, so the kind is still labelled inferred.
    "virtual_placeholder": ("virtual",),
}

_REF_PREFIX_HINTS = {
    "C": "capacitor-like",
    "L": "inductor-like",
    "R": "resistor-like",
    "RS": "regular-shape sense terminal",
    "RT": "resistor-type descriptor",
    "Q": "ferrite/negative-pole-like",
    "K": "capacitor-like",
    "D": "two-to-three terminal descriptor",
    "LB": "labelled two-terminal descriptor",
    "VS": "virtual short",
    "U": "unit / integrated-circuit-like",
    "J": "jack / connector",
    "M": "module / multi-pin unit",
    "G": "large multi-pin unit",
    "CN": "connector",
    "FM": "frame/marking",
    "MEC": "mechanical",
    "TP": "test point",
    "Y": "split / multi-terminal",
    "T": "terminal",
    "F": "frame",
}

# Kinds that may be traversed as a tentative two-terminal bridge (Phase 3 policy).
PASSIVE_KINDS = frozenset({"capacitor", "inductor", "ferrite_bead", "resistor", "fuse", "virtual_short"})
# Kinds the file itself marks as a placeholder (SHAPE/DEVICE says VIRTUAL). Not passive: their
# internal crossings are offered only because the file says the component is a stand-in.
PLACEHOLDER_KINDS = frozenset({"virtual_placeholder"})
ACTIVE_KINDS = frozenset(
    {"integrated_circuit", "connector", "test_point", "mounting_hole", "multi_pin_unit", "unknown"}
)


def _unit_evidence(device_name: str) -> list[tuple[str, float, str]]:
    """Physical-unit evidence from a DEVICE name: [(kind, weight, why)]."""
    out: list[tuple[str, float, str]] = []
    if _UNIT_F.search(device_name):
        out.append(("capacitor", 0.9, "farad value in the DEVICE name"))
    if _UNIT_H.search(device_name):
        out.append(("inductor", 0.9, "henry value in the DEVICE name"))
    if _UNIT_OHM.search(device_name) or _SHORTHAND_OHM.search(device_name) or _PLAIN_OHM.search(device_name):
        out.append(("resistor", 0.85, "ohm value in the DEVICE name"))
    if _MEGA_HZ.search(device_name):
        out.append(("frequency_marker", 0.8, "MHz value in the DEVICE name"))
    if _VOLT_VALUE.search(device_name):
        out.append(("voltage_value", 0.6, "volt value in the DEVICE name"))
    return out


def _token_evidence(names: str) -> list[tuple[str, float, str]]:
    """Word/abbreviation evidence from the combined DEVICE/PART/SHAPE names."""
    low = names.lower()
    out: list[tuple[str, float, str]] = []
    for kind, tokens in _EXPLICIT_TOKENS.items():
        for tok in tokens:
            # long, unambiguous abbreviations may appear inside a longer name (PWRCONN8P -> conn kind)
            pat = re.escape(tok) if len(tok) >= 5 else rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])"
            if re.search(pat, low):
                weight = 0.7 if len(tok) > 3 else 0.4
                out.append((kind, weight, f"DEVICE name contains token {tok!r}"))
    if "_B25/" in names or "_B25(" in names:
        out.append(("thermal_descriptor", 0.75, "DEVICE name carries a `_B25/...` thermal descriptor"))
    return out


def classify_component(component, devices: dict) -> dict:
    """Best-effort kind for a component from its DEVICE name, SHAPE name and reference prefix.

    Always returns ``inferred: True`` plus the ordered ``basis`` list - never a bare label.
    """
    device = component.device or ""
    device_def = devices.get(device)
    part = (device_def.part or "") if device_def else ""
    shape = component.package or ""
    ref = component.ref
    m = re.match(r"[A-Za-z]+", ref)
    prefix = m.group(0) if m else ""

    evidence: list[tuple[str, float, str]] = []
    evidence += _unit_evidence(device)
    evidence += _token_evidence(f"{device} {part} {shape}")
    hint = _REF_PREFIX_HINTS.get(prefix)
    if hint:
        evidence.append((hint, 0.25, f"reference prefix {prefix} is a viewer convention, not file data"))

    if len(component.pins) > 2:
        evidence.append(("multi_pin_unit", 0.55, f"{len(component.pins)} declared pins"))
    if len(component.pins) == 1:
        evidence.append(("single_terminal", 0.55, "1 declared pin"))

    ranked = sorted(evidence, key=lambda e: -e[1])
    kind, weight = _resolve(ranked, device=device, shape=shape, pins=len(component.pins))
    return {
        "kind": kind,
        "confidence": round(weight, 2),
        "inferred": True,
        "basis": [f"{e[0]} (weight {e[1]}): {e[2]}" for e in ranked],
        "device_name": device,
        "part": part or None,
        "tol": (device_def.tol if device_def else None),
        "package": shape or None,
        "pin_count_declared": len(component.pins),
        "ref": ref,
    }


def _resolve(evidence, *, device: str, shape: str, pins: int) -> tuple[str, float]:
    """Pick the strongest kind, promoting structural kinds over unit guesses."""
    for kind, weight, _why in evidence:
        if kind in {"connector", "test_point", "mounting", "gpu", "memory", "optical/unpopulated", "voltage regulator", "fuse", "shunt", "virtual_placeholder"}:
            return _structural(kind), weight
    for kind, weight, _why in evidence:
        if kind in {"capacitor", "inductor", "ferrite", "ferrite_bead", "resistor", "virtual_short", "fuse"}:
            return _normalise(kind), weight
    if "multi_pin_unit" in {k for k, _w, _ in evidence}:
        return "integrated_circuit" if pins > 2 else "multi_pin_unit", 0.55
    if device.upper() in {"OPT", ""}:
        return "unknown", 0.0
    return "unknown", 0.0


def _normalise(kind: str) -> str:
    return {"ferrite": "ferrite_bead", "optical/unpopulated": "unknown"}.get(kind, kind)


def _structural(kind: str) -> str:
    return {"virtual_placeholder": "virtual_placeholder", "mounting": "mounting_hole", "optical/unpopulated": "unpopulated_marker", "voltage regulator": "integrated_circuit", "gpu": "integrated_circuit", "memory": "integrated_circuit", "shunt": "virtual_short"}.get(kind, kind)
