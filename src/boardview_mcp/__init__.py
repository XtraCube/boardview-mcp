"""Read-only GenCAD 1.4 boardview inspector exposed to an MCP client (Streamable HTTP).

Public API: :func:`load_board` (parse once -> :class:`Board`), :class:`BoardContext` (board + graph +
labelled classification, backs every tool), :func:`build_server` (nine registered MCP tools).
"""

from .models import Board
from .parser import parse_file, GenCadError
from .context import BoardContext
from .graph import ConnectivityGraph, BRIDGE_POLICY_NOTE
from .classify import classify_component, PASSIVE_KINDS
from .server import build_server, run, TOOLS, INSTRUCTIONS

__version__ = "0.1.0"


def load_board(path: str, *, max_bytes: int | None = None) -> Board:
    """Parse one GenCAD 1.4 file into a :class:`Board`. Raises :class:`GenCadError` for non-GenCAD input."""
    return parse_file(path, max_bytes=max_bytes) if max_bytes else parse_file(path)
