# Architecture

## Overview

`cad-mcp-server` is split into four layers:

```
┌──────────────────────────────────────────────────────────────┐
│                          Interface                           │
│   CLI (typer)          MCP Server (Phase 2)                  │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                            Core                              │
│   Document  Entity  Layer  Style  Session  History           │
│   Transform  Kernel (analytic / OCC / FreeCAD)               │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                             IO                               │
│   Importers (JSON / DXF / STEP*)  Exporters (JSON/DXF/STL)   │
│   Schemas (Pydantic v2: Geometry, Scene)                     │
└──────────────────────────────────────────────────────────────┘
```

- **Interface**: `cli/` (typer commands, aliases) and, later, `mcp/`
  (JSON-RPC tools over stdio / HTTP). No business logic here.
- **Core**: in-memory document model. `DocumentState` aggregates
  `EntityManager`, `LayerManager`, `StyleManager` plus unit, timestamps
  and a dirty flag. Geometry is produced by a `CADKernel`.
- **IO**: persistence and interchange. The JSON scene format is the
  canonical on-disk format; DXF is a 2D interchange target; STL is a
  mesh export. STEP/IGES require the optional OCC backend.
- **Utils / Schemas**: cross-cutting concerns (errors, config, units,
  structured logging) and Pydantic v2 validation models.

## Geometry kernel

`core/kernel.py` defines the `CADKernel` ABC and the default
`AnalyticKernel`, a pure-Python implementation in which every shape is a
JSON-serialisable dict:

```json
{"kind": "line", "params": {"start": [0, 0, 0], "end": [100, 0, 0]}}
```

This keeps the kernel dependency-free and headless-friendly. Optional
backends (`core/backends/occt.py`, `freecad.py`) expose the same ABC via
`get_kernel(runtime=...)`, selected with the `CAD_RUNTIME` environment
variable. Boolean operations and BREP serialization (STEP/IGES) are
currently only available through those backends.

## Document & persistence

`DocumentState.to_dict()` emits a versioned scene document:

```
format: tianshang-cad-scene
version: 1
layers / styles / entities / current_layer
```

`DocumentManager.save()` writes this JSON, and
`io/importers/json_io.py::JSONImporter.scene_to_document()` restores it.
The Pydantic `SceneDefinition` in `schemas/scene.py` is the validated,
interchange-oriented view of the same data.

## Transform convention

`core/transform.py` follows a **left-multiplication** convention:
`compose(A, B) = A @ B`, so the leftmost matrix is applied last.
Internal geometry is always stored in millimetres; unit conversion lives
in `utils/units.py`.

## CLI command tree

`cli/main.py` registers sub-apps: `file`, `draw`, `edit`, `view`,
`layer`, `measure`, `block`, `render`, `batch`. Short aliases
(`l`, `c`, `m`, ...) are expanded by `main()` before typer runs.

## Testing

- `tests/unit/test_core/` — kernel, transforms, document, session,
  history, layers, styles.
- `tests/unit/test_cli/` — command behaviour via typer's CliRunner.
- `tests/unit/test_io/` — JSON/DXF/STL/STEP import-export round trips.
- `tests/integration/` — end-to-end workflows (added in Phase 2).

The CI pipeline (`.github/workflows/cad-ci.yml`) runs `ruff`, `mypy`
and `pytest --cov --cov-fail-under=80`.
