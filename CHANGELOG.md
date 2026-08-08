# Changelog

Notable changes to TianshangCAD (tianshangcad on PyPI), newest first.

## v0.12.0 - 2026-08-08

Full MCP tool-surface consolidation (77 → **19** aggregate tools) plus
server-side Tool Search. This is a **wire-breaking** change: every tool is
now a `cad_<domain>` aggregate whose first argument discriminates the
operation.

### Breaking
- The MCP surface is now **19 aggregate tools** (`cad_file`, `cad_object`,
  `cad_layer`, `cad_json`, `cad_measure`, `cad_validate`, `cad_view`,
  `cad_render`, `cad_nlp`, `cad_assembly`, `cad_drawing`, `cad_feature`,
  `cad_sim`, `cad_collab`, `cad_status`, `cad_batch`, `cad_constraint`,
  `cad_variable`, `cad_version`). Each takes a discriminated input, e.g.
  `cad_object` with `object.action` in {create, read, update, delete, copy,
  transform, list, boolean}.
- All 58 former granular tools (`cad_object_create`, `cad_metrics_get`,
  `cad_view_3d_create`, ...) are **no longer registered**. Their functions
  remain importable for internal / CLI use with a `# Deprecated` marker.
- Folded into aggregates: boolean → `cad_object` (action=boolean),
  file import/export → `cad_file` (import/export), logs → `cad_status`
  (logs_get/logs_clear).
- SCR scripts and batch JSON may use nested dotted keys
  (`cad_file file.action=create file.filename=a.json`) so old flat-key
  scripts need `key=` prefixes to match the aggregate input shape.

### Added
- **Tool Search**: `tools/list` accepts a `query` string and returns only
  tools whose name or description matches (substring + keyword scoring), per
  SEP-1821 progressive-discovery thinking.
- Per-action permission table (`ACTION_PERMISSIONS`) in `security.py`; tool
  hints (`readOnly` / `destructive` / `idempotent`) derived per aggregate.
- Aggregate `cad_nlp` mapping emits the new aggregate tool names.

### Changed
- Version bumped to 0.12.0.
- `docs/mcp_tools.md` re-synced to the 19-tool surface.

## v0.11.1 - 2026-08-07

Tool-description quality pass to improve MCP discoverability (registry
scorecards such as Glama) without changing the tool surface (still 77
tools).

### Added
- **Tool annotations (hints)**. Every registered tool now publishes
  `readOnlyHint` / `destructiveHint` / `idempotentHint` via
  `ToolAnnotations`, derived from the permission table and operation kind.
  Clients and scorecards can classify tools without parsing descriptions.
- **Field descriptions in `tools/list`**. `_flatten_tool` now carries each
  Pydantic field's `description` (plus examples / extra schema keywords)
  into the flat input schema, so every one of the 215 input parameters and
  367 output fields is documented. Previously descriptions were dropped,
  publishing bare type-only schemas.
- **Usage guidelines in tool descriptions**. The previously under-documented
  tools (collab, drawing, layer, file, variable, file_io, sim, feature,
  nlp) now explain when NOT to use them and which alternative tool to pick
  (e.g. `cad_drawing_add_view` vs `cad_drawing_add_section`, or
  `cad_file_save` vs `cad_file_io`).

### Changed
- Version bumped to 0.11.1.

## v0.11.0 - 2026-08-07

Tool-surface consolidation. The number of registered MCP tools drops from
103 to **77** by merging low-value, per-action tools into aggregate tools
using discriminated-union input models (`action` / `target` discriminator).

### Added
- Aggregate tools (each replaces several legacy tools):
  - `cad_render` (mode: ortho/view_3d/section/explode/animation/webgl)
  - `cad_json` (action: load/parse/validate/import_geometry/export_geometry/
    import_scene/export_scene/save)
  - `cad_object_boolean` (operation: union/subtract/intersect)
  - `cad_status` (target: check/file/object/layer/health)
  - `cad_logs` (action: get/clear)
  - `cad_variable` (action: set/list)
  - `cad_version` (action: save/list/diff/restore)
  - `cad_file_io` (action: export/import)
  - `cad_constraint` (action: add/remove/list/solve)
  - `cad_batch` (action: execute/schedule/status/cancel/list/templates/
    run_script)

### Changed
- Legacy per-action tools (`cad_status_health`, `cad_logs_get`, ...) are no
  longer registered. They remain importable and functional with a
  `# Deprecated, merged into cad_xxx` marker, so existing tests and CLI code
  keep working unchanged.
- Aggregate inputs use strict Pydantic validation with a discriminated
  union, so each action exposes only its own parameters.
- Batch templates and the NLP rules that referenced removed tools now emit
  the aggregate names (`cad_batch`, `cad_status`, `cad_logs`).
- `docs/mcp_tools.md` re-synced to the 77-tool surface.

## v0.10.0 - 2026-08-04

First PyPI release. Package installable via `pip install tianshangcad`.

### Added
- PyPI publish job in `release.yml` (OIDC trusted publishing). Every future
  `v*` tag automatically publishes the wheel and source distribution to PyPI.
- `glama.json` -- Glama MCP server registry claim.
- Root-level `Dockerfile` for registry auto-detection.

### Changed
- Bumped version to `0.10.0`; `build` added to dev dependencies so CI can
  produce standard wheels.

## v0.9.1 - 2026-08-04

Maintenance release.

### Changed
- The Debian package is now a real self-contained bundle: the project wheel
  plus pinned runtime dependency wheels are installed under
  `/usr/lib/tianshangcad-server/site` with `/usr/bin` entry-point wrappers. No
  network access is required at install time. Architecture is `amd64`.
- `_DEGENERATE_LENGTH` widened to `1e-4` so boundary-degenerate lines
  (length exactly `1e-5`) converge instead of stalling the constraint solver.

### Fixed
- `test_parallel_holds_for_random_lines`: the parallel assertion now
  normalizes directions before the cross product (tolerance is `sin(theta)`,
  scale-invariant), and boundary-length lines converge. Verified across
  hypothesis seeds 1..60.
- API key comparison is constant-time (`hmac.compare_digest`).

## v0.9.0 - 2026-08-03

Largest release yet: pre-research spikes (solver, OCC, CRDT), Phase 7
(assemblies + drawings), Phase 8 (features + simulation), Phase 9 Task A
(collaboration) and a maintenance cleanup.

### Breaking

- **Flat MCP tool inputs.** Every single-input tool now publishes its fields
  as top-level arguments in `tools/list` and `tools/call`, instead of a
  nested `{"input": {...}}` object. Clients should read `tools/list` for the
  authoritative schema. See `MIGRATION.md`.
- **`batch schedule` lifecycle.** New `--wait` / `--timeout` keep the CLI
  alive until a job reaches a terminal state; the new `batch run` subcommand
  executes synchronously through `cad_batch_execute`.

### Added

- Assembly modeling: `core/assembly.py`, `cad_assembly_*` tools, `assembly`
  CLI group (parts, sub-assemblies, mates, BOM, explode).
- Engineering drawings: `core/drawing.py`, `cad_drawing_*` tools, `drawing`
  CLI group (views, ISO-129 dimensions, GD and T, DXF/PDF/SVG export).
- Parametric features: sweep, loft, fillet, chamfer, patterns and
  `cad_feature_*` tools, integrating with parametric variables.
- Simulation interface: `cad_sim_*` tools and `sim` CLI group, CalculiX and
  PyBullet backends behind the optional `[sim]` extra.
- Real-time collaboration: LWW-Map CRDT, WebSocket transport, RBAC roles,
  document branches, annotations and `cad_collab_*` tools.
- Pure-Python STEP and DWG file bridge tools.
- HTTP transport integration tests and the `build_http_app` helper.

### Changed

- Flattened MCP `inputSchema` (see Breaking).
- Server default version now `0.9.0`; runtime `__version__` synced (drives
  the `.deb` version and filename).

### Fixed

- Batch scheduler one-shot jobs now run in CLI mode.
- API key comparison is constant-time via `hmac.compare_digest`.
- Env-robust `mypy` no-any-return ignores for optional backends (`occ`,
  `solver`) and `features.py`, so both CI lint and release gate pass.

## v0.4.0 - 2026-08-01

Phase 5 and 6: 3D view definitions, camera + navigation, section and explode
views, animation, WebGL preview; performance caching, security hardening,
production Docker, monitoring and alerting, docs.

## v0.2.5 - 2026-08-01

Phase 3 and 4: batch scheduling and script execution, logging + audit,
health check; geometry validation, metrics, versioning and diff, NLP command
parsing, 2D and 3D rendering.

## v0.1.0 - 2026-07-31

Phase 1 and 2: project scaffolding and CI, pluggable CAD kernel (analytic),
CLI `file` / `draw` / `edit` / `view` groups, MCP server core and tool
registry, JSON-schema geometry, CRUD tools, stdio + HTTP transport,
bilingual README, Apache-2.0 license.