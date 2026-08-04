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