"""Entry point for ``python -m cad_mcp_server``.

Runs the MCP server (stdio or HTTP) when ``--transport`` is given,
otherwise dispatches to the CLI.
"""

import argparse
import sys

from cad_mcp_server.mcp.server import build_server
from cad_mcp_server.mcp.transport import run_http, run_stdio


def main() -> None:
    """Parse arguments and dispatch to the MCP server or the CLI."""
    parser = argparse.ArgumentParser(prog="cad-mcp-server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="MCP transport mode (stdio | http)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host for the HTTP transport"
    )
    parser.add_argument(
        "--port", type=int, default=8081, help="Bind port for the HTTP transport"
    )
    args, _ = parser.parse_known_args(sys.argv[1:])

    if args.transport is None:
        from cad_mcp_server.cli.main import main as cli_main

        cli_main()
        return

    server = build_server()
    if args.transport == "stdio":
        run_stdio(server)
    else:
        run_http(server, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
