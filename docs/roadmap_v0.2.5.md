# TianshangCAD Roadmap (v0.2.5+)

> **Document Date**: 2026-08-02
> **Basis**: v0.2.5 release report
> **Current Status**: Phase 1 (CLI + IO), Phase 2 (MCP Server), Phase 3 (Batch & Automation) and Phase 4 (Advanced Features) complete
> **Baseline Version**: v0.2.5
> **Target Versions**: Phase 5 → v0.3.0, Phase 6 → v0.4.0

With batch automation and the validation/rendering layer delivered, the
foundational toolchain is solid. Building on the documented Phase 5/6 plans
and CAD industry trends, the following development directions are proposed.

---

## 1. Deepening the Planned Path (in-document roadmap)

### Phase 5: 3D Views & Visualization (v0.3.0)

| Feature | Direction |
|---------|-----------|
| **Complete 3D view toolchain** | Implement `schemas/view3d.py` and the corresponding MCP tools (e.g. `cad_view_3d`), supporting perspective/orthographic switching and camera pose control |
| **WebGL real-time preview** | Upgrade from static JSON export to **incremental sync** (WebSocket/SSE) with multi-client collaborative viewing |
| **Animation / GIF export** | Reuse the already-introduced `imageio` to render assembly-sequence animations and exploded views |
| **POV-Ray integration** | High-quality offline rendering with materials, lighting and shadows for product-grade output |

### Phase 6: Production Deployment (v0.4.0)

| Feature | Direction |
|---------|-----------|
| **Dockerization** | Provide an official image with headless operation (combined with the existing matplotlib Agg backend) |
| **Monitoring & observability** | Expose Prometheus metrics (the `prometheus-client` dependency is already reserved): queue depth, render latency, geometry error rates |
| **API authentication** | API Key + OAuth2 to prepare for team/enterprise deployment |
| **Configuration center** | Tiered management: environment variables → config files → remote config (e.g. Consul/Nacos) |

---

## 2. Architecture Upgrades

### 2.1 Distributed Task Queue

APScheduler + SQLite suits a single node but becomes a bottleneck as batch
workloads grow:

- Migrate to **Celery + Redis/RabbitMQ** with multiple worker nodes for
  parallel rendering and validation
- For large-model scenarios, geometry computation can be **GPU-accelerated**
  (CUDA BVH construction, triangle-mesh boolean operations)

### 2.2 Incremental Storage & Version Control

The current `deepdiff`-based JSON snapshots fit small documents; next steps:

- Introduce **Git-LFS-style binary diffing** for large CAD files
  (millions of triangles)
- Branch management (`branch` / `merge`) for parallel multi-designer workflows
- Native Git integration: `cad-cli version commit` generates a Git commit directly

### 2.3 Cloud Collaboration Architecture

```
browser / client <- WebSocket -> CAD gateway <- MCP -> geometry engine
                                      |
                                 object storage (S3/OSS) <- version snapshots
```

- Multi-user real-time collaborative editing (CRDT or Operational Transform,
  similar to Figma)
- Permission model: project-level / document-level / tool-level ACLs

---

## 3. AI Capability Depth (core differentiator)

The current NLP layer has only 12 hard-coded intents — this is the biggest
upgrade opportunity.

### 3.1 Deep LLM Agent Integration

- **Autonomous tool calling**: let the LLM decompose natural-language goals
  into MCP tool-call chains (ReAct / ToolFormer pattern)
- **Geometric intent understanding**: "add an M3 threaded hole at the top-left
  of this part, 10mm deep" → parse coordinates + call `cad_draw_cylinder` +
  `cad_boolean_subtract`
- **Design review agent**: automatically run the `cad_validate_*` tools and
  generate diagnostic reports with screenshots

### 3.2 Generative Design

- Parametric topology optimization: generate lightweight structures from
  loads and constraints
- Integrate with open-source solvers (e.g. **CalculiX**, **OpenFOAM**) for
  FEA pre-processing

### 3.3 Multimodal Interaction

- **Voice input** → NLP parsing → geometry operations
- **Sketch recognition**: hand-drawn sketch → 2D outline → 3D extrusion/revolution

---

## 4. Ecosystem & Integration

### 4.1 Industrial Interoperability

| Direction | Technical Path |
|-----------|----------------|
| **STEP/IGES import/export** | Wrap OpenCASCADE to interoperate with the SolidWorks / CATIA / UG ecosystem |
| **BIM integration** | IFC format support for Revit / ArchiCAD data exchange |
| **3D printing pipeline** | Direct STL output + slice preview (G-code visualization) |

### 4.2 Low-Code / No-Code Platform

- Visual node editor (like Grasshopper/Dynamo) wrapping MCP tools as draggable nodes
- Template marketplace: community-shared batch templates (the Jinja2 template
  foundation is already in place)

### 4.3 Browser-Native CAD

- Build on the existing WebGL export capability and compile the **core
  geometry engine to WASM**
- Pure browser-side CAD preview and light editing, with the server handling
  only heavy computation

---

## 5. Enterprise & Commercialization Path

| Dimension | Suggestion |
|-----------|------------|
| **Multi-tenant SaaS** | Build on the Phase 6 auth system: project isolation, resource quotas (render minutes, storage) |
| **Audit & compliance** | Complete operation logs (who, when, through which tool, which object changed) to satisfy manufacturing ISO audits |
| **Plugin system** | Open third-party MCP tool registration, similar to a VS Code extension marketplace |
| **Private deployment** | Offline enterprise-intranet edition with support for domestic OS / XinChuang environments |

---

## 6. Near-Term Priorities (v0.3.0 → v0.4.0)

With limited resources, invest in this order:

1. **Complete the 3D view toolchain** — fulfill the Phase 5 commitment and
   improve product completeness
2. **LLM agent-based rework** — upgrade NLP from hard-coded intents to
   dynamic LLM planning; this is the core value of an MCP server
3. **Docker + authentication** — fulfill Phase 6, turning the project from a
   "tool" into a "service"
4. **STEP/IGES support** — without industrial-standard format exchange, a CAD
   tool cannot enter real workflows

---

## Summary

The current stack (MCP protocol, Python ecosystem, APScheduler, Jinja2,
Three.js) has established the prototype of an **"AI-native CAD
infrastructure"**. The greatest differentiation opportunity: **do not leave
NLP at the intent-matching layer — evolve it into the LLM agent's "geometry
operation brain"**, letting natural language drive the full design,
validation and rendering pipeline directly.
