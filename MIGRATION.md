# MIGRATION.md

Guide for moving an MCP client from tianshangcad-server v0.6.0 (or earlier) to
v0.9.0. There is one breaking change: tool arguments are now flat.

## Top-level breaking change

In v0.9.0 every tool that previously accepted a single nested `input` object
now publishes its fields as top-level tool parameters. The authoritative
definition lives `tools/list`; clients should parse `inputSchema` from there
instead of hard-coding payload shapes.

### Before (v0.6.0) - nested

`tools/call` payload for `cad_file_create`:

    {"input": {"filename": "part.json", "unit": "mm", "template": null}}

The `tools/list` `inputSchema` showed a single property named `input` whose
`type` was the model.

### After (v0.9.0) (flat)

`tools/call` payload now uses top-level fields:

    {"filename": "part.json", "unit": "mm", "template": null}

The `tools/list` `inputSchema` shows `filename`, `template`, `unit` directly
under `properties`, with required indicators for the requireds as before.

## Examples across tool families

All 103 registered tools are single-input and were flattened. Examples:

- `cad_file_create` -> `filename`, `template`, `unit`.
- `cad_object_create` -> `type`, `params`, `layer`, `properties`.
- `cad_batch_schedule` -> `name`, `commands`, `cron_expression`, `depends_on`,
  `webhook_url`, `script`, `script_type`, `timeout`, `template`,
  `template_vars`.

## Migrating a client

### Option 1 - read tools/list at startup

Load `tools/list` and cache each tool's `inputSchema.properties`. When calling
a tool, build the payload from the property names directly. This works for
any MCP client and requires no version logic.

### Option 2 - adapter wrapper

If your client already builds `{"input": {...}}` payloads, add a thin adapter
that flattens the outer `input` key:

    def adapt(payload):
        if "input" in payload and len(payload) == 1:
            return payload["input"]
        return payload

then pass the result to the tool call. Note the model still validates, and
unknown top-level keys produce a validation error, so the adapter should only
unwrap a single `input` key.

---

## v0.12.0 - aggregate tool surface (77 → 19 tools)

### Top-level breaking change

Every registered tool is now a `cad_<domain>` aggregate. The tool's
`tools/list` `inputSchema` shows one discriminator property (named after the
domain, e.g. `file`, `object`, `layer`, `query`, `status`, `batch`) whose
`action` / `tool` / `target` selects the operation. Always parse
`inputSchema` from `tools/list`; the shape below is illustrative.

### Before (v0.11.x) - granular tools

    cad_file_create    {"filename": "part.json", "unit": "mm"}
    cad_object_create  {"type": "box", "params": {...}, "layer": "0"}
    cad_metrics_get    {}

### After (v0.12.0) - aggregate tools

    cad_file           {"file": {"action": "create", "filename": "part.json", "unit": "mm"}}
    cad_object         {"object": {"action": "create", "type": "box", "params": {...}, "layer": "0"}}
    cad_validate       {"query": {"action": "metrics"}}

### Legacy-name mapping

The following former tool families were folded into aggregates (all 58 former
granular tools are unregistered):

| Former tool family | Aggregate (discriminator) |
|--------------------|---------------------------|
| `cad_file_create/open/save/close/delete/list`, `cad_file_io` | `cad_file` (`file.action`) |
| `cad_object_create/read/update/delete/copy/transform/list`, `cad_object_boolean`, `cad_boolean_*` | `cad_object` (`object.action`) |
| `cad_layer_create/read/update/delete/list` | `cad_layer` (`layer.action`) |
| `cad_json_load/parse/validate/save/import_*/export_*` | `cad_json` (`params.action`) |
| `cad_measure_distance/area` | `cad_measure` (`measure.action`) |
| `cad_validate_geometry/interference/topology`, `cad_metrics_get` | `cad_validate` (`query.action`) |
| `cad_view_3d_create/read/list/update/delete` | `cad_view` (`view.action`) |
| `cad_nlp_command/chat` | `cad_nlp` (`nlp.action`) |
| `cad_assembly_*` | `cad_assembly` (`assembly.action`) |
| `cad_drawing_*` | `cad_drawing` (`drawing.action`) |
| `cad_feature_*` | `cad_feature` (`feature.action`) |
| `cad_sim_*` | `cad_sim` (`sim.action`) |
| `cad_collab_*` | `cad_collab` (`collab.tool`) |
| `cad_status_*`, `cad_logs_*` | `cad_status` (`status.target` incl. logs_get/logs_clear) |

### SCR / batch scripts

SCR scripts and batch JSON now accept nested dotted keys to address the
aggregate input, e.g.

    cad_object object.action=create object.type=box

Previously flat keys such as `cad_metrics_get` are no longer registered; use
`cad_validate query.action=metrics`. `cad_batch` / `cad_json` / `cad_status` /
`cad_variable` / `cad_version` / `cad_constraint` / `cad_render` were already
aggregates in v0.11.x and are unchanged.
