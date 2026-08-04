# awesome-mcp-servers entry for TianshangCAD

Ready-to-paste submission for the
[punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)
list. Because there is no dedicated "CAD & Engineering" category yet (CAD
servers are currently scattered under Art & Culture), we propose adding one.

## README change

New category heading (place alphabetically among the emoji-anchored
sections, after the TOC entry):

```
* 📐 - [CAD & Engineering](#cad-and-engineering)
```

Then the section itself (insert after the `### 📐 Architecture & Design`
block, keeping the alphabetical order of the `* ...` TOC links):

```
### 📐 <a name="cad-and-engineering"></a>CAD & Engineering

- [Tianshang301/TianshangCAD](https://github.com/Tianshang301/TianshangCAD)
  🐍 🏠 🍎 🪟 🐧 - Modern CAD CLI + MCP Server: 2D/3D drawing, editing,
  measurement, validation, assembly modeling, engineering drawings, batch
  automation and real-time collaboration (CRDT + WebSocket). 103 JSON-RPC
  tools over stdio, streamable HTTP or WebSocket. `pip install tianshangcad-server`
```

## Pull request body

```markdown
Add TianshangCAD - CAD CLI + MCP Server

A modern CAD CLI + MCP Server system. Geometry, scenes and parameters are
defined via JSON Schema and operated either from the command line or as MCP
tools callable by any AI agent.

Highlights:
- 103 tools: file/geometry CRUD, layers, batch scheduling, geometry
  validation, assembly mates + BOM, engineering drawings (DXF/PDF/SVG),
  parametric features, simulation interface, real-time collaboration.
- 2D + 3D: line/circle/arc/box/cylinder/sphere/mesh primitives, booleans,
  sweeps/lofts, transforms, bounding-box measurement.
- Transports: stdio, streamable HTTP, and WebSocket for collaboration.
- Zero native deps on the default analytic kernel; optional OCC (cadquery)
  and FreeCAD kernels.

Install: `pip install tianshangcad-server`
Docs: https://github.com/Tianshang301/TianshangCAD
```

## Notes

- Transport emojis: `🐍` Python, `🏠` local, `🍎` macOS, `🪟` Windows,
  `🐧` Linux — the server is cross-platform and runs locally.
- The maintainers ask for a single bullet; keep the entry one line if they
  prefer a compact list.
