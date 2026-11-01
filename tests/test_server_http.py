"""End-to-end test over the wire: a real Streamable HTTP server, a real MCP client, real JSON.

This is the only test that touches a port. The server is a child process of this test, bound to
127.0.0.1 on a port that is free at the moment the test starts, and it is terminated at the end.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import pytest

from conftest import REAL_BOARD

pytestmark = []


def _free_port(start: int = 8100, stop: int = 8199) -> int:
    """Pick a port nothing is listening on, so a concurrent run cannot steal it."""

    for candidate in range(start, stop):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", candidate))
            return candidate
        except OSError:
            continue
    raise RuntimeError("no free port in range")


async def _call(url: str, name: str, args: dict) -> dict:
    from mcp import Client

    async with Client(url) as client:
        result = await client.call_tool(name, args)
    parts = [item.text for item in result.content]
    assert len(parts) == 1, f"expected one text block, got {len(parts)}"
    return json.loads(parts[0])


async def _names(url: str) -> list[str]:
    from mcp import Client

    async with Client(url) as client:
        return [t.name for t in (await client.list_tools()).tools]


async def _wait_ready(url: str, *, tries: int = 40, delay: float = 0.5) -> list[str]:
    """Poll the endpoint with a real MCP handshake, so readiness is proven, not guessed from logs."""

    last: Exception | None = None
    for _ in range(tries):
        try:
            return await asyncio.wait_for(_wait_ready_once(url), timeout=6)
        except Exception as exc:  # transient: the socket is not listening yet
            last = exc
            await asyncio.sleep(delay)
    raise AssertionError(f"server never became reachable at {url}: {last!r}")


async def _wait_ready_once(url: str) -> list[str]:
    names = await _names(url)
    assert names, "a reachable server must advertise its tools"
    return names


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.skipif(REAL_BOARD is None, reason="real MS-V397 boardview not present")
def test_live_http_server_serves_the_tools():
    """Spawn the CLI, speak MCP over HTTP, and confirm three tools answer with real board data."""

    port = _free_port()
    board = str(REAL_BOARD)
    env = dict(os.environ)
    log = subprocess.Popen(
        [sys.executable, "-m", "boardview_mcp", "--board", board, "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        banner = None
        deadline = time.time() + 60
        while time.time() < deadline and banner is None:
            line = log.stdout.readline()
            if not line:
                break
            if "serving MCP over Streamable HTTP" in line:
                banner = line.strip()
        assert banner is not None, "the server never announced its endpoint"

        url = f"http://127.0.0.1:{port}/mcp"
        listed = _run(_wait_ready(url))
        assert len(listed) == 10, f"expected ten tools over HTTP, got {sorted(listed)}"
        assert set(listed) == {
            "board_summary", "search_components", "get_component", "get_net",
            "find_connected_components", "trace_connectivity", "trace_power_path",
            "find_shared_rails", "export_subgraph", "evaluate_crossing",
        }

        summary = _run(_call(url, "board_summary", {}))
        assert summary["counts"]["components"] == 1932
        assert summary["counts"]["nets"] == 1363
        assert summary["file"]["bytes"] == 5868394

        net = _run(_call(url, "get_net", {"name": "12V_PEX6_8_INP", "limit": 3}))
        assert net["total_members"] == 7 and len(net["members"]) == 3
        assert net["truncated"] is True
        assert net["grouping_scope_note"] != "members_by_component covers every member of this net"

        comp = _run(_call(url, "get_component", {"ref": "J15"})
        )
        assert comp["component"]["pin_count_declared"] == 10
        assert comp["component"]["same_component_shared_net"]["12V_PEX6_8_INP"] == ["6", "7", "8"]

        unknown = _run(_call(url, "get_net", {"name": "12V_PEX8_6_INP"}))
        assert unknown["error"] == "net name not found"
        assert "12V_PEX6_8_INP" in unknown["similar_nets"]
        assert "12V_PEX8_6_INP" not in unknown["similar_nets"]
    finally:
        log.terminate()
        try:
            log.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: clean up, never fail the test on shutdown noise
            log.kill()
