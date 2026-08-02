# TianshangCAD (cad-mcp-server)

A modern **CAD CLI + MCP Server** system. 2D/3D drawing, editing,
measurement, validation and JSON-driven workflows are available both from the
command line and as standardized tools callable by any MCP client (AI agent).

> **Status**: Phases 1–6 complete, plus the v0.6.0 sprint (parametric
> variables, mesh boolean ops, pure-Python STEP + DWG bridge). 545 tests
> passing, 85%+ coverage, `ruff` and `mypy` clean.

**中文文档**: [readme/README.zh-CN.md](readme/README.zh-CN.md)

## Features

- **CAD CLI** — `file`, `draw`, `edit`, `view`, `measure`, `layer`, `batch`
  command groups with short aliases (`l` = `draw line`, `c` = `draw circle`, ...)
- **MCP Server** — 65 JSON-RPC tools over stdio or streamable HTTP, callable
  from Claude, Cursor and other MCP clients
- **3D views** — JSON-defined `View3DDefinition` with spherical camera pose,
  named views (iso / top / front / side / back / bottom), perspective /
  orthographic projection, plane sections (XY / YZ / XZ), exploded views and
  orbit GIF animation; incremental WebGL delta sync for browser clients
- **Batch automation** — schedule one-off / cron / dependency-chained jobs,
  sandboxed Python / SCR / batch script execution, webhook notifications,
  SQLite persistence and reusable Jinja2 command templates
- **Geometry validation** — self-intersection, degenerate-face and
  non-manifold-edge checks with structured `type` / `location` /
  `fix_suggestion` diagnostics; box-box interference volumes; topology metrics
- **Rendering** — 2D orthographic PNG (top / front / side, DPI 72–300), shaded
  3D preview and Three.js WebGL export with a bundled browser viewer
- **Versioning** — full document snapshots with `deepdiff`-based
  save / list / diff / restore
- **Natural language** — `cad_nlp_command` maps English / Chinese requests to
  tool calls with ambiguity handling
- **JSON-driven** — scenes and geometry defined and validated with Pydantic
  schemas; full import/export round-trip
- **Pluggable kernel** — analytic (default, no native deps) / OCC
  (`cadquery`) / FreeCAD
- **File IO** — JSON, DXF, STL (STEP via the OCC backend)
- **Production hardening** — Docker image with healthcheck, Prometheus
  metrics (`/metrics`), API-key authentication (401/403), sliding-window
  rate limiting (429) and a `/health` endpoint
- **Quality gates** — `mypy` strict typing, `ruff` linting, `pytest` with a
  80% coverage floor; GitHub Actions CI runs lint + tests on every push

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

Optional OCC kernel:

```bash
pip install -e ".[occ]"
```

## CLI Usage

```bash
cad-cli --version
cad-cli file new design.json --unit mm
cad-cli draw line 0,0 100,0
cad-cli draw circle 50,50 --radius 25
cad-cli draw box 0,0,0 --dimensions 100,50,30
cad-cli edit move line_1 --dx 50
cad-cli view zoom --extents
cad-cli measure distance 0,0 100,100
```

Short aliases are expanded automatically:
`cad-cli l 0,0 100,0` equals `cad-cli draw line 0,0 100,0`.
`cad-cli --version` prints the current version (e.g. `cad-cli 0.6.0`).

### Command groups

| Group | Commands |
|-------|----------|
| `file` | new, open, save, close, list, info, export, import |
| `draw` | line, circle, arc, rectangle, polygon, polyline, box, cylinder, sphere |
| `edit` | move, copy, rotate, scale, erase, list, undo, redo |
| `view` | zoom, pan, list |
| `measure` | distance, area, list |
| `layer` | create, list, set, on, off, delete |
| `render` | view, 3d, webgl, view3d, section, explode, gif, views, status |
| `batch` | schedule, run-script, list, status, cancel, templates, logs |

## MCP Server

Run the server and connect any MCP client to it.

### stdio (local agents)

```bash
python -m cad_mcp_server --transport stdio
```

### Streamable HTTP

```bash
python -m cad_mcp_server --transport http --host 127.0.0.1 --port 8081
```

The server then serves MCP at `http://127.0.0.1:8081/mcp`, exposes a health
check at `/health` and Prometheus metrics at `/metrics`.

When an API key is configured (via the `CAD_API_KEYS` env var, comma-separated),
HTTP requests must send it as `x-api-key` or `Authorization: Bearer <key>`:
missing keys get `401`, invalid keys get `403`. Requests are also subject to a
sliding-window rate limit (default 100 requests / 60 s, configurable via
`CAD_RATE_LIMIT_MAX` and `CAD_RATE_LIMIT_WINDOW`); exceeding it returns `429`.
`/health` and `/metrics` are always public. stdio mode is unaffected.

### Tools (65 total)

| Group | Tools |
|-------|-------|
| Files | `cad_file_create`, `cad_file_open`, `cad_file_save`, `cad_file_close`, `cad_file_list`, `cad_file_export`, `cad_file_import` |
| Objects | `cad_object_create`, `cad_object_read`, `cad_object_update`, `cad_object_delete`, `cad_object_list` |
| Boolean | `cad_boolean_union`, `cad_boolean_subtract`, `cad_boolean_intersect`, `cad_object_boolean` |
| Variables | `cad_variable_set`, `cad_variable_list` |
| Layers | `cad_layer_create`, `cad_layer_read`, `cad_layer_update`, `cad_layer_delete`, `cad_layer_list` |
| JSON | `cad_json_load`, `cad_json_parse`, `cad_json_validate`, `cad_json_import_geometry`, `cad_json_export_geometry`, `cad_json_import_scene`, `cad_json_export_scene`, `cad_json_save` |
| Status | `cad_status_check`, `cad_status_file`, `cad_status_object`, `cad_status_layer`, `cad_status_health`, `cad_logs_get`, `cad_logs_clear` |
| Validation | `cad_validate_geometry`, `cad_validate_interference`, `cad_validate_topology`, `cad_metrics_get` |
| Render | `cad_render_view` |
| 3D Views | `cad_view_3d_create`, `cad_view_3d_read`, `cad_view_3d_list`, `cad_view_3d_update`, `cad_view_3d_delete`, `cad_view_3d_render`, `cad_view_section`, `cad_view_explode`, `cad_view_animation`, `cad_webgl_sync` |
| Version | `cad_version_save`, `cad_version_list`, `cad_version_diff`, `cad_version_restore` |
| NLP | `cad_nlp_command` |
| Batch | `cad_batch_execute`, `cad_batch_schedule`, `cad_batch_status`, `cad_batch_cancel`, `cad_batch_list`, `cad_batch_templates`, `cad_batch_run_script` |

### Validation, rendering, 3D views & NLP

Validate geometry with structured diagnostics, render orthographic views, snapshot
and restore document versions, drive tools from natural language, and create
named 3D views with camera, section, explode and animation:

```bash
# Render a 300 DPI top view PNG
cad-cli render view --view top --dpi 300 --output preview.png
cad-cli render 3d --output preview3d.png
cad-cli render webgl --output viewer_data.json --viewer examples/threejs_viewer.html

# 3D views
cad-cli render view3d iso --output iso.png
cad-cli render section XY --offset 0 --output section.png
cad-cli render explode --scale 1.5 --output explode.png
cad-cli render gif --frames 48 --output orbit.gif
cad-cli render views

# NLP examples (via the MCP tool cad_nlp_command)
"new file design.dwg"        -> cad_file_create  {filename: design.dwg}
"draw a line from 0,0 to 10,10" -> cad_object_create (line)
"render the side view"       -> cad_render_view  {view: side}
"save a version"             -> cad_version_save
```

Version diffing uses `deepdiff` and reports changed fields, added/removed
items and the raw result. The WebGL export writes Three.js `BufferGeometry`
JSON consumable by `examples/threejs_viewer.html`. View definitions
(camera pose, projection, section/explode parameters) are persisted with the
document and are also exposed as MCP tools (`cad_view_3d_*`,
`cad_view_section`, `cad_view_explode`, `cad_view_animation`,
`cad_webgl_sync`).

### Batch & automation

Schedule jobs with a standard 5-field cron expression, dependency chains and
webhook notifications; run scripts through a sandboxed engine; persist job
state to SQLite:

```bash
# One-off job
cad-cli batch schedule commands.json --name report

# Cron job (daily at 02:00) using a built-in template
cad-cli batch schedule commands.json --cron "0 2 * * *"

# Run a sandboxed Python script
cad-cli batch run-script script.py --type python --timeout 30

# Inspect results
cad-cli batch list
cad-cli batch status <job_id>
cad-cli batch logs --source batch --job-id <job_id>
```

Scripts run in an isolated subprocess (`python -I`) with an import whitelist
(`os`, `subprocess`, `socket`, ... are blocked), a runtime `sys.modules`
guard and a hard timeout.

## Docker

A multi-stage image (< 500 MB, `python:3.11-slim`) is provided in
`docker/` for headless deployment:

```bash
docker compose -f docker/docker-compose.yml up -d
```

The container runs the MCP server over streamable HTTP on port `8081` with a
`/health` healthcheck, and mounts `data/` + `config/` volumes. Environment
overrides: `CAD_RUNTIME`, `CAD_HEADLESS`, `CAD_TEMP_DIR`, `CAD_API_KEYS`,
`CAD_LOG_LEVEL`, `CAD_RATE_LIMIT_MAX`, `CAD_RATE_LIMIT_WINDOW`.

Example MCP client configuration (Claude Desktop `~/.config/claude/mcp.json`):

```json
{
  "mcpServers": {
    "cad-server": {
      "command": "python",
      "args": ["-m", "cad_mcp_server", "--transport", "stdio"],
      "autoApprove": [
        "cad_object_read",
        "cad_object_list",
        "cad_status_check",
        "cad_json_load",
        "cad_json_validate",
        "cad_validate_geometry",
        "cad_metrics_get"
      ]
    }
  }
}
```

## Development

```bash
bash scripts/setup_dev.sh   # venv + editable install + stubs
bash scripts/run_tests.sh   # ruff + mypy + pytest (coverage gate >= 80%)
bash scripts/build_docs.sh
```

Or run each gate directly:

```bash
ruff check .   # lint
mypy src       # type check
pytest         # tests (coverage gate >= 80%)
```

## Project Layout

```
src/cad_mcp_server/
|-- cli/            # typer CLI: commands + alias expansion
|-- mcp/            # MCP server, transports, security and tool registry
|   |-- server.py       # MCPServer wiring (65 tools)
|   |-- transport.py    # stdio / streamable HTTP (+ auth, rate limiting)
|   |-- security.py     # tool permission whitelist
|   |-- auth.py         # API-key authentication
|   |-- rate_limit.py   # sliding-window rate limiter
|   `-- tools/          # crud, json_ops, status, validate, batch, boolean,
|                       # file_io, variables, render, versioning, nlp, view3d
|-- core/           # document, entity, layer, kernel, session, history,
|                   # variables, scheduler, script_runner, batch_templates,
|                   # validation, versioning, view_manager
|-- io/             # JSON / DXF / STL importers and exporters
|-- schemas/        # Pydantic geometry, scene and view3d schemas
|-- render/         # 2D / 3D PNG rendering, WebGL export, section, explode,
|                   # animation
`-- utils/          # logger, config, errors, validators, units, metrics
examples/
`-- threejs_viewer.html  # browser viewer for WebGL exports
docker/
|-- Dockerfile          # multi-stage image (python:3.11-slim)
|-- docker-compose.yml  # service definition with healthcheck
`-- entrypoint.sh
tests/
|-- unit/           # CLI, core, IO, MCP tool unit tests
`-- integration/    # MCP e2e, batch, JSON workflow and performance tests
```

## Documentation

- `AGENTS.md` — full development guide and roadmap
- `docs/architecture.md` — system design
- `docs/roadmap_v0.2.5.md` — future development roadmap
- `docs/development_plan_v0.3.0.md` — Phase 5/6 implementation plan
- `readme/README.zh-CN.md` — Chinese README

## Continuous Integration

`.github/workflows/ci.yml` runs `ruff` + `mypy` on every push / PR, and
`pytest` with the 80% coverage gate on Python 3.11 and 3.12. Pushing a `v*`
tag triggers `.github/workflows/release.yml`, which builds the Windows
executables (`cad-cli.exe`, `cad-mcp-server.exe` via PyInstaller) and the
Debian package (`build_deb.py`) and publishes them to a GitHub Release.

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE).

Third-party runtime dependencies are all permissive-licensed (MIT / BSD /
Apache-2.0 / ISC / PSF, plus MPL-2.0 for `certifi`); the full inventory is in
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

Optional backends: `cadquery` (Apache-2.0) is compatible. The optional
FreeCAD / OpenCASCADE backends are LGPL-2.1 and are **not** bundled; if you
enable them you must comply with the LGPL (retain notices, keep the library
re-linkable). The default `AnalyticKernel` is self-authored and fully
Apache-2.0.
