"""Tool payloads: plain JSON-friendly dicts, every field traceable to the file or labelled derived.

Conventions used by every tool here:

* names/values are byte-exact from the file; nothing is renamed, uppercased or merged.
* ``source: "file"`` marks parsed fact; ``"derived"`` marks application-computed geometry/counts;
  ``"inferred"`` marks a name-pattern guess that must be verified.
* large lists are paginated (``offset``/``limit`` + ``total`` + ``truncated``).
"""

from __future__ import annotations

import re

from .context import BoardContext  # noqa: F401  (type-only use below)
from .graph import ASSUMED_EDGE, RULE_EDGE, _validate_assumptions  # crossing vocabulary

LIMIT_MAX = 500
DEPTH_MAX = 6
HOPS_MAX = 10


def _clamp(value: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def _provenance(**marks: str) -> dict:
    return dict(marks)


def _component_detail(ctx: BoardContext, ref: str) -> dict:
    comp = ctx.board.components[ref]
    info = ctx.classified[ref]
    elig = ctx.bridgeable[ref]
    pins = {}
    for name in sorted(comp.pins):
        pin = comp.pins[name]
        pins[name] = {
            "nets": list(pin.nets),
            "padstack": pin.padstack,
            "x": pin.x,
            "y": pin.y,
            "layer": pin.layer,
            "declared_by_shape": pin.declared_by_shape,
            "connected": pin.connected,
            "node_records": pin.node_records,
            "source": _provenance(
                nets="file", padstack="file", x="file", y="file", layer="file",
                declared_by_shape="derived", connected="derived", node_records="file",
            ),
        }
    return {
        "ref": ref,
        "package": comp.package,
        "device": comp.device,
        "part": _dev(ctx, comp, "part"),
        "tol": _dev(ctx, comp, "tol"),
        "position": {"x": comp.x, "y": comp.y, "units": "file units (see board_summary.units)"},
        "rotation": comp.rotation,
        "side": comp.side,
        "explicitly_in_file": sorted(k for k, v in comp.explicit.items() if v),
        "pins": pins,
        "nets": ctx.graph.nets_of(ref),
        "connected_pins": sorted(n for n, p in comp.pins.items() if p.nets),
        "unconnected_pins": sorted(n for n, p in comp.pins.items() if not p.nets),
        "pin_count_declared": len(comp.pins),
        "pin_count_connected": sum(1 for p in comp.pins.values() if p.nets),
        "same_component_shared_net": _same_component_nets(ctx, ref),
        "structure": _structure(ctx, ref),
        "inferred_classification": info,
        "bridge_eligibility": elig,
        "source": _provenance(
            ref="file", package="file", device="file", position="file", rotation="file", side="file",
            explicitly_in_file="file (which COMPONENT/PLACE/ROTATION/SIDE records were present)",
            part="file (DEVICE part field, when that DEVICE record carries one)",
            tol="file (DEVICE tolerance field, when that DEVICE record carries one)",
            pins="file (SHAPE PIN declarations plus NODE records; per-pin source flags inside)",
            nets="derived (read off the graph; every membership comes from a NODE record)",
            connected_pins="derived (pin has at least one NODE record)",
            unconnected_pins="derived (pin has no NODE record)",
            pin_count_declared="derived (count of declared pins)",
            pin_count_connected="derived (count of pins with nets)",
            same_component_shared_net="derived (graph incidence)",
            structure="derived (geometry computed from the file's coordinates and name text: footprint extent, "
                      "per-pad coordinates, pad-to-pad distances and the vocabulary the names are built from). These "
                      "are facts about the drawing and the names, NOT statements of electrical connectivity",
            inferred_classification="inferred (name patterns; see kind_basis)",
            bridge_eligibility="inferred (policy applied to the inferred kind; see reason)",
        ),
    }


def _dev(ctx: BoardContext, comp, field: str):
    device = ctx.board.devices.get(comp.device or "")
    return getattr(device, field, None) if device else None


def _same_component_nets(ctx: BoardContext, ref: str) -> dict:
    """Nets that list more than one pin of this single component (a fact about that component only)."""
    out: dict[str, list[str]] = {}
    for net_name in ctx.graph.nets_of(ref):
        pins = [pin for ref_, pin in ctx.graph.members(net_name) if ref_ == ref]
        if len(pins) > 1:
            out[net_name] = pins
    return out


def _structure(ctx: BoardContext, ref: str, *, max_pairs: int = 24) -> dict:
    """The reasoning surface for one component: geometry and naming facts, kept apart from
    electrical facts.

    Everything here answers "what does the file show about this part?" - footprint, pad
    coordinates, distances, the words the names are built from. What the file does NOT have is
    any record saying a component is wired to itself internally, so this block is what lets a
    model reason about the internal path instead of the server deciding it. Distances are
    drawing artefacts in file units; they are never electrical evidence.
    """
    comp = ctx.board.components[ref]
    pads = []
    for name in sorted(comp.pins):
        p = comp.pins[name]
        if p.x is not None and p.y is not None:
            pads.append((name, p.x, p.y, list(p.nets)))
    extent = None
    if pads:
        xs = [q[1] for q in pads]
        ys = [q[2] for q in pads]
        extent = {
            "x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys),
            "width": max(xs) - min(xs), "height": max(ys) - min(ys),
            "centre": {"x": (min(xs) + max(xs)) / 2.0, "y": (min(ys) + max(ys)) / 2.0},
            "units": "file units (see board_summary units)",
            "from": "bounding box of the component's own declared pad coordinates",
        }
    pairs: list[dict] = []
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            a, b = pads[i], pads[j]
            shared = sorted(set(a[3]) & set(b[3]))
            pairs.append(
                {
                    "pins": [a[0], b[0]],
                    "distance": round(((a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5, 3),
                    "shared_nets": shared,
                    "nets_first_pad": a[3],
                    "nets_second_pad": b[3],
                    "across_footprint": bool(
                        extent
                        and (
                            abs(a[1] - b[1]) > 0.5 * max(extent["width"], 1e-9)
                            or abs(a[2] - b[2]) > 0.5 * max(extent["height"], 1e-9)
                        )
                    ),
                }
            )
    pairs.sort(key=lambda q: (not q["across_footprint"], q["distance"]))
    truncated = len(pairs) > max_pairs
    return {
        "pad_count_declared": len(comp.pins),
        "pad_count_with_coordinates": len(pads),
        "pads": {
            name: {"x": p.x, "y": p.y, "nets": list(p.nets), "connected": bool(p.nets)}
            for name, p in sorted(comp.pins.items())
        },
        "footprint": extent,
        "pad_pairs_by_distance": pairs[:max_pairs],
        "pad_pairs_total": len(pairs),
        "pad_pairs_truncated": truncated,
        "pads_already_sharing_a_net": [q["pins"] for q in pairs if q["shared_nets"]],
        "name_vocabulary": {
            "package_tokens": _tokens(comp.package or ""),
            "device_tokens": _tokens(comp.device or ""),
            "matched_by_classify": ctx.classified[ref].get("basis", []),
            "note": "the words present in SHAPE/DEVICE names, and which of them the classifier used; "
                    "names are file data, the classification built from them is not",
        },
        "undrawn_connections": {
            "file_states": [
                "which pads exist, where they are, which SIGNAL each belongs to, and the SHAPE/DEVICE names",
                "that two pads of this component already carry the same SIGNAL (see pads_already_sharing_a_net)",
            ],
            "file_never_states": [
                "that a pad on one SIGNAL continues to another pad of the same component",
                "which pad faces which, or what internal path a part has",
            ],
            "how_to_reason": (
                "read pad_pairs_by_distance together with the names: pads at opposite ends of the footprint "
                "(`across_footprint: true`) on a part whose name marks a through-path (filter, sense pad, "
                "virtual placeholder) are the usual in/out pair. Record the conclusion as an assumed_bridges "
                "item on the next call, with the reason - it then appears in every result as "
                "edge_kind=inferred_crossing_asserted_by_caller and tentative=true"
            ),
            "geometry_caveat": (
                "coordinates come from the drawing: they say where a pad was placed, not that a wire exists. "
                "Rotation, mirroring and stylised schematics can put two connected pads next to each other "
                "and two unconnected pads far apart, so distance is a hint, never evidence"
            ),
        },
    }


def _tokens(name: str) -> list[str]:
    out: list[str] = []
    for chunk in re.split(r"[^A-Za-z0-9]+", name):
        if chunk:
            out.append(chunk)
    return out


def evaluate_crossing(ctx: BoardContext, component: str, pins: list[str], *, reason: str | None = None, detail_limit: int = 40) -> dict:
    """Settle one proposed internal connection against the file, without ever asserting it.

    This is the reasoning surface the model uses instead of the server deciding: the caller says
    "I think pad A of REF continues to pad B inside the part, because ..." and the tool answers
    with what the file says about those two pads, what it says about the rails they sit on, and
    what would change if the model adopts the idea. The tool never adds the crossing to the
    graph - to use it, the caller passes the same item back as ``assumed_bridges`` on another
    call, where it is labelled ``inferred_crossing_asserted_by_caller``.
    """
    ref, cands = ctx.resolve_component(component)
    if ref is None:
        return {"error": f"unknown component {component!r}", "similar": cands[:10]}
    comp = ctx.board.components[ref]
    if not isinstance(pins, list) or len(pins) != 2:
        return {"error": "give exactly two pad names: pins=[A, B]"}
    a, b = [str(p) for p in pins]
    unknown = [p for p in (a, b) if p not in comp.pins]
    if unknown:
        return {
            "error": f"pad(s) {unknown} are not declared for {ref}",
            "declared_pads": sorted(comp.pins),
            "suggestions": {p: _pad_suggestions(p, comp.pins)[:8] for p in unknown},
        }
    if a == b:
        return {"error": "the two pads must be different pads", "pad": a}
    pa, pb = comp.pins[a], comp.pins[b]
    nets_a, nets_b = list(pa.nets), list(pb.nets)
    shared = sorted(set(nets_a) & set(nets_b))
    struct = _structure(ctx, ref, max_pairs=500)
    geo = {k: v for k, v in struct.items() if k != "pad_pairs_by_distance"}
    pair = next((q for q in struct["pad_pairs_by_distance"] if set(q["pins"]) == {a, b}), None)
    # Does the file already join these two rails somewhere else? If a single component carries
    # a net from each side, the file states a real path and no internal crossing is needed.
    joins: list[dict] = []
    for na in nets_a:
        for nb in nets_b:
            if na == nb:
                continue
            ma = {(c, p) for c, p in ctx.graph.members(na) if c != ref}
            mb = {(c, p) for c, p in ctx.graph.members(nb) if c != ref}
            common = sorted({c for c, _ in ma} & {c for c, _ in mb})
            if common:
                joins.append(
                    {
                        "nets": [na, nb],
                        "components_carrying_both": [
                            {"component": c, "pins": sorted(p for cc, p in ma | mb if cc == c)} for c in common[:detail_limit]
                        ],
                        "note": "the file states this component is on both nets, so a route between the nets exists "
                                "without going through REF",
                    }
                )
    geometry = {
        "distance": pair["distance"] if pair else None,
        "across_footprint": pair["across_footprint"] if pair else None,
        "footprint": geo["footprint"],
        "pad_a": {"name": a, "x": pa.x, "y": pa.y, "nets": nets_a, "connected": bool(nets_a)},
        "pad_b": {"name": b, "x": pb.x, "y": pb.y, "nets": nets_b, "connected": bool(nets_b)},
    }
    naming = geo["name_vocabulary"]
    elig = ctx.bridgeable[ref]
    contradicts: list[str] = []
    if not nets_a:
        contradicts.append(f"pad {a} carries no SIGNAL at all: the file leaves it unconnected, so a crossing "
                           f"through it would invent a connection the drawing does not even wire up")
    if not nets_b:
        contradicts.append(f"pad {b} carries no SIGNAL at all (same caution)")
    if shared:
        contradicts.append(f"pads {a} and {b} are both listed under SIGNAL {shared[0]}: the file already states "
                           f"they are on the same net, so an assumed crossing would only duplicate a fact")
    verdict = {
        "stated_in_file": bool(shared),
        "joined_elsewhere_in_file": bool(joins),
        "contradicted_by_file": bool(contradicts),
        "file_cannot_settle_it": bool(not shared and not contradicts),
        "summary": (
            f"the file already states pads {a}/{b} share SIGNAL {shared[0]}" if shared else
            "the file neither states nor forbids this: no record says a component is wired to itself, "
            "and no record contradicts the pair either"
        ),
    }
    suggested_label = reason or (
        f"reasoning from the file: {ref} package {comp.package!r} / device {comp.device!r}, "
        f"pad {a} on {nets_a or ['(no net)']}, pad {b} on {nets_b or ['(no net)']}, "
        f"distance {geometry['distance']}, across the footprint {geometry['across_footprint']}"
    )
    return {
        "question": {"component": ref, "pads": [a, b], "proposed_by": "caller (the model, not the file)"},
        "file_facts": {
            "pad_a_nets": nets_a,
            "pad_b_nets": nets_b,
            "pads_share_a_net": shared,
            "rails_joined_by_other_components": joins,
            "pads_of_this_component_already_sharing_a_net": geo["pads_already_sharing_a_net"],
        },
        "structural_facts": {
            "geometry": geometry,
            "naming": naming,
            "component_geometry": geo["footprint"],
            "candidate_alternatives": [
                q for q in struct["pad_pairs_by_distance"] if not (set(q["pins"]) == {a, b})
            ][:detail_limit],
        },
        "policy_opinion": {
            "server_rule_says": {"bridgeable": elig["bridgeable"], "rule_or_reason": elig["reason"], "inferred_kind": elig.get("inferred_kind")},
            "note": "the server rule is a name-shape heuristic and the model may disagree with it in either "
                    "direction; it is not evidence about this part, only a hint about the name",
        },
        "contradicts_file": contradicts,
        "verdict": verdict,
        "if_the_model_agrees": {
            "record_as": {"component": ref, "pins": [a, b], "label": suggested_label},
            "how_to_use": (
                "pass this object in assumed_bridges on the next connectivity call; the crossing then appears "
                "as edge_kind=inferred_crossing_asserted_by_caller with tentative=true and this label, so every "
                "result still separates it from file facts"
            ),
            "what_changes": (
                "traversals may enter at one pad and leave at the other; the file-only answers (allow_bridges="
                "false) stay unchanged, so a strict search can still be run for comparison"
            ),
        },
        "if_the_model_disagrees": {
            "what_to_do": (
                "leave assumed_bridges out of the call: the file-only graph then reports exactly what the file "
                "states, and the absence of a route is exhaustive rather than suspicious"
            ),
        },
        "source": _provenance(
            pad_nets="file", pads_share_a_net="file", rails_joined_by_other_components="file (NODE membership)",
            geometry="derived (coordinates in the file)", naming="file (name text) + derived (token split)",
            policy_opinion="inferred (name-shape heuristic; not evidence)",
            verdict="derived (from the file facts above)",
        ),
        "next_steps": [
            f"call get_component({ref!r}) for the whole structure block",
            "call find_shared_rails([...]) to compare the rails on either side",
            "call trace_power_path(..., assumed_bridges=[<record_as>]) to see the route this reasoning enables",
        ],
    }


def _pad_suggestions(want: str, names) -> list[str]:
    return [n for n in sorted(names) if n.strip().upper().lstrip("#") == want.strip().upper().lstrip("#")][:10] or [
        n for n in sorted(names) if want.upper() in n.upper() or n.upper() in want.upper()
    ][:10]


# ---------------------------------------------------------------------- 1. board_summary

def board_summary(ctx: BoardContext) -> dict:
    b = ctx.board
    units = b.header.get("UNITS")
    return {
        "file": {"path": b.path, "bytes": _bytes(b.path), "format": b.format, "version": b.version},
        "header": {k: v for k, v in b.header.items()},
        "attributes": b.attributes,
        "counts": {
            "components": len(b.components),
            "nets": len(b.nets),
            "shapes": len(b.shapes),
            "padstacks": len(b.padstacks),
            "pads": len(b.pads),
            "devices": len(b.devices),
            "layers": len(b.layers),
            "tracks": len(b.tracks),
            "routes": len(b.routes),
            "pin_records_total": sum(len(c.pins) for c in b.components.values()),
            "pin_net_memberships": sum(len(n.members) for n in b.nets.values()),
            "declared_pins_unconnected": sum(
                1 for c in b.components.values() for p in c.pins.values() if p.declared_by_shape and not p.nets
            ),
            "components_with_no_nets": sum(1 for c in b.components.values() if not any(p.nets for p in c.pins.values())),
        },
        "sides": b.sides,
        "bbox": (dict(x0=b.bbox[0], y0=b.bbox[1], x1=b.bbox[2], y1=b.bbox[3]) if b.bbox else None),
        "bbox_derived": b.bbox_derived,
        "sections_seen": b.sections_seen,
        "kinds_present": ctx.kinds_present(),
        "parse": {"errors": [e.__dict__ for e in b.errors], "warnings": b.warnings},
        "connectivity_model": {
            "how_pins_connect": "two pins listed under the same SIGNAL share that net",
            "net_names": "byte-exact from the file; never renamed, normalised or merged",
            "route_vias": "ROUTE/VIA records are drawing data, NOT electrical members",
            "ic_internal_bridging": (
                "an internal crossing is only ever reported as an explicit hypothesis, never as file data, and "
                "only for components the policy deems eligible; such edges carry kind=inferred_crossing_from_name_rules and "
                "tentative=true. " + ctx.graph.bridge_policy_note
            ),
        },
        "notes": ["bbox is derived from geometry (bbox_derived=true)", f"units header: {units}"],
    }


def _bytes(path: str) -> int:
    import os

    try:
        return os.path.getsize(path)
    except OSError:
        return -1


# ---------------------------------------------------------------------- 2. search_components

def search_components(ctx: BoardContext, query: str, *, field: str = "all", kind: str | None = None, limit: int = 25, offset: int = 0) -> dict:
    if not query:
        return {"error": "query must be a non-empty string or glob", "query": query}
    page = ctx.search(query, fields=field, kind=kind, limit=limit, offset=offset)
    return {
        "query": query,
        "match_mode": "glob" if "*" in query or "?" in query else "substring",
        "case_insensitive": True,
        "field": field,
        "kind_filter": kind,
        "total_matched": page["total_matched"],
        "counts_note": (
            f"total_matched is the exact number of components matching this query across all "
            f"{len(ctx.board.components)} components on the board; matches only covers the returned window"
        ),
        "offset": page["offset"],
        "limit": page["limit"],
        "truncated": page["truncated"],
        "matches": page["matches"],
        "kinds_present": ctx.kinds_present(),
        "hint": "use get_component(ref) for exact pins/nets; kinds come from name patterns and are inferred",
    }


# ---------------------------------------------------------------------- 3. get_component

def get_component(ctx: BoardContext, ref: str, *, include_pins: bool = True) -> dict:
    resolved, cands = ctx.resolve_component(ref)
    if resolved is None:
        nets = ctx.search_nets(ref, limit=10)
        return {
            "error": "component reference not found",
            "queried": ref,
            "similar_components": cands,
            "similar_nets": nets,
            "note": "references are case-sensitive in the file; only a unique case-insensitive match is accepted",
        }
    detail = _component_detail(ctx, resolved)
    if not include_pins:
        detail = {k: v for k, v in detail.items() if k != "pins"}
        detail["source"] = {k: v for k, v in detail["source"].items() if k != "pins"}
        detail["source"]["pins_omitted"] = "not returned (include_pins=false); re-call with include_pins=true"
        detail["pins_omitted"] = True
    return {"found": True, "resolved_ref": resolved, "resolution_notes": cands, "component": detail}


# ---------------------------------------------------------------------- 4. get_net

def get_net(ctx: BoardContext, name: str, *, offset: int = 0, limit: int = 100) -> dict:
    limit = _clamp(limit, 1, LIMIT_MAX)
    offset = _clamp(offset, 0, 10**9)
    resolved, cands = ctx.resolve_net(name)
    if resolved is None:
        comps = [r for r in (ctx.resolve_component(name)[1] or [])]
        return {
            "error": "net name not found",
            "queried": name,
            "similar_nets": cands,
            "similar_components": comps,
            "note": "net names are case-sensitive and byte-exact; only a unique case-insensitive match is accepted",
        }
    net = ctx.board.nets[resolved]
    members = ctx.graph.members(resolved)
    per_component: dict[str, list[str]] = {}
    for ref, pin in members:
        per_component.setdefault(ref, []).append(pin)
    page = [{"component": r, "pin": p, "index": i} for i, (r, p) in enumerate(members)][offset : offset + limit]
    window = members[offset : offset + limit]
    truncated = len(members) > offset + limit
    per_component_window: dict[str, list[str]] = {}
    for ref, pin in window:
        per_component_window.setdefault(ref, []).append(pin)
    multi_pin_same = {r: ps for r, ps in per_component.items() if len(ps) > 1}
    multi_pin_reported = multi_pin_same if not truncated else {
        r: ps for r, ps in multi_pin_same.items() if r in per_component_window
    }
    return {
        "net": resolved,
        "spelling_note": "net name is exactly as written in the file",
        "total_members": len(members),
        "distinct_components": len(per_component),
        "offset": offset,
        "limit": limit,
        "truncated": truncated,
        "members": page,
        "members_by_component": (per_component if not truncated else per_component_window),
        "grouping_scope_note": (
            "members_by_component and multi_pin_components_on_this_net cover only the returned window; ask again with another offset for the rest"
            if truncated
            else "members_by_component covers every member of this net"
        ),
        "multi_pin_components_on_this_net": multi_pin_reported,
        "same_component_shared_net_note": (
            "these components contribute several pins to this net; that says nothing about their other pins"
        ),
        "duplicate_member_records": net.duplicate_members,
        "route_drawing_exists": resolved in ctx.board.routes,
        "route_vias_are_not_members": True,
        "inferred_classification_of_members": {r: ctx.classified[r]["kind"] for r in per_component_window},
        "classification_scope_note": "classification covers the components in this window only",
        "source": _provenance(
            net="file (name is byte-exact; see spelling_note)",
            members="file (NODE records inside one SIGNAL block)",
            members_by_component="derived (grouping of those members)",
            multi_pin_components_on_this_net="derived (grouping of those members)",
            total_members="derived (count of members)",
            distinct_components="derived (count of distinct component refs among members)",
            duplicate_member_records="derived (count of repeated NODE comp pin lines inside this SIGNAL block, each kept once)",
            route_drawing_exists="file (a ROUTE with this SIGNAL name exists or does not)",
            route_vias_are_not_members="fixed rule (ROUTE/VIA records are drawing data; no member comes from one)",
            inferred_classification_of_members="inferred (name patterns; see kind_basis in get_component)",
        ),
    }


def _seeds(ctx: BoardContext, start: list[dict]) -> tuple[list[tuple[str, str | None]], list[str], list[str]]:
    """Resolve start descriptors ({component,pin?} or {net}) into graph seeds; report misses."""
    seeds: list[tuple[str, str | None]] = []
    missed: list[str] = []
    notes: list[str] = []
    for item in start or []:
        if "net" in item:
            resolved, cands = ctx.resolve_net(item["net"])
            if resolved is None:
                missed.append(f"net {item['net']!r}: {cands[:5]}")
                continue
            notes.extend(cands)
            seeds.extend((ref, pin) for ref, pin in ctx.graph.members(resolved))
            continue
        ref = item.get("component") or item.get("ref")
        if not ref:
            missed.append(f"unusable start descriptor {item!r}")
            continue
        resolved, cands = ctx.resolve_component(ref)
        if resolved is None:
            missed.append(f"component {ref!r}: {cands[:5]}")
            continue
        notes.extend(cands)
        seeds.append((resolved, item.get("pin")))
    return seeds, notes, missed


def _assumed_breakdown(ctx: BoardContext, assumed: list[dict] | None) -> dict:
    """What the caller asked the graph to assume, split into accepted/rejected (never file evidence)."""
    _mapping, acc, rej = _validate_assumptions(ctx.graph, assumed)
    return {
        "requested": assumed or [],
        "accepted": acc,
        "rejected": rej,
        "note": "caller assertions are never file evidence: edges built from them carry edge_kind=inferred_crossing_asserted_by_caller and tentative=true",
    }


def _edge_view(ctx: BoardContext, edge: dict) -> dict:
    kind = edge["kind"]
    out = {
        "from": edge["from"],
        "to": {"component": edge["component"], "pin": edge["pin"]},
        "net": edge["net"],
        "edge_kind": kind,
        "tentative": bool(edge.get("tentative", False)),
        "depth": edge.get("depth"),
        "evidence": edge["net"] if kind in ("net", "same_component_shared_net") else None,
        "why": (
            f"both pins are listed under SIGNAL {edge['net']} in the file"
            if kind in ("net", "same_component_shared_net")
            else (
                f"caller assertion: {edge.get('asserted_label') or 'no label'} - the caller (not the file) states that "
                f"{edge['component']} connects pin {edge['from']['pin']} to pin {edge['pin']} internally"
                if kind == ASSUMED_EDGE
                else (
                    f"{edge.get('rule', 'two-terminal passive rule')}: path enters {edge['component']} at pin {edge['from']['pin']} "
                    f"and leaves at pin {edge['pin']}; the file never states an internal connection for {edge['component']}"
                )
            )
        ),
    }
    if kind == ASSUMED_EDGE:
        out["intervening_component"] = edge["component"]
        out["asserted_by"] = edge.get("asserted_by")
        out["asserted_label"] = edge.get("asserted_label")
        out["eligibility"] = edge.get("eligibility")
        return out
    if kind == "inferred_crossing_from_name_rules":
        out["intervening_component"] = edge["intervening_component"]
        out["inferred_kind"] = edge.get("inferred_kind")
        out["kind_basis"] = edge.get("kind_basis")
        out["eligibility"] = edge.get("eligibility")
    if kind == "same_component_shared_net":
        out["same_component_shared_net"] = True
    return out


def find_connected_components(ctx: BoardContext, *, component: str | None = None, net: str | None = None, pin: str | None = None, depth: int = 1, allow_bridges: bool = True, limit: int = 100, offset: int = 0, assumed_bridges: list[dict] | None = None, per_net_window: int = 12, exclude_nets: list[str] | None = None, exclude_components: list[str] | None = None) -> dict:
    limit = _clamp(limit, 1, LIMIT_MAX)
    depth = _clamp(depth, 1, DEPTH_MAX)
    if component is None and net is None:
        return {"error": "provide component or net"}
    start: list[dict] = []
    if net is not None:
        start.append({"net": net})
    if component is not None:
        start.append({"component": component, "pin": pin})
    seeds, notes, missed = _seeds(ctx, start)
    if missed:
        return {"error": "start not found", "missed": missed, "component": component, "net": net}
    if not seeds:
        return {"error": "no usable start descriptors", "component": component, "net": net}
    keep_nets = {n for n in (exclude_nets or ()) if n in ctx.board.nets}
    drop_refs = {r for r in (exclude_components or ()) if r in ctx.bridgeable}
    walk = ctx.graph.trace(seeds, max_depth=depth, max_nodes=_clamp(limit, 1, LIMIT_MAX) * (depth + 1),
                           allow_bridges=allow_bridges, assumed_bridges=assumed_bridges,
                           exclude_nets=keep_nets, exclude_refs=drop_refs, per_net_window=per_net_window)
    edges = [_edge_view(ctx, e) for e in walk["edges"]][offset : offset + limit]
    return {
        "start": {"component": component, "net": net, "pin": pin},
        "resolution_notes": notes,
        "depth": depth,
        "allow_bridges": allow_bridges,
        "seed_nodes": walk["seed_nodes"],
        "edges": edges,
        "edge_count": len(walk["edges"]),
        "truncated": walk["truncated"] or len(walk["edges"]) > offset + limit,
        "visited_components": walk["visited_components"],
        "nets_touched": walk["nets_touched"],
        "tentative_edges": walk["tentative_edges"],
        "assumed_edges": walk.get("assumed_edges", 0),
        "net_fanout": walk.get("net_fanout", []),
        "bridge_policy": ctx.graph.bridge_policy_note,
        "excluded_nets": sorted(keep_nets),
        "excluded_components": sorted(drop_refs),
        "source": _provenance(
            seed_nodes="file (start pins and their nets)",
            edges="file for edge_kind=net (a shared SIGNAL is stated in the file); hypothesis for edge_kind=inferred_crossing_from_name_rules (internal crossing) - read edge_kind/tentative per edge, not this field as a whole",
            counts="derived",
            resolution_notes="derived (case-insensitive / similar-name suggestions)",
        ),
    }


def trace_connectivity(ctx: BoardContext, start: list[dict], *, max_depth: int = 2, max_nodes: int = 200, allow_bridges: bool = True, only_refs: list[str] | None = None, only_kinds: list[str] | None = None, exclude_refs: list[str] | None = None, exclude_nets: list[str] | None = None, assumed_bridges: list[dict] | None = None, per_net_window: int = 12) -> dict:
    seeds, notes, missed = _seeds(ctx, start)
    if not seeds:
        return {"error": "no usable start descriptors", "missed": missed, "hint": "give [{'component':'C191','pin':'1'}] or [{'net':'NAME'}]"}
    walk = ctx.graph.trace(
        seeds,
        max_depth=_clamp(max_depth, 1, DEPTH_MAX),
        max_nodes=_clamp(max_nodes, 1, LIMIT_MAX),
        allow_bridges=allow_bridges,
        assumed_bridges=assumed_bridges,
        only_refs=only_refs,
        only_kinds=only_kinds,
        exclude_refs=exclude_refs,
        exclude_nets=exclude_nets,
        per_net_window=per_net_window,
    )
    walk["filters"] = {
        "only_refs": only_refs,
        "only_kinds": only_kinds,
        "exclude_refs": exclude_refs,
        "exclude_nets": exclude_nets,
        "per_net_window": per_net_window,
    }
    walk["edges"] = [_edge_view(ctx, e) for e in walk["edges"]]
    walk["resolution_notes"] = notes
    walk["missed"] = missed
    walk["kinds_of_nodes"] = {n["component"]: ctx.classified[n["component"]]["kind"] for n in walk["nodes"]}
    walk["excluded_nets"] = sorted(n for n in (exclude_nets or ()) if n in ctx.board.nets)
    walk["excluded_components"] = sorted(r for r in (exclude_refs or ()) if r in ctx.bridgeable)
    walk["bridge_policy"] = ctx.graph.bridge_policy_note
    _mapping, _acc, _rej = _validate_assumptions(ctx.graph, assumed_bridges)
    walk["assumed_bridges"] = {
        "requested": assumed_bridges or [],
        "accepted": _acc,
        "rejected": _rej,
        "note": "caller assertions are never file evidence: edges built from them carry edge_kind=inferred_crossing_asserted_by_caller and tentative=true",
    }
    walk["source"] = _provenance(
        nodes="file (pin/net membership of each reached pin)",
        edges="file for edge_kind=net; hypothesis for edge_kind=inferred_crossing_from_name_rules (read edge_kind/tentative per edge)",
        depth_and_counts="derived (traversal bookkeeping)",
        kinds_of_nodes="inferred (name patterns; see kind_basis in get_component)",
        filters="requested by the caller",
    )
    return walk


def trace_power_path(ctx: BoardContext, start: list[dict], target_components: list[str], *, max_paths: int = 8, max_hops: int = 6, allow_bridges: bool = True, assumed_bridges: list[dict] | None = None, exclude_nets: list[str] | None = None, exclude_components: list[str] | None = None, per_net_window: int = 12) -> dict:
    seeds, notes, missed = _seeds(ctx, start)
    if not seeds:
        return {"error": "no usable start descriptors", "missed": missed}
    targets: list[str] = []
    unknown: list[str] = []
    for item in target_components or []:
        ref = item.get("component", item.get("label")) if isinstance(item, dict) else item
        if not isinstance(ref, str):
            unknown.append({"queried": str(item), "similar": []})
            continue
        resolved, cands = ctx.resolve_component(ref)
        if resolved is None:
            unknown.append({"queried": ref, "similar": cands[:8]})
        else:
            targets.append(resolved)
    if not targets:
        return {"error": "no target components resolved", "unknown": unknown}
    drop_refs = {r for r in (exclude_components or ()) if r in ctx.bridgeable}
    keep_nets = {n for n in (exclude_nets or ()) if n in ctx.board.nets}
    res = ctx.graph.paths_between(
        seeds,
        targets,
        max_paths=_clamp(max_paths, 1, 50),
        max_hops=_clamp(max_hops, 1, HOPS_MAX),
        allow_bridges=allow_bridges,
        assumed_bridges=assumed_bridges,
        exclude_refs=drop_refs,
        exclude_nets=keep_nets,
    )
    paths: list[dict] = []
    for i, route in enumerate(res["paths"]):
        hops = [_edge_view(ctx, e) for e in route["hops"]]
        intervening = [h for h in hops if h["edge_kind"] != "net" and h["edge_kind"] != "same_component_shared_net"]
        nets = [h["net"] for h in hops if h["net"]]
        paths.append(
            {
                "index": i,
                "target": route["target"],
                "label": route["label"],
                "components": [h["to"]["component"] for h in hops],
                "pins": [f"{h['to']['component']}.{h['to']['pin']}" for h in hops],
                "hops": hops,
                "nets_in_order": nets,
                "tentative_hops": [h["to"] for h in hops if h["tentative"]],
                "tentative_hop_kinds": sorted({h["edge_kind"] for h in hops if h["tentative"]}),
                "intervening_components": sorted({h["intervening_component"] for h in intervening}),
                "file_certain_hops": sum(1 for h in hops if not h["tentative"]),
                "hypothesis_hops": sum(1 for h in hops if h["edge_kind"] == RULE_EDGE),
                "asserted_hops": sum(1 for h in hops if h["edge_kind"] == ASSUMED_EDGE),
                "same_route_without_internal_crossing": route.get("asserted_only"),
                "same_route_note": (
                    f"{route.get('asserted_only', False)!r} refers to the route named by `label`: "
                    + res["asserted_only_note"]
                ),
                "verdict": (
                    "asserted by the file (every hop is a shared SIGNAL)"
                    if not intervening
                    else "file plus your own conclusions (no name-rule crossing was needed)"
                    if not any(h["edge_kind"] == RULE_EDGE for h in hops)
                    else "partly hypothetical: at least one hop is a crossing the name rule offered"
                ),
                "caller_asserted_hops": sum(1 for h in hops if h["edge_kind"] == ASSUMED_EDGE),
                "verdict_note": route["label"],
            }
        )
    return {
        "start": start,
        "requested_targets": target_components,
        "assumed_bridges_requested": assumed_bridges,
        "resolved_targets": targets,
        "excluded_nets": sorted(keep_nets),
        "excluded_components": sorted(drop_refs),
        "unknown_targets": unknown,
        "seed_nodes": res["seed_nodes"],
        "paths": paths,
        "max_paths": res["max_paths"],
        "max_hops": res["max_hops"],
        "truncated": res["truncated"],
        "assumed_bridges": _assumed_breakdown(ctx, assumed_bridges),
        "search_note": (
            "one best route per target per search, capped by max_hops and an internal pop budget; the file does "
            "not contain route topology, so an undiscovered target means the search budget ran out, not that no "
            "route exists"
        ),
        "bridge_policy": ctx.graph.bridge_policy_note,
        "asserted_only_note": res["asserted_only_note"],
        "source": _provenance(
            hops="file for edge_kind=net (shared SIGNAL stated in the file); hypothesis for edge_kind=inferred_crossing_from_name_rules (internal crossing)",
            nets_in_order="file (the SIGNALs each asserted hop shares)",
            verdict="derived (counted from the per-hop edge kinds)",
            same_route_without_internal_crossing="derived (a second search that forbids internal crossings)",
        ),
        "next_steps": [
            "call get_net(name) for every net in a candidate path to inspect all members",
            "call get_component(ref) on each intervening component to see its inferred kind and terminals",
            "call find_shared_rails([...]) to confirm two components really share a net",
        ],
    }


def find_shared_rails(ctx: BoardContext, components: list[str], *, detail_limit: int = 40,
                             exclude_components: list[str] | None = None,
                             exclude_nets: list[str] | None = None) -> dict:
    detail_limit = _clamp(detail_limit, 1, LIMIT_MAX)
    refs: list[str] = []
    unknown: list[dict] = []
    for ref in components or []:
        resolved, cands = ctx.resolve_component(ref)
        if resolved is None:
            unknown.append({"queried": ref, "similar": cands[:8]})
        else:
            refs.append(resolved)
    if len(refs) < 2:
        return {"error": "need at least two resolvable components", "resolved": refs, "unknown": unknown}
    drop_refs = {r for r in (exclude_components or ()) if r in ctx.bridgeable}
    if drop_refs:
        refs = [r for r in refs if r not in drop_refs]
    drop_nets = set(n for n in (exclude_nets or ()) if n in ctx.board.nets)
    res = ctx.graph.shared_nets(refs, exclude_nets=drop_nets)
    rails: list[dict] = []
    for net_name, sharers in sorted(res["shared_nets"].items()):
        members = ctx.graph.members(net_name)
        pins_of_sharers = {r: [p for rr, p in members if rr == r] for r in sharers}
        rails.append(
            {
                "net": net_name,
                "shared_by": sharers,
                "total_members_on_net": len(members),
                "members_truncated": len(members) > detail_limit,
                "members_sample": [{"component": r, "pin": p} for r, p in members[:detail_limit]],
                "pins_of_each_sharer_on_this_net": pins_of_sharers,
            }
        )
    return {
        "requested": components,
        "resolved": refs,
        "unknown": unknown,
        "rail_count": len(rails),
        "rails": rails,
        "pairwise": res["pairwise"],
        "excluded_components": sorted(drop_refs),
        "excluded_nets": sorted(drop_nets),
        "source": _provenance(rails="file", member_counts="derived"),
    }


def export_subgraph(ctx: BoardContext, start: list[dict], *, depth: int = 2, max_nodes: int = 200, allow_bridges: bool = True, include_geometry: bool = True, assumed_bridges: list[dict] | None = None, per_net_window: int = 12, exclude_nets: list[str] | None = None, exclude_components: list[str] | None = None) -> dict:
    seeds, notes, missed = _seeds(ctx, start)
    if not seeds:
        return {"error": "no usable start descriptors", "missed": missed}
    drop_refs = {r for r in (exclude_components or ()) if r in ctx.bridgeable}
    keep_nets = {n for n in (exclude_nets or ()) if n in ctx.board.nets}
    sub = ctx.graph.subgraph(
        seeds,
        depth=_clamp(depth, 1, DEPTH_MAX),
        max_nodes=_clamp(max_nodes, 1, LIMIT_MAX),
        allow_bridges=allow_bridges,
        include_geometry=include_geometry,
        assumed_bridges=assumed_bridges,
        exclude_refs=drop_refs,
        exclude_nets=keep_nets,
        per_net_window=per_net_window,
    )
    sub["excluded_nets"] = sorted(keep_nets)
    sub["excluded_components"] = sorted(drop_refs)
    sub["resolution_notes"] = notes
    sub["missed"] = missed
    sub["kinds"] = {ref: ctx.classified[ref]["kind"] for ref in sub["components"]}
    sub["bridge_policy"] = ctx.graph.bridge_policy_note
    rule_edges = [e for e in sub["edges"] if e.get("edge_kind", e.get("kind")) == RULE_EDGE]
    assumed_edges = [e for e in sub["edges"] if e.get("edge_kind", e.get("kind")) == ASSUMED_EDGE]
    through = rule_edges + assumed_edges

    def _far_end(_e: dict) -> tuple[tuple[str, str], tuple[str | None, str | None]]:
        # subgraph edges are {component, pin, from: {component, pin}}; tool edges use from/to.
        end = _e.get("to") or _e
        src = _e.get("from") or {}
        return ((end or {}).get("component") or _e.get("component"), (end or {}).get("pin") or _e.get("pin")), (
            src.get("component"), src.get("pin"))

    def _pad_has_a_net(where: tuple[str | None, str | None]) -> bool:
        ref, pin = where
        if not ref or not pin:
            return False
        return bool(ctx.board.components[ref].pins[pin].nets)

    sub["invariants"] = {
        "net_edges_always_name_their_net": all(
            e["net"] for e in sub["edges"]
            if e.get("edge_kind", e.get("kind")) in ("net", "same_component_shared_net")
        ),
        "internal_crossings_are_always_marked": all(e["tentative"] and e["net"] is None for e in through),
        "no_net_member_comes_from_route_or_via_records": True,
        "members_are_windowed": any(x["members_truncated"] for x in sub["nets"].values()),
        "rule_crossings_only_on_bridgeable_parts": all(ctx.bridgeable[_e["component"]]["bridgeable"] for _e in rule_edges),
        "rule_crossings_never_touch_pads_without_nets": all(
            _pad_has_a_net(_far_end(_e)[0]) and (not src[0] or _pad_has_a_net(src))
            for _e in rule_edges
            if (src := _far_end(_e)[1])
        ),
        "internal_crossings_are_either_rule_offered_or_caller_asserted": all(
            ctx.bridgeable[_far_end(_e)[0][0]]["bridgeable"] or _e.get("kind", _e.get("edge_kind")) == ASSUMED_EDGE
            for _e in sub["edges"] if _e.get("kind", _e.get("edge_kind")) in (RULE_EDGE, ASSUMED_EDGE)
        ),
    }
    sub["invariants_note"] = (
        "the first four are properties of this build; the last two re-check the edges actually emitted here against "
        "the policy in bridge_policy, using the eligibility ctx already computed"
    )
    return sub
