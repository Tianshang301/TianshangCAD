# TianshangCAD (cad-mcp-server)

A modern **CAD CLI + MCP Server** system. 2D/3D drawing, editing,
measurement and rendering are driven from the command line and exposed as
JSON Schema defined geometry and scenes.

> **Status**: Phase 1 (Basic CLI + IO) complete — Phase 2 (MCP Server) next.

## Features

- Command-line CAD operations: `file`, `draw`, `edit`, `view`, `layer`, `measure`
- Pluggable geometry kernel: analytic (default) / OCC (`cadquery`) / FreeCAD
- JSON scene persistence (`SceneDefinition`)
- File import/export: JSON, DXF, STL (STEP via OCC backend)
- Strict typing (`mypy`), linting (`ruff`) and > 80% unit-test coverage

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

Optional OCC backend:

```bash
pip install -e ".[occ]"
```

## Usage

```bash
cad-cli file new design.json --unit mm
cad-cli draw line 0,0 100,0
cad-cli draw circle 50,50 --radius 25
cad-cli draw box 0,0,0 --dimensions 100,50,30
cad-cli edit move line_1 --dx 50
cad-cli view zoom --extents
cad-cli measure distance 0,0 100,100
```

Short aliases are supported: `cad-cli l 0,0 100,0` == `cad-cli draw line 0,0 100,0`.

## Development

```bash
bash scripts/setup_dev.sh   # venv + editable install + stubs
bash scripts/run_tests.sh   # ruff + mypy + pytest (coverage gate >= 80%)
bash scripts/build_docs.sh
```

Or run each tool directly:

```bash
ruff check .        # lint
mypy src            # type check
pytest              # tests (coverage gate >= 80%)
```

See `AGENTS.md` for the full development guide and roadmap, and
`docs/architecture.md` for the system design.
