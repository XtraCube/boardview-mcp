import asyncio
import json

from boardview_mcp.context import BoardContext
from boardview_mcp.server import build_server
from boardview_mcp.tools import evaluate_crossing, get_component

PATH = r"S:\WindowsLibraries\Documents\GPU REPAIR\MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad"
ctx = BoardContext(PATH)

c = get_component(ctx, "R1")["component"]
print("ref:", c["ref"], "package:", c["package"], "device:", c["device"])
print("nets:", c["nets"], "connected:", c["connected_pins"], "declared:", c["pin_count_declared"])
print("pins:", json.dumps(c["pins"], ensure_ascii=False)[:400])
print("explicitly_in_file:", json.dumps(c["explicitly_in_file"], ensure_ascii=False)[:300])
st = c["structure"]
print("STRUCTURE:", json.dumps(st, ensure_ascii=False)[:900])
q = evaluate_crossing(ctx, "R1", ["1", "2"])
print("Q KEYS:", sorted(q.keys()))
print("Q file_facts:", json.dumps(q["file_facts"], ensure_ascii=False))
print("Q policy:", json.dumps(q["policy_opinion"], ensure_ascii=False))
print("Q verdict:", json.dumps(q["verdict"], ensure_ascii=False))
print("Q agrees:", json.dumps(q.get("if_the_model_agrees"), ensure_ascii=False))
print("Q pads:", q.get("pads"))

server = build_server(context=ctx)


async def main() -> None:
    from mcp import Client

    async with Client(server) as client:
        strict = await client.call_tool(
            "find_connected_components",
            {"start": [{"component": "R1", "pin": "1"}], "depth": 1, "allow_bridges": False},
        )
        res = await client.call_tool(
            "find_connected_components",
            {
                "start": [{"component": "R1", "pin": "1"}],
                "depth": 1,
                "assumed_bridges": [{"component": "R1", "pins": ["1", "2"], "label": "R1 joins its rails"}],
            },
        )

    def flat(result):
        return json.loads([i.text for i in result.content][0])

    s, a = flat(strict), flat(res)
    print("STRICT edge to-pins:", sorted({(e["to"]["component"], e["to"].get("pin")) for e in s["edges"]}))
    print("RES KEYS:", sorted(a.keys()))
    print("assumed:", json.dumps(a.get("assumed_bridges"), ensure_ascii=False)[:500])
    print("edge kinds:", sorted({e.get("edge_kind") for e in a["edges"]}))
    for e in a["edges"]:
        if e["to"].get("component") == "R1" and e["to"].get("pin") == "2":
            print("EDGE:", json.dumps(e, ensure_ascii=False))


asyncio.run(main())
