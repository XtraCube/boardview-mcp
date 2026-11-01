"""MCP server (v2 SDK, Streamable HTTP): registers the nine read-only boardview tools.

The board file is parsed once, in :func:`build_server`, before any tool is callable; the same
:class:`BoardContext` instance backs every request.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from .context import BoardContext
from . import tools as _t

CTX: BoardContext | None = None  # created once by build_server()/cli


def _require_ctx() -> BoardContext:
    if CTX is None:
        raise RuntimeError("server context not initialised - call build_server(board_path) first")
    return CTX


# ---------------------------------------------------------------------- thin, schema-bearing wrappers
# `ctx` is never a parameter: the parsed board is bound at startup, so the model only sees
# board-level arguments.


def _board_summary() -> Dict:
    return _t.board_summary(_require_ctx())


def _search_components(query: str, field: str = "all", kind: Optional[str] = None, limit: int = 25, offset: int = 0) -> Dict:
    return _t.search_components(_require_ctx(), query, field=field, kind=kind, limit=limit, offset=offset)


def _get_component(ref: str, include_pins: bool = True) -> Dict:
    return _t.get_component(_require_ctx(), ref, include_pins=include_pins)


def _get_net(name: str, offset: int = 0, limit: int = 100) -> Dict:
    return _t.get_net(_require_ctx(), name, offset=offset, limit=limit)


def _find_connected_components(component: Optional[str] = None, net: Optional[str] = None, pin: Optional[str] = None, depth: int = 1, allow_bridges: bool = True, limit: int = 100, offset: int = 0, exclude_nets: Optional[List[str]] = ["GND"], exclude_components: Optional[List[str]] = None, assumed_bridges: Optional[List[Dict]] = None) -> Dict:
    return _t.find_connected_components(_require_ctx(), component=component, net=net, pin=pin, depth=depth, allow_bridges=allow_bridges, limit=limit, offset=offset, exclude_nets=exclude_nets, exclude_components=exclude_components, assumed_bridges=assumed_bridges)


def _trace_connectivity(start: List[Dict], max_depth: int = 2, max_nodes: int = 200, allow_bridges: bool = True, only_refs: Optional[List[str]] = None, only_kinds: Optional[List[str]] = None, exclude_refs: Optional[List[str]] = None, exclude_nets: Optional[List[str]] = ["GND"], per_net_window: int = 12, assumed_bridges: Optional[List[Dict]] = None) -> Dict:
    return _t.trace_connectivity(_require_ctx(), start, max_depth=max_depth, max_nodes=max_nodes, allow_bridges=allow_bridges, only_refs=only_refs, only_kinds=only_kinds, exclude_refs=exclude_refs, exclude_nets=exclude_nets, per_net_window=per_net_window, assumed_bridges=assumed_bridges)


def _trace_power_path(start: List[Dict], target_components: List[str], max_paths: int = 8, max_hops: int = 6, allow_bridges: bool = True, exclude_nets: Optional[List[str]] = ["GND"], exclude_components: Optional[List[str]] = None, assumed_bridges: Optional[List[Dict]] = None) -> Dict:
    return _t.trace_power_path(_require_ctx(), start, target_components, max_paths=max_paths, max_hops=max_hops, allow_bridges=allow_bridges, exclude_nets=exclude_nets, exclude_components=exclude_components, assumed_bridges=assumed_bridges)


def _find_shared_rails(components: List[str], detail_limit: int = 40, exclude_nets: Optional[List[str]] = ["GND"], exclude_components: Optional[List[str]] = None) -> Dict:
    return _t.find_shared_rails(_require_ctx(), components, detail_limit=detail_limit, exclude_nets=exclude_nets, exclude_components=exclude_components)


def _export_subgraph(start: List[Dict], depth: int = 2, max_nodes: int = 200, allow_bridges: bool = True, include_geometry: bool = True, exclude_nets: Optional[List[str]] = ["GND"], exclude_components: Optional[List[str]] = None, assumed_bridges: Optional[List[Dict]] = None) -> Dict:
    return _t.export_subgraph(_require_ctx(), start, depth=depth, max_nodes=max_nodes, allow_bridges=allow_bridges, include_geometry=include_geometry, exclude_nets=exclude_nets, exclude_components=exclude_components, assumed_bridges=assumed_bridges)


def _evaluate_crossing(component: str, pins: List[str], reason: Optional[str] = None, detail_limit: int = 40) -> Dict:
    return _t.evaluate_crossing(_require_ctx(), component, pins, reason=reason, detail_limit=detail_limit)


TOOLS: Tuple[str, ...] = (
    "board_summary",
    "search_components",
    "get_component",
    "get_net",
    "find_connected_components",
    "trace_connectivity",
    "trace_power_path",
    "find_shared_rails",
    "export_subgraph",
    "evaluate_crossing",
)

DESCRIPTIONS = {
    "board_summary": "Board identity, section/record counts, units, bbox, parse errors/warnings and the connectivity model this server applies. Call once first.",
    "search_components": "Find components by exact/glob substring over ref/package/device/pins/nets/kind. Case-insensitive, paginated. Names returned are byte-exact from the file.",
    "get_component": "One component: exact position/rotation/side, every declared pin with its nets and padstack, which pins are connected vs declared-but-unconnected, nets shared by several of its own pins, plus labelled inferred kind and bridge eligibility.",
    "get_net": "One net (SIGNAL): every member pin in file order with pagination, members grouped per component, components contributing several pins, net size, duplicate NODE count. ROUTE/VIA drawing data is explicitly excluded from members.",
    "find_connected_components": "Immediate (or up to `depth`) neighbours of a component or net as evidence-carrying edges. Each edge names the SIGNAL that makes it true; `tentative` marks a hypothesis. Pass `pin` to anchor one terminal, `exclude_nets` (default GND) to cut the chassis rail, `exclude_components` to skip a component entirely (e.g. the filter you suspect), and `assumed_bridges` for internal crossings you know from outside the file.",
    "trace_connectivity": "Breadth-first connectivity walk from pins or nets with depth/node caps and filters (only_refs/only_kinds/exclude_refs/exclude_nets/per_net_window). Reports `net_fanout` (widest nets touched) and `nets_windowed` (nets whose members were only partly followed), so a truncated walk tells you what to exclude rather than silently missing.",
    "trace_power_path": "Candidate paths from a start (e.g. a connector pin) to named target components, labelled by evidence: file-asserted hops (shared SIGNAL), internal crossings offered by the bridge rules (hypothesis), and caller-asserted crossings (`assumed_bridges`, echoed as accepted/rejected). `exclude_components`/`exclude_nets` test the route while skipping a part you suspect. States per route whether the same route exists without internal crossings.",
    "find_shared_rails": "Which of the given components share nets (rails/fan-in): each rail names the net, its sharers, every pin of each sharer on that net and the net's total size. `exclude_nets` (default GND) keeps the chassis rail out of the result.",
    "export_subgraph": "Machine-readable neighbourhood: components with pin->net maps, the nets touching them, walk edges and invariants. For downstream analysis, not for display.",
    "evaluate_crossing": (
        "Settle one PROPOSED internal connection - the model says 'I think pad A of REF continues to pad B inside "
        "the part, because ...' - against the file. Returns what each pad carries, whether the file already states "
        "or contradicts the pair, whether the two rails are joined through other components, geometry and naming "
        "evidence with per-pad distances, and a ready-made assumed_bridges item carrying the model's reason. The "
        "tool never adds the crossing: the model owns that decision, and any edge built from it is labelled "
        "inferred_crossing_asserted_by_caller and stays tentative."
    ),
}

INSTRUCTIONS = """
You are inspecting a GenCAD 1.4 PCB boardview through read-only tools.
The board has ALREADY been parsed once at startup; every tool answers from that in-memory model.

VOCABULARY - use these words exactly when reasoning about results:
- component: a placed thing in $COMPONENTS ($COMPONENTS REF/SHAPE/DEVICE/PLACE/ROTATION/LAYER).
- net: one SIGNAL record in $SIGNALS; net names are byte-exact and are never renamed or merged.
- pin: a terminal of a component; declared by a SHAPE PIN record, or added when a NODE record named it.
- net member / edge: a (component, pin) listed inside one SIGNAL. Two net members of different
  components share that net - that is what "connected" means here.
- same_component_shared_net: several pins of ONE component listed in one net (real, e.g. a connector
  pin group). It says nothing about that component's other pins.
- tentative / hypothetical: a path that crosses a component internally. Always labelled, never silent.
- assumed_bridges: internal crossings YOU assert from outside the file (physical board, schematic). Each
  is echoed as accepted or rejected and builds edges labelled
  "inferred_crossing_asserted_by_caller". Use them for a part the rules refuse (e.g. a 4-pad sense block or
  an IC) but never present such an edge as file evidence.
- evidence: the exact net name (and file section) that supports a claim. Claims without evidence are
  labelled inferred and carry the reason.

CONNECTIVITY MODEL - four layers. Keep them apart in every claim; never blend one into another:
  1. FILE FACT (edge_kind="net", or "same_component_shared_net" for several pads of one part on one SIGNAL):
     both pads are listed inside one SIGNAL record. ONLY these edges are statements about the board, and a
     route built only from them is what "the file asserts" means here.
  2. STRUCTURE FACT (get_component -> "structure"): footprint extent, every pad coordinate, pad-to-pad
     distances, which pads of the part already carry the same SIGNAL, and the words the SHAPE/DEVICE names
     are built from. This is fact about the DRAWING and the NAMES - the format has no record that wires a
     component to itself, so this layer is what you reason over. It is never connectivity on its own.
  3. YOUR OWN CONCLUSION (edge_kind="inferred_crossing_asserted_by_caller", tentative=true): YOU say pad A
     of REF continues to pad B inside the part, and you give the reason. Pass it as
     assumed_bridges=[{"component":"REF","pins":["A","B"],"label":"<your reason>"}]; every item is echoed
     accepted/rejected and your label travels with the edge wherever it is used. The file cannot settle this
     layer and neither can I - you own it, so attribute it to yourself, not to the board.
  4. SERVER HINT (edge_kind="inferred_crossing_from_name_rules", tentative=true): a name-shape shortcut for
     the shapes whose names usually do imply a through-path - a part with exactly two net-carrying pads and a
     passive-looking name (filter, inductor, ferrite bead, resistor, fuse), or a SHAPE/DEVICE name containing
     VIRTUAL, the file's own word for a stand-in the drawing does not draw (RSENSE_VIRTUAL_04_SMD_2512). It is
     a reading of the NAME, not knowledge about the part: reach your own conclusion with evaluate_crossing and
     treat the hint as agreement to test, not as authority. When your conclusion and a hint coincide the edge
     says also_rule_offered=true.
  A part the hint refuses (an IC, a connector, G1 with 2714 pins, anything with three or more net-carrying
  pads and no VIRTUAL in its name) is not "unconnected": crossing one simply takes layer 3 instead of layer 4.
  allow_bridges=false asks the layer-1-only question, and its "no route" is exhaustive within max_hops.
- ROUTE/VIA/GEOMETRY records are drawing data: a waypoint is never an electrical member.
- GND is one SIGNAL with ~2858 members in this board: it is excluded by default in the traversal tools
  (exclude_nets defaults to ["GND"], and per_net_window caps how many members of one net one pin expands
  into). Re-call with exclude_nets=[] or a bigger window when you want the chassis rail, and read back
  excluded_nets / nets_windowed / net_fanout to see what the answer left out.

REASONING WORKFLOW for any internal connection (do it in this order):
  a. get_component(REF) and read "structure": pads, coordinates, distances, name vocabulary.
  b. evaluate_crossing(REF, [A, B], reason=...) - it reports whether the file already STATES the pair (both
     pads on one SIGNAL: no reasoning needed), whether the two rails are joined through some other component
     (then you do not need the crossing at all), what contradicts it, and a ready-made record_as object.
  c. if you accept the pair, pass that object in assumed_bridges on the next connectivity call.
  d. report the resulting chain hop by hop with its layer - "file" for layer 1, your label for layer 3 -
     never as one flat "these are connected" claim.

WORKFLOW:
1. board_summary first: counts, units, parse errors/warnings, inferred kinds.
2. search_components to find real refs/nets; a wrong guess returns similar candidates (refs AND nets).
3. get_component / get_net for exact evidence. Nets can be huge - check total_members/truncated, then re-call with offset.
4. trace_power_path for "does 12V from the connector reach X?" style questions: it separates layer-1 hops from
   crossing hops, counts them (tentative_hops, hypothesis_hops, caller_asserted_hops), states a per-route verdict,
   and says whether the same route exists without crossing any part.
5. trace_connectivity to enumerate an area; find_shared_rails to prove named components share a rail;
   export_subgraph for machine-readable neighbourhoods.
NEVER quote a net or pin name from memory: copy it from a tool result. Never report an inferred kind
as a fact: state the DEVICE/SHAPE basis and mark it inferred.
"""


def _resolve_path(board_path: str | None, env_var: str = "BOARDVIEW_FILE") -> str:
    if board_path:
        return board_path
    env = os.environ.get(env_var, "").strip()
    if env:
        return env
    raise SystemExit(
        "no board file: pass --board or set BOARDVIEW_FILE (a *.cad file holding GenCAD 1.4 data)"
    )


def build_server(board_path: str | None = None, *, env_var: str = "BOARDVIEW_FILE", max_bytes: int | None = None, name: str = "boardview", load: bool = True, context: BoardContext | None = None) -> object:
    """Parse the board once, then return a ready :class:`MCPServer` with all ten tools registered.

    ``load=False`` builds the server without parsing (for tool-schema inspection/tests).
    """
    global CTX
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    wrappers = {
        "board_summary": _board_summary,
        "search_components": _search_components,
        "get_component": _get_component,
        "get_net": _get_net,
        "find_connected_components": _find_connected_components,
        "trace_connectivity": _trace_connectivity,
        "trace_power_path": _trace_power_path,
        "find_shared_rails": _find_shared_rails,
        "export_subgraph": _export_subgraph,
        "evaluate_crossing": _evaluate_crossing,
    }
    if load:
        CTX = context if context is not None else BoardContext(_resolve_path(board_path, env_var), max_bytes=max_bytes)
    server = MCPServer(
        name=name,
        title="GenCAD boardview inspector",
        description="Read-only connectivity inspector for GenCAD 1.4 PCB boardviews.",
        instructions=INSTRUCTIONS,
    )
    for tool_name, fn in wrappers.items():
        server.add_tool(
            fn,
            name=tool_name,
            description=DESCRIPTIONS[tool_name],
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        )
    return server


def streamable_app(board_path: str | None = None, **kw) -> object:  # embedding helper: ASGI app for tests/mounting
    server = build_server(board_path, **kw)
    return server.streamable_http_app()


def run(board_path: str | None = None, *, host: str = "127.0.0.1", port: int = 8000, path: str = "/mcp", env_var: str = "BOARDVIEW_FILE", max_bytes: int | None = None, context: BoardContext | None = None) -> None:
    """Start the server on Streamable HTTP (default: 127.0.0.1:8000/mcp)."""
    server = build_server(board_path, env_var=env_var, max_bytes=max_bytes, context=context)
    server.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path=path,
        stateless_http=True,
    )
