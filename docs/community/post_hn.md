# Show HN draft

Paste the following into https://news.ycombinator.com/submit

## Title

Show HN: TianshangCAD – a CAD CLI + MCP server, JSON-driven and headless

## URL

https://github.com/Tianshang301/TianshangCAD

## Text (optional body)

I built a CAD system that speaks MCP: 103 tools that let an AI agent (or a
human in a terminal) create, edit, measure, validate and assemble 2D/3D
models, all defined as JSON Schema and executed on a pluggable kernel
(analytic by default, OCC/FreeCAD optional).

Why this exists: most CAD is a GUI first. I wanted CAD that a model can
drive directly - draw a line, boolean two solids, build a BOM, export STEP -
without a human babysitting the viewport.

Highlights:
- Headless and JSON-driven: scenes, geometry and parameters round-trip
  through Pydantic schemas.
- Transports: stdio, streamable HTTP, and WebSocket for real-time
  collaboration (LWW-Map CRDT, RBAC, document branches).
- Assembly modeling (6 mate types, BOM, explode) + engineering drawings
  (ISO-129 dimensions, GD&T, DXF/PDF/SVG).
- Parametric features (sweep/loft/fillet/patterns) and a simulation
  interface (CalculiX, PyBullet) as optional extras.
- Batch scheduling, geometry validation, natural-language command mapping.
- ~915 tests, 87% coverage, ruff + mypy clean. Windows exe and a Debian
  package are published per release.

Feedback welcome - especially on the flat tool schema (a deliberate v0.9
breaking change) and whether a dedicated CAD category belongs in the
awesome-mcp-servers list.

Install: pip install tianshangcad-server

## Posting tips

- Post the URL as the link, and use the text box only if you want a longer
  first comment; otherwise put this body in a top-level comment right after
  submitting.
- Timing: Hacker News is busiest Mon-Thu 7-10am and 2-4pm ET.
