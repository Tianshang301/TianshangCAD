# Development Plan — v0.3.0 (Phase 5) and v0.4.0 (Phase 6)

> **Baseline**: v0.2.5 (2026-08-14) — Phase 4 complete
> **Targets**: v0.3.0 (2026-08-28, Phase 5) · v0.4.0 (2026-09-04, Phase 6)
> **Author**: TianshangCAD team · **Date**: 2026-08-02
> **Sources**: `docs/roadmap_v0.2.5.md`, `TianshangCAD_Development_Plan_v2.md`

---

## 1. Baseline State (v0.2.5)

| Area | Status |
|------|--------|
| Version | `0.2.5` (`src/cad_mcp_server/__init__.py`) |
| MCP tools | 47 registered (`mcp/tools/_registry.py`) |
| Schemas | `schemas/geometry.py`, `schemas/scene.py` (no `view3d.py`) |
| Rendering | `renderer_2d.py` (ortho PNG), `renderer_3d.py` (fixed camera preview), `webgl_exporter.py` (full Three.js snapshot) |
| MCP render tool | `cad_render_view` only (ortho top/front/side) |
| Dependencies | `imageio`, `prometheus-client`, `apscheduler[sqlalchemy]`, `deepdiff`, `matplotlib` already in `pyproject.toml` |
| Quality gates | 388 tests passing, coverage 85.51% (threshold ≥80%), `ruff` + `mypy` clean |
| Permissions | `mcp/security.py` maps every tool to a `PermissionLevel` |

---

## 2. Phase 5 — v0.3.0: 3D View Toolchain

### 2.1 Goal

Turn the existing static 3D preview into a first-class 3D view system:
JSON-defined views, explicit camera control, section and exploded views,
GIF animation, and incremental WebGL synchronization for browser clients.

### 2.2 Deliverables

#### 2.2.1 `schemas/view3d.py` (new)

- `CameraPose` — spherical camera: `azimuth` (deg), `elevation` (deg),
  `distance`, `target` `[x, y, z]`, `fov` (deg), `up` vector.
- `SectionPlane` — plane type (`XY` / `YZ` / `XZ`), `offset` along the
  plane normal, `show_cut_faces` (bool).
- `ExplodeSpec` — per-axis `offset_x/y/z` scale factor.
- `View3DDefinition` — `view_id`, `name`, `projection`
  (`perspective` / `orthographic`), `camera: CameraPose`, `viewport`
  (`width`, `height`), `clipping` (`near`, `far`), `section: SectionPlane | None`,
  `explode: ExplodeSpec | None`, `fit_to_bounds` (bool), metadata.
- `ANIMATION_TIMELINE` — `frames`, `fps`, `mode`
  (`orbit` / `turntable`), `total_degrees`.
- Named views map: `iso`, `top`, `front`, `side`, `back`, `bottom`.
- `default_view()` helper producing a fit-to-bounds iso camera.

#### 2.2.2 `render/renderer_3d.py` (upgrade)

- `render_3d(..., camera: CameraPose | None, projection: str)` — applies
  spherical camera pose and orthographic vs. perspective projection to the
  matplotlib 3D axes (`set_proj_type`, `view_init`, `dist`).
- `fit_camera_to_bounds(records, kernel)` — compute bbox centre + radius
  and return a `CameraPose` framing the model.
- Backward compatible: `camera=None` keeps current default behaviour.

#### 2.2.3 `render/section.py` (new)

- `section_mesh(records, kernel, plane)` — clip tessellated triangles to a
  plane; return cut surface polygons + the kept portion.
- Only plane sections (XY/YZ/XZ) per Plan v2 risk mitigation; curved
  sections deferred.

#### 2.2.4 `render/explode.py` (new)

- `explode_mesh(records, kernel, spec)` — translate each entity's
  tessellated vertices outward from the model centre along each axis by
  `offset * signed_distance(centre)`.

#### 2.2.5 `render/animation.py` (new)

- `render_orbit_gif(records, kernel, frames=48, fps=10, path=None)` —
  renders successive camera poses via `renderer_3d` and assembles a GIF
  with `imageio`.
- Returns GIF bytes; optionally writes to `path`.

#### 2.2.6 `render/webgl_exporter.py` (upgrade)

- `export_webgl_delta(previous_ids, records, kernel)` — returns
  `{added: [...], removed: [...], updated: [...], data: full snapshot if
  requested}`. An incremental sync for browser clients where added/updated
  objects carry their BufferGeometry and removed objects are only ids.
- `export_webgl` unchanged (full snapshot path).

#### 2.2.7 `mcp/tools/view3d.py` (new)

| Tool | Description | Permission |
|------|-------------|------------|
| `cad_view_3d_create` | Create a named 3D view definition | STANDARD |
| `cad_view_3d_read` | Read a view definition by id/name | READ_ONLY |
| `cad_view_3d_list` | List all view definitions | READ_ONLY |
| `cad_view_3d_update` | Update camera/projection/section/explode | STANDARD |
| `cad_view_3d_delete` | Delete a view definition | DESTRUCTIVE |
| `cad_view_3d_render` | Render the document to PNG with a view's camera | READ_ONLY |
| `cad_view_section` | Render a plane-section PNG | READ_ONLY |
| `cad_view_explode` | Render an exploded PNG | READ_ONLY |
| `cad_view_animation` | Render an orbit GIF | READ_ONLY |
| `cad_webgl_sync` | Return incremental WebGL delta | READ_ONLY |

Views are stored per-document in `ViewManager` attached to
`DocumentState`.

#### 2.2.8 `mcp/security.py`

Register all ten new tools with the permissions above.

#### 2.2.9 CLI (`cli/commands/render.py`)

Add subcommands to the `render` group: `view3d`, `section`, `explode`,
`gif`, and a `views` listing command.

### 2.3 Phase 5 Acceptance Criteria

- [ ] `cad_view_3d_create` + `cad_view_3d_read` round-trip view definitions
- [ ] `cad_view_3d_render` honours azimuth/elevation/projection; PNG differs
  between named views
- [ ] `cad_view_section` cuts a box in half on the XY plane
- [ ] `cad_view_explode` produces spatially separated parts
- [ ] `cad_view_animation` returns a valid GIF (magic `GIF8`)
- [ ] `cad_webgl_sync` returns added/removed/updated deltas across edits
- [ ] CLI `render view3d iso` writes a PNG
- [ ] 10+ new unit tests; total coverage maintained ≥80%

---

## 3. Phase 6 — v0.4.0: Docker + Production Hardening

### 3.1 Goal

Ship a deployable, observable, secured server: small Docker image,
Prometheus metrics, API-key authentication, rate limiting and a verified
sandbox — without adding heavy new dependencies.

### 3.2 Deliverables

#### 3.2.1 `docker/Dockerfile` + `docker/docker-compose.yml` + `docker/entrypoint.sh`

- Multi-stage build: builder (`python:3.11-slim`, build-essential, `pip
  install --user -e '.[prod]'`) → runtime (`python:3.11-slim`).
- `ENV CAD_RUNTIME=analytic CAD_HEADLESS=true CAD_TEMP_DIR=/tmp/cad
  CAD_MAX_MEMORY=4096`, `EXPOSE 8081`.
- `HEALTHCHECK` on `/health`, `ENTRYPOINT ['python', '-m',
  'cad_mcp_server']`, `CMD ['--transport', 'http', '--port', '8081']`.
- Compose: volume mounts for `data/` and `config/`, env overrides,
  healthcheck, `restart: unless-stopped`.
- Target image size `< 500MB` (matplotlib Agg headless; no display stack).

#### 3.2.2 `utils/metrics.py` (new) + HTTP `/metrics` route

- `OPERATION_DURATION` Histogram (`cad_operation_duration_seconds`,
  `['tool_name']`, buckets 0.001→10s).
- `OPERATION_COUNT` Counter (`cad_operations_total`, `['tool_name',
  'status']`).
- `ENTITY_COUNT` Counter (`cad_entities_total`, `['entity_type']`).
- `metrics_endpoint(request)` Starlette handler returning
  `generate_latest()`.
- Instrument tool dispatch in the HTTP transport wrapper; keep label
  cardinality bounded (`tool_name` < 50).

#### 3.2.3 Auth: API Key (+ OAuth2 reserved) — `mcp/security.py`

- `CAD_API_KEYS` env (comma-separated) or `config/` file.
- HTTP transport returns `401` without a valid token and `403` with a
  wrong token; stdio mode unaffected.
- OAuth2 (JWT) scaffolding reserved behind `CAD_AUTH_MODE=oauth2`, not
  implemented in this milestone.

#### 3.2.4 `mcp/rate_limit.py` (new)

- Sliding-window `RateLimiter(max_requests=100, window_seconds=60)`
  per client id; applied in the HTTP transport middleware.
- `429` response on limit breach.

#### 3.2.5 Sandbox hardening (verify)

- Batch script runner blocks `import os`, `import sys`, and file reads
  like `/etc/passwd`; enforced via import whitelist + timeout
  (subprocess). Add regression tests.

#### 3.2.6 Config centre (reserved)

- Precedence env → file (`config/`) → remote (Consul/Nacos reserved);
  implement env + file now via existing `pydantic-settings` `Settings`.

### 3.3 Phase 6 Acceptance Criteria

- [ ] Docker image builds successfully, size `< 500MB`
- [ ] `docker-compose up` starts; `/health` returns 200
- [ ] `/metrics` exposes `cad_operations_total` and
      `cad_operation_duration_seconds`
- [ ] Sandbox blocks `import os` and reading `/etc/passwd`
- [ ] HTTP mode returns `401` without token, `403` with wrong token
- [ ] 1000-object document operations average latency `< 100ms`
      (`pytest-benchmark`)
- [ ] 15+ new unit tests; coverage maintained ≥80%

---

## 4. Milestones

| Milestone | Date | Version | Core Deliverables | Key Metrics |
|-----------|------|---------|-------------------|-------------|
| **Phase 5** | 2026-08-28 | v0.3.0 | View3D schema, camera/section/explode/GIF, WebGL delta, 10 new tools | PNG per view, GIF output, ≥80% coverage |
| **Phase 6** | 2026-09-04 | v0.4.0 | Docker image, Prometheus metrics, API-key auth, rate limiting, sandbox verify | Image <500MB, 401/403, <100ms latency |

---

## 5. Dependencies & Risks

### 5.1 Dependencies

- No new runtime dependencies for Phase 5/6 core — `imageio` and
  `prometheus-client` are already in `pyproject.toml`.
- `pytest-benchmark` added to the dev test extras for the latency gate.

### 5.2 Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| matplotlib camera API varies | Medium | Low | Abstract pose→`view_init`/`set_proj_type` in one helper; pin matplotlib |
| Section clipping edge cases (coplanar/vertex) | Medium | Medium | Robust epsilon-based triangle-plane clip; test box + cylinder |
| GIF size for large models | Low | Medium | Downsample frames, cap `frames<=96` |
| WebGL delta correctness | Medium | Medium | Deterministic object ordering; unit-test add/remove/update |
| Image > 500MB | Low | Medium | Keep render deps optional; split `[render]` extra if needed |
| Metrics cardinality | Low | Low | Bounded `tool_name` labels (<50) |

---

## 6. First Tasks

1. **Phase 5**: implement `schemas/view3d.py` + `renderer_3d.py` camera
   support (foundation).
2. **Phase 5**: add `section.py`, `explode.py`, `animation.py`,
   `webgl_exporter` delta.
3. **Phase 5**: `mcp/tools/view3d.py` + `security.py` + CLI + tests.
4. **Phase 6**: `utils/metrics.py`, auth, `rate_limit.py`, sandbox tests.
5. **Phase 6**: `docker/` files.
6. Bump version, run `ruff` + `mypy` + full `pytest`.
