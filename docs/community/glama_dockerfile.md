# Glama server Dockerfile configuration

Reference for registering TianshangCAD on the Glama MCP server registry.

## Symptom

The Glama "Dockerfile 验证" (build validation) fails early with:

```
[internal] load metadata for docker.io/library/debian:trixie-slim
```

sometimes followed by `DockerBuildError: aborted` / `ECONNRESET`.

## Root cause

The failure is on the **Glama build worker pulling the base image
metadata** — not in this repository's code. `debian:trixie-slim` is Debian
13, released Aug 2025; the tag is young and cached poorly on the registry
nodes Glama builds on, so the manifest fetch stalls or resets. The server
itself is fine: `python -m tianshangcad --transport stdio` completes the
full MCP handshake (initialize + tools/list) locally.

## Recommended configuration

Use the same base image and install path as the repo's own `Dockerfile`
(`python:3.12-slim` + `pip install -e .`), and run the server directly over
stdio without `mcp-proxy` (the server already speaks MCP stdio natively):

```json
{
  "baseImage": "python:3.12-slim",
  "buildSteps": ["pip install --no-cache-dir -e ."],
  "cmdArguments": ["python", "-m", "tianshangcad", "--transport", "stdio"],
  "nodeVersion": "24",
  "pinnedCommit": null,
  "placeholderArguments": {},
  "pythonVersion": "3.12"
}
```

Notes:

- `python:3.12-slim` matches the root `Dockerfile` and is cached reliably.
- `uv sync` is NOT used — the project has no `uv.lock`; it installs via pip.
- `mcp-proxy` is unnecessary and was a separate failure point; the server
  implements the MCP stdio protocol directly.
- If `nodeVersion` must be set for the dashboard, keeping `24` is harmless.

## Alternative (keep uv)

Only if you insist on uv, switch the base image to the older, well-cached
Debian 12 image (still untested in a clean build — pip path is preferred):

```json
{
  "baseImage": "debian:bookworm-slim",
  "buildSteps": ["curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh && uv sync"],
  "cmdArguments": ["python", "-m", "tianshangcad", "--transport", "stdio"],
  "pythonVersion": "3.12"
}
```

## Repository Dockerfile

The root `Dockerfile` (and `docker/Dockerfile`) are pip-based on
`python:3.12-slim`. Their default `CMD` is HTTP on 8081 because
`docker/docker-compose.yml` health-checks that endpoint; the stdio entry
point is reachable by overriding the command:

```bash
docker run --rm -i tianshangcad:latest python -m tianshangcad --transport stdio
```
