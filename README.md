# TianshangCAD (cad-mcp-server)

A modern **CAD CLI + MCP Server** system. 2D/3D drawing, editing,
measurement, validation and JSON-driven workflows are available both from the
command line and as standardized tools callable by any MCP client (AI agent).

> **Status**: Phase 1 (CLI + IO) and Phase 2 (MCP Server) complete.
> 241 tests passing, 82%+ coverage, `ruff` and `mypy` clean.

**中文文档**: [readme/README.zh-CN.md](readme/README.zh-CN.md)

## Features

- **CAD CLI** — `file`, `draw`, `edit`, `view`, `measure`, `layer` command
  groups with short aliases (`l` = `draw line`, `c` = `draw circle`, ...)
- **MCP Server** — 39 JSON-RPC tools over stdio or streamable HTTP, callable
  from Claude, Cursor and other MCP clients
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

### Command groups

| Group | Commands |
|-------|----------|
| `file` | new, open, save, close, list, info, export, import |
| `draw` | line, circle, arc, rectangle, polygon, polyline, box, cylinder, sphere |
| `edit` | move, copy, rotate, scale, erase, list, undo, redo |
| `view` | zoom, pan, list |
| `measure` | distance, area, list |
| `layer` | create, list, set, on, off, delete |

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

### Tools (39 total)

| Group | Tools |
|-------|-------|
| Files | `cad_file_create`, `cad_file_open`, `cad_file_save`, `cad_file_close`, `cad_file_list` |
| Objects | `cad_object_create`, `cad_object_read`, `cad_object_update`, `cad_object_delete`, `cad_object_list` |
| Layers | `cad_layer_create`, `cad_layer_read`, `cad_layer_update`, `cad_layer_delete`, `cad_layer_list` |
| JSON | `cad_json_load`, `cad_json_parse`, `cad_json_validate`, `cad_json_import_geometry`, `cad_json_export_geometry`, `cad_json_import_scene`, `cad_json_export_scene`, `cad_json_save` |
| Status | `cad_status_check`, `cad_status_file`, `cad_status_object`, `cad_status_layer`, `cad_status_health`, `cad_logs_get`, `cad_logs_clear` |
| Validation | `cad_validate_geometry`, `cad_validate_interference`, `cad_validate_topology`, `cad_metrics_get` |
| Batch | `cad_batch_execute`, `cad_batch_schedule`, `cad_batch_status`, `cad_batch_cancel`, `cad_batch_list` |

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
|   |-- server.py       # MCPServer wiring (39 tools)
|   |-- transport.py    # stdio / streamable HTTP
|   |-- security.py     # tool permission whitelist
|   `-- tools/          # crud, json_ops, status, validate, batch
|-- core/           # document, entity, layer, kernel, session, history
|-- io/             # JSON / DXF / STL importers and exporters
|-- schemas/        # Pydantic geometry and scene schemas
|-- render/         # 2D/3D rendering (reserved)
`-- utils/          # logger, config, errors, validators, units
tests/
|-- unit/           # CLI, core, IO, MCP tool unit tests
`-- integration/    # MCP e2e, batch and JSON workflow tests
```

## Documentation

- `AGENTS.md` — full development guide and roadmap
- `docs/architecture.md` — system design
- `readme/README.zh-CN.md` — Chinese README
