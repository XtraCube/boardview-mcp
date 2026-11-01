# GenCAD 1.4 — observed structure of `MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad`

Inspected with plain text tooling (line counts, token histograms, per-section token counts) against the
real 5,868,394-byte / 147,973-line file in the workspace. No format feature below this line is assumed;
every claim was checked against this file.

## Header

```
$HEADER
GENCAD 1.4
USER "RSI-TRANSLATOR CAMCAD Professional 3.9.6b - Licensed to Teradyne, Douglas Raymond"
DRAWING board
REVISION "Wednesday, November 11, 2020 at 2:40pm"
UNITS USER 1000
ORIGIN 0 0
INTERTRACK 0
ATTRIBUTE HEADER_1 "Number of Routing Layers" "6"
$ENDHEADER
```

Quoted strings appear only in the header of this file (16 lines total). No `\` line-continuations
are used by this generator, but the parser supports them because GenCAD 1.4 defines them.

## Sections present (line ranges, token counts)

| Section | Lines | Records |
|---|---|---|
| `$BOARD` | 12–9930 | ARTWORK 555 groups, LINE 9163, ARC 200 — **graphics only** |
| `$PADS` | 9933–10564 | PAD 293 (ROUND/RECTANGULAR + CIRCLE/RECTANGLE/LINE/ARC geometry) |
| `$PADSTACKS` | 10567–11474 | PADSTACK 178, PAD 716, ATTRIBUTE 13 (`"BLIND" "??"`) |
| `$ARTWORKS` | — | empty |
| `$SHAPES` | 11480–14978 | SHAPE 53, PIN 3409, INSERT 36 — **pin definitions of footprints** |
| `$COMPONENTS` | 14981–26573 | COMPONENT/PLACE/LAYER/ROTATION/SHAPE/DEVICE — 1932 each |
| `$DEVICES` | 26576–27096 | DEVICE 190, PART 190, TOL 140 |
| `$SIGNALS` | 27099–37162 | SIGNAL 1363, NODE 8700 — **the electrical connectivity** |
| `$TRACKS` | 37165–37476 | TRACK 311 |
| `$LAYERS` | 37479–37483 | DEFINE 4 (SOLDERMASK_TOP/BOTTOM, SOLDERPASTE_TOP/BOTTOM) |
| `$ROUTES` | 37486–147962 | ROUTE 1363, VIA 5950, TRACK 3967, LAYER 4695, LINE 68733, ARC 25768 |
| `$MECH`, `$TESTPINS`, `$POWERPINS` | — | empty |

## Record grammar (relevant subset)

```
COMPONENT <ref>
PLACE <x> <y>
LAYER <TOP|BOTTOM>
ROTATION <degrees>
SHAPE <shape-name> <dx> <dy>
DEVICE <device-name>

SHAPE <shape-name>
PIN <pin-name> <padstack-name> <x> <y> <layer> <pad-dx> <pad-dy>
INSERT <subshape-name>

SIGNAL <net-name>
NODE <component-ref> <pin-name>

DEVICE <device-name>
PART <part-number>
TOL <percent>

PADSTACK <name> <drill-diameter>
PAD <pad-name> <layer> <dx> <dy>
ATTRIBUTE <padstack> "<key>" "<value>"
```

Pin names are not always numeric: 2771 distinct pin names, e.g. `1`, `4`, `A11`, `BH10`, `MEC1`.
Component refs are alphanumeric, 1–6 chars (max `MEC15`). Net names use `[A-Za-z0-9_*]` (e.g.
`INPUT_PEX6_8_DT1*`, `PS_NVVDD_PH8_ZCD*`); no spaces, no quoting needed here.

## Connectivity model found in the file

- `SIGNAL <net-name>` + `NODE <component-ref> <pin-name>` is a complete bipartite net↔pin incidence list.
- Counts: **1932 components, 1363 nets, 8700 pin→net memberships, 8868 shape-declared pins.**
- Every `NODE` target is declared by its component's `SHAPE` (0 orphans). 168 declared pins have no
  net membership (e.g. `U501 pin 13`, `G1 pin BH10`) → "declared, unconnected in file".
- 8 components have zero net memberships (`FM1`–`FM8`): unpopulated footprints / optical pads.
- Net sizes range 1 → 2858 members (`GND` is the huge one) → **pagination is mandatory**.
- ROUTE records are 1:1 with SIGNAL names (1363 = 1363) and are **drawing** of the net (VIA waypoints,
  TRACK, LAYER, LINE, ARC). VIA waypoints reference pads the route passes over — they are **not**
  electrical connections and must never be merged into net membership.
- `LAYER` values in `$COMPONENTS`: `TOP`, `BOTTOM` only. `$LAYERS` additionally defines SOLDERMASK_*/SOLDERPASTE_*.

## Target-board facts verified in the file (test hypotheses, not parser assumptions)

- `J15` → `SHAPE POWCONN_D8_10` (10 declared pins: 1-8 + `MEC1`, `MEC2`), `DEVICE PWRCONN8P_BLACK-RH-7`,
  `ROTATION 180.00`, `LAYER TOP`, at `4601.457 3787.598`.
  Memberships: `1,2,4 → GND`; `6,7,8 → 12V_PEX6_8_INP`; `3 → INPUT_PEX6_8_DT1*`; `5 → INPUT_PEX6_8_DT2*`.
  **`12V_PEX8_6_INP` does not exist anywhere in the file** (0 matches for `PEX8`); the user-reported name
  is a mis-transcription of `12V_PEX6_8_INP`. Nets are kept byte-exact, never normalized/merged.
- `RS1` → `SHAPE RSENSE_VIRTUAL_04_SMD_2512`, `DEVICE 0.005ohm`, 4 pins (1,2,3,4).
  `4 → 12V_PEX6_8_INP`, `1 → 12V_PEX6_8_INN`, `2 → 12V_PEX6_8_CH2_INN`, `3 → 12V_PEX6_8_CH2_INP`.
  Full net `12V_PEX6_8_INP` members: `C191:1, C190:1, C192:1, J15:6, J15:7, J15:8, RS1:4`.
  `12V_PEX6_8_INN` = [`L45:1`, `RS1:1`]; `12V_PEX6_8_CH2_INN` = [`R275:2`, `RS1:2`];
  `12V_PEX6_8_CH2_INP` = [`R261:1`, `R276:2`, `RS1:3`].
- `L45` → `2 → 12V_PEX6_8_F1`, `1 → 12V_PEX6_8_INN`. Downstream: net `12V_PEX6_8_F1` carries `U7:8,9,10,11,34`
  and `U11:8,9,10,11,34` plus capacitors (confirms the reported L45 → U7..U11 route).
- `U7` has 41 declared pins across 16 nets (GND×8, `12V_PEX6_8_F1`×5, `PS_NVVDD_PHASE8`×11, ...) —
  a multi-pin IC, so it must never be treated as an internal bridge between its pins.

## Bridge policy as implemented (four kinds of edge, three of them crossings)

The file states internal connectivity for **no** component. `graph.py:bridge_eligibility` offers a pad-to-pad
hint by two sub-rules (see `docs/BRIDGE_POLICY.md`); a refusal is a refusal to *offer a hint*, not a claim
that the part is unconnected:
`RS501` = `RSENSE_VIRTUAL_04_SMD_2512` / `0.005ohm`, `RS3`/`RS4` = `RSENSE_VIRTUAL_04_SMD_1206_B` /
`0.001ohm`, `VS501` = `VIRTUAL_SHORT`) or a component with exactly two net-carrying pins and an
inferred passive kind. Everything else - 39 ferrite beads and 728 resistors with 3+ terminals, 60 ICs
(`U7` 41 pins / 16 nets, `G1` `BGA_2714_P070_400X400` = 2714 pins), 51 test points, 7 connectors
(`J15`) - is refused, and only a caller assertion (`assumed_bridges`) can cross it. Asserted edges
carry `edge_kind: "inferred_crossing_asserted_by_caller"`. `tools.evaluate_crossing` asks the model about
one pad pair (geometry, names, file verdict) without adding the crossing; a caller assertion replaces the
rule's hint for that same pair. The verified chain
`J15:8 -12V_PEX6_8_INP-> RS1:4 | RS1:4 -asserted-> RS1:1 | RS1:1 -12V_PEX6_8_INN-> L45:1 |
L45:1 -rule hypothesis-> L45:2 | L45:2 -12V_PEX6_8_F1-> U7:34` is recorded in
`docs/BRIDGE_POLICY.md` and in `tests/test_graph.py`.

## Component ref prefixes observed (vocabulary, not hardcoding)

`C` 990, `R` 714, `TP` 51, `Q` 43, `U` 36, `D` 18, `L` 15, `MEC` 14, `J` 12, `LB` 10, `FM` 8, `M` 8,
`RS` 5, `RT` 4, `CN` 1, `G` 1, `VS` 1, `Y` 1.

Declared pin counts per prefix: C 2, R 2, L 2, LB 2, RT 2, VS 2, RS 4, Y 4, D 2-3, Q 3-6, J 2-26,
U 5-41, M 180, CN 164, G 2714, MEC 1, TP 1, FM 1.

Device-name grammar carries the physical value: `560uF`, `0.1uF`, `1.5nF`, `100pF` (capacitors),
`4.7uH`, `0.22uH`, `1uH` (inductors/ferrite beads), `0R`, `0ohm`, `100ohm`, `10Kohm`, `100k_B25/50=4250K`
(resistors/thermal-shrink RTD), `0.005ohm`, `0.001ohm` (RS = regular-shape sense pads), `U_MEM_SG_GDDR6`,
`U_GPU_GB5_256`, `PWRCONN8P_BLACK-RH-7`, `CON_PCI_EXPRESS`, `OPT`, `MOUNTING_HOLE`.
Classification from those strings is **inference** and must be labelled as such in tool output.

## Proposed internal data model

`Board`
- `format`/`version` (from `GENCAD 1.4`), `header` (raw records incl. `ATTRIBUTE`), `units`
- `components: dict[ref, Component]` — ref, `package` (SHAPE name = footprint), `device` (viewer-visible
  value), `position`, `rotation`, `side`, `pins: dict[pin_name, Pin]`, `explicit: set[str]` (fields present in file)
- `nets: dict[name, Net]` — `Net.name` exact, `Net.members: list[(ref, pin_name)]` in file order
- `shapes: dict[name, Shape]` — `Pin(name, padstack, x, y, layer, pad_dx, pad_dy)`
- `padstacks`, `pads`, `devices(name → part/tol)`, `layers`, `tracks`
- `routes: dict[net, summary]` (via/track/layer/geometry counts only; waypoint coords kept out of the
  connectivity graph, since they are drawing, not electrical data)
- `bbox` from `$BOARD` artwork coordinates (reported as derived, with `derived=True`)
- `warnings: list[ParseWarning(section, line, message)]`, `sections_seen: dict[str, int]`
- derived aggregates: `components_without_nets`, `declared_unconnected_pins`, duplicate-membership count

Provenance rule: every field on `Component`/`Pin`/`Net` exists **only** if the file said so. Anything the
application adds (kind classification, bridgeable flag, human value string, bounding box) lives in
`inferred_*` keys and is surfaced in tool output as `inferred` with its basis.
