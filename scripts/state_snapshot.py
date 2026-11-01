"""Regenerate docs/STATE_SNAPSHOT.txt: the layer vocabulary, the tool set, and the real board's
eligibility verdicts and crossing verdicts as the code stands today.

Run: ``python3 scripts/state_snapshot.py > docs/STATE_SNAPSHOT.txt``
"""

import json

from boardview_mcp.context import BoardContext
from boardview_mcp.graph import (
    ASSUMED_EDGE,
    NET_EDGE,
    RULE_EDGE,
    SHARED_NET_EDGE,
    ConnectivityGraph,
)
from boardview_mcp.tools import evaluate_crossing
from boardview_mcp.server import TOOLS

REAL = r"S:\WindowsLibraries\Documents\GPU REPAIR\MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad"

LAYERS = [NET_EDGE, SHARED_NET_EDGE, RULE_EDGE, ASSUMED_EDGE]
REFS = ["J15", "RS1", "L45", "C191", "U7", "G1", "R1", "FM1", "VS501"]
PAIRS = [("RS1", ["4", "1"]), ("L45", ["1", "2"]), ("U7", ["1", "2"]), ("R1", ["1", "2"])]

ctx = BoardContext(REAL)
graph = ConnectivityGraph(ctx.board)
print("LAYERS:", json.dumps(LAYERS))
print("TOOLS:", json.dumps(list(TOOLS)))
for ref in REFS:
    print("ELIG", ref, json.dumps(graph.bridge_eligibility(ref), ensure_ascii=False))
for ref, pads in PAIRS:
    q = evaluate_crossing(ctx, ref, pads)
    keep = ("question", "file_facts", "verdict", "policy_opinion", "if_the_model_agrees")
    print("CROSSING", ref, json.dumps({k: q[k] for k in keep}, ensure_ascii=False))
print("SENTINEL: OK")
