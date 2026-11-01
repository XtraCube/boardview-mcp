server banner: serving MCP over Streamable HTTP at http://127.0.0.1:8200/mcp (Ctrl+C to stop); tools: 10; board file: S:\WindowsLibraries\Documents\GPU REPAIR\MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad
tools advertised over the wire (10): board_summary, evaluate_crossing, export_subgraph, find_connected_components, find_shared_rails, get_component, get_net, search_components, trace_connectivity, trace_power_path

### board_summary (identity, counts, connectivity model in words)

```json
{
 "file": {
  "path": "S:\\WindowsLibraries\\Documents\\GPU REPAIR\\MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad",
  "bytes": 5868394,
  "format": "GENCAD",
  "version": "1.4"
 },
 "counts": {
  "components": 1932,
  "nets": 1363,
  "shapes": 53,
  "padstacks": 178,
  "pads": 293,
  "devices": 190,
  "layers": 4,
  "tracks": 311,
  "routes": 1363,
  "pin_records_total": 8868,
  "pin_net_memberships": 8700,
  "declared_pins_unconnected": 168,
  "components_with_no_nets": 8
 },
 "connectivity_model": {
  "how_pins_connect": "two pins listed under the same SIGNAL share that net",
  "net_names": "byte-exact from the file; never renamed, normalised or merged",
  "route_vias": "ROUTE/VIA records are drawing data, NOT electrical members",
  "ic_internal_bridging": "an internal crossing is only ever reported as an explicit hypothesis, never as file data, and only for components the policy deems eligible; such edges carry kind=inferred_crossing_from_name_rules and tentative=true. internal crossings are only ever hypotheses or caller assertions, never file facts; two rule-based sub-rules create edges of kind=inferred_crossing_from_name_rules and tentative=true: (1) exactly two declared pads, both carrying nets, and an inferred passive kind (capacitor/inductor/ferrite_bead/resistor/fuse); (2) the component's own SHAPE/DEVICE name marks it as a placeholder for a connection the drawing does not make (kind virtual_placeholder, e.g. SHAPE RSENSE_VIRTUAL_04_SMD_2512 or SHAPE VIRTUAL_SHORT) - the file says the stand-in is there but never says which pads face each other, so each pad pairing is offered as a labelled hypothesis. Everything else is refused by the rules: active or structural kinds (integrated_circuit, connector, test_point, mounting_hole) are NEVER crossed internally - each pad is re-entered through its own net - and a passive component with more than two net-carrying pads is refused because naming the pairing would invent electrical facts. Either way the caller may assert a specific crossing through assumed_bridges, which yields kind=inferred_crossing_asserted_by_caller: the caller's knowledge, still not file evidence. Pad coordinates, distances and the words in SHAPE/DEVICE names are exposed by tools.get_component so the caller can reason instead of guessing. ROUTE/VIA records are drawing data and never take part in connectivity."
 }
}
```

### get_net on the connector rail (every member in file order)

```json
{
 "truncated": false,
 "source": {
  "net": "file (name is byte-exact; see spelling_note)",
  "members": "file (NODE records inside one SIGNAL block)",
  "members_by_component": "derived (grouping of those members)",
  "multi_pin_components_on_this_net": "derived (grouping of those members)",
  "total_members": "derived (count of members)",
  "distinct_components": "derived (count of distinct component refs among members)",
  "duplicate_member_records": "derived (count of repeated NODE comp pin lines inside this SIGNAL block, each kept once)",
  "route_drawing_exists": "file (a ROUTE with this SIGNAL name exists or does not)",
  "route_vias_are_not_members": "fixed rule (ROUTE/VIA records are drawing data; no member comes from one)",
  "inferred_classification_of_members": "inferred (name patterns; see kind_basis in get_component)"
 }
}
```

### get_component J15: the connector and its pin->net map

```json
{
 "ref": "J15",
 "package": "POWCONN_D8_10",
 "device": "PWRCONN8P_BLACK-RH-7",
 "pin_count_declared": 10,
 "pin_count_connected": 8,
 "nets": [
  "GND",
  "INPUT_PEX6_8_DT1*",
  "INPUT_PEX6_8_DT2*",
  "12V_PEX6_8_INP"
 ],
 "connected_pins": [
  "1",
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "8"
 ],
 "explicitly_in_file": [
  "device",
  "package",
  "position",
  "rotation",
  "side"
 ],
 "source": {
  "ref": "file",
  "package": "file",
  "device": "file",
  "position": "file",
  "rotation": "file",
  "side": "file",
  "explicitly_in_file": "file (which COMPONENT/PLACE/ROTATION/SIDE records were present)",
  "part": "file (DEVICE part field, when that DEVICE record carries one)",
  "tol": "file (DEVICE tolerance field, when that DEVICE record carries one)",
  "pins": "file (SHAPE PIN declarations plus NODE records; per-pin source flags inside)",
  "nets": "derived (read off the graph; every membership comes from a NODE record)",
  "connected_pins": "derived (pin has at least one NODE record)",
  "unconnected_pins": "derived (pin has no NODE record)",
  "pin_count_declared": "derived (count of declared pins)",
  "pin_count_connected": "derived (count of pins with nets)",
  "same_component_shared_net": "derived (graph incidence)",
  "structure": "derived (geometry computed from the file's coordinates and name text: footprint extent, per-pad coordinates, pad-to-pad distances and the vocabulary the names are built from). These are facts about the drawing and the names, NOT statements of electrical connectivity",
  "inferred_classification": "inferred (name patterns; see kind_basis)",
  "bridge_eligibility": "inferred (policy applied to the inferred kind; see reason)"
 }
}
```

### get_component RS1: structure block only (the reasoning surface)

```json
{
 "pad_count_declared": 4,
 "pad_count_with_coordinates": 4,
 "pads": {
  "1": {
   "x": -131.89,
   "y": 0.0,
   "nets": [
    "12V_PEX6_8_INN"
   ],
   "connected": true
  },
  "2": {
   "x": -100.394,
   "y": 0.0,
   "nets": [
    "12V_PEX6_8_CH2_INN"
   ],
   "connected": true
  },
  "3": {
   "x": 100.394,
   "y": 0.0,
   "nets": [
    "12V_PEX6_8_CH2_INP"
   ],
   "connected": true
  },
  "4": {
   "x": 131.89,
   "y": 0.0,
   "nets": [
    "12V_PEX6_8_INP"
   ],
   "connected": true
  }
 },
 "footprint": {
  "x_min": -131.89,
  "x_max": 131.89,
  "y_min": 0.0,
  "y_max": 0.0,
  "width": 263.78,
  "height": 0.0,
  "centre": {
   "x": 0.0,
   "y": 0.0
  },
  "units": "file units (see board_summary units)",
  "from": "bounding box of the component's own declared pad coordinates"
 },
 "pad_pairs_by_distance": [
  {
   "pins": [
    "2",
    "3"
   ],
   "distance": 200.788,
   "shared_nets": [],
   "nets_first_pad": [
    "12V_PEX6_8_CH2_INN"
   ],
   "nets_second_pad": [
    "12V_PEX6_8_CH2_INP"
   ],
   "across_footprint": true
  },
  {
   "pins": [
    "1",
    "3"
   ],
   "distance": 232.284,
   "shared_nets": [],
   "nets_first_pad": [
    "12V_PEX6_8_INN"
   ],
   "nets_second_pad": [
    "12V_PEX6_8_CH2_INP"
   ],
   "across_footprint": true
  },
  {
   "pins": [
    "2",
    "4"
   ],
   "distance": 232.284,
   "shared_nets": [],
   "nets_first_pad": [
    "12V_PEX6_8_CH2_INN"
   ],
   "nets_second_pad": [
    "12V_PEX6_8_INP"
   ],
   "across_footprint": true
  },
  {
   "pins": [
    "1",
    "4"
   ],
   "distance": 263.78,
   "shared_nets": [],
   "nets_first_pad": [
    "12V_PEX6_8_INN"
   ],
   "nets_second_pad": [
    "12V_PEX6_8_INP"
   ],
   "across_footprint": true
  },
  {
   "pins": [
    "1",
    "2"
   ],
   "distance": 31.496,
   "shared_nets": [],
   "nets_first_pad": [
    "12V_PEX6_8_INN"
   ],
   "nets_second_pad": [
    "12V_PEX6_8_CH2_INN"
   ],
   "across_footprint": false
  },
  {
   "pins": [
    "3",
    "4"
   ],
   "distance": 31.496,
   "shared_nets": [],
   "nets_first_pad": [
    "12V_PEX6_8_CH2_INP"
   ],
   "nets_second_pad": [
    "12V_PEX6_8_INP"
   ],
   "across_footprint": false
  }
 ],
 "pad_pairs_total": 6,
 "name_vocabulary": {
  "package_tokens": [
   "RSENSE",
   "VIRTUAL",
   "04",
   "SMD",
   "2512"
  ],
  "device_tokens": [
   "0",
   "005ohm"
  ],
  "matched_by_classify": [
   "resistor (weight 0.85): ohm value in the DEVICE name",
   "sense (weight 0.7): DEVICE name contains token 'sense'",
   "sense (weight 0.7): DEVICE name contains token 'rsense'",
   "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
   "multi_pin_unit (weight 0.55): 4 declared pins",
   "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
  ],
  "note": "the words present in SHAPE/DEVICE names, and which of them the classifier used; names are file data, the classification built from them is not"
 },
 "undrawn_connections": {
  "file_states": [
   "which pads exist, where they are, which SIGNAL each belongs to, and the SHAPE/DEVICE names",
   "that two pads of this component already carry the same SIGNAL (see pads_already_sharing_a_net)"
  ],
  "file_never_states": [
   "that a pad on one SIGNAL continues to another pad of the same component",
   "which pad faces which, or what internal path a part has"
  ],
  "how_to_reason": "read pad_pairs_by_distance together with the names: pads at opposite ends of the footprint (`across_footprint: true`) on a part whose name marks a through-path (filter, sense pad, virtual placeholder) are the usual in/out pair. Record the conclusion as an assumed_bridges item on the next call, with the reason - it then appears in every result as edge_kind=inferred_crossing_asserted_by_caller and tentative=true",
  "geometry_caveat": "coordinates come from the drawing: they say where a pad was placed, not that a wire exists. Rotation, mirroring and stylised schematics can put two connected pads next to each other and two unconnected pads far apart, so distance is a hint, never evidence"
 }
}
```

### evaluate_crossing RS1 pads 4/1: the question asked back, no edge added

```json
{
 "question": {
  "component": "RS1",
  "pads": [
   "4",
   "1"
  ],
  "proposed_by": "caller (the model, not the file)"
 },
 "file_facts": {
  "pad_a_nets": [
   "12V_PEX6_8_INP"
  ],
  "pad_b_nets": [
   "12V_PEX6_8_INN"
  ],
  "pads_share_a_net": [],
  "rails_joined_by_other_components": [],
  "pads_of_this_component_already_sharing_a_net": []
 },
 "structural_facts": {
  "geometry": {
   "distance": 263.78,
   "across_footprint": true,
   "footprint": {
    "x_min": -131.89,
    "x_max": 131.89,
    "y_min": 0.0,
    "y_max": 0.0,
    "width": 263.78,
    "height": 0.0,
    "centre": {
     "x": 0.0,
     "y": 0.0
    },
    "units": "file units (see board_summary units)",
    "from": "bounding box of the component's own declared pad coordinates"
   },
   "pad_a": {
    "name": "4",
    "x": 131.89,
    "y": 0.0,
    "nets": [
     "12V_PEX6_8_INP"
    ],
    "connected": true
   },
   "pad_b": {
    "name": "1",
    "x": -131.89,
    "y": 0.0,
    "nets": [
     "12V_PEX6_8_INN"
    ],
    "connected": true
   }
  },
  "naming": {
   "package_tokens": [
    "RSENSE",
    "VIRTUAL",
    "04",
    "SMD",
    "2512"
   ],
   "device_tokens": [
    "0",
    "005ohm"
   ],
   "matched_by_classify": [
    "resistor (weight 0.85): ohm value in the DEVICE name",
    "sense (weight 0.7): DEVICE name contains token 'sense'",
    "sense (weight 0.7): DEVICE name contains token 'rsense'",
    "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
    "multi_pin_unit (weight 0.55): 4 declared pins",
    "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
   ],
   "note": "the words present in SHAPE/DEVICE names, and which of them the classifier used; names are file data, the classification built from them is not"
  },
  "component_geometry": {
   "x_min": -131.89,
   "x_max": 131.89,
   "y_min": 0.0,
   "y_max": 0.0,
   "width": 263.78,
   "height": 0.0,
   "centre": {
    "x": 0.0,
    "y": 0.0
   },
   "units": "file units (see board_summary units)",
   "from": "bounding box of the component's own declared pad coordinates"
  },
  "candidate_alternatives": [
   {
    "pins": [
     "2",
     "3"
    ],
    "distance": 200.788,
    "shared_nets": [],
    "nets_first_pad": [
     "12V_PEX6_8_CH2_INN"
    ],
    "nets_second_pad": [
     "12V_PEX6_8_CH2_INP"
    ],
    "across_footprint": true
   },
   {
    "pins": [
     "1",
     "3"
    ],
    "distance": 232.284,
    "shared_nets": [],
    "nets_first_pad": [
     "12V_PEX6_8_INN"
    ],
    "nets_second_pad": [
     "12V_PEX6_8_CH2_INP"
    ],
    "across_footprint": true
   },
   {
    "pins": [
     "2",
     "4"
    ],
    "distance": 232.284,
    "shared_nets": [],
    "nets_first_pad": [
     "12V_PEX6_8_CH2_INN"
    ],
    "nets_second_pad": [
     "12V_PEX6_8_INP"
    ],
    "across_footprint": true
   },
   {
    "pins": [
     "1",
     "2"
    ],
    "distance": 31.496,
    "shared_nets": [],
    "nets_first_pad": [
     "12V_PEX6_8_INN"
    ],
    "nets_second_pad": [
     "12V_PEX6_8_CH2_INN"
    ],
    "across_footprint": false
   },
   {
    "pins": [
     "3",
     "4"
    ],
    "distance": 31.496,
    "shared_nets": [],
    "nets_first_pad": [
     "12V_PEX6_8_CH2_INP"
    ],
    "nets_second_pad": [
     "12V_PEX6_8_INP"
    ],
    "across_footprint": false
   }
  ]
 },
 "policy_opinion": {
  "server_rule_says": {
   "bridgeable": true,
   "rule_or_reason": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
   "inferred_kind": "virtual_placeholder"
  },
  "note": "the server rule is a name-shape heuristic and the model may disagree with it in either direction; it is not evidence about this part, only a hint about the name"
 },
 "contradicts_file": [],
 "verdict": {
  "stated_in_file": false,
  "joined_elsewhere_in_file": false,
  "contradicted_by_file": false,
  "file_cannot_settle_it": true,
  "summary": "the file neither states nor forbids this: no record says a component is wired to itself, and no record contradicts the pair either"
 },
 "if_the_model_agrees": {
  "record_as": {
   "component": "RS1",
   "pins": [
    "4",
    "1"
   ],
   "label": "the 0.005ohm current-sense stand-in is one through-path"
  },
  "how_to_use": "pass this object in assumed_bridges on the next connectivity call; the crossing then appears as edge_kind=inferred_crossing_asserted_by_caller with tentative=true and this label, so every result still separates it from file facts",
  "what_changes": "traversals may enter at one pad and leave at the other; the file-only answers (allow_bridges=false) stay unchanged, so a strict search can still be run for comparison"
 },
 "if_the_model_disagrees": {
  "what_to_do": "leave assumed_bridges out of the call: the file-only graph then reports exactly what the file states, and the absence of a route is exhaustive rather than suspicious"
 },
 "source": {
  "pad_nets": "file",
  "pads_share_a_net": "file",
  "rails_joined_by_other_components": "file (NODE membership)",
  "geometry": "derived (coordinates in the file)",
  "naming": "file (name text) + derived (token split)",
  "policy_opinion": "inferred (name-shape heuristic; not evidence)",
  "verdict": "derived (from the file facts above)"
 },
 "next_steps": [
  "call get_component('RS1') for the whole structure block",
  "call find_shared_rails([...]) to compare the rails on either side",
  "call trace_power_path(..., assumed_bridges=[<record_as>]) to see the route this reasoning enables"
 ]
}
```

### get_component R1: the user's own example, a real 2-pad resistor (0402 / 100k)

```json
{
 "ref": "R1",
 "package": "0402",
 "device": "100k",
 "pin_count_declared": 2,
 "pin_count_connected": 2,
 "nets": [
  "12V_F",
  "DP1_MODE*"
 ],
 "connected_pins": [
  "1",
  "2"
 ],
 "structure": {
  "pad_count_declared": 2,
  "pad_count_with_coordinates": 2,
  "pads": {
   "1": {
    "x": -15.757,
    "y": -0.0,
    "nets": [
     "12V_F"
    ],
    "connected": true
   },
   "2": {
    "x": 15.757,
    "y": -0.0,
    "nets": [
     "DP1_MODE*"
    ],
    "connected": true
   }
  },
  "footprint": {
   "x_min": -15.757,
   "x_max": 15.757,
   "y_min": -0.0,
   "y_max": -0.0,
   "width": 31.514,
   "height": 0.0,
   "centre": {
    "x": 0.0,
    "y": -0.0
   },
   "units": "file units (see board_summary units)",
   "from": "bounding box of the component's own declared pad coordinates"
  },
  "pad_pairs_by_distance": [
   {
    "pins": [
     "1",
     "2"
    ],
    "distance": 31.514,
    "shared_nets": [],
    "nets_first_pad": [
     "12V_F"
    ],
    "nets_second_pad": [
     "DP1_MODE*"
    ],
    "across_footprint": true
   }
  ],
  "pad_pairs_total": 1,
  "pad_pairs_truncated": false,
  "pads_already_sharing_a_net": [],
  "name_vocabulary": {
   "package_tokens": [
    "0402"
   ],
   "device_tokens": [
    "100k"
   ],
   "matched_by_classify": [
    "resistor (weight 0.85): ohm value in the DEVICE name",
    "resistor-like (weight 0.25): reference prefix R is a viewer convention, not file data"
   ],
   "note": "the words present in SHAPE/DEVICE names, and which of them the classifier used; names are file data, the classification built from them is not"
  },
  "undrawn_connections": {
   "file_states": [
    "which pads exist, where they are, which SIGNAL each belongs to, and the SHAPE/DEVICE names",
    "that two pads of this component already carry the same SIGNAL (see pads_already_sharing_a_net)"
   ],
   "file_never_states": [
    "that a pad on one SIGNAL continues to another pad of the same component",
    "which pad faces which, or what internal path a part has"
   ],
   "how_to_reason": "read pad_pairs_by_distance together with the names: pads at opposite ends of the footprint (`across_footprint: true`) on a part whose name marks a through-path (filter, sense pad, virtual placeholder) are the usual in/out pair. Record the conclusion as an assumed_bridges item on the next call, with the reason - it then appears in every result as edge_kind=inferred_crossing_asserted_by_caller and tentative=true",
   "geometry_caveat": "coordinates come from the drawing: they say where a pad was placed, not that a wire exists. Rotation, mirroring and stylised schematics can put two connected pads next to each other and two unconnected pads far apart, so distance is a hint, never evidence"
  }
 }
}
```

### evaluate_crossing R1 pads 1/2: 12V_F against DP1_MODE* - the file cannot settle this pair

```json
{
 "question": {
  "component": "R1",
  "pads": [
   "1",
   "2"
  ],
  "proposed_by": "caller (the model, not the file)"
 },
 "file_facts": {
  "pad_a_nets": [
   "12V_F"
  ],
  "pad_b_nets": [
   "DP1_MODE*"
  ],
  "pads_share_a_net": [],
  "rails_joined_by_other_components": [],
  "pads_of_this_component_already_sharing_a_net": []
 },
 "structural_facts": {
  "geometry": {
   "distance": 31.514,
   "across_footprint": true,
   "footprint": {
    "x_min": -15.757,
    "x_max": 15.757,
    "y_min": -0.0,
    "y_max": -0.0,
    "width": 31.514,
    "height": 0.0,
    "centre": {
     "x": 0.0,
     "y": -0.0
    },
    "units": "file units (see board_summary units)",
    "from": "bounding box of the component's own declared pad coordinates"
   },
   "pad_a": {
    "name": "1",
    "x": -15.757,
    "y": -0.0,
    "nets": [
     "12V_F"
    ],
    "connected": true
   },
   "pad_b": {
    "name": "2",
    "x": 15.757,
    "y": -0.0,
    "nets": [
     "DP1_MODE*"
    ],
    "connected": true
   }
  },
  "naming": {
   "package_tokens": [
    "0402"
   ],
   "device_tokens": [
    "100k"
   ],
   "matched_by_classify": [
    "resistor (weight 0.85): ohm value in the DEVICE name",
    "resistor-like (weight 0.25): reference prefix R is a viewer convention, not file data"
   ],
   "note": "the words present in SHAPE/DEVICE names, and which of them the classifier used; names are file data, the classification built from them is not"
  },
  "component_geometry": {
   "x_min": -15.757,
   "x_max": 15.757,
   "y_min": -0.0,
   "y_max": -0.0,
   "width": 31.514,
   "height": 0.0,
   "centre": {
    "x": 0.0,
    "y": -0.0
   },
   "units": "file units (see board_summary units)",
   "from": "bounding box of the component's own declared pad coordinates"
  },
  "candidate_alternatives": []
 },
 "policy_opinion": {
  "server_rule_says": {
   "bridgeable": true,
   "rule_or_reason": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
   "inferred_kind": "resistor"
  },
  "note": "the server rule is a name-shape heuristic and the model may disagree with it in either direction; it is not evidence about this part, only a hint about the name"
 },
 "contradicts_file": [],
 "verdict": {
  "stated_in_file": false,
  "joined_elsewhere_in_file": false,
  "contradicted_by_file": false,
  "file_cannot_settle_it": true,
  "summary": "the file neither states nor forbids this: no record says a component is wired to itself, and no record contradicts the pair either"
 },
 "if_the_model_agrees": {
  "record_as": {
   "component": "R1",
   "pins": [
    "1",
    "2"
   ],
   "label": "reasoning from the file: R1 package '0402' / device '100k', pad 1 on ['12V_F'], pad 2 on ['DP1_MODE*'], distance 31.514, across the footprint True"
  },
  "how_to_use": "pass this object in assumed_bridges on the next connectivity call; the crossing then appears as edge_kind=inferred_crossing_asserted_by_caller with tentative=true and this label, so every result still separates it from file facts",
  "what_changes": "traversals may enter at one pad and leave at the other; the file-only answers (allow_bridges=false) stay unchanged, so a strict search can still be run for comparison"
 },
 "if_the_model_disagrees": {
  "what_to_do": "leave assumed_bridges out of the call: the file-only graph then reports exactly what the file states, and the absence of a route is exhaustive rather than suspicious"
 },
 "source": {
  "pad_nets": "file",
  "pads_share_a_net": "file",
  "rails_joined_by_other_components": "file (NODE membership)",
  "geometry": "derived (coordinates in the file)",
  "naming": "file (name text) + derived (token split)",
  "policy_opinion": "inferred (name-shape heuristic; not evidence)",
  "verdict": "derived (from the file facts above)"
 },
 "next_steps": [
  "call get_component('R1') for the whole structure block",
  "call find_shared_rails([...]) to compare the rails on either side",
  "call trace_power_path(..., assumed_bridges=[<record_as>]) to see the route this reasoning enables"
 ]
}
```

file-only from R1 pad 1: 12 edges, all kind=net, tentative_edges=0

### the model's own join through R1, echoed as its conclusion

```json
{
 "from": {
  "component": "R1",
  "pin": "1"
 },
 "to": {
  "component": "R1",
  "pin": "2"
 },
 "net": null,
 "edge_kind": "inferred_crossing_asserted_by_caller",
 "tentative": true,
 "depth": 1,
 "evidence": null,
 "why": "caller assertion: reasoning from the file: R1 package '0402' / device '100k', pad 1 on ['12V_F'], pad 2 on ['DP1_MODE*'], distance 31.514, across the footprint True - the caller (not the file) states that R1 connects pin 1 to pin 2 internally",
 "intervening_component": "R1",
 "asserted_by": "caller (the file never states this crossing)",
 "asserted_label": "reasoning from the file: R1 package '0402' / device '100k', pad 1 on ['12V_F'], pad 2 on ['DP1_MODE*'], distance 31.514, across the footprint True",
 "eligibility": {
  "bridgeable": true,
  "reason": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
  "rule": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
  "inferred_kind": "resistor",
  "kind_basis": [
   "resistor (weight 0.85): ohm value in the DEVICE name",
   "resistor-like (weight 0.25): reference prefix R is a viewer convention, not file data"
  ],
  "terminals": [
   "1",
   "2"
  ],
  "pin_count_declared": 2,
  "pin_count_connected": 2,
  "pairings": 1,
  "inferred": true,
  "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
  "assumed_bridges": [],
  "assumed_pair": [
   "1",
   "2"
  ]
 }
}
```

### trace_power_path with allow_bridges=false: the file alone cannot get past the sense pad

```json
{
 "paths": [],
 "search_note": "one best route per target per search, capped by max_hops and an internal pop budget; the file does not contain route topology, so an undiscovered target means the search budget ran out, not that no route exists",
 "bridge_policy": "internal crossings are only ever hypotheses or caller assertions, never file facts; two rule-based sub-rules create edges of kind=inferred_crossing_from_name_rules and tentative=true: (1) exactly two declared pads, both carrying nets, and an inferred passive kind (capacitor/inductor/ferrite_bead/resistor/fuse); (2) the component's own SHAPE/DEVICE name marks it as a placeholder for a connection the drawing does not make (kind virtual_placeholder, e.g. SHAPE RSENSE_VIRTUAL_04_SMD_2512 or SHAPE VIRTUAL_SHORT) - the file says the stand-in is there but never says which pads face each other, so each pad pairing is offered as a labelled hypothesis. Everything else is refused by the rules: active or structural kinds (integrated_circuit, connector, test_point, mounting_hole) are NEVER crossed internally - each pad is re-entered through its own net - and a passive component with more than two net-carrying pads is refused because naming the pairing would invent electrical facts. Either way the caller may assert a specific crossing through assumed_bridges, which yields kind=inferred_crossing_asserted_by_caller: the caller's knowledge, still not file evidence. Pad coordinates, distances and the words in SHAPE/DEVICE names are exposed by tools.get_component so the caller can reason instead of guessing. ROUTE/VIA records are drawing data and never take part in connectivity.",
 "truncated": false
}
```

### evaluate_crossing L45 pads 1/2

```json
{
 "question": {
  "component": "L45",
  "pads": [
   "1",
   "2"
  ],
  "proposed_by": "caller (the model, not the file)"
 },
 "structural_facts": {
  "geometry": {
   "distance": 267.874,
   "across_footprint": true,
   "footprint": {
    "x_min": -133.937,
    "x_max": 133.937,
    "y_min": 0.0,
    "y_max": 0.0,
    "width": 267.874,
    "height": 0.0,
    "centre": {
     "x": 0.0,
     "y": 0.0
    },
    "units": "file units (see board_summary units)",
    "from": "bounding box of the component's own declared pad coordinates"
   },
   "pad_a": {
    "name": "1",
    "x": -133.937,
    "y": 0.0,
    "nets": [
     "12V_PEX6_8_INN"
    ],
    "connected": true
   },
   "pad_b": {
    "name": "2",
    "x": 133.937,
    "y": 0.0,
    "nets": [
     "12V_PEX6_8_F1"
    ],
    "connected": true
   }
  },
  "naming": {
   "package_tokens": [
    "CHK",
    "S2",
    "8",
    "7X8",
    "1",
    "3"
   ],
   "device_tokens": [
    "1uH",
    "CHK",
    "S2",
    "8",
    "7X8",
    "1",
    "3"
   ],
   "matched_by_classify": [
    "inductor (weight 0.9): henry value in the DEVICE name",
    "inductor (weight 0.4): DEVICE name contains token 'chk'",
    "inductor-like (weight 0.25): reference prefix L is a viewer convention, not file data"
   ],
   "note": "the words present in SHAPE/DEVICE names, and which of them the classifier used; names are file data, the classification built from them is not"
  },
  "component_geometry": {
   "x_min": -133.937,
   "x_max": 133.937,
   "y_min": 0.0,
   "y_max": 0.0,
   "width": 267.874,
   "height": 0.0,
   "centre": {
    "x": 0.0,
    "y": 0.0
   },
   "units": "file units (see board_summary units)",
   "from": "bounding box of the component's own declared pad coordinates"
  },
  "candidate_alternatives": []
 },
 "file_facts": {
  "pad_a_nets": [
   "12V_PEX6_8_INN"
  ],
  "pad_b_nets": [
   "12V_PEX6_8_F1"
  ],
  "pads_share_a_net": [],
  "rails_joined_by_other_components": [],
  "pads_of_this_component_already_sharing_a_net": []
 },
 "policy_opinion": {
  "server_rule_says": {
   "bridgeable": true,
   "rule_or_reason": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
   "inferred_kind": "inductor"
  },
  "note": "the server rule is a name-shape heuristic and the model may disagree with it in either direction; it is not evidence about this part, only a hint about the name"
 },
 "verdict": {
  "stated_in_file": false,
  "joined_elsewhere_in_file": false,
  "contradicted_by_file": false,
  "file_cannot_settle_it": true,
  "summary": "the file neither states nor forbids this: no record says a component is wired to itself, and no record contradicts the pair either"
 }
}
```

### trace_power_path with only the server's name-rule crossings (the model has said nothing)

```json
{
 "paths": [
  {
   "index": 0,
   "target": "L45",
   "label": "fewest component crossings",
   "components": [
    "RS1",
    "RS1",
    "L45"
   ],
   "pins": [
    "RS1.4",
    "RS1.1",
    "L45.1"
   ],
   "hops": [
    {
     "from": {
      "component": "J15",
      "pin": "8"
     },
     "to": {
      "component": "RS1",
      "pin": "4"
     },
     "net": "12V_PEX6_8_INP",
     "edge_kind": "net",
     "tentative": false,
     "depth": 1,
     "evidence": "12V_PEX6_8_INP",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INP in the file"
    },
    {
     "from": {
      "component": "RS1",
      "pin": "4"
     },
     "to": {
      "component": "RS1",
      "pin": "1"
     },
     "net": null,
     "edge_kind": "inferred_crossing_from_name_rules",
     "tentative": true,
     "depth": 2,
     "evidence": null,
     "why": "two-terminal passive rule: path enters RS1 at pin 4 and leaves at pin 1; the file never states an internal connection for RS1",
     "intervening_component": "RS1",
     "inferred_kind": "virtual_placeholder",
     "kind_basis": [
      "resistor (weight 0.85): ohm value in the DEVICE name",
      "sense (weight 0.7): DEVICE name contains token 'sense'",
      "sense (weight 0.7): DEVICE name contains token 'rsense'",
      "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
      "multi_pin_unit (weight 0.55): 4 declared pins",
      "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
     ],
     "eligibility": {
      "bridgeable": true,
      "reason": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "rule": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "inferred_kind": "virtual_placeholder",
      "kind_basis": [
       "resistor (weight 0.85): ohm value in the DEVICE name",
       "sense (weight 0.7): DEVICE name contains token 'sense'",
       "sense (weight 0.7): DEVICE name contains token 'rsense'",
       "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
       "multi_pin_unit (weight 0.55): 4 declared pins",
       "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2",
       "3",
       "4"
      ],
      "pin_count_declared": 4,
      "pin_count_connected": 4,
      "pairings": 6,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": []
     }
    },
    {
     "from": {
      "component": "RS1",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "1"
     },
     "net": "12V_PEX6_8_INN",
     "edge_kind": "net",
     "tentative": false,
     "depth": 3,
     "evidence": "12V_PEX6_8_INN",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INN in the file"
    }
   ],
   "nets_in_order": [
    "12V_PEX6_8_INP",
    "12V_PEX6_8_INN"
   ],
   "tentative_hops": [
    {
     "component": "RS1",
     "pin": "1"
    }
   ],
   "tentative_hop_kinds": [
    "inferred_crossing_from_name_rules"
   ],
   "intervening_components": [
    "RS1"
   ],
   "file_certain_hops": 2,
   "hypothesis_hops": 1,
   "asserted_hops": 0,
   "same_route_without_internal_crossing": false,
   "same_route_note": "False refers to the route named by `label`: asserted_only=true means the same route also exists without crossing any component internally",
   "verdict": "partly hypothetical: at least one hop is a crossing the name rule offered",
   "caller_asserted_hops": 0,
   "verdict_note": "fewest component crossings"
  },
  {
   "index": 1,
   "target": "U7",
   "label": "fewest component crossings",
   "components": [
    "RS1",
    "RS1",
    "L45",
    "L45",
    "U7"
   ],
   "pins": [
    "RS1.4",
    "RS1.1",
    "L45.1",
    "L45.2",
    "U7.8"
   ],
   "hops": [
    {
     "from": {
      "component": "J15",
      "pin": "8"
     },
     "to": {
      "component": "RS1",
      "pin": "4"
     },
     "net": "12V_PEX6_8_INP",
     "edge_kind": "net",
     "tentative": false,
     "depth": 1,
     "evidence": "12V_PEX6_8_INP",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INP in the file"
    },
    {
     "from": {
      "component": "RS1",
      "pin": "4"
     },
     "to": {
      "component": "RS1",
      "pin": "1"
     },
     "net": null,
     "edge_kind": "inferred_crossing_from_name_rules",
     "tentative": true,
     "depth": 2,
     "evidence": null,
     "why": "two-terminal passive rule: path enters RS1 at pin 4 and leaves at pin 1; the file never states an internal connection for RS1",
     "intervening_component": "RS1",
     "inferred_kind": "virtual_placeholder",
     "kind_basis": [
      "resistor (weight 0.85): ohm value in the DEVICE name",
      "sense (weight 0.7): DEVICE name contains token 'sense'",
      "sense (weight 0.7): DEVICE name contains token 'rsense'",
      "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
      "multi_pin_unit (weight 0.55): 4 declared pins",
      "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
     ],
     "eligibility": {
      "bridgeable": true,
      "reason": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "rule": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "inferred_kind": "virtual_placeholder",
      "kind_basis": [
       "resistor (weight 0.85): ohm value in the DEVICE name",
       "sense (weight 0.7): DEVICE name contains token 'sense'",
       "sense (weight 0.7): DEVICE name contains token 'rsense'",
       "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
       "multi_pin_unit (weight 0.55): 4 declared pins",
       "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2",
       "3",
       "4"
      ],
      "pin_count_declared": 4,
      "pin_count_connected": 4,
      "pairings": 6,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": []
     }
    },
    {
     "from": {
      "component": "RS1",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "1"
     },
     "net": "12V_PEX6_8_INN",
     "edge_kind": "net",
     "tentative": false,
     "depth": 3,
     "evidence": "12V_PEX6_8_INN",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INN in the file"
    },
    {
     "from": {
      "component": "L45",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "2"
     },
     "net": null,
     "edge_kind": "inferred_crossing_from_name_rules",
     "tentative": true,
     "depth": 4,
     "evidence": null,
     "why": "two-terminal passive rule: path enters L45 at pin 1 and leaves at pin 2; the file never states an internal connection for L45",
     "intervening_component": "L45",
     "inferred_kind": "inductor",
     "kind_basis": [
      "inductor (weight 0.9): henry value in the DEVICE name",
      "inductor (weight 0.4): DEVICE name contains token 'chk'",
      "inductor-like (weight 0.25): reference prefix L is a viewer convention, not file data"
     ],
     "eligibility": {
      "bridgeable": true,
      "reason": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
      "rule": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
      "inferred_kind": "inductor",
      "kind_basis": [
       "inductor (weight 0.9): henry value in the DEVICE name",
       "inductor (weight 0.4): DEVICE name contains token 'chk'",
       "inductor-like (weight 0.25): reference prefix L is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2"
      ],
      "pin_count_declared": 2,
      "pin_count_connected": 2,
      "pairings": 1,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": []
     }
    },
    {
     "from": {
      "component": "L45",
      "pin": "2"
     },
     "to": {
      "component": "U7",
      "pin": "8"
     },
     "net": "12V_PEX6_8_F1",
     "edge_kind": "net",
     "tentative": false,
     "depth": 5,
     "evidence": "12V_PEX6_8_F1",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_F1 in the file"
    }
   ],
   "nets_in_order": [
    "12V_PEX6_8_INP",
    "12V_PEX6_8_INN",
    "12V_PEX6_8_F1"
   ],
   "tentative_hops": [
    {
     "component": "RS1",
     "pin": "1"
    },
    {
     "component": "L45",
     "pin": "2"
    }
   ],
   "tentative_hop_kinds": [
    "inferred_crossing_from_name_rules"
   ],
   "intervening_components": [
    "L45",
    "RS1"
   ],
   "file_certain_hops": 3,
   "hypothesis_hops": 2,
   "asserted_hops": 0,
   "same_route_without_internal_crossing": false,
   "same_route_note": "False refers to the route named by `label`: asserted_only=true means the same route also exists without crossing any component internally",
   "verdict": "partly hypothetical: at least one hop is a crossing the name rule offered",
   "caller_asserted_hops": 0,
   "verdict_note": "fewest component crossings"
  }
 ],
 "search_note": "one best route per target per search, capped by max_hops and an internal pop budget; the file does not contain route topology, so an undiscovered target means the search budget ran out, not that no route exists",
 "bridge_policy": "internal crossings are only ever hypotheses or caller assertions, never file facts; two rule-based sub-rules create edges of kind=inferred_crossing_from_name_rules and tentative=true: (1) exactly two declared pads, both carrying nets, and an inferred passive kind (capacitor/inductor/ferrite_bead/resistor/fuse); (2) the component's own SHAPE/DEVICE name marks it as a placeholder for a connection the drawing does not make (kind virtual_placeholder, e.g. SHAPE RSENSE_VIRTUAL_04_SMD_2512 or SHAPE VIRTUAL_SHORT) - the file says the stand-in is there but never says which pads face each other, so each pad pairing is offered as a labelled hypothesis. Everything else is refused by the rules: active or structural kinds (integrated_circuit, connector, test_point, mounting_hole) are NEVER crossed internally - each pad is re-entered through its own net - and a passive component with more than two net-carrying pads is refused because naming the pairing would invent electrical facts. Either way the caller may assert a specific crossing through assumed_bridges, which yields kind=inferred_crossing_asserted_by_caller: the caller's knowledge, still not file evidence. Pad coordinates, distances and the words in SHAPE/DEVICE names are exposed by tools.get_component so the caller can reason instead of guessing. ROUTE/VIA records are drawing data and never take part in connectivity.",
 "truncated": false
}
```

name-rule chain to U7: ['RS1', 'RS1', 'L45', 'L45', 'U7'] hypothesis_hops=2 caller_asserted_hops=0

assumed_bridges records handed back by evaluate_crossing, passed through unchanged:
[
 {
  "component": "RS1",
  "pins": [
   "4",
   "1"
  ],
  "label": "the 0.005ohm current-sense stand-in is one through-path"
 },
 {
  "component": "L45",
  "pins": [
   "1",
   "2"
  ],
  "label": "the 1uH filter has one through-path"
 }
]

### trace_power_path with the model's own crossings asserted

```json
{
 "assumed_bridges": {
  "requested": [
   {
    "component": "RS1",
    "pins": [
     "4",
     "1"
    ],
    "label": "the 0.005ohm current-sense stand-in is one through-path"
   },
   {
    "component": "L45",
    "pins": [
     "1",
     "2"
    ],
    "label": "the 1uH filter has one through-path"
   }
  ],
  "accepted": [
   {
    "component": "RS1",
    "pins": [
     "4",
     "1"
    ],
    "label": "the 0.005ohm current-sense stand-in is one through-path"
   },
   {
    "component": "L45",
    "pins": [
     "1",
     "2"
    ],
    "label": "the 1uH filter has one through-path"
   }
  ],
  "rejected": [],
  "note": "caller assertions are never file evidence: edges built from them carry edge_kind=inferred_crossing_asserted_by_caller and tentative=true"
 },
 "paths": [
  {
   "index": 0,
   "target": "L45",
   "label": "fewest component crossings",
   "components": [
    "RS1",
    "RS1",
    "L45"
   ],
   "pins": [
    "RS1.4",
    "RS1.1",
    "L45.1"
   ],
   "hops": [
    {
     "from": {
      "component": "J15",
      "pin": "8"
     },
     "to": {
      "component": "RS1",
      "pin": "4"
     },
     "net": "12V_PEX6_8_INP",
     "edge_kind": "net",
     "tentative": false,
     "depth": 1,
     "evidence": "12V_PEX6_8_INP",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INP in the file"
    },
    {
     "from": {
      "component": "RS1",
      "pin": "4"
     },
     "to": {
      "component": "RS1",
      "pin": "1"
     },
     "net": null,
     "edge_kind": "inferred_crossing_asserted_by_caller",
     "tentative": true,
     "depth": 2,
     "evidence": null,
     "why": "caller assertion: the 0.005ohm current-sense stand-in is one through-path - the caller (not the file) states that RS1 connects pin 4 to pin 1 internally",
     "intervening_component": "RS1",
     "asserted_by": "caller (the file never states this crossing)",
     "asserted_label": "the 0.005ohm current-sense stand-in is one through-path",
     "eligibility": {
      "bridgeable": true,
      "reason": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "rule": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "inferred_kind": "virtual_placeholder",
      "kind_basis": [
       "resistor (weight 0.85): ohm value in the DEVICE name",
       "sense (weight 0.7): DEVICE name contains token 'sense'",
       "sense (weight 0.7): DEVICE name contains token 'rsense'",
       "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
       "multi_pin_unit (weight 0.55): 4 declared pins",
       "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2",
       "3",
       "4"
      ],
      "pin_count_declared": 4,
      "pin_count_connected": 4,
      "pairings": 6,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": [],
      "assumed_pair": [
       "4",
       "1"
      ]
     }
    },
    {
     "from": {
      "component": "RS1",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "1"
     },
     "net": "12V_PEX6_8_INN",
     "edge_kind": "net",
     "tentative": false,
     "depth": 3,
     "evidence": "12V_PEX6_8_INN",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INN in the file"
    }
   ],
   "nets_in_order": [
    "12V_PEX6_8_INP",
    "12V_PEX6_8_INN"
   ],
   "tentative_hops": [
    {
     "component": "RS1",
     "pin": "1"
    }
   ],
   "tentative_hop_kinds": [
    "inferred_crossing_asserted_by_caller"
   ],
   "intervening_components": [
    "RS1"
   ],
   "file_certain_hops": 2,
   "hypothesis_hops": 0,
   "asserted_hops": 1,
   "same_route_without_internal_crossing": false,
   "same_route_note": "False refers to the route named by `label`: asserted_only=true means the same route also exists without crossing any component internally",
   "verdict": "file plus your own conclusions (no name-rule crossing was needed)",
   "caller_asserted_hops": 1,
   "verdict_note": "fewest component crossings"
  },
  {
   "index": 1,
   "target": "U7",
   "label": "fewest component crossings",
   "components": [
    "RS1",
    "RS1",
    "L45",
    "L45",
    "U7"
   ],
   "pins": [
    "RS1.4",
    "RS1.1",
    "L45.1",
    "L45.2",
    "U7.8"
   ],
   "hops": [
    {
     "from": {
      "component": "J15",
      "pin": "8"
     },
     "to": {
      "component": "RS1",
      "pin": "4"
     },
     "net": "12V_PEX6_8_INP",
     "edge_kind": "net",
     "tentative": false,
     "depth": 1,
     "evidence": "12V_PEX6_8_INP",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INP in the file"
    },
    {
     "from": {
      "component": "RS1",
      "pin": "4"
     },
     "to": {
      "component": "RS1",
      "pin": "1"
     },
     "net": null,
     "edge_kind": "inferred_crossing_asserted_by_caller",
     "tentative": true,
     "depth": 2,
     "evidence": null,
     "why": "caller assertion: the 0.005ohm current-sense stand-in is one through-path - the caller (not the file) states that RS1 connects pin 4 to pin 1 internally",
     "intervening_component": "RS1",
     "asserted_by": "caller (the file never states this crossing)",
     "asserted_label": "the 0.005ohm current-sense stand-in is one through-path",
     "eligibility": {
      "bridgeable": true,
      "reason": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "rule": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "inferred_kind": "virtual_placeholder",
      "kind_basis": [
       "resistor (weight 0.85): ohm value in the DEVICE name",
       "sense (weight 0.7): DEVICE name contains token 'sense'",
       "sense (weight 0.7): DEVICE name contains token 'rsense'",
       "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
       "multi_pin_unit (weight 0.55): 4 declared pins",
       "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2",
       "3",
       "4"
      ],
      "pin_count_declared": 4,
      "pin_count_connected": 4,
      "pairings": 6,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": [],
      "assumed_pair": [
       "4",
       "1"
      ]
     }
    },
    {
     "from": {
      "component": "RS1",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "1"
     },
     "net": "12V_PEX6_8_INN",
     "edge_kind": "net",
     "tentative": false,
     "depth": 3,
     "evidence": "12V_PEX6_8_INN",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INN in the file"
    },
    {
     "from": {
      "component": "L45",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "2"
     },
     "net": null,
     "edge_kind": "inferred_crossing_asserted_by_caller",
     "tentative": true,
     "depth": 4,
     "evidence": null,
     "why": "caller assertion: the 1uH filter has one through-path - the caller (not the file) states that L45 connects pin 1 to pin 2 internally",
     "intervening_component": "L45",
     "asserted_by": "caller (the file never states this crossing)",
     "asserted_label": "the 1uH filter has one through-path",
     "eligibility": {
      "bridgeable": true,
      "reason": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
      "rule": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
      "inferred_kind": "inductor",
      "kind_basis": [
       "inductor (weight 0.9): henry value in the DEVICE name",
       "inductor (weight 0.4): DEVICE name contains token 'chk'",
       "inductor-like (weight 0.25): reference prefix L is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2"
      ],
      "pin_count_declared": 2,
      "pin_count_connected": 2,
      "pairings": 1,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": [],
      "assumed_pair": [
       "1",
       "2"
      ]
     }
    },
    {
     "from": {
      "component": "L45",
      "pin": "2"
     },
     "to": {
      "component": "U7",
      "pin": "8"
     },
     "net": "12V_PEX6_8_F1",
     "edge_kind": "net",
     "tentative": false,
     "depth": 5,
     "evidence": "12V_PEX6_8_F1",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_F1 in the file"
    }
   ],
   "nets_in_order": [
    "12V_PEX6_8_INP",
    "12V_PEX6_8_INN",
    "12V_PEX6_8_F1"
   ],
   "tentative_hops": [
    {
     "component": "RS1",
     "pin": "1"
    },
    {
     "component": "L45",
     "pin": "2"
    }
   ],
   "tentative_hop_kinds": [
    "inferred_crossing_asserted_by_caller"
   ],
   "intervening_components": [
    "L45",
    "RS1"
   ],
   "file_certain_hops": 3,
   "hypothesis_hops": 0,
   "asserted_hops": 2,
   "same_route_without_internal_crossing": false,
   "same_route_note": "False refers to the route named by `label`: asserted_only=true means the same route also exists without crossing any component internally",
   "verdict": "file plus your own conclusions (no name-rule crossing was needed)",
   "caller_asserted_hops": 2,
   "verdict_note": "fewest component crossings"
  },
  {
   "index": 2,
   "target": "U7",
   "label": "fewest internal-crossing hops",
   "components": [
    "RS1",
    "RS1",
    "L45",
    "L45",
    "U7"
   ],
   "pins": [
    "RS1.4",
    "RS1.1",
    "L45.1",
    "L45.2",
    "U7.34"
   ],
   "hops": [
    {
     "from": {
      "component": "J15",
      "pin": "8"
     },
     "to": {
      "component": "RS1",
      "pin": "4"
     },
     "net": "12V_PEX6_8_INP",
     "edge_kind": "net",
     "tentative": false,
     "depth": 1,
     "evidence": "12V_PEX6_8_INP",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INP in the file"
    },
    {
     "from": {
      "component": "RS1",
      "pin": "4"
     },
     "to": {
      "component": "RS1",
      "pin": "1"
     },
     "net": null,
     "edge_kind": "inferred_crossing_asserted_by_caller",
     "tentative": true,
     "depth": 2,
     "evidence": null,
     "why": "caller assertion: the 0.005ohm current-sense stand-in is one through-path - the caller (not the file) states that RS1 connects pin 4 to pin 1 internally",
     "intervening_component": "RS1",
     "asserted_by": "caller (the file never states this crossing)",
     "asserted_label": "the 0.005ohm current-sense stand-in is one through-path",
     "eligibility": {
      "bridgeable": true,
      "reason": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "rule": "virtual-placeholder rule: the SHAPE/DEVICE name marks this component as a stand-in for a connection the file does not draw, so crossings between its pads are offered; the pairing of the pads is not stated in the file, so each pairing is a hypothesis",
      "inferred_kind": "virtual_placeholder",
      "kind_basis": [
       "resistor (weight 0.85): ohm value in the DEVICE name",
       "sense (weight 0.7): DEVICE name contains token 'sense'",
       "sense (weight 0.7): DEVICE name contains token 'rsense'",
       "virtual_placeholder (weight 0.7): DEVICE name contains token 'virtual'",
       "multi_pin_unit (weight 0.55): 4 declared pins",
       "regular-shape sense terminal (weight 0.25): reference prefix RS is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2",
       "3",
       "4"
      ],
      "pin_count_declared": 4,
      "pin_count_connected": 4,
      "pairings": 6,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": [],
      "assumed_pair": [
       "4",
       "1"
      ]
     }
    },
    {
     "from": {
      "component": "RS1",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "1"
     },
     "net": "12V_PEX6_8_INN",
     "edge_kind": "net",
     "tentative": false,
     "depth": 3,
     "evidence": "12V_PEX6_8_INN",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_INN in the file"
    },
    {
     "from": {
      "component": "L45",
      "pin": "1"
     },
     "to": {
      "component": "L45",
      "pin": "2"
     },
     "net": null,
     "edge_kind": "inferred_crossing_asserted_by_caller",
     "tentative": true,
     "depth": 4,
     "evidence": null,
     "why": "caller assertion: the 1uH filter has one through-path - the caller (not the file) states that L45 connects pin 1 to pin 2 internally",
     "intervening_component": "L45",
     "asserted_by": "caller (the file never states this crossing)",
     "asserted_label": "the 1uH filter has one through-path",
     "eligibility": {
      "bridgeable": true,
      "reason": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
      "rule": "two-terminal passive rule: exactly two terminals, both with nets, and an inferred passive kind",
      "inferred_kind": "inductor",
      "kind_basis": [
       "inductor (weight 0.9): henry value in the DEVICE name",
       "inductor (weight 0.4): DEVICE name contains token 'chk'",
       "inductor-like (weight 0.25): reference prefix L is a viewer convention, not file data"
      ],
      "terminals": [
       "1",
       "2"
      ],
      "pin_count_declared": 2,
      "pin_count_connected": 2,
      "pairings": 1,
      "inferred": true,
      "note": "tentative: the file never states an internal connection; a path through this component is a hypothesis to verify against the physical board or the schematic",
      "assumed_bridges": [],
      "assumed_pair": [
       "1",
       "2"
      ]
     }
    },
    {
     "from": {
      "component": "L45",
      "pin": "2"
     },
     "to": {
      "component": "U7",
      "pin": "34"
     },
     "net": "12V_PEX6_8_F1",
     "edge_kind": "net",
     "tentative": false,
     "depth": 5,
     "evidence": "12V_PEX6_8_F1",
     "why": "both pins are listed under SIGNAL 12V_PEX6_8_F1 in the file"
    }
   ],
   "nets_in_order": [
    "12V_PEX6_8_INP",
    "12V_PEX6_8_INN",
    "12V_PEX6_8_F1"
   ],
   "tentative_hops": [
    {
     "component": "RS1",
     "pin": "1"
    },
    {
     "component": "L45",
     "pin": "2"
    }
   ],
   "tentative_hop_kinds": [
    "inferred_crossing_asserted_by_caller"
   ],
   "intervening_components": [
    "L45",
    "RS1"
   ],
   "file_certain_hops": 3,
   "hypothesis_hops": 0,
   "asserted_hops": 2,
   "same_route_without_internal_crossing": false,
   "same_route_note": "False refers to the route named by `label`: asserted_only=true means the same route also exists without crossing any component internally",
   "verdict": "file plus your own conclusions (no name-rule crossing was needed)",
   "caller_asserted_hops": 2,
   "verdict_note": "fewest internal-crossing hops"
  }
 ],
 "bridge_policy": "internal crossings are only ever hypotheses or caller assertions, never file facts; two rule-based sub-rules create edges of kind=inferred_crossing_from_name_rules and tentative=true: (1) exactly two declared pads, both carrying nets, and an inferred passive kind (capacitor/inductor/ferrite_bead/resistor/fuse); (2) the component's own SHAPE/DEVICE name marks it as a placeholder for a connection the drawing does not make (kind virtual_placeholder, e.g. SHAPE RSENSE_VIRTUAL_04_SMD_2512 or SHAPE VIRTUAL_SHORT) - the file says the stand-in is there but never says which pads face each other, so each pad pairing is offered as a labelled hypothesis. Everything else is refused by the rules: active or structural kinds (integrated_circuit, connector, test_point, mounting_hole) are NEVER crossed internally - each pad is re-entered through its own net - and a passive component with more than two net-carrying pads is refused because naming the pairing would invent electrical facts. Either way the caller may assert a specific crossing through assumed_bridges, which yields kind=inferred_crossing_asserted_by_caller: the caller's knowledge, still not file evidence. Pad coordinates, distances and the words in SHAPE/DEVICE names are exposed by tools.get_component so the caller can reason instead of guessing. ROUTE/VIA records are drawing data and never take part in connectivity.",
 "search_note": "one best route per target per search, capped by max_hops and an internal pop budget; the file does not contain route topology, so an undiscovered target means the search budget ran out, not that no route exists",
 "excluded_nets": [
  "GND"
 ]
}
```

the chain, hop by hop, with its layer:
  net: J15:8 -> RS1:4 net=12V_PEX6_8_INP tentative=False label=None
  inferred_crossing_asserted_by_caller: RS1:4 -> RS1:1 net=None tentative=True label=the 0.005ohm current-sense stand-in is one through-path
  net: RS1:1 -> L45:1 net=12V_PEX6_8_INN tentative=False label=None
  inferred_crossing_asserted_by_caller: L45:1 -> L45:2 net=None tentative=True label=the 1uH filter has one through-path
  net: L45:2 -> U7:8 net=12V_PEX6_8_F1 tentative=False label=None
  verdict: file plus your own conclusions (no name-rule crossing was needed)
  file_certain_hops=3 hypothesis_hops=0 asserted_hops=2 tentative_hop_kinds=['inferred_crossing_asserted_by_caller']

### find_shared_rails across the chain (GND cut out, exclusions echoed)

```json
{
 "requested": [
  "RS1",
  "L45",
  "U7",
  "J15"
 ],
 "resolved": [
  "RS1",
  "L45",
  "U7",
  "J15"
 ],
 "excluded_nets": [
  "GND"
 ],
 "rail_count": 3,
 "rails": [
  {
   "net": "12V_PEX6_8_F1",
   "shared_by": [
    "L45",
    "U7"
   ],
   "total_members_on_net": 47,
   "members_truncated": true,
   "members_sample": [
    {
     "component": "C119",
     "pin": "1"
    },
    {
     "component": "C121",
     "pin": "1"
    },
    {
     "component": "C123",
     "pin": "1"
    },
    {
     "component": "C124",
     "pin": "1"
    },
    {
     "component": "C126",
     "pin": "1"
    },
    {
     "component": "C110",
     "pin": "1"
    },
    {
     "component": "C111",
     "pin": "1"
    },
    {
     "component": "C112",
     "pin": "1"
    },
    {
     "component": "C113",
     "pin": "1"
    },
    {
     "component": "C116",
     "pin": "1"
    },
    {
     "component": "C218",
     "pin": "1"
    },
    {
     "component": "C220",
     "pin": "1"
    },
    {
     "component": "C223",
     "pin": "1"
    },
    {
     "component": "C64",
     "pin": "1"
    },
    {
     "component": "C66",
     "pin": "1"
    },
    {
     "component": "C70",
     "pin": "1"
    },
    {
     "component": "C72",
     "pin": "1"
    },
    {
     "component": "C74",
     "pin": "1"
    },
    {
     "component": "L45",
     "pin": "2"
    },
    {
     "component": "R762",
     "pin": "1"
    },
    {
     "component": "R885",
     "pin": "1"
    },
    {
     "component": "RS2",
     "pin": "1"
    },
    {
     "component": "U10",
     "pin": "8"
    },
    {
     "component": "U10",
     "pin": "9"
    },
    {
     "component": "U10",
     "pin": "10"
    },
    {
     "component": "U10",
     "pin": "11"
    },
    {
     "component": "U10",
     "pin": "34"
    },
    {
     "component": "U11",
     "pin": "8"
    },
    {
     "component": "U11",
     "pin": "9"
    },
    {
     "component": "U11",
     "pin": "10"
    },
    {
     "component": "U11",
     "pin": "11"
    },
    {
     "component": "U11",
     "pin": "34"
    },
    {
     "component": "U7",
     "pin": "8"
    },
    {
     "component": "U7",
     "pin": "9"
    },
    {
     "component": "U7",
     "pin": "10"
    },
    {
     "component": "U7",
     "pin": "11"
    },
    {
     "component": "U7",
     "pin": "34"
    },
    {
     "component": "U8",
     "pin": "8"
    },
    {
     "component": "U8",
     "pin": "9"
    },
    {
     "component": "U8",
     "pin": "10"
    }
   ],
   "pins_of_each_sharer_on_this_net": {
    "L45": [
     "2"
    ],
    "U7": [
     "8",
     "9",
     "10",
     "11",
     "34"
    ]
   }
  },
  {
   "net": "12V_PEX6_8_INN",
   "shared_by": [
    "RS1",
    "L45"
   ],
   "total_members_on_net": 2,
   "members_truncated": false,
   "members_sample": [
    {
     "component": "L45",
     "pin": "1"
    },
    {
     "component": "RS1",
     "pin": "1"
    }
   ],
   "pins_of_each_sharer_on_this_net": {
    "RS1": [
     "1"
    ],
    "L45": [
     "1"
    ]
   }
  },
  {
   "net": "12V_PEX6_8_INP",
   "shared_by": [
    "RS1",
    "J15"
   ],
   "total_members_on_net": 7,
   "members_truncated": false,
   "members_sample": [
    {
     "component": "C191",
     "pin": "1"
    },
    {
     "component": "C190",
     "pin": "1"
    },
    {
     "component": "C192",
     "pin": "1"
    },
    {
     "component": "J15",
     "pin": "6"
    },
    {
     "component": "J15",
     "pin": "7"
    },
    {
     "component": "J15",
     "pin": "8"
    },
    {
     "component": "RS1",
     "pin": "4"
    }
   ],
   "pins_of_each_sharer_on_this_net": {
    "RS1": [
     "4"
    ],
    "J15": [
     "6",
     "7",
     "8"
    ]
   }
  }
 ],
 "pairwise": {
  "12V_PEX6_8_INN": [
   "RS1",
   "L45"
  ],
  "12V_PEX6_8_INP": [
   "RS1",
   "J15"
  ],
  "12V_PEX6_8_F1": [
   "L45",
   "U7"
  ]
 }
}
```

### export_subgraph around RS1 pad 4 (machine-readable, invariants stated)

```json
{
 "counts": {
  "components": 9,
  "nets": 4,
  "edges": 61
 },
 "kinds": {
  "C190": "capacitor",
  "C191": "capacitor",
  "C192": "capacitor",
  "J15": "connector",
  "L45": "inductor",
  "R261": "resistor",
  "R275": "resistor",
  "R276": "resistor",
  "RS1": "virtual_placeholder"
 },
 "nets_windowed": [],
 "net_fanout": [
  {
   "net": "12V_PEX6_8_INP",
   "members_on_net": 7,
   "times_followed": 36
  },
  {
   "net": "12V_PEX6_8_CH2_INP",
   "members_on_net": 3,
   "times_followed": 2
  },
  {
   "net": "12V_PEX6_8_CH2_INN",
   "members_on_net": 2,
   "times_followed": 1
  },
  {
   "net": "12V_PEX6_8_INN",
   "members_on_net": 2,
   "times_followed": 1
  }
 ],
 "invariants": {
  "net_edges_always_name_their_net": true,
  "internal_crossings_are_always_marked": true,
  "no_net_member_comes_from_route_or_via_records": true,
  "members_are_windowed": false,
  "rule_crossings_only_on_bridgeable_parts": true,
  "rule_crossings_never_touch_pads_without_nets": true,
  "internal_crossings_are_either_rule_offered_or_caller_asserted": true
 },
 "invariants_note": "the first four are properties of this build; the last two re-check the edges actually emitted here against the policy in bridge_policy, using the eligibility ctx already computed",
 "excluded_nets": [
  "GND"
 ],
 "truncated": false
}
```

sentinel: OK
