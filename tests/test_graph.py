"""Connectivity graph + inference tests, against the curated fixture and the real board."""

import os

import pytest

from boardview_mcp.graph import BRIDGE_POLICY_NOTE, ConnectivityGraph
from boardview_mcp.classify import PASSIVE_KINDS, classify_component
from boardview_mcp.parser import parse_file
from conftest import MINIMAL, MALFORMED, REAL_BOARD, real_board, real_context


def trace_edges(walk: dict) -> set[tuple]:
    return {(e["from"]["component"], e["from"]["pin"], e["component"], e["pin"], e["net"], e["kind"]) for e in walk["edges"]}


def edge_kinds(walk: dict) -> set[str]:
    return {e["kind"] for e in walk["edges"]}


# ------------------------------------------------------------------ net facts from the fixture


def test_fixture_net_edges_are_exactly_the_declared_memberships():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    assert g.members("RAIL_IN") == [("J1", "1"), ("C1", "1"), ("R1", "2"), ("IC1", "6")]
    assert g.nets_of("C1") == ["RAIL_IN", "DUP_NET", "MID_NET"]  # pin 1 first (file order), then pin 2
    assert g.nets_of("C1", pin="2") == ["MID_NET"]
    assert g.components_on("MID_NET") == ["C1", "RS1", "K1"]
    kinds = {(e["kind"], e["same_component"]) for e in g.direct_neighbours("C1", "1")}
    assert kinds == {("net", False)}
    assert [(e["component"], e["pin"], e["net"]) for e in g.direct_neighbours("J1", "1")] == [
        ("C1", "1", "RAIL_IN"),
        ("R1", "2", "RAIL_IN"),
        ("IC1", "6", "RAIL_IN"),
    ]
    assert [(e["component"], e["pin"], e["net"]) for e in g.direct_neighbours("IC1", "6")] == [
        ("J1", "1", "RAIL_IN"),
        ("C1", "1", "RAIL_IN"),
        ("R1", "2", "RAIL_IN"),
    ]
    # no edge ever leads from IC1:6 to another pin of IC1 through that net
    assert not [e for e in g.direct_neighbours("IC1", "6") if e["component"] == "IC1"]


def test_same_component_shared_net_is_kept_and_labelled():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    edges = g.direct_neighbours("J1", "1")
    assert all(e["kind"] == "net" for e in edges)
    # J1 has one pin on RAIL_IN; the multi-pin case lives in ALPHA_NET (FP1 A1 + MEC1)
    edges = g.direct_neighbours("FP1", "A1")
    assert [(e["component"], e["pin"], e["kind"]) for e in edges] == [
        ("FP1", "MEC1", "same_component_shared_net"),
        ("IC1", "B2", "net"),
    ]
    assert g.direct_neighbours("FP1", "A1")[0]["tentative"] is False
    # from the IC1 side, both ALPHA_NET pins of FP1 are plain cross-component net edges
    assert {(e["component"], e["pin"], e["kind"]) for e in g.direct_neighbours("IC1", "B2")} == {
        ("FP1", "A1", "net"),
        ("FP1", "MEC1", "net"),
    }


def test_empty_net_yields_no_edges():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    assert g.members("ORPHAN_NET") == []
    assert g.direct_neighbours("J1", "2") == []


def test_duplicate_membership_is_counted_not_multiplied():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    assert g.members("DUP_NET") == [("C1", "1"), ("R1", "1")]
    assert board.nets["DUP_NET"].duplicate_members == 1


def test_route_vias_never_appear_as_net_members():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    all_members = {(r, p) for net in board.nets for r, p in g.members(net)}
    assert all(r in board.components for r, _p in all_members)
    assert "PS_1" not in {r for r, _ in all_members}  # padstack names are not component refs


# ------------------------------------------------------------------ bridging policy


def test_only_net_carrying_terminals_can_form_a_crossing():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    assert g.bridge_eligibility("C1")["bridgeable"] is True  # 10uF, two pins
    assert g.bridge_eligibility("C1")["inferred_kind"] == "capacitor"
    assert g.bridge_eligibility("C1")["inferred"] is True
    assert g.bridge_eligibility("IC1")["bridgeable"] is False
    assert "not a passive terminal pair" in g.bridge_eligibility("IC1")["reason"]
    assert g.bridge_eligibility("NOPE")["bridgeable"] is False
    assert g.bridge_eligibility("NOPE")["inferred"] is False
    assert g.bridge_eligibility("J1")["bridgeable"] is False  # a connector: active/structural kind


def test_bridge_edges_are_tentative_and_name_the_component():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    edges = g.bridge_neighbours("C1", "1")
    assert len(edges) == 1
    edge = edges[0]
    assert edge["kind"] == "inferred_crossing_from_name_rules" and edge["tentative"] is True
    assert edge["component"] == "C1" and edge["pin"] == "2"
    assert edge["intervening_component"] == "C1"
    assert edge["inferred_kind"] == "capacitor"
    assert "never states an internal connection" in edge["eligibility"]["note"]
    assert g.bridge_neighbours("IC1", "1") == []


def test_bridges_off_changes_only_tentative_edges():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    on = g.trace([("J1", "1")], max_depth=2, allow_bridges=True)
    off = g.trace([("J1", "1")], max_depth=2, allow_bridges=False)
    assert on["tentative_edges"] == 2  # C1 and R1 are both two-terminal passive components
    assert off["tentative_edges"] == 0
    assert edge_kinds(off) == {"net"}
    assert len(off["nodes"]) < len(on["nodes"])
    assert {(n["component"], n["pin"]) for n in off["nodes"]} <= {(n["component"], n["pin"]) for n in on["nodes"]}


def test_ic_is_never_crossed_internally():
    """IC1 pin 6 sits on RAIL_IN; its other pins must stay unreachable without bridges."""
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    walk = g.trace([("IC1", "6")], max_depth=3, allow_bridges=False)
    reached = {n["component"] for n in walk["nodes"]}
    assert reached == {"IC1", "J1", "C1", "R1"}
    assert not any(n["component"] == "IC1" and n["pin"] != "6" for n in walk["nodes"])
    assert "inferred_crossing_from_name_rules" not in edge_kinds(walk)


def test_trace_seeds_from_a_net():
    board = parse_file(str(MINIMAL))
    g = ConnectivityGraph(board)
    walk = g.trace([("C1", None)], max_depth=1, allow_bridges=False)
    assert {(e["from"]["component"], e["from"]["pin"]) for e in walk["edges"]} == {("C1", "1"), ("C1", "2")}
    assert walk["seed_nodes"] == [{"component": "C1", "pin": "1"}, {"component": "C1", "pin": "2"}]
    assert walk["max_depth"] == 1


# ------------------------------------------------------------------ real board: policy must hold on it

PLACEHOLDER_ON = {"RS1", "RS2", "RS501", "RS3", "RS4", "VS501"}  # SHAPE/DEVICE says VIRTUAL or VIRTUAL_SHORT


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_bridge_decisions():
    g = ConnectivityGraph(real_board())
    for ref in ("C191", "C190", "C192", "L45", "R275"):
        assert g.bridge_eligibility(ref)["bridgeable"] is True
        assert g.bridge_eligibility(ref)["rule"].startswith("two-terminal")
    assert g.bridge_eligibility("C191")["inferred_kind"] == "capacitor"
    assert g.bridge_eligibility("L45")["inferred_kind"] == "inductor"
    # the sense pad is a placeholder: crossings offered, but only as labelled hypotheses
    assert g.bridge_eligibility("RS1")["bridgeable"] is True
    assert g.bridge_eligibility("RS1")["rule"].startswith("virtual-placeholder")
    assert g.bridge_eligibility("RS1")["terminals"] == ["1", "2", "3", "4"]
    assert g.bridge_eligibility("RS1")["pairings"] == 6
    assert g.bridge_eligibility("J15")["bridgeable"] is False  # ten pins, active kind
    assert g.bridge_eligibility("U7")["bridgeable"] is False
    assert g.bridge_eligibility("G1")["bridgeable"] is False  # 2714-pin BGA
    assert g.bridge_eligibility("G1")["pin_count_declared"] == 2714
    assert g.bridge_eligibility("G1")["reason"].startswith("inferred kind"), "the refusal is about the NAME"


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_multi_pin_net_edges_are_labelled():
    g = ConnectivityGraph(real_board())
    # direct_neighbours is the file-only layer, so no internal crossings appear in it at all
    edges = g.direct_neighbours("J15", "6")
    assert [(e["component"], e["pin"], e["kind"]) for e in edges] == [
        ("C191", "1", "net"),
        ("C190", "1", "net"),
        ("C192", "1", "net"),
        ("J15", "7", "same_component_shared_net"),
        ("J15", "8", "same_component_shared_net"),
        ("RS1", "4", "net"),
    ]
    assert g.nets_of("J15", pin="6") == ["12V_PEX6_8_INP"]
    # order follows the component's own pins 1..4 (file order), NOT alphabetical
    assert g.nets_of("RS1") == ["12V_PEX6_8_INN", "12V_PEX6_8_CH2_INN", "12V_PEX6_8_CH2_INP", "12V_PEX6_8_INP"]


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_crossing_the_sense_pad_needs_both_bridges():
    """J15 pin 6 and L45 pin 1 share no net: the only way between the two rails crosses RS1
    internally. Strict search proves the absence; the placeholder sub-rule offers the crossing,
    and it must land on L45 pin 1 exactly once, labelled as a hypothesis (user chain, m00882)."""
    g = ConnectivityGraph(real_board())
    strict = g.paths_between([("J15", "6")], ["L45"], allow_bridges=False, max_hops=4)
    assert strict["paths"] == [] and strict["truncated"] is False  # absence is exhaustive
    assert g.bridge_eligibility("RS1")["bridgeable"] is True
    assert g.bridge_eligibility("RS1")["rule"].startswith("virtual-placeholder")
    res = g.paths_between([("J15", "6")], ["L45"], allow_bridges=True, max_hops=4)
    assert res["paths"], "the placeholder sub-rule must make the verified crossing walkable"
    for path in res["paths"]:
        crossings = [h for h in path["hops"] if h["component"] == "RS1" and h["kind"] == "inferred_crossing_from_name_rules"]
        assert len(crossings) == 1, "one internal crossing only, or the test scenario changed"
        assert path["tentative_hops"] >= 1 and path["caller_asserted_hops"] == 0
        assert (path["hops"][-1]["component"], path["hops"][-1]["pin"]) == ("L45", "1")
        assert path["asserted_only"] is False
    # explicit re-entry needs no bridge at all: name RS1's other pin, then continue from it
    res2 = g.paths_between([("RS1", "1")], ["L45"], allow_bridges=False, max_hops=2)
    assert len(res2["paths"]) >= 1
    assert (res2["paths"][0]["hops"][-1]["component"], res2["paths"][0]["hops"][-1]["pin"]) == ("L45", "1")
    assert res2["paths"][0]["asserted_only"] is True


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_bridged_walk_is_marked():
    g = ConnectivityGraph(real_board())
    strict = g.trace([("J15", "6")], max_depth=3, allow_bridges=False, max_nodes=300)
    assert strict["tentative_edges"] == 0 and strict["assumed_edges"] == 0
    assert "GND" not in strict["nets_touched"]
    walk = g.trace([("J15", "6")], max_depth=3, allow_bridges=True, max_nodes=300)
    assert walk["tentative_edges"] > 0
    assert "GND" in walk["nets_touched"]
    for e in walk["edges"]:
        if e["kind"] == "inferred_crossing_from_name_rules":
            assert g.bridge_eligibility(e["intervening_component"])["bridgeable"] is True
    assert BRIDGE_POLICY_NOTE.startswith("internal crossings are")


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_user_verified_chain_hops_are_labelled():
    """The user-supplied chain (m00882) step by step, each hop labelled by its own evidence kind.

    J15 pin 8 -> RS1 pin 4 (shared SIGNAL 12V_PEX6_8_INP); RS1 pin 4 -> RS1 pin 1 (internal crossing);
    RS1 pin 1 -> L45 pin 1 (12V_PEX6_8_INN); L45 pin 1 -> L45 pin 2; L45 pin 2 -> U7 pin 34 (12V_PEX6_8_F1).
    """
    board = real_board()
    g = ConnectivityGraph(board)
    steps = [
        ("J15", "8", "RS1", "4"),
        ("RS1", "4", "RS1", "1"),
        ("RS1", "1", "L45", "1"),
        ("L45", "1", "L45", "2"),
        ("L45", "2", "U7", "34"),
    ]
    for comp_a, pin_a, comp_b, pin_b in steps:
        file_edges = [e for e in g.direct_neighbours(comp_a, pin_a) if (e["component"], e["pin"]) == (comp_b, pin_b)]
        bridged = [e for e in g.neighbours(comp_a, pin_a, allow_bridges=True) if (e["component"], e["pin"]) == (comp_b, pin_b)]
        if file_edges:
            assert [e["kind"] for e in file_edges] == ["net"], "this hop is a file fact"
            assert file_edges[0]["net"] in board.components[comp_a].pins[pin_a].nets
        else:
            assert file_edges == [], "this hop is not a file fact"
        assert bridged, f"{comp_a}:{pin_a} -> {comp_b}:{pin_b} must be walkable once crossings are allowed"
        assert all(e["tentative"] for e in bridged if e["kind"] != "net")


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_rule_hypothesis_and_caller_assertion_are_distinguishable():
    """The placeholder sub-rule offers RS1 4<->1 as a hypothesis; the caller can assert the same pair,
    and a pair the rules refuse (an IC crossing on U7, both pins with nets) is accepted only as an
    assertion - the two edge kinds must never be confused."""
    from boardview_mcp.graph import ASSUMED_EDGE

    g = ConnectivityGraph(real_board())
    hypothesis = [e for e in g.neighbours("RS1", "4") if (e["component"], e["pin"]) == ("RS1", "1")]
    assert hypothesis and hypothesis[0]["kind"] == "inferred_crossing_from_name_rules"
    assert hypothesis[0]["eligibility"]["rule"].startswith("virtual-placeholder")
    res = g.set_assumed_bridges([
        {"component": "RS1", "pins": ["4", "1"], "label": "user-verified: opposite pads of the 0.005ohm current-sense part"},
        {"component": "U7", "pins": ["1", "2"], "label": "crossing an IC"},
        {"component": "NO_SUCH", "pins": ["1", "2"], "label": "bogus"},
    ])
    assert len(res["accepted"]) == 2, "the rules refusing U7 must not stop a caller assertion"
    assert res["rejected"] == [{"assumption": "NO_SUCH", "why": "unknown component reference"}]
    asserted = [e for e in g.neighbours("RS1", "4") if (e["component"], e["pin"]) == ("RS1", "1")]
    assert [e["kind"] for e in asserted] == [ASSUMED_EDGE], "the assertion replaces the hypothesis for that pair"
    assert "never states" in asserted[0]["asserted_by"]
    assert "user-verified" in asserted[0]["asserted_label"]
    assert g.bridge_eligibility("U7")["bridgeable"] is False and g.bridge_eligibility("U7")["assumed_bridges"], (
        "U7 stays rule-refused but carries the caller assertion")
    ic_hop = [e for e in g.neighbours("U7", "1") if (e["component"], e["pin"]) == ("U7", "2")]
    assert [e["kind"] for e in ic_hop] == [ASSUMED_EDGE], "an asserted IC crossing is walkable and labelled"
    g.set_assumed_bridges([])  # every later test sees the rule-only policy again


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_no_asserted_path_through_the_sense_pad():
    """File-only search proves J15 pin 6 cannot reach L45: the crossing would be invented evidence."""
    g = ConnectivityGraph(real_board())
    strict = g.paths_between([("J15", "6")], ["L45"], allow_bridges=False, max_hops=4)
    assert strict["paths"] == [] and strict["truncated"] is False  # absence is exhaustive
    assert g.bridge_eligibility("RS1")["bridgeable"] is True  # the rule offers it, but not as a file fact
    res = g.paths_between([("RS1", "1")], ["L45"], allow_bridges=False, max_hops=2)
    assert len(res["paths"]) >= 1
    assert (res["paths"][0]["hops"][-1]["component"], res["paths"][0]["hops"][-1]["pin"]) == ("L45", "1")
    assert res["paths"][0]["asserted_only"] is True and res["paths"][0]["tentative_hops"] == 0


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_user_chain_end_to_end_through_the_tool():
    """The whole m00882 chain walked through the tool layer, GND excluded, both crossings asserted."""
    from boardview_mcp.tools import trace_power_path

    ctx = real_context()
    assumptions = [
        {"component": "RS1", "pins": ["4", "1"], "label": "user-verified: opposite pads of the 0.005ohm current-sense part"},
        {"component": "L45", "pins": ["1", "2"], "label": "user-verified: opposite ends of the 1uH filter"},
    ]
    res = trace_power_path(ctx, [{"component": "J15", "pin": "8"}], [{"component": "U7", "label": "U7"}],
                           max_hops=8, exclude_nets=["GND"], assumed_bridges=assumptions)
    assert res["assumed_bridges"]["rejected"] == [], "both pairs are real pads, so nothing may be dropped"
    chains = [tuple(dict.fromkeys(p["components"])) for p in res["paths"]]
    assert ("RS1", "L45", "U7") in chains, "the user-verified rail must be among the routes"
    mine = [p for p in res["paths"] if tuple(dict.fromkeys(p["components"])) == ("RS1", "L45", "U7")][0]
    assert mine["components"] == ["RS1", "RS1", "L45", "L45", "U7"], "each component is entered and left once"
    assert mine["asserted_hops"] == 2 and mine["hypothesis_hops"] == 0
    assert mine["verdict"] == "file plus your own conclusions (no name-rule crossing was needed)"
    assert mine["tentative_hop_kinds"] == ["inferred_crossing_asserted_by_caller"]
    accepted = {(a["component"], tuple(a["pins"])) for a in res["assumed_bridges"]["accepted"]}
    assert {("RS1", ("4", "1")), ("L45", ("1", "2"))} <= accepted, "both assertions must be taken"
