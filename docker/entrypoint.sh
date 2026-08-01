#!/usr/bin/env sh
set -eu

# Container entrypoint for the CAD MCP Server.
#
# Reads CAD_* environment variables and launches the server over the
# configured transport (default: HTTP on port 8081).

TRANSPORT="${CAD_MCP_TRANSPORT:-http}"
PORT="${CAD_MCP_PORT:-8081}"

exec python -m cad_mcp_server --transport "$TRANSPORT" --port "$PORT" "$@"
