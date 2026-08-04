# TianshangCAD

A modern **CAD CLI + MCP Server** system. 2D/3D drawing, editing,
measurement, validation and JSON-driven workflows are available both from the
command line and as standardized tools callable by any MCP client (AI agent).

> **Status**: Phases 1–7 complete (v0.7.0 assembly + engineering drawings),
> plus the v0.6.0 sprint, the v0.8.0 Task A/B (parametric features +
> simulation interface) and the v0.9.0 Task A (real-time collaboration).
> 907 tests passing, ~87% coverage (measured with optional extras
> installed), `ruff` and `mypy` clean.

**中文文档**: [readme/README.zh-CN.md](readme/README.zh-CN.md)

**[Changelog](CHANGELOG.md)** · **[Migration guide v0.6.0 → v0.9.0](MIGRATION.md)**

## Features

- **CAD CLI** — `file`, `draw`, `edit`, `view`, `measure`, `layer`, `batch`
  command groups with short aliases (`l` = `draw line`, `c` = `draw circle`, ...)
- **MCP Server** — 103 JSON-RPC tools over stdio, streamable HTTP or
  WebSocket (collaboration), callable
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
  80% coverage floor; GitHub Actions CI runs lint + tests on every push.
  The reported ~87% coverage assumes the optional extras (`boolean`,
  `solver`, `occ`, `collab`, `sim`) are installed; the base
  `pip install -e .` suite measures lower.

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

Self-contained Debian package (Linux amd64, bundles all runtime wheels — no
network access needed at install time):

```bash
wget <release>/tianshangcad_<version>_amd64.deb
sudo dpkg -i tianshangcad_<version>_amd64.deb
```

Optional OCC kernel:

```bash
pip install -e ".[occ]"
```

## CLI Usage

```bash
tianshangcad --version
tianshangcad file new design.json --unit mm
tianshangcad draw line 0,0 100,0
tianshangcad draw circle 50,50 --radius 25
tianshangcad draw box 0,0,0 --dimensions 100,50,30
tianshangcad edit move line_1 --dx 50
tianshangcad view zoom --extents
tianshangcad measure distance 0,0 100,100
```

Short aliases are expanded automatically:
`tianshangcad l 0,0 100,0` equals `tianshangcad draw line 0,0 100,0`.
`tianshangcad --version` prints the current version (e.g. `tianshangcad 0.9.0`).

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
python -m tianshangcad --transport stdio
```

### Streamable HTTP

```bash
python -m tianshangcad --transport http --host 127.0.0.1 --port 8081
```

The server then serves MCP at `http://127.0.0.1:8081/mcp`, exposes a health
check at `/health` and Prometheus metrics at `/metrics`.

When an API key is configured (via the `TIANSHANGTIANGSHANGCAD_API_KEYS` env var, comma-separated),
HTTP requests must send it as `x-api-key` or `Authorization: Bearer <key>`:
missing keys get `401`, invalid keys get `403`. Requests are also subject to a
sliding-window rate limit (default 100 requests / 60 s, configurable via
`TIANGSHANGCAD_RATE_LIMIT_MAX` and `TIANGSHANGCAD_RATE_LIMIT_WINDOW`); exceeding it returns `429`.
`/health` and `/metrics` are always public. stdio mode is unaffected.

### Tools (103 total)

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
| NLP | `cad_nlp_command`, `cad_nlp_chat` |
| Batch | `cad_batch_execute`, `cad_batch_schedule`, `cad_batch_status`, `cad_batch_cancel`, `cad_batch_list`, `cad_batch_templates`, `cad_batch_run_script` |
| Constraints | `cad_constraint_add`, `cad_constraint_remove`, `cad_constraint_list`, `cad_constraint_solve` |
| Assembly | `cad_assembly_create`, `cad_assembly_add_part`, `cad_assembly_add_subasm`, `cad_assembly_add_mate`, `cad_assembly_solve`, `cad_assembly_bom`, `cad_assembly_explode` |
| Drawing | `cad_drawing_create`, `cad_drawing_add_view`, `cad_drawing_add_section`, `cad_drawing_add_dimension`, `cad_drawing_add_tolerance`, `cad_drawing_export` |
| Features | `cad_feature_sweep`, `cad_feature_loft`, `cad_feature_fillet`, `cad_feature_chamfer`, `cad_feature_pattern_linear`, `cad_feature_pattern_circular`, `cad_feature_pattern_mirror` |
| Simulation | `cad_sim_mesh`, `cad_sim_setup`, `cad_sim_run`, `cad_sim_result`, `cad_sim_list` |
| Collaboration | `cad_collab_session`, `cad_collab_branch`, `cad_collab_annotation`, `cad_collab_presence`, `cad_collab_history`, `cad_collab_resolve`, `cad_collab_permission`, `cad_collab_sync` |

### Validation, rendering, 3D views & NLP

Validate geometry with structured diagnostics, render orthographic views, snapshot
and restore document versions, drive tools from natural language, and create
named 3D views with camera, section, explode and animation:

```bash
# Render a 300 DPI top view PNG
tianshangcad render view --view top --dpi 300 --output preview.png
tianshangcad render 3d --output preview3d.png
tianshangcad render webgl --output viewer_data.json --viewer examples/threejs_viewer.html

# 3D views
tianshangcad render view3d iso --output iso.png
tianshangcad render section XY --offset 0 --output section.png
tianshangcad render explode --scale 1.5 --output explode.png
tianshangcad render gif --frames 48 --output orbit.gif
tianshangcad render views

# NLP examples (via the MCP tool cad_nlp_command)
"new file design.dwg"        -> cad_file_create  {filename: design.dwg}
"draw a line from 0,0 to 10,10" -> cad_object_create (line)
"render the side view"       -> cad_render_view  {view: side}
"save a version"             -> cad_version_save
```

`cad_nlp_chat` adds multi-turn dialogue with anaphora resolution: each
`session_id` remembers the last created object so later turns can refer to
it with pronouns or descriptions. Create intents are executed against the
current document, so "it" / "它" resolves to the real object id.

```bash
# Turn 1: draw a circle (creates the object, records it in the session)
"draw a circle at 5,5 radius 3"   -> cad_object_create, object_id tracked
# Turn 2: move the referenced circle (same session_id)
"move it to 10,10"                -> cad_object_update {object_id, params}
"move the circle I just drew to 3,3" -> same, explicit anaphora
"把它移到 4,4"                     -> same, Chinese pronoun
```

Version diffing uses `deepdiff` and reports changed fields, added/removed
items and the raw result. The WebGL export writes Three.js `BufferGeometry`
JSON consumable by `examples/threejs_viewer.html`. View definitions
(camera pose, projection, section/explode parameters) are persisted with the
document and are also exposed as MCP tools (`cad_view_3d_*`,
`cad_view_section`, `cad_view_explode`, `cad_view_animation`,
`cad_webgl_sync`).

### Real-time collaboration

Phase 9 collaboration builds on the LWW-Map CRDT: a session holds the shared
document state as keyed registers (geometry / layers / variables /
constraints / assembly), with 4-role × 4-scope RBAC (viewer / editor / admin /
owner over document / scene / assembly / settings). Sessions support
presence, annotations, document branches (fork / edit / merge with explicit
conflict resolution) and a transport-agnostic sync primitive:

```bash
# Optional dependency for the WebSocket hub
pip install -e ".[collab]"

tianshangcad collab create --name review        # seed a session over the current doc
tianshangcad collab list
tianshangcad collab annotate <session_id> "check the hole"
tianshangcad collab perm <session_id> bob --role editor

# WebSocket transport (default port 8082)
python -m tianshangcad --transport ws --port 8082
```

MCP clients use `cad_collab_session`, `cad_collab_branch`,
`cad_collab_annotation`, `cad_collab_presence`, `cad_collab_history`,
`cad_collab_resolve`, `cad_collab_permission` and `cad_collab_sync`.
WebSocket clients speak a small JSON envelope (`subscribe` / `op` / `sync` /
`ping`) that maps onto the sync tool. A multi-client hub fans an applied
`op` out as a `deltas` broadcast to every subscriber of the same session
(excluding the origin sender, which already received its live response).

### Batch & automation

Schedule jobs with a standard 5-field cron expression, dependency chains and
webhook notifications; run scripts through a sandboxed engine; persist job
state to SQLite:

```bash
# One-off job
tianshangcad batch schedule commands.json --name report

# Cron job (daily at 02:00) using a built-in template
tianshangcad batch schedule commands.json --cron "0 2 * * *"

# Run a sandboxed Python script
tianshangcad batch run-script script.py --type python --timeout 30

# Inspect results
tianshangcad batch list
tianshangcad batch status <job_id>
tianshangcad batch logs --source batch --job-id <job_id>
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
overrides: `TIANGSHANGCAD_RUNTIME`, `TIANGSHANGCAD_HEADLESS`, `TIANGSHANGCAD_TEMP_DIR`, `TIANSHANGTIANGSHANGCAD_API_KEYS`,
`TIANGSHANGCAD_LOG_LEVEL`, `TIANGSHANGCAD_RATE_LIMIT_MAX`, `TIANGSHANGCAD_RATE_LIMIT_WINDOW`.

Example MCP client configuration (Claude Desktop `~/.config/claude/mcp.json`):

```json
{
  "mcpServers": {
    "cad-server": {
      "command": "python",
      "args": ["-m", "tianshangcad", "--transport", "stdio"],
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

### Benchmark harness (CADGenBench)

`scripts/cadgenbench_harness.py` is an offline demo harness that drives the
real MCP server over stdio to build a small set of 3D parts, export them as
STEP, and run a local validity check (watertight manifold) mirroring
CADGenBench's scoring gate -- no external API or HuggingFace token needed:

```bash
python scripts/cadgenbench_harness.py            # analytic AP203 exporter
python scripts/cadgenbench_harness.py --occ      # OCCT kernel path
# Results: dist/cadgenbench/run_summary.json
```

To turn this into a real CADGenBench submission, read a sample's
`description.yaml`, let an LLM choose the tool calls with this server as the
backend, and upload the resulting `output.step` candidates to the leaderboard
Space.

## Project Layout

```
src/tianshangcad/
|-- cli/            # typer CLI: commands + alias expansion
|-- mcp/            # MCP server, transports, security and tool registry
|   |-- server.py       # MCPServer wiring (103 tools)
|   |-- transport.py    # stdio / streamable HTTP (+ auth, rate limiting)
|   |-- security.py     # tool permission whitelist
|   |-- auth.py         # API-key authentication
|   |-- rate_limit.py   # sliding-window rate limiter
|   `-- tools/          # crud, json_ops, status, validate, batch, boolean,
|                       # file_io, variables, render, versioning, nlp, view3d,
|                       # features, simulation
|-- core/           # document, entity, layer, kernel, session, history,
|                   # variables, scheduler, script_runner, batch_templates,
|                   # validation, versioning, view_manager, features, simulation,
|                   # assembly, drawing, constraint
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

- `readme/README.zh-CN.md` — Chinese README

## Continuous Integration

`.github/workflows/ci.yml` runs `ruff` + `mypy` on every push / PR,
`pytest` with the 80% coverage gate on Python 3.11 and 3.12, and a separate
`stress` job for the concurrency / soak suite. Pushing a `v*` tag triggers
`.github/workflows/release.yml`, which builds the Windows executables
(`tianshangcad.exe`, `tianshangcad-server.exe` via PyInstaller) and the self-contained
Debian package (`scripts/build_deb.py`, bundles runtime wheels for Linux
amd64) and publishes them to a GitHub Release.

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE).

Community guidelines: [Code of Conduct](CODE_OF_CONDUCT.md) ·
Security: [SECURITY.md](SECURITY.md) · Contributing via pull requests is
welcome.

Third-party runtime dependencies are all permissive-licensed (MIT / BSD /
Apache-2.0 / ISC / PSF, plus MPL-2.0 for `certifi`); the full inventory is in
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

Optional backends: `cadquery` (Apache-2.0) is compatible. The optional
FreeCAD / OpenCASCADE backends are LGPL-2.1 and are **not** bundled; if you
enable them you must comply with the LGPL (retain notices, keep the library
re-linkable). The default `AnalyticKernel` is self-authored and fully
Apache-2.0.
