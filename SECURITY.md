# Security Policy

## Supported Versions

Security fixes are released for the latest minor version on the `main`
branch. When a vulnerability is fixed, a new patch release (e.g. `v0.9.2`)
is cut; older minor versions are not backported unless the issue is
trivially safe to backport.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security problems. Report
them privately to the maintainer:

- Email: **Tianshang301@outlook.com**
- Subject prefix: `[SECURITY] `

You can expect:

1. An acknowledgement within **48 hours**.
2. A triage / severity assessment and a target fix timeline.
3. Coordination on disclosure (typically a fix release first, then a public
   advisory) once the issue is resolved.

If the report is confirmed, the reporter is credited (unless they ask to
remain anonymous).

## Security Features

The project ships several security-relevant capabilities; operators are
expected to enable them in production:

### API-key authentication (HTTP transport)

- The streamable-HTTP endpoint is guarded by `TIANGSHANGCAD_API_KEY` (single key) or
  `TIANSHANGTIANGSHANGTIANGSHANGCAD_API_KEYS` (comma-separated list).
- Key comparison is constant-time via `hmac.compare_digest`, so timing
  attacks cannot leak key bytes.
- If no key is configured the HTTP endpoint is open — intended for local
  development only; always set a key in production.
- `stdio` transport is unaffected (local subprocess).

### Tool permission model (RBAC)

- Every MCP tool maps to a `PermissionLevel`: `read_only`, `standard`,
  `destructive`, or `admin`.
- Read-only tools auto-approve; write tools require confirmation;
  destructive tools (delete / overwrite / cancel) always require explicit
  confirmation; admin tools are reserved for operators.
- `TIANGSHANGCAD_AUTO_APPROVE` configures the auto-approved tool set;
  `TIANGSHANGCAD_SAFE_MODE=true` disables destructive operations entirely.

### Rate limiting

- A sliding-window limiter caps requests per client (`max_requests` per
  `window_seconds`, defaults 100/60s) on the HTTP transport.
- Clients are identified by header / IP; the limiter is thread-safe.

### Sandboxed script execution

- Batch jobs run Python / SCR / batch scripts in a sandboxed subprocess with
  a configurable timeout (`TIANGSHANGCAD_SAFE_MODE` and batch scheduling options).
- Scripts are never executed inline in the server process.

## Configuration Checklist

- Set `TIANGSHANGCAD_API_KEY` (or `TIANSHANGTIANGSHANGTIANGSHANGCAD_API_KEYS`) in production.
- Keep `TIANGSHANGCAD_AUTO_APPROVE` as small as possible.
- Enable `TIANGSHANGCAD_SAFE_MODE=true` when destructive operations are not needed.
- Do not expose the MCP HTTP endpoint to the public internet without a
  reverse proxy, TLS, and an API key.
