"""Parser tests: curated GenCAD fixtures + the real MS-V397 boardview when available."""

import os

import pytest

from boardview_mcp.parser import GenCadError, logical_lines, parse_file, sniff, tokenize
from boardview_mcp.models import Board

from conftest import MINIMAL, MALFORMED, REAL_BOARD  # type: ignore


def net_map(board: Board) -> dict[str, list[tuple[str, str]]]:
    return {name: list(net.members) for name, net in board.nets.items()}


def pin_nets(board: Board, ref: str) -> dict[str, list[str]]:
    return {name: list(p.nets) for name, p in board.components[ref].pins.items() if p.nets}


# --------------------------------------------------------------------------- tokenizer / lines


def test_tokenize_quotes_and_escapes():
    assert tokenize('USER "RSI-TRANSLATOR CAMCAD 3.9.6b - Licensed to Teradyne"') == [
        "USER",
        "RSI-TRANSLATOR CAMCAD 3.9.6b - Licensed to Teradyne",
    ]
    assert tokenize('ATTRIBUTE PADST_1 "BLIND" "??"') == ["ATTRIBUTE", "PADST_1", "BLIND", "??"]
    assert tokenize('X "quote -> \\" inside" tail') == ["X", 'quote -> " inside', "tail"]


def test_backslash_continuation_is_joined():
    lines = logical_lines('SIGNAL A\\\nVERY_LONG_NAME\nNODE C1 1\n')
    assert lines[0] == (1, "SIGNAL AVERY_LONG_NAME")
    assert any(rec == "NODE C1 1" for _no, rec in lines)


def test_crlf_and_blank_lines_survive():
    lines = logical_lines("$SIGNALS\r\nSIGNAL N\r\n\r\nNODE C1 1\r\n$ENDSIGNALS\r\n")
    joined = "\n".join(rec for _no, rec in lines)
    assert "SIGNAL N" in joined and "NODE C1 1" in joined


# --------------------------------------------------------------------------- minimal fixture


def test_minimal_fixture_reports_only_its_intentional_defects():
    board = parse_file(str(MINIMAL))
    assert board.format == "GENCAD" and board.version == "1.4"
    assert len(board.components) == 7
    assert len(board.nets) == 6  # includes the intentionally empty ORPHAN_NET
    # the fixture's only deliberate structural defect is the duplicate NODE line inside DUP_NET
    assert board.errors == []  # a repeated NODE is informational, not a parse error
    assert any("repeated inside SIGNAL" in w for w in board.warnings)


def test_minimal_components_keep_file_values_exactly():
    board = parse_file(str(MINIMAL))
    c1 = board.components["C1"]
    assert (c1.package, c1.device) == ("TWO_PIN", "10uF")
    assert (c1.x, c1.y, c1.rotation, c1.side) == (100.0, 0.0, 90.0, "TOP")
    assert set(c1.explicit) == {"position", "side", "rotation", "package", "device"}
    r1 = board.components["R1"]
    assert r1.side == "BOTTOM" and r1.rotation == 270.0
    assert board.devices["10uF"].part == "10uF" and board.devices["10uF"].tol == "20"


def test_pin_declaration_versus_net_membership():
    board = parse_file(str(MINIMAL))
    j1 = board.components["J1"]
    assert {p.name for p in j1.pins.values() if p.declared_by_shape} == {"1", "2"}
    assert j1.pins["1"].nets == ["RAIL_IN"]
    assert (j1.pins["1"].padstack, j1.pins["2"].padstack) == ("PS_1", "PS_2")
    assert j1.pins["1"].connected is True
    k1 = board.components["K1"]
    assert k1.pins["2"].nets == [] and k1.pins["2"].declared_by_shape is True
    ic1 = board.components["IC1"]
    assert ic1.pins["B2"].nets == ["ALPHA_NET"]  # referenced by NODE but absent from SIX_PIN_IC
    assert ic1.pins["B2"].declared_by_shape is False and ic1.pins["B2"].connected is True


def test_alpha_pin_names_are_preserved():
    board = parse_file(str(MINIMAL))
    fp1 = board.components["FP1"]
    assert {p.name for p in fp1.pins.values()} == {"A1", "B2", "MEC1"}
    assert fp1.pins["A1"].nets == ["ALPHA_NET"] and fp1.pins["MEC1"].nets == ["ALPHA_NET"]
    assert board.components["IC1"].pins["B2"].padstack is None


def test_net_membership_is_exact_in_order_and_spelling():
    board = parse_file(str(MINIMAL))
    nets = net_map(board)
    assert nets["RAIL_IN"] == [("J1", "1"), ("C1", "1"), ("R1", "2"), ("IC1", "6")]
    assert nets["MID_NET"] == [("C1", "2"), ("RS1", "4"), ("K1", "1")]
    assert nets["SENSE_A"] == [("RS1", "2"), ("IC1", "1")]
    assert nets["ORPHAN_NET"] == []
    assert nets["DUP_NET"] == [("C1", "1"), ("R1", "1")]
    assert board.nets["DUP_NET"].duplicate_members == 1


def test_net_names_are_never_renamed_or_merged():
    board = parse_file(str(MINIMAL))
    assert "MID_NET" in board.nets and "MID_NETT" not in board.nets
    assert len({n for n in board.nets if n.replace("_", "") == "MIDNET"}) == 1


def test_empty_net_is_reported():
    board = parse_file(str(MINIMAL))
    assert any("no NODE members" in w for w in board.warnings)


def test_bbox_is_flagged_derived():
    board = parse_file(str(MINIMAL))
    assert board.bbox == (0.0, 0.0, 1000.0, 500.0)
    assert board.bbox_derived is True


def test_route_vias_are_not_net_members():
    board = parse_file(str(MINIMAL))
    assert "RAIL_IN" in board.routes
    assert board.routes["RAIL_IN"].vias[0]["padstack"] == "PS_1"
    members = {pair for n in board.nets.values() for pair in n.members}
    assert all(len(pair) == 2 for pair in members)
    assert ("PS_1", "via1") not in members


def test_header_records_are_preserved():
    board = parse_file(str(MINIMAL))
    assert board.header["USER"] == "boardview-mcp test fixture"
    assert board.header["DRAWING"] == "fixture"
    assert board.attributes == [{"id": "HEADER_1", "key": "Number of Routing Layers", "value": "1"}]


def test_section_record_counts_are_reported():
    board = parse_file(str(MINIMAL))
    for name in ("HEADER", "BOARD", "PADS", "PADSTACKS", "SHAPES", "COMPONENTS", "DEVICES", "SIGNALS", "ROUTES"):
        assert name in board.sections_seen


# --------------------------------------------------------------------------- malformed input


def test_malformed_fixture_reports_useful_errors():
    board = parse_file(str(MALFORMED))
    msgs = [e.message for e in board.errors]
    for needle in (
        "duplicate component reference DUP1",
        "PLACE needs exactly two numbers",
        "ROTATION needs exactly one number",
        "NODE needs exactly component-ref pin-name",
        "references unknown component GHOST",
        "SHAPE MISSING_SHAPE with no SHAPE record",
        "DEVICE NO_DEVICE_RECORD with no DEVICE record",
        "duplicate PIN",
        "non-numeric PIN coordinates",
        "non-numeric VIA coordinates",
        "VIA needs padstack/x/y",
        "ROUTE without a net name",
    ):
        assert any(needle in m for m in msgs), needle
    assert len(board.errors) >= 10
    assert set(board.components) == {"DUP1", "NOPE"}
    assert "GOOD_NET" in board.nets


def test_parse_errors_never_raise_mid_file():
    board = parse_file(str(MALFORMED))
    assert isinstance(board.errors, list) and board.errors
    assert set(board.nets) >= {"GOOD_NET", "BAD_NET", "NO_NAME"}


def test_unknown_section_is_counted_not_dropped():
    board = parse_file(str(MALFORMED))
    assert "WATSECTION" in board.sections_seen
    assert any("unknown section" in w for w in board.warnings)


# --------------------------------------------------------------------------- file-level rejection


def test_non_gencad_file_is_rejected(tmp_path):
    p = tmp_path / "other.cad"
    p.write_bytes(b"$PIEV2\n# Eeschema/other boardviewer dialect\n\n1234\n")
    with pytest.raises(GenCadError) as exc:
        sniff(str(p))
    assert "no GENCAD marker" in str(exc.value)
    with pytest.raises(GenCadError):
        parse_file(str(p))


def test_binary_and_empty_files_are_rejected(tmp_path):
    b = tmp_path / "binary.cad"
    b.write_bytes(b"\x00\x01GENCAD 1.4\x00")
    with pytest.raises(GenCadError) as exc:
        parse_file(str(b))
    assert "NUL bytes" in str(exc.value)
    e = tmp_path / "empty.cad"
    e.write_bytes(b"")
    with pytest.raises(GenCadError) as exc:
        parse_file(str(e))
    assert "file is empty" in str(exc.value)


def test_size_guard(tmp_path):
    p = tmp_path / "big.cad"
    p.write_bytes(b"GENCAD 1.4\n" + b"PAD X ROUND -1\n" * 5000)
    with pytest.raises(GenCadError) as exc:
        parse_file(str(p), max_bytes=1024)
    assert "max_bytes" in str(exc.value)


def test_genacad_extension_alone_is_not_trusted(tmp_path):
    p = tmp_path / "mislabelled.cad"
    p.write_text("BEGIN LIBRARY\nEND LIBRARY\n", encoding="utf-8")
    with pytest.raises(GenCadError) as exc:
        parse_file(str(p))
    assert "extension alone" in str(exc.value)


# --------------------------------------------------------------------------- real board integration


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_counts():
    board = parse_file(str(REAL_BOARD))
    assert board.version == "1.4"
    assert len(board.components) == 1932
    assert len(board.nets) == 1363
    assert board.sides == ["BOTTOM", "TOP"]
    assert sum(len(n.members) for n in board.nets.values()) == 8700
    assert sum(len(c.pins) for c in board.components.values()) == 8868
    assert sum(1 for c in board.components.values() for p in c.pins.values() if p.declared_by_shape and not p.nets) == 168
    assert sorted(r for r, c in board.components.items() if not any(p.nets for p in c.pins.values())) == [
        f"FM{i}" for i in range(1, 9)
    ]
    assert board.bbox_derived is True


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_target_observations():
    """TRACE-reported observations are checked against the file; the parser never assumes them."""

    board = parse_file(str(REAL_BOARD))
    assert pin_nets(board, "J15") == {
        "1": ["GND"],
        "2": ["GND"],
        "3": ["INPUT_PEX6_8_DT1*"],
        "4": ["GND"],
        "5": ["INPUT_PEX6_8_DT2*"],
        "6": ["12V_PEX6_8_INP"],
        "7": ["12V_PEX6_8_INP"],
        "8": ["12V_PEX6_8_INP"],
    }
    assert len(board.components["J15"].pins) == 10  # 8 numbered + MEC1 + MEC2
    assert pin_nets(board, "RS1") == {
        "1": ["12V_PEX6_8_INN"],
        "2": ["12V_PEX6_8_CH2_INN"],
        "3": ["12V_PEX6_8_CH2_INP"],
        "4": ["12V_PEX6_8_INP"],
    }
    assert net_map(board)["12V_PEX6_8_INP"] == [
        ("C191", "1"),
        ("C190", "1"),
        ("C192", "1"),
        ("J15", "6"),
        ("J15", "7"),
        ("J15", "8"),
        ("RS1", "4"),
    ]
    assert net_map(board)["12V_PEX6_8_INN"] == [("L45", "1"), ("RS1", "1")]
    assert net_map(board)["12V_PEX6_8_CH2_INN"] == [("R275", "2"), ("RS1", "2")]
    assert net_map(board)["12V_PEX6_8_CH2_INP"] == [("R261", "1"), ("R276", "2"), ("RS1", "3")]
    assert pin_nets(board, "L45") == {"1": ["12V_PEX6_8_INN"], "2": ["12V_PEX6_8_F1"]}
    assert [n for n in board.nets if "PEX8" in n] == []  # the mis-transcribed name is not synthesised


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_real_board_clean_parse():
    board = parse_file(str(REAL_BOARD))
    assert board.errors == [] and board.warnings == []
    with open(REAL_BOARD, "rb") as fh:
        assert fh.read(8).startswith(b"$HEADER")
    assert os.stat(REAL_BOARD).st_size == 5868394
