# Bridge policy — what may be crossed internally, and how it is labelled

Implemented in `src/boardview_mcp/graph.py`, method `ConnectivityGraph.bridge_eligibility(ref)`
(`graph.py:209`) and `ConnectivityGraph.bridge_neighbours(ref, pin, assumed=...)` (`graph.py:318`).
Rule text also lives in `BRIDGE_POLICY_NOTE` (`graph.py:28`) and is quoted by `board_summary`.

Nothing here is electrical evidence. **The GenCAD 1.4 format states one fact and one fact only:
a pin is a member of a `SIGNAL`.** Everything else here is either a *hypothesis* the server generates
from name shapes, or an *assertion the model makes about the part*: "caller" in this project means the AI
model talking to the server, and the server itself never decides that a part is wired to itself.
Every crossing below is a *hypothesis* or a *caller assertion*,
and each edge says which.

## The three sources of a crossing edge

| # | Source | Who decides | Edge label | On this board |
| - | ------ | ----------- | ---------- | ------------- |
| 1 | **virtual-placeholder rule** | the file's own vocabulary: `SHAPE` or `DEVICE` name contains `VIRTUAL` | `kind: "inferred_crossing_from_name_rules"`, `rule: virtual-placeholder…`, `tentative: true` | 6 components: `RS1`/`RS2`/`RS501` (`RSENSE_VIRTUAL_04_SMD_2512`, `0.005ohm`, pads `1`–`4`), `RS3`/`RS4` (`RSENSE_VIRTUAL_04_SMD_1206_B`, `0.001ohm`), `VS501` (`VIRTUAL_SHORT`, 2 pads) |
| 2 | **two-terminal passive rule** | exactly two net-carrying pins, both with nets, plus an *inferred* passive kind (capacitor / inductor / ferrite bead / resistor / fuse / virtual short) | same as above, `rule: two-terminal passive rule…`, `inferred: true`, kind basis quoted | e.g. `L45` (`1uH_CHK_S2_8_7X8_1_3` → inductor), the 2-pad filters `C190` (`1uF_0603`), `C191` (`0.1uF`), `C192` (`1uF_0603`) |
| 3 | **model assertion** | the model passes `assumed_bridges=[{"component": "RS1", "pins": ["4","1"], "label": "…"}]` on `find_connected_components`, `trace_connectivity`, `trace_power_path`, `export_subgraph` | `edge_kind: "inferred_crossing_asserted_by_caller"`, `asserted_by`, `asserted_label`, `tentative: true`, plus the component's `eligibility` | needed for anything the rules refuse: ICs (`U7` 41 pins, `G1` 2714 pins), connectors (`J15`), 3+ terminal passive parts |

`bridge_eligibility` gate (`graph.py:209-215`): a component is rule-bridgeable only if its inferred kind
is in `PASSIVE_KINDS` (`src/boardview_mcp/classify.py:112`) **or** it is in `PLACEHOLDER_KINDS`
(`virtual_placeholder`, `classify.py:105`). Refused kinds report the reason verbatim, e.g.
`"inferred kind 'integrated_circuit' is active/structural, not a passive terminal pair"`.

## Rules refuse, assertions allow

Refused by both rules (assertion still possible, and the edge then says no rule offered it):

- 39 ferrite beads and 728 resistors with three or more terminals — bridging them would invent a pair;
- 60 integrated circuits (`U7`, `G1`), 51 test points, 7 connectors (`J15`) — these have internal structure
  (a BGA with 2714 pads is not a terminal pair).

Accepted by rule 2 in full: `terminals = sorted(name for name in declared if self.pin_nets.get((ref, name)))`
— pins with **no net are never terminals**, so declared-but-unconnected pads cannot create a crossing.

## Worked chain (the verified path on this board)

```
J15:8  ──net 12V_PEX6_8_INP──► RS1:4      file fact (both NODEd in that SIGNAL)
RS1:4  ─────────────────────► RS1:1      caller assertion / rule 1 hypothesis
RS1:1  ──net 12V_PEX6_8_INN─► L45:1      file fact
L45:1  ─────────────────────► L45:2      rule 2 (two net-carrying terminals + inferred inductor)
L45:2  ──net 12V_PEX6_8_F1─► U7:34       file fact (U7 also owns pins 8,9,10,11 on that net)
```

`12V_PEX6_8_INP` has exactly 7 members, file order: `C191:1, C190:1, C192:1, J15:6, J15:7, J15:8, RS1:4`.
`12V_PEX6_8_INN` has 2: `L45:1, RS1:1`. A strict search (`allow_bridges=False`) finds **no** route from
`J15` to `L45` — that absence is exhaustive (`truncated: false`), and it is the proof that the crossing
between the two rails is not stated by the file.

Accepted by rule 2 in full: `terminals = sorted(name for name in declared if self.pin_nets.get((ref, name)))`
— pins with **no net are never terminals**, so declared-but-unconnected pads cannot create a crossing.

## Where the rules offer a hint, the model decides

The rules are a reading of the name text, nothing more. A refusal is a refusal to *offer a hint*, never a
claim that the part is not internally connected. So the server also exposes the material a model reasons
over, and keeps it away from connectivity:

| What | Where | It gives |
| ---- | ----- | -------- |
| structure block | `get_component` | pad coordinates, the component footprint, every pad pair with its distance and an `across_footprint` flag, the words in `SHAPE`/`DEVICE`, and `undrawn_connections` (what the file does state, and what it never states) |
| the question asked back | `evaluate_crossing(component, pads)` | the two pads' nets, whether those nets are already joined elsewhere in the file, the geometry, the rule's opinion (labelled inference), and a verdict that says whether the file can settle the pair at all |

`evaluate_crossing` never adds a crossing. Its verdict on `RS1` pads `4`/`1` reads
`stated_in_file: false, joined_elsewhere_in_file: false, contradicted_by_file: false,
file_cannot_settle_it: true`, and it hands back the exact `assumed_bridges` record to pass if the model
agrees. If the model disagrees it says so, and the route simply does not exist for that pair; the model
then names the pads it does believe in, or excludes the component.

Precedence when both layers describe one pad pair: **the caller's conclusion replaces the rule's hint** for
that pair (one edge, labelled `inferred_crossing_asserted_by_caller`), while `also_rule_offered` still notes
that the rules would have offered it too. A model's own reading is therefore what the graph carries, and the
hint remains visible.

### The user's example: `R1` (`0402` / `100k`)

`R1` is a real 2-pad resistor on MS-V397: package `0402`, device `100k`, pad `1` on net `12V_F`, pad `2` on
net `DP1_MODE*`, the two pads 31.514 apart at opposite ends of a footprint 31.514 wide. `evaluate_crossing`
reports `stated_in_file: false`, `joined_elsewhere_in_file: false` (`rails_joined_by_other_components: []` —
nothing in the file joins those two rails anywhere), `contradicted_by_file: false`, `file_cannot_settle_it: true`,
and the rule's opinion beside it, marked "not evidence about this part, only a hint about the name".

The file-only answer stays exhaustive: with no `assumed_bridges` there is no route from `12V_F` to `DP1_MODE*`,
and that absence is the file's own statement. The model's reading of `0402 100k` becomes a through-path only
as `assumed_bridges: [{"component": "R1", "pins": ["1", "2"], "label": "…"}]`, and it comes back as
`edge_kind: inferred_crossing_asserted_by_caller`, `net: null`, `asserted_by: "caller (the file never states
this crossing)"`, with the label echoed verbatim. Asserted at the MCP layer in
`tests/test_tools.py::test_real_board_reasoning_about_a_two_pad_part_is_the_models_own`.

## Why the split matters

A route reports `file_certain_hops`, `hypothesis_hops`, `asserted_hops`, `tentative_hop_kinds` and
`same_route_without_internal_crossing`. A route whose crossings are all rule-2 (a 2-pad capacitor) is
almost certainly real hardware; one whose crossing is an asserted IC pad-pair (`G1`) is a claim you must
verify on the physical board. The numbers let you rank candidate rails without losing the difference.

## Concurrency

`assumed_bridges` is **per call**, never stored on the shared graph: the server is `stateless_http=True`
and one `BoardContext` backs every request, so a mutable "current assumptions" field would leak between
tools and threads. Each tool validates its own list (`_validate_assumptions`, `graph.py:117`) and echoes
`assumed_bridges: {requested, accepted, rejected, note}` so you can see what actually took effect.
`ConnectivityGraph.set_assumed_bridges()` exists for tests/analysis only and is not used by any tool.
