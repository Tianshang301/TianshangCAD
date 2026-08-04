# Changelog

Notable changes to TianshangCAD (tianshangcad on PyPI), newest first.

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
  `/usr/lib/cad-mcp-server/site` with `/usr/bin` entry-point wrappers. No
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