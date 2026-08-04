"""Entry point for ``python -m tianshangcad``.

Runs the MCP server (stdio or HTTP) when ``--transport`` is given,
otherwise dispatches to the CLI.
"""

import argparse
import sys

from tianshangcad.mcp.server import build_server
from tianshangcad.mcp.transport import run_http, run_stdio, run_ws


def main() -> None:
    """Parse arguments and dispatch to the MCP server or the CLI."""
    parser = argparse.ArgumentParser(prog="tianshangcad-server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "ws"],
        default=None,
        help="MCP transport mode (stdio | http | ws)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host for the HTTP/WS transport"
    )
    parser.add_argument(
        "--port", type=int, default=8081, help="Bind port for the HTTP/WS transport"
    )
    args, _ = parser.parse_known_args(sys.argv[1:])

    if args.transport is None:
        from tianshangcad.cli.main import main as cli_main

        cli_main()
        return

    server = build_server()
    if args.transport == "stdio":
        run_stdio(server)
    elif args.transport == "http":
        run_http(server, host=args.host, port=args.port)
    else:
        run_ws(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
