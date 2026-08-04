#!/usr/bin/env sh
set -eu

# Container entrypoint for the CAD MCP Server.
#
# Reads CAD_* environment variables and launches the server over the
# configured transport (default: HTTP on port 8081).

TRANSPORT="${TIANSHANGCAD_MCP_TRANSPORT:-http}"
PORT="${TIANSHANGCAD_MCP_PORT:-8081}"

exec python -m tianshangcad --transport "$TRANSPORT" --port "$PORT" "$@"
