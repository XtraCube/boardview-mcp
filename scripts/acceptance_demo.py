"""Run the acceptance chain against a LIVE server over Streamable HTTP, and print the evidence.

The chain the final goal asks for: follow 12 V from the PCIe power connector through the current-sense
stand-in and the 1uH filter into the downstream integrated circuit, quoting only pin/net spellings that a
tool returned. Run it as

    python scripts/acceptance_demo.py > docs/EVIDENCE_ACCEPTANCE.md

so the transcript in the repo is reproducible. Nothing here imports the parser: the script starts the same
CLI a human would start, and then speaks MCP to it exactly as Open WebUI does.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from typing import Any

BOARD_DEFAULT = r"S:\WindowsLibraries\Documents\GPU REPAIR\MS-V397 REV 10 BOARDVIEW (BDV)(.CAD) .cad"
BANNER = "serving MCP over Streamable HTTP"


def _free_port(start: int = 8200, stop: int = 8299) -> int:
    for candidate in range(start, stop):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", candidate))
            return candidate
        except OSError:
            continue
    raise RuntimeError("no free port in the search range")


def _call(url: str, name: str, args: dict) -> Any:
    from mcp import Client

    async def _go() -> Any:
        async with Client(url) as client:
            result = await client.call_tool(name, args)
        parts = [item.text for item in result.content]
        assert len(parts) == 1, f"expected one text block, got {len(parts)}"
        return json.loads(parts[0])

    return asyncio.run(_go())


def _names(url: str) -> list[str]:
    from mcp import Client

    async def _go() -> list[str]:
        async with Client(url) as client:
            return [t.name for t in (await client.list_tools()).tools]

    return asyncio.run(_go())


def _show(title: str, payload: Any, *, keys: list[str] | None = None, width: int = 100) -> None:
    print(f"\n### {title}\n")
    print("```json")
    shown = {k: payload[k] for k in keys if k in payload} if keys else payload
    print(json.dumps(shown, indent=1, ensure_ascii=False))
    print("```")


def main() -> int:
    board = os.environ.get("BOARDVIEW_FILE", "").strip() or BOARD_DEFAULT
    port = _free_port()
    env = dict(os.environ)
    proc = subprocess.Popen(
        [sys.executable, "-m", "boardview_mcp", "--board", board, "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    deadline = time.time() + 120
    banner = None
    while time.time() < deadline and banner is None:
        line = proc.stdout.readline()
        if not line:
            break
        if BANNER in line:
            banner = line.strip()
    if banner is None:
        proc.terminate()
        print("server never announced its endpoint")
        return 1
    print(f"server banner: {banner}")
    url = f"http://127.0.0.1:{port}/mcp"

    try:
        listed = _wait_names(url)
        print(f"tools advertised over the wire ({len(listed)}): {', '.join(sorted(listed))}")

        summary = _call(url, "board_summary", {})
        _show("board_summary (identity, counts, connectivity model in words)", summary,
              keys=["file", "format", "version", "counts", "units", "parse_errors", "warnings",
                    "connectivity_model", "inferred_kinds"])

        net = _call(url, "get_net", {"name": "12V_PEX6_8_INP"})
        _show("get_net on the connector rail (every member in file order)", net,
              keys=["net_count", "nets", "window", "total_members_truncated", "truncated", "source"])

        connector = _call(url, "get_component", {"ref": "J15"})
        _show("get_component J15: the connector and its pin->net map", connector["component"],
              keys=["ref", "package", "device", "pin_count_declared", "pin_count_connected",
                    "nets", "connected_pins", "explicitly_in_file", "source"])

        rs1 = _call(url, "get_component", {"ref": "RS1"})
        _show("get_component RS1: structure block only (the reasoning surface)", rs1["component"]["structure"],
              keys=["pad_count_declared", "pad_count_with_coordinates", "pads", "footprint",
                    "pad_pairs_by_distance", "pad_pairs_total", "name_vocabulary", "undrawn_connections"])

        q1 = _call(url, "evaluate_crossing", {"component": "RS1", "pins": ["4", "1"],
                                              "reason": "the 0.005ohm current-sense stand-in is one through-path"})
        _show("evaluate_crossing RS1 pads 4/1: the question asked back, no edge added", q1)

        r1 = _call(url, "get_component", {"ref": "R1"})
        _show("get_component R1: the user's own example, a real 2-pad resistor (0402 / 100k)", r1["component"],
              keys=["ref", "package", "device", "pin_count_declared", "pin_count_connected", "nets",
                    "connected_pins", "structure"])
        r1q = _call(url, "evaluate_crossing", {"component": "R1", "pins": ["1", "2"]})
        _show("evaluate_crossing R1 pads 1/2: 12V_F against DP1_MODE* - the file cannot settle this pair", r1q)
        assert r1q["verdict"]["file_cannot_settle_it"] is True, "the file must not answer this one either way"
        assert r1q["file_facts"]["rails_joined_by_other_components"] == [], (
            "no other component joins those two rails anywhere in the file"
        )
        r1strict = _call(url, "find_connected_components",
                         {"component": "R1", "pin": "1", "depth": 1, "allow_bridges": False})
        assert ("R1", "2") not in {(e["to"]["component"], e["to"]["pin"]) for e in r1strict["edges"]}, {
            "the file joins nothing inside R1"
        }
        print(f"\nfile-only from R1 pad 1: {len(r1strict['edges'])} edges, all kind=net,"
              f" tentative_edges={r1strict['tentative_edges']}")
        r1loose = _call(url, "find_connected_components",
                        {"component": "R1", "pin": "1", "depth": 1,
                         "assumed_bridges": [r1q["if_the_model_agrees"]["record_as"]]})
        joined = [e for e in r1loose["edges"] if (e["to"]["component"], e["to"]["pin"]) == ("R1", "2")]
        assert len(joined) == 1, "exactly one edge for the pair the model asserted"
        assert joined[0]["edge_kind"] == "inferred_crossing_asserted_by_caller" and joined[0]["net"] is None
        _show("the model's own join through R1, echoed as its conclusion", joined[0])

        file_only = _call(url, "trace_power_path",
                          {"start": [{"component": "J15", "pin": "8"}], "target_components": ["U7", "L45"],
                           "max_hops": 6, "exclude_nets": ["GND"], "allow_bridges": False})
        _show("trace_power_path with allow_bridges=false: the file alone cannot get past the sense pad",
              file_only, keys=["paths", "search_note", "bridge_policy", "truncated"])
        assert file_only["paths"] == [], "file facts alone must not reach U7"

        q2 = _call(url, "evaluate_crossing", {"component": "L45", "pins": ["1", "2"],
                                              "reason": "the 1uH filter has one through-path"})
        _show("evaluate_crossing L45 pads 1/2", q2,
              keys=["question", "structural_facts", "file_facts", "policy_opinion", "verdict"])

        rules_only = _call(url, "trace_power_path",
                           {"start": [{"component": "J15", "pin": "8"}], "target_components": ["U7", "L45"],
                            "max_hops": 8, "exclude_nets": ["GND"]})
        _show("trace_power_path with only the server's name-rule crossings (the model has said nothing)",
              rules_only, keys=["paths", "search_note", "bridge_policy", "truncated"])
        rule_chains = [p for p in rules_only["paths"] if re.search(r"\bU7\b", " ".join(p["components"]))]
        assert rule_chains, "two-pad parts offer their own crossing, so the chain is reachable by hypothesis"
        rbest = rule_chains[0]
        print(f"\nname-rule chain to U7: {rbest['components']} "
              f"hypothesis_hops={rbest['hypothesis_hops']} caller_asserted_hops={rbest['caller_asserted_hops']}")
        assert rbest["hypothesis_hops"] >= 1 and rbest["same_route_without_internal_crossing"] is False, \
            "a name-rule chain is a hypothesis, and no bridge-free route exists for the same pair"

        records = [q1["if_the_model_agrees"]["record_as"], q2["if_the_model_agrees"]["record_as"]]
        print("\nassumed_bridges records handed back by evaluate_crossing, passed through unchanged:")
        print(json.dumps(records, indent=1, ensure_ascii=False))

        loose = _call(url, "trace_power_path",
                      {"start": [{"component": "J15", "pin": "8"}],
                       "target_components": ["U7", "L45"],
                       "max_hops": 8, "exclude_nets": ["GND"], "assumed_bridges": records})
        _show("trace_power_path with the model's own crossings asserted", loose,
              keys=["assumed_bridges", "paths", "bridge_policy", "search_note", "excluded_nets"])
        chain = [p for p in loose["paths"] if re.search(r"\bU7\b", " ".join(p["components"]))]
        assert chain, "the verified chain must come back once both crossings are asserted"
        best = chain[0]
        print("\nthe chain, hop by hop, with its layer:")
        for hop in best["hops"]:
            print(f"  {hop['edge_kind']}: {hop['from']['component']}:{hop['from']['pin']} -> "
                  f"{hop['to']['component']}:{hop['to']['pin']} net={hop['net']}"
                  f" tentative={hop['tentative']} label={hop.get('asserted_label')}")
        print(f"  verdict: {best['verdict']}")
        print(f"  file_certain_hops={best['file_certain_hops']} hypothesis_hops={best['hypothesis_hops']} "
              f"asserted_hops={best['asserted_hops']} tentative_hop_kinds={best['tentative_hop_kinds']}")
        assert best["caller_asserted_hops"] >= 1 and set(best["tentative_hop_kinds"]) == {
            "inferred_crossing_asserted_by_caller"}, \
            "the model's own crossings replace the name-rule hints for those pairs"

        rails = _call(url, "find_shared_rails", {"components": ["RS1", "L45", "U7", "J15"],
                                                 "exclude_nets": ["GND"]})
        _show("find_shared_rails across the chain (GND cut out, exclusions echoed)", rails,
              keys=["requested", "resolved", "excluded_nets", "rail_count", "rails", "pairwise"])

        sub = _call(url, "export_subgraph",
                    {"start": [{"component": "RS1", "pin": "4"}], "depth": 2,
                     "exclude_nets": ["GND"], "assumed_bridges": records})
        _show("export_subgraph around RS1 pad 4 (machine-readable, invariants stated)", sub,
              keys=["counts", "kinds", "nets_windowed", "net_fanout", "invariants", "invariants_note",
                    "excluded_nets", "truncated"])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("\nsentinel: OK")
    return 0


def _wait_names(url: str, tries: int = 40) -> list[str]:
    """Poll with a real MCP handshake, so readiness is proven and not guessed from the banner."""
    last: Exception | None = None
    for _ in range(tries):
        try:
            return _names(url)
        except Exception as exc:
            last = exc
            time.sleep(0.5)
    raise AssertionError(f"server never became reachable at {url}: {last!r}")


if __name__ == "__main__":
    raise SystemExit(main())
