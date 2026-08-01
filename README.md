# TianshangCAD (cad-mcp-server)

A modern **CAD CLI + MCP Server** system. 2D/3D drawing, editing,
measurement, validation and JSON-driven workflows are available both from the
command line and as standardized tools callable by any MCP client (AI agent).

> **Status**: Phase 1 (CLI + IO), Phase 2 (MCP Server), Phase 3 (Batch &
> Automation) and Phase 4 (Advanced Features) complete. 388 tests passing,
> 85%+ coverage, `ruff` and `mypy` clean.

**中文文档**: [readme/README.zh-CN.md](readme/README.zh-CN.md)

## Features

- **CAD CLI** — `file`, `draw`, `edit`, `view`, `measure`, `layer`, `batch`
  command groups with short aliases (`l` = `draw line`, `c` = `draw circle`, ...)
- **MCP Server** — 47 JSON-RPC tools over stdio or streamable HTTP, callable
  from Claude, Cursor and other MCP clients
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
- **Quality gates** — `mypy` strict typing, `ruff` linting, `pytest` with a
  80% coverage floor

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
`cad-cli --version` prints the current version (e.g. `cad-cli 0.4.0`).

### Command groups

| Group | Commands |
|-------|----------|
| `file` | new, open, save, close, list, info, export, import |
| `draw` | line, circle, arc, rectangle, polygon, polyline, box, cylinder, sphere |
| `edit` | move, copy, rotate, scale, erase, list, undo, redo |
| `view` | zoom, pan, list |
| `measure` | distance, area, list |
| `layer` | create, list, set, on, off, delete |
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

The server then serves MCP at `http://127.0.0.1:8081/mcp`.

### Tools (47 total)

| Group | Tools |
|-------|-------|
| Files | `cad_file_create`, `cad_file_open`, `cad_file_save`, `cad_file_close`, `cad_file_list` |
| Objects | `cad_object_create`, `cad_object_read`, `cad_object_update`, `cad_object_delete`, `cad_object_list` |
| Layers | `cad_layer_create`, `cad_layer_read`, `cad_layer_update`, `cad_layer_delete`, `cad_layer_list` |
| JSON | `cad_json_load`, `cad_json_parse`, `cad_json_validate`, `cad_json_import_geometry`, `cad_json_export_geometry`, `cad_json_import_scene`, `cad_json_export_scene`, `cad_json_save` |
| Status | `cad_status_check`, `cad_status_file`, `cad_status_object`, `cad_status_layer`, `cad_status_health`, `cad_logs_get`, `cad_logs_clear` |
| Validation | `cad_validate_geometry`, `cad_validate_interference`, `cad_validate_topology`, `cad_metrics_get` |
| Render | `cad_render_view` |
| Version | `cad_version_save`, `cad_version_list`, `cad_version_diff`, `cad_version_restore` |
| NLP | `cad_nlp_command` |
| Batch | `cad_batch_execute`, `cad_batch_schedule`, `cad_batch_status`, `cad_batch_cancel`, `cad_batch_list`, `cad_batch_templates`, `cad_batch_run_script` |

### Validation, rendering, versioning & NLP

Validate geometry with structured diagnostics, render orthographic views, snapshot
and restore document versions, and drive tools from natural language:

```bash
# Render a 300 DPI top view PNG
cad-cli render view --view top --dpi 300 --output preview.png
cad-cli render 3d --output preview3d.png
cad-cli render webgl --output viewer_data.json --viewer examples/threejs_viewer.html

# NLP examples (via the MCP tool cad_nlp_command)
"new file design.dwg"        -> cad_file_create  {filename: design.dwg}
"draw a line from 0,0 to 10,10" -> cad_object_create (line)
"render the side view"       -> cad_render_view  {view: side}
"save a version"             -> cad_version_save
```

Version diffing uses `deepdiff` and reports changed fields, added/removed
items and the raw result. The WebGL export writes Three.js `BufferGeometry`
JSON consumable by `examples/threejs_viewer.html`.

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
|   |-- server.py       # MCPServer wiring (47 tools)
|   |-- transport.py    # stdio / streamable HTTP
|   |-- security.py     # tool permission whitelist
|   `-- tools/          # crud, json_ops, status, validate, batch,
|                       # render, versioning, nlp
|-- core/           # document, entity, layer, kernel, session, history,
|                   # scheduler, script_runner, batch_templates, validation,
|                   # versioning
|-- io/             # JSON / DXF / STL importers and exporters
|-- schemas/        # Pydantic geometry and scene schemas
|-- render/         # 2D / 3D PNG rendering and WebGL export
`-- utils/          # logger, config, errors, validators, units
examples/
`-- threejs_viewer.html  # browser viewer for WebGL exports
tests/
|-- unit/           # CLI, core, IO, MCP tool unit tests
`-- integration/    # MCP e2e, batch and JSON workflow tests
```

## Documentation

- `AGENTS.md` — full development guide and roadmap
- `docs/architecture.md` — system design
- `readme/README.zh-CN.md` — Chinese README

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
