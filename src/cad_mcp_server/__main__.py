"""Entry point for ``python -m cad_mcp_server``.

Phase 1 dispatches to the CLI. Phase 2 will honour ``--transport``
(stdio / http) and run the MCP server instead.
"""

import sys

from cad_mcp_server.cli.main import main as cli_main


def main() -> None:
    """Dispatch based on the first argument."""
    if "--transport" in sys.argv:
        sys.stderr.write(
            "MCP server transport is implemented in Phase 2. "
            "Use `cad-cli` for the command-line interface for now.\n"
        )
        raise SystemExit(1)
    cli_main()


if __name__ == "__main__":
    main()
