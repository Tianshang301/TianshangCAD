# Reddit post draft

Candidates: r/MCP, r/FreeCAD, r/cad, r/3Dprinting, r/openscad.
r/MCP is the best fit (MCP servers audience); r/cad and r/FreeCAD are good
for the CAD angle. Do not post the identical text in more than two subs.

## Title (r/MCP)

TianshangCAD: an open-source CAD CLI + MCP server (103 tools, JSON-driven,
stdio / HTTP / WebSocket)

## Body (r/MCP)

I built a CAD system exposed over MCP so that AI agents can drive real
geometry operations directly - no GUI babysitting.

What it does:
- 103 JSON-RPC tools across files, geometry CRUD, layers, batch scheduling,
  geometry validation, assembly mates + BOM, engineering drawings, parametric
  features and a simulation interface.
- Three transports: stdio, streamable HTTP, and WebSocket for multi-user
  real-time collaboration (CRDT merge, RBAC, document branches).
- JSON-driven: scenes and geometry are Pydantic-validated and round-trip
  through JSON.
- Pluggable kernel: zero-native-dep analytic by default; OCC (cadquery) and
  FreeCAD backends as extras.

Quality: ~915 tests, 87% coverage, ruff + mypy clean. Releases ship Windows
executables and a Debian package.

A note for MCP clients: v0.9.0 flattens tool input schemas (top-level params
instead of nested "input"). `tools/list` is authoritative; see MIGRATION.md.

Try it: pip install cad-mcp-server
Repo: https://github.com/Tianshang301/TianshangCAD

Happy to discuss the transport choices and the flat-schema design.

## Alternative body (r/cad)

We open-sourced a CAD CLI + MCP server. The pitch for CAD folks: scripted,
headless, JSON-driven geometry with a real (optional) OCC/FreeCAD kernel,
assembly mates, engineering drawings, and - the novel part - an MCP server
so an LLM can operate it. Feedback on the schema and tool surface is
welcome. https://github.com/Tianshang301/TianshangCAD

## Posting tips

- r/MCP: add the "Showcase" flair if available.
- Keep replies civil; do not spam the same post across many subreddits.
