"""Electrical connectivity graph over parsed GenCAD data.

Four relationship layers, deliberately never conflated - a claim must say which one it comes from:

* ``net`` - two pads listed under one ``SIGNAL`` share a logical connection (a fact stated in the file).
* ``same_component_shared_net`` - several pads of ONE component sit on one net (e.g. J15 6/7/8 on
  ``12V_PEX6_8_INP``). Parsed fact about that component; says nothing about its other pads.
* ``inferred_crossing_asserted_by_caller`` (``ASSUMED_EDGE``) - the CALLER (i.e. the model) states that
  pad A of a component continues to pad B inside it, with a reason. The file never states this, so the
  edge carries ``tentative: True``, the caller's label, and the component it crosses. This is the layer
  the model owns: geometry and names are exposed so it can reason, and the conclusion comes back
  attributed to the caller wherever it is used.
* ``inferred_crossing_from_name_rules`` (``RULE_EDGE``) - the server's own name-shape hint, offered only
  for shapes whose names usually do imply a through-path: exactly two net-carrying pads on a passive-looking
  name, or a SHAPE/DEVICE name containing VIRTUAL (the file's own word for a stand-in the drawing does not
  draw). A reading of the NAME, not knowledge about the part - prefer to reach your own conclusion through
  :meth:`tools.evaluate_crossing` and pass it back as ``assumed_bridges``.

Nothing here is ever a claim about a component's function: :func:`boardview_mcp.classify.classify_component`
only produces labelled guesses, and guesses never become facts by being used in a traversal.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

from .models import Board
from .classify import PASSIVE_KINDS, PLACEHOLDER_KINDS, classify_component

Node = Tuple[str, str]  # (component ref, pin name)

MEMBER_WINDOW_MAX = 500  # hard ceiling for the per-net member window in :meth:`ConnectivityGraph.subgraph`
NET_EDGE = "net"  # the two pads are listed under one SIGNAL: a fact stated in the file
SHARED_NET_EDGE = "same_component_shared_net"  # two pads of one component on one SIGNAL: also a file fact
RULE_EDGE = "inferred_crossing_from_name_rules"  # the server's own name-shape hypothesis
ASSUMED_EDGE = "inferred_crossing_asserted_by_caller"  # the caller's (the model's) own conclusion


def _clamp(value: object, lo: int, hi: int) -> int:
    try:
        n = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))

def _chain_key(chain: list[dict]) -> tuple:
    """Hashable identity for a route: per hop, (entry component/pin, exit component/pin, net, edge kind).

    The entry terminal is part of the key on purpose. Two BFS runs (fewest crossings, fewest internal
    crossings) often reach the same target through the same two-terminal component but at *different*
    terminals; without the entry terminal those two routes collapse to one key, :meth:`paths_between`
    drops the alternate route, and the remaining one can be mislabelled as asserted-only.
    """
    return tuple(
        (
            h.get("from", {}).get("component"),
            h.get("from", {}).get("pin"),
            h["component"],
            h["pin"],
            h["net"],
            h["kind"],
        )
        for h in chain[1:]
    )


BRIDGE_POLICY_NOTE = (
    "internal crossings are only ever hypotheses or caller assertions, never file facts; two rule-based "
    "sub-rules create edges of kind=inferred_crossing_from_name_rules and tentative=true: "
    "(1) exactly two declared pads, both carrying nets, and an inferred passive kind "
    "(capacitor/inductor/ferrite_bead/resistor/fuse); "
    "(2) the component's own SHAPE/DEVICE name marks it as a placeholder for a connection the drawing "
    "does not make (kind virtual_placeholder, e.g. SHAPE RSENSE_VIRTUAL_04_SMD_2512 or SHAPE VIRTUAL_SHORT) - "
    "the file says the stand-in is there but never says which pads face each other, so each pad pairing is "
    "offered as a labelled hypothesis. "
    "Everything else is refused by the rules: active or structural kinds (integrated_circuit, connector, "
    "test_point, mounting_hole) are NEVER crossed internally - each pad is re-entered through its own net - "
    "and a passive component with more than two net-carrying pads is refused because naming the pairing would "
    "invent electrical facts. Either way the caller may assert a specific crossing through assumed_bridges, "
    "which yields kind=inferred_crossing_asserted_by_caller: the caller's knowledge, still not file evidence. "
    "Pad coordinates, distances and the words in SHAPE/DEVICE names are exposed by tools.get_component so the "
    "caller can reason instead of guessing. ROUTE/VIA records are drawing data and never take part in connectivity."
)


def _validate_assumptions(graph: "ConnectivityGraph", raw: Sequence[object]) -> tuple[dict, list[dict], list[dict]]:
    """Normalise caller assumptions into ``{ref: [(pinA, pinB, label)]}`` plus accepted/rejected breakdowns."""
    mapping: dict[str, list[tuple[str, str, str]]] = {}
    accepted: list[dict] = []
    rejected: list[dict] = []
    for item in raw or ():
        if not isinstance(item, dict):
            rejected.append({"assumption": str(item), "why": "not an object"})
            continue
        ref = item.get("component")
        pins = item.get("pins") or []
        label = str(item.get("label") or item.get("why") or "")
        comp = graph.board.components.get(ref) if isinstance(ref, str) else None
        if comp is None:
            rejected.append({"assumption": str(ref), "why": "unknown component reference"})
            continue
        if not isinstance(pins, list) or len(pins) != 2 or any(not isinstance(x, str) for x in pins):
            rejected.append({"assumption": str(ref), "why": "pins must be exactly two pin names"})
            continue
        a, b = pins
        if a not in comp.pins or b not in comp.pins:
            rejected.append({"assumption": f"{ref}:{a}/{b}",
                             "why": f"pin names not declared for {ref} (known: {', '.join(sorted(comp.pins))})"})
            continue
        if not graph.pin_nets.get((ref, a)) or not graph.pin_nets.get((ref, b)):
            rejected.append({"assumption": f"{ref}:{a}/{b}",
                             "why": "one of the two pins carries no net, so there is nothing to cross"})
            continue
        mapping.setdefault(ref, []).append((a, b, label))
        accepted.append({"component": ref, "pins": [a, b], "label": label})
    return mapping, accepted, rejected


class ConnectivityGraph:
    """Bipartite incidence structure: component-pin nodes, net hyperedges."""

    def __init__(self, board: Board) -> None:
        self.board = board
        self.net_pins: dict[str, list[Node]] = {}
        self.pin_nets: dict[Node, list[str]] = {}
        self.bridge_policy_note: str = BRIDGE_POLICY_NOTE
        self._kind_cache: dict[str, dict] = {}
        self._assumed: dict[str, list[tuple[str, str, str]]] = {}  # caller-asserted internal crossings
        self._assumed_rejected: list[dict] = []
        for net_name, net in board.nets.items():
            members = list(net.members)
            self.net_pins[net_name] = members
            for node in members:
                self.pin_nets.setdefault(node, []).append(net_name)

    # ------------------------------------------------------------ lookups

    def pins_of(self, ref: str) -> list[str]:
        comp = self.board.components.get(ref)
        return sorted(comp.pins) if comp else []

    def members(self, net_name: str) -> list[Node]:
        return list(self.net_pins.get(net_name, []))

    def nets_of(self, ref: str, pin: str | None = None) -> list[str]:
        if pin is not None:
            return list(self.pin_nets.get((ref, pin), []))
        out: list[str] = []
        for name in sorted(self.pins_of(ref)):
            for net_name in self.pin_nets.get((ref, name), []):
                if net_name not in out:
                    out.append(net_name)
        return out

    def components_on(self, net_name: str) -> list[str]:
        seen: list[str] = []
        for ref, _pin in self.members(net_name):
            if ref not in seen:
                seen.append(ref)
        return seen

    # ------------------------------------------------------------ net (parsed) edges

    def direct_neighbours(self, ref: str, pin: str) -> list[dict]:
        """Other pins on this pin's nets, in file order, each with its net as evidence."""
        out: list[dict] = []
        for net_name in self.pin_nets.get((ref, pin), []):
            for other_ref, other_pin in self.net_pins[net_name]:
                if (other_ref, other_pin) == (ref, pin):
                    continue
                out.append(
                    {
                        "component": other_ref,
                        "pin": other_pin,
                        "net": net_name,
                        "same_component": other_ref == ref,
                        "kind": "same_component_shared_net" if other_ref == ref else "net",
                        "tentative": False,
                    }
                )
        return out

    def _kind_info(self, ref: str) -> dict:
        """Memoised :func:`classify_component` result. Classification is a property of a component, so it
        is computed once per reference - never per candidate edge inside a traversal."""
        cached = self._kind_cache.get(ref)
        if cached is None:
            comp = self.board.components.get(ref)
            cached = classify_component(comp, self.board.devices) if comp else {"kind": None, "basis": [], "inferred": False}
            self._kind_cache[ref] = cached
        return cached

    # ------------------------------------------------------------ tentative bridging policy

    def set_assumed_bridges(self, assumptions: Sequence[dict]) -> dict:
        """Register caller-asserted internal crossings. The file never states these, so edges built
        from them are labelled ``inferred_crossing_asserted_by_caller`` and stay ``tentative: true``.

        Each item: ``{"component": REF, "pins": [PIN_A, PIN_B], "label": "why the caller believes it"}``.
        Returns ``{"accepted": [...], "rejected": [...]}`` so a tool can report exactly what was taken.
        """
        mapping, accepted, rejected = _validate_assumptions(self, assumptions)
        self._assumed = mapping
        self._assumed_rejected = rejected
        return {"accepted": accepted, "rejected": rejected}

    def assumed_bridges(self) -> dict:
        """Currently registered caller assumptions, as a JSON-friendly breakdown."""
        return {
            "assumed": [{"component": ref, "pins": [a, b], "label": label} for ref, (a, b, label) in
                        ((r, trip) for r, trips in self._assumed.items() for trip in trips)],
            "rejected": list(self._assumed_rejected),
        }

    def _assumed_for(self, ref: str) -> list[dict]:
        """Caller-asserted crossings recorded for ``ref`` (never file evidence)."""
        return [{"component": ref, "pins": [a, b], "label": lbl} for a, b, lbl in self._assumed.get(ref, [])]

    def bridge_eligibility(self, ref: str) -> dict:
        """Does this component have a through-path on the server's name-shape hint? Always labelled.

        Two offer sub-rules (passive two-pad parts, ``virtual_placeholder`` names) and three refusal
        reasons (active/structural kind, fewer than two net-carrying pads, more than two net-carrying
        pads on a passive part). A refusal is a refusal to OFFER a hint, not a claim that the part is
        not connected: the caller can still assert a specific crossing through ``assumed_bridges``
        (see :meth:`set_assumed_bridges`).
        """
        comp = self.board.components.get(ref)
        if comp is None:
            return {"bridgeable": False, "reason": "unknown component reference", "inferred": False}
        declared = sorted(comp.pins)
        connected = sorted(name for name in declared if self.pin_nets.get((ref, name)))
        info = self._kind_info(ref)
        if info["kind"] not in PASSIVE_KINDS and info["kind"] not in PLACEHOLDER_KINDS:
            return {
                "bridgeable": False,
                "reason": f"inferred kind {info['kind']!r} is active/structural, not a passive terminal pair",
                "inferred_kind": info["kind"],
                "kind_basis": info["basis"],
                "terminals": connected[:2],
                "pin_count_declared": len(declared),
                "inferred": True,
                "assumed_bridges": self._assumed_for(ref),
            }
        if len(connected) < 2:
            return {
                "bridgeable": False,
                "reason": f"{len(connected)} pins with nets: nothing to cross between",
                "inferred_kind": info["kind"],
                "kind_basis": info["basis"],
                "terminals": connected,
                "pin_count_declared": len(declared),
                "inferred": True,
                "assumed_bridges": self._assumed_for(ref),
            }
        if info["kind"] in PLACEHOLDER_KINDS:
            rule = (
                "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection "
                "the file does not draw, so crossings between its pads are offered; the pairing of the pads is not "
                "stated in the file, so each pairing is a hypothesis"
            )
        elif len(connected) > 2:
            return {
                "bridgeable": False,
                "reason": f"passive kind but {len(connected)} pins carry nets: which pads face each other is not in the file "
                          "and guessing a pairing would invent electrical facts; ask the caller to assert a specific crossing "
                          "(assumed_bridges) or rely on the file-only route that enters and leaves at named pins",
                "inferred_kind": info["kind"],
                "kind_basis": info["basis"],
                "terminals": connected,
                "pin_count_declared": len(declared),
                "pin_count_connected": len(connected),
                "inferred": True,
                "assumed_bridges": self._assumed_for(ref),
            }
        else:
            rule = "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind"
        return {
            "bridgeable": True,
            "reason": rule,
            "rule": rule,
            "inferred_kind": info["kind"],
            "kind_basis": info["basis"],
            "terminals": connected,
            "pin_count_declared": len(declared),
            "pin_count_connected": len(connected),
            "pairings": len(connected) * (len(connected) - 1) // 2,
            "inferred": True,
            "note": (
                "tentative: the file never states an internal connection; a path through this component is a "
                "hypothesis to verify against the physical board or the schematic"
            ),
            "assumed_bridges": self._assumed_for(ref),
        }

    def bridge_neighbours(self, ref: str, pin: str, assumed: dict | None = None) -> list[dict]:
        """Internal crossings for ``pin``: caller-asserted pairs first, then the rule-based ones.

        ``assumed=None`` means "use whatever this graph already holds"; traversal methods pass an
        explicit mapping so a single shared graph can serve concurrent requests with different
        assumptions without cross-talk.
        """
        elig = self.bridge_eligibility(ref)
        out: list[dict] = []
        asserted_targets: set[str] = set()
        for a, b, label in (self._assumed if assumed is None else assumed).get(ref, ()):
            if pin not in (a, b):
                continue
            other = a if pin == b else b
            asserted_targets.add(other)
            out.append(
                {
                    "component": ref,
                    "pin": other,
                    "net": None,
                    "same_component": True,
                    "kind": ASSUMED_EDGE,
                    "tentative": True,
                    "intervening_component": ref,
                    "asserted_by": "caller (the file never states this crossing)",
                    "asserted_label": label,
                    "eligibility": {**elig, "assumed_pair": [a, b]},
                    "also_rule_offered": bool(elig["bridgeable"]) and bool(self.pin_nets.get((ref, other))),
                }
            )
        if not elig["bridgeable"]:
            return out
        for other in self.pins_of(ref):
            if other == pin or other in asserted_targets or not self.pin_nets.get((ref, other)):
                continue
            out.append(
                {
                    "component": ref,
                    "pin": other,
                    "net": None,
                    "same_component": True,
                    "kind": RULE_EDGE,
                    "tentative": True,
                    "intervening_component": ref,
                    "inferred_kind": elig.get("inferred_kind"),
                    "kind_basis": elig.get("kind_basis", []),
                    "eligibility": elig,
                }
            )
        return out

    def neighbours(
        self, ref: str, pin: str, *, allow_bridges: bool = True, assumed: dict | None = None
    ) -> list[dict]:
        edges = self.direct_neighbours(ref, pin)
        if allow_bridges:
            edges.extend(self.bridge_neighbours(ref, pin, assumed))
        return edges

    # ------------------------------------------------------------ traversal

    def seeds(self, start: Sequence[tuple[str, str | None]]) -> list[Node]:
        out: list[Node] = []
        for ref, pin in start:
            comp = self.board.components.get(ref)
            if comp is None:
                continue
            for name in [pin] if pin else self.pins_of(ref):
                if self.pin_nets.get((ref, name)) and (ref, name) not in out:
                    out.append((ref, name))
        return out

    def trace(
        self,
        start: Sequence[tuple[str, str | None]],
        *,
        max_depth: int = 3,
        assumed_bridges: Sequence[object] | None = None,
        max_nodes: int = 500,
        allow_bridges: bool = True,
        only_refs: Sequence[str] | None = None,
        only_kinds: Sequence[str] | None = None,
        exclude_refs: Sequence[str] | None = None,
        exclude_nets: Sequence[str] | None = None,
        per_net_window: int = 12,
    ) -> dict:
        """Breadth-first expansion. Depth counts component->component hops; edges keep evidence.

        ``per_net_window`` caps how many members of ONE net are followed from any single pin. Without it a
        net like GND (2858 members on this board) swallows the whole node budget at depth 1 and the walk never
        reaches the components the caller actually asked about; the cap is reported (``nets_windowed``) rather
        than hidden, and get_net still lists every member with pagination. 0 disables the cap.
        """
        wanted = set(only_refs) if only_refs else None
        kinds = set(only_kinds) if only_kinds else None
        drop_refs = set(exclude_refs or ())
        drop_nets = set(exclude_nets or ())
        assumed_map = _validate_assumptions(self, assumed_bridges)[0] if assumed_bridges else None
        frontier = self.seeds(start)
        truncated = False
        if len(frontier) > max_nodes:
            frontier = frontier[:max_nodes]
            truncated = True
        visited = set(frontier)
        nodes = [{"component": r, "pin": p, "depth": 0, "nets": self.pin_nets.get((r, p), [])} for r, p in frontier]
        windowed: set[str] = set()
        edges: list[dict] = []
        budget_hit = False
        depth = 0
        while frontier and depth < max_depth and not budget_hit:
            depth += 1
            nxt: list[Node] = []
            for ref, pin in frontier:
                per_net: dict[str, int] = {}
                for edge in self.neighbours(ref, pin, allow_bridges=allow_bridges, assumed=assumed_map):
                    if budget_hit:
                        break
                    if edge["net"] in drop_nets:
                        continue
                    if per_net_window and edge["net"] is not None:
                        count = per_net.get(edge["net"], 0)
                        if count >= per_net_window:
                            windowed.add(edge["net"])
                            continue
                        per_net[edge["net"]] = count + 1
                    target = (edge["component"], edge["pin"])
                    if target[0] in drop_refs:
                        continue
                    if wanted and target[0] not in wanted:
                        continue
                    if kinds and self._kind_info(target[0])["kind"] not in kinds:
                        continue
                    if len(nodes) >= max_nodes or len(edges) >= 4 * max_nodes:
                        budget_hit = True
                        break
                    rec = dict(edge)
                    rec["from"] = {"component": ref, "pin": pin}
                    rec["depth"] = depth
                    edges.append(rec)
                    if target in visited:
                        continue
                    visited.add(target)
                    nodes.append({
                        "component": target[0],
                        "pin": target[1],
                        "depth": depth,
                        "nets": self.pin_nets.get(target, []),
                    })
                    nxt.append(target)
            frontier = nxt
        return {
            "seed_nodes": [{"component": r, "pin": p} for r, p in self.seeds(start)],
            "nodes": nodes,
            "edges": edges,
            "max_depth": max_depth,
            "visited_components": sorted({n["component"] for n in nodes}),
            "nets_touched": sorted({e["net"] for e in edges if e["net"]}),
            "tentative_edges": sum(1 for e in edges if e.get("tentative")),
            "assumed_edges": sum(1 for e in edges if e["kind"] == ASSUMED_EDGE),
            "nets_windowed": sorted(windowed),
            "net_fanout": self._net_fanout(edges, top=6),
            "net_window_note": (
                f"per_net_window={per_net_window}: some members of these nets were not followed from a given pin "
                "because one net (usually GND) has thousands of members; use get_net for the complete member list"
                if windowed else None
            ),
            "truncated": truncated or budget_hit,
        }

    def _bfs_paths(
        self,
        seeds: list[Node],
        targets: set[str],
        *,
        allow_bridges: bool,
        cost: str = "hops",
        max_pops: int = 20000,
        max_len: int = 0,
        exclude_refs: set[str] | None = None,
        exclude_nets: set[str] | None = None,
        assumed: dict | None = None,
    ) -> dict[str, list[dict] | bool]:
        """One route per target component. ``cost='hops'`` = fewest crossings; ``cost='tentative'`` = fewest
        internal-crossing hops, so an all-asserted route is preferred when one exists. Routes are never
        enumerated exhaustively (that is combinatorial); ``max_len`` caps hops per route and ``max_pops``/
        ``max_pushes`` cap the search, all reported through ``truncated``.
        """
        import heapq

        dist: dict[Node, float] = {}
        depth_of: dict[Node, int] = {}
        parent: dict[Node, tuple[Node | None, dict | None]] = {}
        heap: list[tuple[float, int, Node]] = []
        counter = 0
        for seed in seeds:
            node = (seed[0], seed[1])
            if node in dist:
                continue
            dist[node] = 0.0
            depth_of[node] = 0
            parent[node] = (None, None)
            heap.append((0.0, counter, node))
            counter += 1
        heapq.heapify(heap)
        found: dict[str, Node] = {}
        popped = pushed = 0
        truncated = False
        max_pushes = 8 * max_pops
        stop = False
        while heap and not stop:
            d, _, node = heapq.heappop(heap)
            if d > dist.get(node, d):
                continue  # stale entry from an earlier relaxation
            popped += 1
            if popped > max_pops:
                truncated = True
                break
            ref, pin = node
            if ref in targets and parent[node][0] is not None:
                found.setdefault(ref, node)
                if len(found) >= len(set(targets)):
                    break  # every requested target has a route
                # NB: still expanded below. A target is only terminal for ITS OWN route; a
                # second target may sit behind this one (J15 -> L45 -> ... -> U7), so refusing
                # to pass through targets would silently drop that route.
            depth = depth_of[node]
            if max_len and depth >= max_len:
                continue  # never extend a route past the hop limit the caller intends to report
            for edge in self.neighbours(ref, pin, allow_bridges=allow_bridges, assumed=assumed):
                nxt = (edge["component"], edge["pin"])
                if nxt == node:
                    continue
                if exclude_refs and edge["component"] in exclude_refs:
                    continue
                if exclude_nets and edge.get("net") in exclude_nets:
                    continue  # a huge common net (usually GND) can swamp the search

                step = 1.0 if cost == "hops" else (1.0 if edge["kind"] == RULE_EDGE else 0.0)
                nd = d + step
                if max_len and depth + 1 > max_len:
                    continue
                if nd >= dist.get(nxt, float("inf")):
                    continue  # only strictly better distances are worth re-pushing
                dist[nxt] = nd
                depth_of[nxt] = depth + 1
                parent[nxt] = (node, dict(edge, **{"from": {"component": ref, "pin": pin}, "depth": depth + 1}))
                pushed += 1
                if pushed > max_pushes:
                    truncated = True
                    stop = True
                    break
                heap.append((nd, counter, nxt))
                counter += 1
        paths: dict[str, list[dict]] = {}
        for ref, node in found.items():
            hops: list[dict] = []
            cur: Node | None = node
            while parent[cur][1] is not None:
                hops.append(parent[cur][1])
                cur = parent[cur][0]
            hops.reverse()
            paths[ref] = hops
        return {"paths": paths, "truncated": truncated}

    def paths_between(
        self,
        start: Sequence[tuple[str, str | None]],
        target_refs: Sequence[str],
        *,
        max_paths: int = 20,
        max_hops: int = 8,
        allow_bridges: bool = True,
        max_pops: int = 20000,
        exclude_refs: Sequence[str] | None = None,
        exclude_nets: Sequence[str] | None = None,
        per_net_window: int = 12,
        assumed_bridges: Sequence[object] | None = None,
    ) -> dict:
        """Candidate paths: the fewest-crossing route and (when bridges are allowed) the route with
        the fewest internal-crossing hops. Both are labelled per hop; nothing is silently asserted."""
        seeds = self.seeds(start)
        targets = set(target_refs)
        drop_refs = {r for r in (exclude_refs or ()) if r not in targets}
        drop_nets = set(exclude_nets or ())
        routes: list[list[dict]] = []
        labels: list[str] = []
        seen_keys: set[tuple] = set()
        truncated = False
        assumed_map = _validate_assumptions(self, assumed_bridges)[0] if assumed_bridges else None
        primary = self._bfs_paths(seeds, targets, allow_bridges=allow_bridges, cost="hops", max_pops=max_pops, max_len=max_hops, assumed=assumed_map, exclude_refs=drop_refs, exclude_nets=drop_nets)
        truncated |= primary["truncated"]
        for ref in sorted(primary["paths"]):
            hops = primary["paths"][ref]
            if len(hops) <= max_hops:
                routes.append(hops)
                labels.append("fewest component crossings")
                seen_keys.add(_chain_key(hops))
        if allow_bridges:
            alt = self._bfs_paths(seeds, targets, allow_bridges=True, cost="tentative", max_pops=max_pops, max_len=max_hops, assumed=assumed_map, exclude_refs=drop_refs, exclude_nets=drop_nets)
            truncated |= alt["truncated"]
            for ref in sorted(alt["paths"]):
                hops = alt["paths"][ref]
                if len(hops) <= max_hops and _chain_key(hops) not in seen_keys:
                    routes.append(hops)
                    labels.append("fewest internal-crossing hops")
                    seen_keys.add(_chain_key(hops))
        strict = (
            self._bfs_paths(seeds, targets, allow_bridges=False, cost="hops", max_pops=max_pops, max_len=max_hops, assumed=assumed_map, exclude_refs=drop_refs, exclude_nets=drop_nets)
            if allow_bridges
            else primary
        )
        truncated |= strict["truncated"]
        strict_keys = {_chain_key(h) for h in strict["paths"].values() if len(h) <= max_hops}
        out: list[dict] = []
        for hops, label in zip(routes, labels):
            out.append(
                {
                    "target": hops[-1]["component"],
                    "hops": hops,
                    "label": label,
                    "asserted_only": _chain_key(hops) in strict_keys,
                    "hops_count": len(hops),
                    "tentative_hops": sum(1 for h in hops if h["kind"] != "net"),
                    "caller_asserted_hops": sum(1 for h in hops if h["kind"] == ASSUMED_EDGE),
                    "intervening_components": sorted({h["component"] for h in hops if h["kind"] != "net"}),
                    "nets_in_order": [h["net"] for h in hops if h["net"]],
                }
            )
        out.sort(key=lambda p: (p["tentative_hops"], p["hops_count"]))
        return {
            "paths": out[: _clamp(max_paths, 1, 100)],
            "seed_nodes": [{"component": r, "pin": p} for r, p in seeds],
            "target_refs": sorted(targets),
            "max_paths": max_paths,
            "max_hops": max_hops,
            "truncated": truncated,
            "route_labels_note": (
                "each route states how it was chosen; tentative_hops>0 means at least one internal crossing"
            ),
            "asserted_only_note": (
                "asserted_only=true means the same route also exists without crossing any component internally"
                if allow_bridges
                else "bridges were not requested, so every route here is already bridge-free by construction"
            ),
        }


    def _net_fanout(self, edges: list[dict], *, top: int = 6) -> list[dict]:
        """Biggest nets the walk touched, with how often the walk followed them.

        The point is to make the cost visible: one net (usually GND) carries most of the members, so a
        bounded walk spends most of its budget on it and a caller can then choose to exclude it. Counts
        only net edges (kind == "net"), which are the file-fact hops.
        """
        counts: dict[str, int] = {}
        for edge in edges:
            if edge["kind"] == "net" and edge["net"]:
                counts[edge["net"]] = counts.get(edge["net"], 0) + 1
        return [
            {"net": n, "members_on_net": len(self.net_pins.get(n, ())), "times_followed": c}
            for n, c in sorted(counts.items(), key=lambda kv: (-len(self.net_pins.get(kv[0], ())), kv[0]))[:top]
        ]

    def shared_nets(self, refs: Sequence[str], *, exclude_nets: set[str] | None = None) -> dict:
        """Which nets are shared by which of the given components (rails/fan-in view).
        `exclude_nets` drops rails the caller does not care about; the dropped names are reported back so
        the caller can see that a rail such as GND (2858 members here) was skipped, not absent."""
        drop = set(exclude_nets or ())
        per_net: dict[str, list[str]] = {}
        for ref in refs:
            for net_name in self.nets_of(ref):
                per_net.setdefault(net_name, []).append(ref)
        dropped = sorted(n for n in per_net if n in drop)
        for n in dropped:
            del per_net[n]
        shared = {n: list(rs) for n, rs in per_net.items() if len(rs) > 1}
        return {
            "requested_refs": list(refs),
            "shared_nets": shared,
            "pairwise": dict(shared),
            "net_sizes": {n: len(self.net_pins.get(n, ())) for n in shared},
            "excluded_nets": dropped,
            "excluded_note": (
                f"{n} is shared by these components but was excluded by the caller; the net itself still "
                f"exists with {len(self.net_pins.get(n, ()))} members - ask for it with exclude_nets=[]."
                for n in dropped
            ),
        }

    def subgraph(
        self,
        start: Sequence[tuple[str, str | None]],
        *,
        depth: int = 2,
        max_nodes: int = 300,
        allow_bridges: bool = True,
        include_geometry: bool = True,
        max_members_per_net: int = 100,
        assumed_bridges: Sequence[object] | None = None,
        exclude_refs: set[str] | None = None,
        exclude_nets: set[str] | None = None,
        per_net_window: int = 12,
    ) -> dict:
        """Exportable neighbourhood: components, their pin->net maps, and the nets that touch them.

        `exclude_nets` / `exclude_refs` drop whole nets/components from the walk before it starts
        (the caller says so, the file never does) and `per_net_window` caps how many members of
        one net are followed from a given pin. Every exclusion is echoed back so the caller can
        see what left the model's view.
        """
        drop_refs = set(exclude_refs or ())
        drop_nets = set(exclude_nets or ())
        walk = self.trace(start, max_depth=depth, max_nodes=max_nodes, allow_bridges=allow_bridges,
                          assumed_bridges=assumed_bridges, exclude_refs=drop_refs,
                          exclude_nets=drop_nets, per_net_window=per_net_window)
        refs = sorted({n["component"] for n in walk["nodes"]})
        net_names = sorted(
            {n for rec in walk["nodes"] for n in rec["nets"]} | {e["net"] for e in walk["edges"] if e["net"]}
        )
        net_names = [n for n in net_names if n not in drop_nets]
        components = {}
        for ref in refs:
            comp = self.board.components[ref]
            components[ref] = {
                "ref": ref,
                "package": comp.package,
                "device": comp.device,
                "pins": {
                    name: {
                        "nets": p.nets,
                        "padstack": p.padstack,
                        "declared_by_shape": p.declared_by_shape,
                        "connected": p.connected,
                        **({"x": p.x, "y": p.y, "layer": p.layer} if include_geometry else {}),
                    }
                    for name, p in comp.pins.items()
                },
            }
        nets = {}
        for name in net_names:
            members = self.net_pins.get(name, [])
            window = _clamp(max_members_per_net, 1, MEMBER_WINDOW_MAX)
            nets[name] = {
                "name": name,
                "member_count": len(members),
                "members": [{"component": r, "pin": p} for r, p in members[:window]],
                "members_truncated": len(members) > window,
            }
        return {
            "components": components,
            "nets": nets,
            "nodes": walk["nodes"],
            "edges": walk["edges"],
            "counts": {"components": len(components), "nets": len(nets), "edges": len(walk["edges"])},
            "truncated": walk["truncated"],
            "excluded_nets": sorted(drop_nets),
            "excluded_components": sorted(drop_refs),
            "net_fanout": walk.get("net_fanout", []),
            "nets_windowed": walk.get("nets_windowed", []),
            "net_window_note": walk.get("net_window_note", ""),
        }
