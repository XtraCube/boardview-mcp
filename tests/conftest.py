"""Shared fixture locations for the test suite."""

import os
from functools import lru_cache
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"

MINIMAL = FIXTURES / "minimal.cad"
MALFORMED = FIXTURES / "malformed.cad"


def _real_board_path() -> Path | None:
    """Real boardview: BOARDVIEW_FILE env wins, else look for a *.cad next to the project."""

    env = os.environ.get("BOARDVIEW_FILE", "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    project_root = TESTS_DIR.parent
    for candidate in (project_root, project_root.parent, project_root.parent.parent):
        for found in sorted(candidate.glob("*.cad")):
            if found.stat().st_size > 100_000:  # a real boardview, not a test fixture
                return found
    return None


REAL_BOARD = _real_board_path()


@lru_cache(maxsize=1)
def real_board():
    """The real boardview parsed once per session (~0.6s per parse, and most tests need it)."""
    from boardview_mcp.parser import parse_file

    assert REAL_BOARD is not None
    return parse_file(str(REAL_BOARD))


@lru_cache(maxsize=1)
def real_context():
    """Real board plus graph/classification indexes, built once per session."""
    from boardview_mcp.context import BoardContext

    assert REAL_BOARD is not None
    return BoardContext(str(REAL_BOARD))
