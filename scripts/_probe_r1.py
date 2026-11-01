"""Print the exact JSON keys the tools return for the user's R1 example.

Run: ``python3 scripts/_probe_r1.py`` (regenerate when the tool envelope changes).
"""

import asyncio
import json

from boardview_mcp.context import BoardContext
from boardview_mcp.server import build_server

PATH = r"S:\WindowsLibraries\Documents\GPU REPAIR\MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad"
server = build_server(context=BoardContext(PATH))

LABEL = "0402 100k resistor: one through-path"
CALLS = [
    ("get_component", {"ref": "R1"}),
    ("evaluate_crossing", {"component": "R1", "pins": ["1", "2"]}),
    ("find_connected_components", {"component": "R1", "pin": "1", "depth": 1, "allow_bridges": False}),
    (
        "find_connected_components",
        {
            "component": "R1",
            "pin": "1",
            "depth": 1,
            "assumed_bridges": [{"component": "R1", "pins": ["1", "2"], "label": LABEL}],
        },
    ),
]


async def main() -> None:
    from mcp import Client

    async with Client(server) as client:
        for name, args in CALLS:
            res = await client.call_tool(name, args)
            obj = json.loads([i.text for i in res.content if i.type == "text"][0])
            print("###", name, json.dumps(args, ensure_ascii=False))
            print("TOP KEYS:", sorted(obj.keys()))
            if "component" in obj and isinstance(obj["component"], dict):
                comp = obj["component"]
                print("COMPONENT KEYS:", sorted(comp.keys()))
                st = comp.get("structure", {})
                print("STRUCTURE KEYS:", sorted(st.keys()))
                print("PADS:", json.dumps(st.get("pads"), ensure_ascii=False))
                print("PAIRS:", json.dumps(st.get("pad_pairs_by_distance"), ensure_ascii=False))
                print("VOCAB:", json.dumps(st.get("name_vocabulary"), ensure_ascii=False))
                print("UNDRAWN KEYS:", sorted(st.get("undrawn_connections", {}).keys()))
                print("UNDRAWN file_never_states:", json.dumps(st.get("undrawn_connections", {}).get("file_never_states"), ensure_ascii=False))
            if "verdict" in obj:
                print("QUESTION:", json.dumps(obj["question"], ensure_ascii=False))
                print("FILE_FACTS:", json.dumps(obj["file_facts"], ensure_ascii=False))
                print("STRUCT_FACTS KEYS:", sorted(obj["structural_facts"].keys()))
                print("GEOMETRY:", json.dumps(obj["structural_facts"]["geometry"], ensure_ascii=False))
                print("NAMING:", json.dumps(obj["structural_facts"]["naming"], ensure_ascii=False))
                print("VERDICT:", json.dumps(obj["verdict"], ensure_ascii=False))
                print("POLICY:", json.dumps(obj["policy_opinion"], ensure_ascii=False))
                print("MODEL_AGREES:", json.dumps(obj["if_the_model_agrees"], ensure_ascii=False))
                print("DISAGREES:", json.dumps(obj["if_the_model_disagrees"], ensure_ascii=False))
                print("CONTRADICTS_FILE:", json.dumps(obj["contradicts_file"], ensure_ascii=False))
                print("SOURCE:", json.dumps(obj["source"], ensure_ascii=False))
            if "edges" in obj:
                print("EDGE0:", json.dumps(obj["edges"][0], ensure_ascii=False))
                print("KINDS:", sorted({e.get("edge_kind") for e in obj["edges"]}))
                for e in obj["edges"]:
                    if (e["to"].get("component"), e["to"].get("pin")) == ("R1", "2"):
                        print("R1 EDGE:", json.dumps(e, ensure_ascii=False))
                print("ASSUMED_EDGES:", json.dumps(obj.get("assumed_edges"), ensure_ascii=False))
                print("TENTATIVE_EDGES:", obj.get("tentative_edges"))
                print("BRIDGE_POLICY:", json.dumps(obj.get("bridge_policy"), ensure_ascii=False)[:400])


asyncio.run(main())
