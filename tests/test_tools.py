"""Tool-level tests: registration, schemas, and the tools called through a real MCP client.

The client here runs *in process* against the same :class:`MCPServer` the CLI would serve, so the
JSON envelope and the annotations are exercised exactly as Open WebUI would see them. The live HTTP
round trip lives in :mod:`test_server_http`.
"""

import asyncio
import json
import os

import pytest

from boardview_mcp.server import TOOLS, build_server
from boardview_mcp.context import BoardContext
from boardview_mcp.server import INSTRUCTIONS
from conftest import MINIMAL, REAL_BOARD, real_context

pytestmark = []  # keep module-level; individual real-board tests use skipif below


def _json_text(result) -> dict:
    """Flatten a CallToolResult into a dict, failing loudly if the server returned anything odd."""

    parts = []
    for item in result.content:
        assert item.type == "text", f"unexpected content type {item.type!r}"
        parts.append(item.text)
    assert len(parts) == 1, f"expected exactly one text block, got {len(parts)}"
    return json.loads(parts[0])


async def _call(server, name: str, args: dict) -> dict:
    from mcp import Client

    async with Client(server) as client:
        return _json_text(await client.call_tool(name, args))


async def _list(server):
    from mcp import Client

    async with Client(server) as client:
        return (await client.list_tools()).tools


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


@pytest.fixture(scope="module")
def minimal_server():
    return build_server(context=BoardContext(str(MINIMAL)))


@pytest.fixture(scope="module")
def schema_only_server():
    return build_server(load=False)


# ------------------------------------------------------------------ registration and schema shape


def test_exactly_ten_tools_are_registered():
    server = build_server(load=False)
    tools = _run(_list(server))
    assert sorted(t.name for t in tools) == sorted(TOOLS)
    assert len(tools) == 10


def test_schemas_bear_descriptions_and_readonly_annotations():
    server = build_server(load=False)
    tools = {t.name: t for t in _run(_list(server))}
    for name in TOOLS:
        tool = tools[name]
        assert len(tool.description) > 30, f"{name} needs an AI-readable description"
        ann = tool.annotations
        assert ann is not None and ann.read_only_hint is True and ann.destructive_hint is False
        dumped = ann.model_dump(by_alias=True)
        assert dumped["readOnlyHint"] is True, "the wire form must carry the camelCase MCP field"
        schema = tool.model_dump(by_alias=True)["inputSchema"]
        assert schema.get("type") == "object"
        assert "ctx" not in schema.get("properties", {}), "the board context must not be model-visible"
        assert "board_path" not in schema.get("properties", {}), "the file path must not be model-visible"


def test_server_advertises_instructions():
    server = build_server(load=False)
    assert INSTRUCTIONS, "the server must ship AI-facing instructions"
    text = INSTRUCTIONS.lower()
    for phrase in ("tentative", "inferred", "net"):
        assert phrase in text, f"instructions must explain {phrase}"


# ------------------------------------------------------------------ fixture-level tool behaviour


def test_fixture_board_summary_counts():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "board_summary", {}))
    assert res["file"]["version"] == "1.4"
    counts = res["counts"]
    assert counts["components"] == 7
    assert counts["nets"] == 6
    assert counts["pin_records_total"] == 22  # 21 shape-declared pins + IC1 pin "B2" named by a NODE but not declared by SIX_PIN_IC
    assert counts["pin_net_memberships"] == 14  # 15 NODE records, one of them a duplicate (DUP_NET repeats C1 1)
    assert counts["declared_pins_unconnected"] >= 3  # J1:2, RS1:1, RS1:3
    assert counts["components_with_no_nets"] == 0
    assert res["parse"]["errors"] == []
    assert any("repeated inside SIGNAL" in w for w in res["parse"]["warnings"]), "the duplicate NODE must be visible to the model"
    assert any("no NODE members" in w for w in res["parse"]["warnings"]), "the empty net must be visible to the model"
    assert res["connectivity_model"]["route_vias"] == "ROUTE/VIA records are drawing data, NOT electrical members"
    assert res["counts"]["routes"] == 5  # one ROUTE per named SIGNAL, drawing data only


def test_fixture_get_net_is_the_declared_membership_list_verbatim():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "get_net", {"name": "RAIL_IN"}))
    assert res["net"] == "RAIL_IN"
    assert res["total_members"] == 4
    assert [(m["component"], m["pin"]) for m in res["members"]] == [("J1", "1"), ("C1", "1"), ("R1", "2"), ("IC1", "6")]
    assert res["truncated"] is False
    assert res["grouping_scope_note"] == "members_by_component covers every member of this net"
    assert res["route_vias_are_not_members"] is True
    assert res["route_drawing_exists"] is True


def test_fixture_duplicate_node_records_are_reported_not_merged():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "get_net", {"name": "DUP_NET"}))
    assert res["total_members"] == 2  # the repeated NODE collapses to one member entry
    assert res["distinct_components"] == 2
    assert res["duplicate_member_records"] == 1, "the repeat must be counted, not silently dropped"


def test_fixture_pagination_window_scoping():
    server = build_server(context=BoardContext(str(MINIMAL)))
    page = _run(_call(server, "get_net", {"name": "RAIL_IN", "offset": 0, "limit": 2}))
    assert [(m["component"], m["pin"]) for m in page["members"]] == [("J1", "1"), ("C1", "1")]
    assert page["truncated"] is True
    assert set(page["members_by_component"]) == {"J1", "C1"}  # scoped to the window, not the whole net
    assert set(page["inferred_classification_of_members"]) <= {"J1", "C1"}
    assert "only the returned window" in page["grouping_scope_note"]
    rest = _run(_call(server, "get_net", {"name": "RAIL_IN", "offset": 2, "limit": 2}))
    assert [(m["component"], m["pin"]) for m in rest["members"]] == [("R1", "2"), ("IC1", "6")]
    assert rest["truncated"] is False
    assert {(m["component"], m["pin"]) for m in page["members"]} & {(m["component"], m["pin"]) for m in rest["members"]} == set()


def test_fixture_search_modes_are_reported():
    server = build_server(context=BoardContext(str(MINIMAL)))
    sub = _run(_call(server, "search_components", {"query": "PIN"}))
    assert sub["match_mode"] == "substring"
    assert {m["ref"] for m in sub["matches"]} == {"J1", "C1", "R1", "RS1", "IC1", "K1"}  # by SHAPE/package name
    glob = _run(_call(server, "search_components", {"query": "IC*"}))
    assert glob["match_mode"] == "glob"
    assert {m["ref"] for m in glob["matches"]} == {"IC1"}


def test_fixture_unknown_reference_errors_with_candidates():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "get_component", {"ref": "C1X"}))
    assert res["error"], "unknown refs must be an explicit error"
    assert res["queried"] == "C1X"
    assert "C1" in res["similar_components"]
    assert res.get("found") is not True, "never fabricate a component"


def test_fixture_four_pin_sense_block_offers_crossings_as_hypotheses():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "get_component", {"ref": "RS1"}))
    elig = res["component"]["bridge_eligibility"]
    assert res["component"]["pin_count_declared"] == 4
    assert elig["bridgeable"] is True, "two of the four pads carry nets: the two-terminal rule offers one crossing"
    assert elig["rule"].startswith("two-terminal")
    assert elig["pin_count_connected"] == 2 and elig["pairings"] == 1
    assert elig["terminals"] == ["2", "4"], "pads without nets must never enter a rule pairing"
    assert res["component"]["unconnected_pins"] == ["1", "3"]
    assert res["component"]["inferred_classification"]["inferred"] is True
    assert res["component"]["inferred_classification"]["kind"] == "resistor"
    assert res["component"]["inferred_classification"]["basis"], "inference must state its basis"
    walk = _run(_call(server, "find_connected_components", {"component": "RS1", "pin": "4", "depth": 1}))
    assert all(e["tentative"] for e in walk["edges"] if e["edge_kind"] != "net"), "any crossing out of RS1 is marked"
    assert "1" not in {e["to"]["pin"] for e in walk["edges"] if e["to"]["component"] == "RS1"}, "an unconnected pad is unreachable"


def test_fixture_two_pin_capacitor_is_the_only_bridgeable_shape():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "get_component", {"ref": "C1"}))
    assert res["component"]["bridge_eligibility"]["bridgeable"] is True
    assert res["component"]["bridge_eligibility"]["inferred_kind"] == "capacitor"
    assert res["component"]["bridge_eligibility"]["terminals"] == ["1", "2"]
    assert res["component"]["bridge_eligibility"]["inferred"] is True


def test_fixture_trace_power_path_states_hypothesis():
    server = build_server(context=BoardContext(str(MINIMAL)))
    args = {"start": [{"component": "J1", "pin": "1"}], "target_components": ["K1"]}
    bridged = _run(_call(server, "trace_power_path", dict(args, allow_bridges=True)))
    assert len(bridged["paths"]) == 1
    path = bridged["paths"][0]
    assert path["components"] == ["C1", "C1", "K1"]  # enters C1, crosses it, then lands on K1
    assert path["nets_in_order"] == ["RAIL_IN", "MID_NET"]
    assert path["file_certain_hops"] == 2 and path["hypothesis_hops"] == 1 and path["asserted_hops"] == 0
    assert path["intervening_components"] == ["C1"]
    assert path["tentative_hop_kinds"] == ["inferred_crossing_from_name_rules"]
    assert path["verdict"] == "partly hypothetical: at least one hop is a crossing the name rule offered"
    strict = _run(_call(server, "trace_power_path", dict(args, allow_bridges=False)))
    assert strict["paths"] == [] and strict["truncated"] is False  # proven, not merely unsearched


def test_fixture_shared_rails():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "find_shared_rails", {"components": ["J1", "C1", "R1"]}))
    assert [r["net"] for r in res["rails"]] == ["DUP_NET", "RAIL_IN"]
    rail = {r["net"]: r for r in res["rails"]}
    assert rail["RAIL_IN"]["pins_of_each_sharer_on_this_net"] == {"J1": ["1"], "C1": ["1"], "R1": ["2"]}
    assert rail["RAIL_IN"]["total_members_on_net"] == 4


def test_fixture_export_subgraph_invariants_hold():
    server = build_server(context=BoardContext(str(MINIMAL)))
    res = _run(_call(server, "export_subgraph", {"start": [{"component": "C1", "pin": "1"}], "depth": 2}))
    assert res["invariants"]["rule_crossings_only_on_bridgeable_parts"] is True
    assert res["invariants"]["net_edges_always_name_their_net"] is True
    assert res["invariants"]["no_net_member_comes_from_route_or_via_records"] is True
    assert res["invariants"]["internal_crossings_are_either_rule_offered_or_caller_asserted"] is True
    assert "RAIL_IN" in res["nets"] and "MID_NET" in res["nets"]
    assert {e["kind"] for e in res["edges"]} <= {"net", "inferred_crossing_from_name_rules", "same_component_shared_net"}
    assert res["counts"]["edges"] == len(res["edges"]) and res["counts"]["nets"] == len(res["nets"])


def test_fixture_export_subgraph_geometry_switch():
    server = build_server(context=BoardContext(str(MINIMAL)))
    with_geo = _run(_call(server, "export_subgraph", {"start": [{"component": "C1", "pin": "1"}], "depth": 1}))
    without = _run(_call(server, "export_subgraph", {"start": [{"component": "C1", "pin": "1"}], "depth": 1, "include_geometry": False}))
    pinned_geo = [p for comp in with_geo["components"].values() for p in comp["pins"].values()]
    assert pinned_geo and all("x" in p and "y" in p for p in pinned_geo)
    pinned_flat = [p for comp in without["components"].values() for p in comp["pins"].values()]
    assert all("x" not in p and "y" not in p for p in pinned_flat)


# ------------------------------------------------------------------ real board through the MCP client


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_three_tools_over_the_wire():
    server = build_server(context=real_context())
    summary = _run(_call(server, "board_summary", {}))
    assert summary["counts"]["components"] == 1932
    assert summary["counts"]["nets"] == 1363
    assert summary["counts"]["pin_net_memberships"] == 8700
    assert summary["counts"]["pin_records_total"] == 8868
    assert summary["file"]["bytes"] == 5868394
    assert summary["parse"]["errors"] == []

    net = _run(_call(server, "get_net", {"name": "12V_PEX6_8_INP"}))
    assert net["net"] == "12V_PEX6_8_INP"
    assert net["total_members"] == 7
    assert [(m["component"], m["pin"]) for m in net["members"]] == [
        ("C191", "1"), ("C190", "1"), ("C192", "1"), ("J15", "6"), ("J15", "7"), ("J15", "8"), ("RS1", "4"),
    ]
    assert net["multi_pin_components_on_this_net"] == {"J15": ["6", "7", "8"]}

    comp = _run(_call(server, "get_component", {"ref": "J15"}))
    assert comp["found"] is True and comp["resolved_ref"] == "J15"
    assert comp["component"]["pin_count_declared"] == 10
    assert list(comp["component"]["pins"]) == ["1", "2", "3", "4", "5", "6", "7", "8", "MEC1", "MEC2"]
    assert comp["component"]["same_component_shared_net"] == {"GND": ["1", "2", "4"], "12V_PEX6_8_INP": ["6", "7", "8"]}
    assert comp["component"]["bridge_eligibility"]["bridgeable"] is False
    assert comp["component"]["inferred_classification"]["kind"] == "connector"
    assert comp["component"]["position"]["x"] == 4601.457
    assert comp["component"]["rotation"] == 180.0


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_pagination_on_the_big_net():
    server = build_server(context=real_context())
    res = _run(_call(server, "get_net", {"name": "GND", "limit": 5}))
    assert res["total_members"] == 2858
    assert len(res["members"]) == 5
    assert res["truncated"] is True
    assert set(res["inferred_classification_of_members"]) <= {m["component"] for m in res["members"]}
    big = _run(_call(server, "get_net", {"name": "GND", "limit": 500}))
    assert len(big["members"]) == 500 and big["truncated"] is True
    payload = len(_json_text.__self__ if False else repr(big))
    assert payload < 400_000, "a page must stay inside a bounded payload"


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_mis_transcribed_name_is_never_repaired():
    """The user reported 12V_PEX8_6_INP; the file has 12V_PEX6_8_INP. The server must not silently fix it."""

    server = build_server(context=real_context())
    res = _run(_call(server, "get_net", {"name": "12V_PEX8_6_INP"}))
    assert res["error"] == "net name not found"
    assert res["queried"] == "12V_PEX8_6_INP"
    assert "12V_PEX8_6_INP" not in res["similar_nets"]
    assert "12V_PEX6_8_INP" in res["similar_nets"]
    comp = _run(_call(server, "get_component", {"ref": "12V_PEX8_6_INP"}))
    assert comp["error"] == "component reference not found"


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_power_trace_from_the_connector():
    server = build_server(context=real_context())
    args = {"start": [{"component": "J15", "pin": "6"}], "target_components": ["C191", "L45"]}
    res = _run(_call(server, "trace_power_path", dict(args, allow_bridges=False)))
    assert res["unknown_targets"] == []
    by_target = {p["target"] for p in res["paths"]}
    assert by_target == {"C191"}, "strict mode: L45 sits behind RS1's internal join, which strict mode refuses"
    assert res["truncated"] is False, "the strict search is exhaustive over what it refused to cross"
    path = res["paths"][0]
    assert path["nets_in_order"] == ["12V_PEX6_8_INP"]
    assert path["tentative_hops"] == [] and path["hypothesis_hops"] == 0 and path["asserted_hops"] == 0
    assert path["verdict"] == "asserted by the file (every hop is a shared SIGNAL)"
    loose = _run(_call(server, "trace_power_path", args))  # default: the name rule may offer crossings
    assert {p["target"] for p in loose["paths"]} >= {"C191", "L45"}, "both already file-certain"
    l45 = [p for p in loose["paths"] if p["target"] == "L45"][0]
    assert set(l45["tentative_hop_kinds"]) <= {"inferred_crossing_from_name_rules"}, (
        "the only hypothesis this mode may introduce is a name-rule crossing"
    )
    assert l45["asserted_hops"] == 0 and l45["hypothesis_hops"] == 1
    assert l45["verdict"] == "partly hypothetical: at least one hop is a crossing the name rule offered"
    assert {h["intervening_component"] for h in l45["hops"] if h["tentative"]} == {"RS1"}


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_start_from_a_net_descriptor():
    server = build_server(context=real_context())
    res = _run(_call(server, "find_connected_components", {"net": "12V_PEX6_8_INP", "depth": 1}))
    assert res["start"]["net"] == "12V_PEX6_8_INP"
    kinds = {e["edge_kind"] for e in res["edges"]}
    assert kinds <= {"net", "same_component_shared_net", "inferred_crossing_from_name_rules"}
    bridged = [e for e in res["edges"] if e["edge_kind"] == "inferred_crossing_from_name_rules"]
    assert bridged and all(e["tentative"] for e in bridged), "depth 1 does bridge 2-pin passive members; each such edge must be labelled tentative"
    assert {e["intervening_component"] for e in bridged} == {"C190", "C191", "C192", "RS1"}, "RS1's own name marks a virtual placeholder"
    assert ("J15", "7") in {(e["to"]["component"], e["to"]["pin"]) for e in res["edges"]}
    bad = _run(_call(server, "find_connected_components", {"component": "NOPE", "net": "12V_PEX8_6_INP"}))
    assert bad["error"] == "start not found" and len(bad["missed"]) == 2


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_reasoning_about_a_two_pad_part_is_the_models_own():
    """`R1` (package `0402`, device `100k`, pad 1 -> `12V_F`, pad 2 -> `DP1_MODE*`): the model may
    read a through-path in its name, but the file never joins those rails, so the join is only ever
    the model's own assertion. This is the user's verified path taken through the tool layer."""

    server = build_server(context=real_context())
    rec = _run(_call(server, "get_component", {"ref": "R1"}))
    assert rec["found"] is True and rec["resolved_ref"] == "R1"
    comp = rec["component"]
    assert comp["ref"] == "R1" and comp["package"] == "0402" and comp["device"] == "100k"
    assert comp["pin_count_declared"] == 2 and comp["pin_count_connected"] == 2
    assert comp["nets"] == ["12V_F", "DP1_MODE*"] and comp["connected_pins"] == ["1", "2"]
    assert {p: v["nets"] for p, v in comp["pins"].items()} == {"1": ["12V_F"], "2": ["DP1_MODE*"]}
    for key in ("cross_net", "bridges", "internal_connections"):
        assert key not in comp, "a crossing may not live in the component's file facts"
    st = comp["structure"]
    assert st["pad_count_declared"] == 2 and st["pad_count_with_coordinates"] == 2
    assert st["pad_pairs_total"] == 1 and st["pad_pairs_truncated"] is False
    assert st["pads_already_sharing_a_net"] == [], "the file shows no two pads sharing a SIGNAL"
    assert set(st["undrawn_connections"]) >= {"file_states", "file_never_states", "how_to_reason"}
    assert any(
        "continues to another pad" in s for s in st["undrawn_connections"]["file_never_states"]
    ), "the structure block states plainly that the file never draws the internal path"
    pair = st["pad_pairs_by_distance"][0]
    assert pair["pins"] == ["1", "2"] and pair["shared_nets"] == []
    assert pair["nets_first_pad"] == ["12V_F"] and pair["nets_second_pad"] == ["DP1_MODE*"]
    assert pair["across_footprint"] is True, "the two pads sit at opposite ends of the footprint"
    vocab = st["name_vocabulary"]
    assert vocab["package_tokens"] == ["0402"] and vocab["device_tokens"] == ["100k"]
    assert any("resistor" in basis for basis in vocab["matched_by_classify"]), "the naming the model reads"

    q = _run(_call(server, "evaluate_crossing", {"component": "R1", "pins": ["1", "2"]}))
    assert q["question"]["pads"] == ["1", "2"] and q["question"]["proposed_by"] == "caller (the model, not the file)"
    assert q["file_facts"]["pad_a_nets"] == ["12V_F"] and q["file_facts"]["pad_b_nets"] == ["DP1_MODE*"]
    assert q["file_facts"]["pads_share_a_net"] == []
    assert q["contradicts_file"] == [], "nothing in the file forbids the model's reading either"
    assert q["structural_facts"]["geometry"]["distance"] == 31.514
    assert q["structural_facts"]["geometry"]["across_footprint"] is True
    naming = q["structural_facts"]["naming"]
    assert naming["package_tokens"] == ["0402"] and naming["device_tokens"] == ["100k"]
    verdict = q["verdict"]
    assert verdict["stated_in_file"] is False and verdict["joined_elsewhere_in_file"] is False
    assert verdict["contradicted_by_file"] is False and verdict["file_cannot_settle_it"] is True
    opinion = q["policy_opinion"]["server_rule_says"]
    assert opinion["bridgeable"] is True and opinion["inferred_kind"] == "resistor"
    assert "name-shape heuristic" in q["policy_opinion"]["note"]
    ready = q["if_the_model_agrees"]["record_as"]
    assert ready["component"] == "R1" and ready["pins"] == ["1", "2"]
    assert "inferred_crossing_asserted_by_caller" in q["if_the_model_agrees"]["how_to_use"]

    args = {"component": "R1", "pin": "1", "depth": 1}
    strict = _run(_call(server, "find_connected_components", dict(args, allow_bridges=False)))
    assert strict["allow_bridges"] is False and strict["tentative_edges"] == 0
    assert ("R1", "2") not in {(e["to"]["component"], e["to"]["pin"]) for e in strict["edges"]}
    assert {e["edge_kind"] for e in strict["edges"]} == {"net"}, "the file joins nothing inside R1"
    asserted = {"component": "R1", "pins": ["1", "2"], "label": "0402 100k resistor: one through-path"}
    res = _run(_call(server, "find_connected_components", dict(args, assumed_bridges=[asserted])))
    joined = [e for e in res["edges"] if (e["to"]["component"], e["to"]["pin"]) == ("R1", "2")]
    assert len(joined) == 1, "one edge, and only because the model asserted it"
    edge = joined[0]
    assert edge["edge_kind"] == "inferred_crossing_asserted_by_caller" and edge["tentative"] is True
    assert edge["net"] is None and edge["intervening_component"] == "R1"
    assert edge["asserted_label"] == asserted["label"]
    assert "the file never states this crossing" in edge["asserted_by"]
    assert edge["eligibility"]["assumed_pair"] == ["1", "2"] and edge["eligibility"]["bridgeable"] is True
    assert res["assumed_edges"] == 1 and res["tentative_edges"] == 1
    assert res["allow_bridges"] is True


def test_tools_are_read_only_and_stable():
    """Two identical calls must return identical JSON, and the board file must be untouched."""

    server = build_server(context=real_context())
    before = os.stat(str(REAL_BOARD))
    a = _run(_call(server, "get_component", {"ref": "RS1"}))
    b = _run(_call(server, "get_component", {"ref": "RS1"}))
    assert a == b
    after = os.stat(str(REAL_BOARD))
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    walk1 = _run(_call(server, "trace_connectivity", {"start": [{"component": "C191", "pin": "1"}], "max_depth": 2}))
    walk2 = _run(_call(server, "trace_connectivity", {"start": [{"component": "C191", "pin": "1"}], "max_depth": 2}))
    assert walk1 == walk2, "the graph must not be mutated by a traversal"
    assert walk1["tentative_edges"] >= 0 and walk1["bridge_policy"] == walk2["bridge_policy"]
