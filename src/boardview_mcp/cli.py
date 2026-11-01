"""Command line entry point (called by :mod:`boardview_mcp.__main__`).

``python -m boardview_mcp --board <path>`` parses the board once, prints a verification summary,
then serves Streamable HTTP on 127.0.0.1 (default). ``--check`` stops after the summary, which makes
startup testable without a network.
"""

from __future__ import annotations

import argparse
import json
import os

from .context import BoardContext
from .server import TOOLS, build_server, run
from .tools import board_summary


def _summary_line(ctx: BoardContext) -> str:
    b = ctx.board
    return (
        f"{b.path}: GenCAD {b.version} - {len(b.components)} components, {len(b.nets)} nets, "
        f"{sum(len(n.members) for n in b.nets.values())} pin-net memberships, "
        f"{sum(len(c.pins) for c in b.components.values())} declared pins, "
        f"{len(b.errors)} errors, {len(b.warnings)} warnings"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m boardview_mcp",
        description="Read-only MCP server (Streamable HTTP) for GenCAD 1.4 PCB boardviews.",
    )
    ap.add_argument("--board", default=os.environ.get("BOARDVIEW_FILE", "").strip() or None,
                    help="GenCAD 1.4 .cad file (env BOARDVIEW_FILE is the default)")
    ap.add_argument("--host", default="127.0.0.1", help="default 127.0.0.1; other values need a deliberate reason")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--http-path", default="/mcp", help="Streamable HTTP path (Open WebUI endpoint: http://host:port/mcp)")
    ap.add_argument("--max-bytes", type=int, default=None, help="guard against oversized files")
    ap.add_argument("--check", action="store_true", help="parse, report, and exit without serving")
    ap.add_argument("--tools", action="store_true", help="list tool names and exit")
    ap.add_argument("--verbose", action="store_true", help="print the full JSON board summary")
    args = ap.parse_args(argv)

    if args.tools:
        print("\n".join(TOOLS))
        return 0

    try:
        ctx = BoardContext(args.board, max_bytes=args.max_bytes)
    except Exception as exc:  # surface parse/format problems as one clean CLI message
        print(f"cannot use this file: {exc}")
        return 2
    print(_summary_line(ctx))  # parsed exactly once here, reused by the server below
    if args.verbose:
        print(json.dumps(board_summary(ctx), indent=2, default=str))
    for err in ctx.board.errors[:20]:
        print(f"  error [{err.section}] line {err.line}: {err.message}")
    for warn in ctx.board.warnings[:20]:
        print(f"  warning: {warn}")
    if args.check:
        return 0
    server = build_server(None, context=ctx)
    print(
        f"serving MCP over Streamable HTTP at http://{args.host}:{args.port}{args.http_path} "
        f"(Ctrl+C to stop); tools: {len(TOOLS)}; board file: {ctx.board.path}",
        flush=True,
    )
    run(None, context=ctx, host=args.host, port=args.port, path=args.http_path)
    return 0
