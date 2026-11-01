# boardview-mcp

Read-only [MCP](https://modelcontextprotocol.io) server (Streamable HTTP) for inspecting **GenCAD 1.4**
PCB boardview files. It parses one board once, indexes
its pin/net connectivity, and exposes ten tools so a local AI can trace power paths with **exact pin
and net evidence** instead of guessing.

Nothing is written, moved, renamed, or re-drawn. Every reference, value, pin name, and net name you see
in a tool result is the byte-exact spelling from the file.

```
boardview-mcp/
├── docs/GENCAD_FORMAT.md      # what the parser was actually verified to read
├── src/boardview_mcp/
│   ├── models.py              # dataclasses: Board, Component, Pin, Net, Shape, Pad, Padstack, Device, Route, ParseError
│   ├── parser.py              # GenCAD 1.4 reader: tokenizer, logical lines, section state machine
│   ├── classify.py            # DEVICE/SHAPE heuristics -> inferred kind (labelled inferred, never asserted)
│   ├── graph.py               # bipartite connectivity graph + traversals, bridge policy
│   ├── context.py             # BoardContext: one parse + graph + classification indexes, name resolution
│   ├── tools.py               # the ten tool implementations (JSON-friendly dicts, provenance marks)
│   ├── server.py              # MCP server assembly: descriptions, annotations, instructions
│   ├── cli.py / __main__.py   # python -m boardview_mcp --board <file>
│   └── __init__.py            # public API: load_board, BoardContext, build_server, run, TOOLS, ...
└── tests/                     # parser, graph, tool, and live-HTTP tests + fixtures/minimal.cad, fixtures/malformed.cad
```

## Requirements

- Python **3.11 or newer** (the project is typed and packaged for >=3.11).
- [`mcp`](https://pypi.org/project/mcp/) **>= 2.0** — the official SDK, v2 API (`mcp.server.mcpserver.MCPServer`).
  Verified against **mcp 2.3.0**. There is no framework, no web UI, and no database here.
- Optional for the test suite: `pytest >= 8`.

## Install

From this directory (the package uses a `src/` layout, so an editable install is what you want):

```bash
cd boardview-mcp
python3 -m venv .venv && source .venv/activate       # PowerShell: .\.venv\Activate.ps1
pip install -e .                                      # or: pip install -e ".[test]"
```

Only `mcp` is fetched. If you would rather not install the package, run it with `PYTHONPATH`:

```bash
PYTHONPATH=src python3 -m boardview_mcp --board "<file>.cad" --check   # PowerShell: $env:PYTHONPATH="src"
```

## Startup

Point the server at one board file — CLI flag, or the `BOARDVIEW_FILE` environment variable:

```bash
python -m boardview_mcp --board "MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad"
# equivalent:
BOARDVIEW_FILE="MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad" python -m boardview_mcp
```

Startup does the parse **once**, prints a verification summary, then serves:

```
<file>: GenCAD 1.4 - 1932 components, 1363 nets, 8700 pin-net memberships, 8868 declared pins, 0 errors, 0 warnings
serving MCP over Streamable HTTP at http://127.0.0.1:8000/mcp (Ctrl+C to stop); tools: 9; board file: ...
```

Flags: `--host` (default **127.0.0.1** — change it only when you have a reason), `--port` (default 8000),
`--http-path` (default `/mcp`), `--max-bytes` (refuse oversized files), `--check` (parse, report, exit —
used by CI and by you to confirm a file before wiring it up), `--tools` (list tool names), `--verbose`
(dump the full JSON board summary).

Endpoint for Open WebUI: `http://127.0.0.1:8000/mcp`.

## Open WebUI integration

Open WebUI talks to MCP servers over Streamable HTTP. With the Docker/desktop build that has
[MCP support](https://docs.openwebui.com/features/mcp), configure the server after it is running:

1. Start `boardview-mcp` (command above) and leave it running.
2. In Open WebUI settings, add the server URL `http://127.0.0.1:8000/mcp` as an MCP server
   (the exact setting name depends on your Open WebUI version — it is the "MCPSERVER_DEFINITIONS"
   / "Remote" server list, and `http://host:port/path` is the accepted form).
   Windows cmd: `set BOARDVIEW_FILE=C:\path\to\board.cad` — PowerShell:
   `$env:BOARDVIEW_FILE = "C:\path\to\board.cad"` — and to keep the Open WebUI connection on the same
   machine, run Open WebUI with the server bound to 127.0.0.1 as above.
3. Ask the model to start with `board_summary`, then follow the tool workflow. The server ships
   instructions (visible to the model) that state the connectivity model, the meaning of
   `tentative`/`inferred`, and that names must be copied from tool results, never from memory.

The default transport is stateless (`stateless_http=True`), which is what most HTTP-only clients want;
Open WebUI need not hold session state.

## The ten tools

| Tool | What it answers |
| --- | --- |
| `board_summary` | file identity, counts, sides, bbox, units, attributes, parse errors/warnings, the connectivity model in words |
| `search_components` | find components by ref/package/device/part/pins/nets/kind (substring or `*` glob), paginated |
| `get_component` | one component verbatim: package, device, part, tol, position, rotation, side, every pin with its nets and padstack, which pins are unconnected, plus a `structure` block (pad coordinates, footprint, every pad pair with its distance and an `across_footprint` flag, the words in its own names) |
| `get_net` | one net verbatim: every `(component, pin)` member in file order, paginated, plus duplicate NODE count and whether a ROUTE of that name exists |
| `find_connected_components` | everything reachable from a component or a named net within N component hops (same filters; `GND` excluded by default and reported as `excluded_nets`) |
| `trace_connectivity` | a depth-limited walk as nodes + edges, with filters (`only_kinds`, `exclude_nets` default `GND`, `exclude_components`, `per_net_window`, `assumed_bridges`) |
| `trace_power_path` | candidate paths between a start and named target components, each labelled by evidence: `asserted by the file`, `hypothesis (modulo internal crossings)`, or the caller's assertion; takes `assumed_bridges`, `exclude_nets`, `exclude_components` |
| `find_shared_rails` | the nets two or more components actually share, with the exact pins involved (`exclude_nets`/`exclude_components` cut the GND noise) |
| `export_subgraph` | a machine-friendly slice (components, pins, nets, edges) for further reasoning or a report |
| `evaluate_crossing` | asks a question instead of answering one: for one component and two of its pads, the geometry, the names, what the file does and does not state about that pair, and a verdict saying whether the file can settle it at all; the pair is never added as connectivity here — that stays a caller assertion |

All tools are annotated `readOnlyHint: true, destructiveHint: false, idempotentHint: true`, are
bounded (`limit`/`offset`, `max_depth`/`max_nodes`), and mark every field as `file`, `derived`, or
`inferred` in a `source` block.

## Connectivity model (what "connected" means here)

- Two pins are connected **iff the file lists both under the same `SIGNAL`/net name**. That is the only
  electrical evidence in this format.
- A component with several pins on one net (e.g. `J15` pins 6,7,8 on `12V_PEX6_8_INP`) is reported as
  `same_component_shared_net` — it says nothing about that component's other pins.
- **Internal crossing is never presented as a file fact.** Three ways a crossing can appear, each with
  its own label, and a route always counts them (`tentative_hops`, `asserted_hops`, `hypothesis_hops`):
  1. **virtual-placeholder rule** — `bridge_eligibility` at `src/boardview_mcp/graph.py:209`: a component
     whose SHAPE or DEVICE name says `VIRTUAL` (the file's own vocabulary for an undrawn stand-in; on this
     board `RS1/RS2/RS501` = `RSENSE_VIRTUAL_04_SMD_2512`, `RS3/RS4` = `RSENSE_VIRTUAL_04_SMD_1206_B`,
     `VS501` = `VIRTUAL_SHORT`) may be crossed between any two of its net-carrying pads.
  2. **two-terminal passive rule** — exactly two pins, both with nets, inferred passive kind
     (capacitor/inductor/ferrite bead/resistor/fuse/virtual short).
  3. **caller assertion** — `assumed_bridges=[{"component": "RS1", "pins": ["4","1"], "label": "…"}]` on
     the four traversal tools, for a crossing you know from the physical board or the schematic. Accepted
     and rejected items are echoed back; asserted edges carry
     `edge_kind: "inferred_crossing_asserted_by_caller"`, `asserted_by`, `asserted_label`, and the
     component's `eligibility` (so you can see when a rule refused it and only the caller's word allows it).
     An assertion replaces the rule's hypothesis for the same pad pair, never for other pairs.
  - Refused by both rules: multi-terminal passive parts (39 ferrite beads, 728 resistors with 3+ terminals)
    and active/structural components (60 ICs, 51 test points, 7 connectors, `G1` with 2714 pins).
    Asserting a crossing on such a component is still possible, but the edge says so in `eligibility`.
- A **multi-pin IC is never bridged by the rules**: `U7` (41 pins / 16 nets) and `G1` (2714 pins) keep
  their pins electrically separate, and `bridge_eligibility` refuses them. A caller may still assert one
  pad-to-pad crossing; the label and `eligibility` make that difference visible.
- `evaluate_crossing(component, pads)` exists because the rules are only a reading of the name text. It
  returns the pair's geometry and names, the file's opinion (labelled inference), and a verdict such as
  `file_cannot_settle_it: true` for `RS1` pads `4`/`1`. It adds no crossing. What a model concludes is
  handed back through `assumed_bridges`, and the caller's label then outranks the rule's hint for that one
  pad pair (`also_rule_offered` still notes that the rules would have offered it too).
- `ROUTE`/`VIA` records are drawing data. A route sharing a net's name is reported as
  `route_drawing_exists` with `route_vias_are_not_members: true`; waypoints are never members.

See `docs/GENCAD_FORMAT.md` for the record-level evidence behind those claims, `docs/BRIDGE_POLICY.md` for
the three sub-rules with the real-board examples, and `BRIDGE_POLICY_NOTE` (`src/boardview_mcp/graph.py`)
for the rule as implemented in code.

## Tests

```bash
python3 -m pytest tests -v
```

- `tests/test_parser.py` — tokenizer, continuations, malformed-record error reporting, and the real board's
  verified counts and exact names.
- `tests/test_graph.py` — the fixture's connectivity: net membership verbatim, `same_component_shared_net`
  vs `net`, bridge eligibility rules, depth/`tentative_edges` accounting, plus the real board's
  verified chain (`J15:8 → RS1:4 → RS1:1 → L45:1 → L45:2 → U7:34` hop by hop, and the same walk through
  `trace_power_path`) and the proof that a strict search finds **no** route through `RS1`.
- `tests/test_tools.py` — tool registration (exactly ten), descriptions, readOnly annotations, and each
  tool's behaviour over the fixture plus the real board through an in-process MCP client.
- `tests/test_server_http.py` — spawns the CLI, waits for the endpoint, and drives **three or more** tools
  over real HTTP on 127.0.0.1, including the mis-transcribed-name error.
The real-board tests skip automatically when no `*.cad` larger than 100 KB sits next to the project, or
when `BOARDVIEW_FILE` points elsewhere.

## Evidence

- `docs/EVIDENCE_ACCEPTANCE.md` — generated by `python3 scripts/acceptance_demo.py`: it starts the CLI as a
  real Streamable-HTTP server and drives the tools over the wire, asserting the acceptance chain
  (file-only search finds no route past the sense pad → name-rule crossings offer one as a hypothesis →
  the model's own `assumed_bridges` replace those hints and the chain reaches `U7` with
  `file_certain_hops=3`, `hypothesis_hops=0`, `caller_asserted_hops=2`).
- `docs/STATE.md` + `docs/STATE_SNAPSHOT.txt` (`python3 scripts/state_snapshot.py`) — the layer vocabulary,
  the ten tools, eligibility verdicts and crossing verdicts as the code stands today.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `no board file: pass --board or set BOARDVIEW_FILE` | neither the flag nor the env var is set (env name is case-sensitive) |
| `cannot use this file: ...` (exit code 2) | the path is missing/unreadable, larger than `--max-bytes`, or not GenCAD 1.4 — run `--check` on the file and read the reported errors |
| parse summary shows errors | they are listed as `[section] line: message`; a file with errors is still served, but the affected records are absent — fix the path/section reported |
| Open WebUI: "connection refused" | the server was never started, or you set `BOARDVIEW_FILE` in a different shell than the one that starts it; the CLI prints the endpoint line before serving |
| Open WebUI: 404 / wrong path | the mount is `/mcp`; match `--http-path` with the URL you register |
| Open WebUI on another machine cannot reach it | default is 127.0.0.1 (deliberate); use `--host` plus port forwarding rather than rebinding to 0.0.0.0 |
| a tool result is `truncated: true` | raise `limit`/`offset` (e.g. `get_net(name="GND")` has 2858 members) — never assume the first page is the whole net |
| a walk stops early with `truncated: true` and `nets_windowed: ["GND"]` | `GND` (2858 members) swamps the budget; `exclude_nets` (default `GND`) or a bigger `per_net_window`/`max_nodes` — `net_fanout` in the result names the widest nets actually touched |
| a verified chain in the physical board is missing from a trace | the file states no internal crossing, so pass `assumed_bridges` for the pad pairs you know, and read back `assumed_bridges.accepted` |
| a name you typed returns `... not found` | the file is case-sensitive; the error carries `similar_components`/`similar_nets` of spellings that *do* exist. On this board `12V_PEX8_6_INP` does not exist — the real net is `12V_PEX6_8_INP` |
| `ImportError: mcp.server.fastmcp` | that is the v1 API; this project uses v2 (`mcp.server.mcpserver`) — install `mcp>=2.0` |
| `requires Python >=3.11` on install | your `pip` belongs to an older interpreter; install with the 3.11+ interpreter (`python3 -m pip install -e .`) or rebuild the venv |
| `UnicodeEncodeError` printing summaries on Windows | console codepage issue, not a data problem: redirect to a file (`--verbose > out.json`) or set `PYTHONIOENCODING=utf-8` |

## Known limits (not bugs)

- Kind inference reads DEVICE and SHAPE names only; it is labelled `inferred` and must never be quoted as
  a fact the file states. On this board the guess is `capacitor`/`resistor`/`inductor` from DEVICE text
  such as `1uH_CHK_S2_8_7X8_1_3`.
- The GenCAD 1.4 reader implements the record families this file exercises (`docs/GENCAD_FORMAT.md`); a
  board that uses other sections reports them as unknown sections/warnings instead of failing.
- Geometry is used only for reporting (bbox, per-pin coordinates) — never for connectivity.
