"""``python -m boardview_mcp`` entry point (delegates to :func:`boardview_mcp.cli.main`)."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
