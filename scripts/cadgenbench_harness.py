"""CADGenBench local demo harness.

Drives the real ``cad-mcp-server`` over stdio to build a small set of
3D mechanical parts from declarative sample "descriptions", exports each
as STEP, and runs a local validity check that mirrors CADGenBench's
validity gate (well-formed, watertight manifold that meshes).

This is the *offline* instrumented harness: it exercises the same MCP
tool pipeline an LLM agent would use, but with hand-written call
sequences, so it needs no external API keys and no HuggingFace token.
To turn it into a real CADGenBench submission you would (a) read a
sample's ``description.yaml``, (b) let an LLM choose the tool calls with
this server as the backend, and (c) upload the resulting ``output.step``
candidates to the leaderboard Space.

Usage:
    python scripts/cadgenbench_harness.py [--out dist/cadgenbench] [--occ]

Flags:
    --out   Output directory (default dist/cadgenbench).
    --occ   Use the OCCT kernel for STEP export instead of the default
            pure-Python AP203 faceted exporter.

Requires: ``pip install -e .`` (and ``trimesh`` for the validity check;
``trimesh`` also needs ``scipy``/``numpy`` installed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# -----------------------------------------------------------------------
# Built-in sample "descriptions" (generation tasks), CADGenBench-style.
# Each is a sequence of MCP calls that build a valid watertight part.
# -----------------------------------------------------------------------

@dataclass
class Sample:
    """One benchmark sample: an id, a human description and the build steps."""

    sample_id: str
    task_type: str
    description: str
    calls: list[dict[str, Any]] = field(default_factory=list)


SAMPLES: list[Sample] = [
    Sample(
        sample_id="101",
        task_type="generation",
        description=(
            "a flat mounting plate 60 x 40 x 8 mm with a centred "
            "through-hole of radius 5 mm"
        ),
        calls=[
            {"tool": "cad_file_create", "args": {"filename": "101.json", "unit": "mm"}},
            {
                "tool": "cad_object_create",
                "args": {
                    "type": "box",
                    "params": {"origin": [0, 0, 0], "dimensions": [60, 40, 8]},
                    "layer": "Body",
                },
            },
            {
                "tool": "cad_object_create",
                "args": {
                    "type": "cylinder",
                    "params": {"origin": [30, 20, 0], "radius": 5, "height": 8},
                    "layer": "Hole",
                },
            },
            {
                "tool": "cad_object_boolean",
                "args": {
                    "operation": "subtract",
                    "target_id": "__last_box__",
                    "tool_ids": ["__last_cyl__"],
                },
            },
        ],
    ),
    Sample(
        sample_id="102",
        task_type="generation",
        description=(
            "a rectangular base block 80 x 50 x 12 mm with a centred boss of "
            "radius 12 mm extruded 20 mm above the top face"
        ),
        calls=[
            {"tool": "cad_file_create", "args": {"filename": "102.json", "unit": "mm"}},
            {
                "tool": "cad_object_create",
                "args": {
                    "type": "box",
                    "params": {"origin": [0, 0, 0], "dimensions": [80, 50, 12]},
                    "layer": "Body",
                },
            },
            {
                "tool": "cad_object_create",
                "args": {
                    "type": "cylinder",
                    "params": {"origin": [40, 25, 12], "radius": 12, "height": 20},
                    "layer": "Boss",
                },
            },
            {
                "tool": "cad_object_boolean",
                "args": {
                    "operation": "union",
                    "target_id": "__last_box__",
                    "tool_ids": ["__last_cyl__"],
                },
            },
        ],
    ),
    Sample(
        sample_id="103",
        task_type="generation",
        description="a solid cube 30 x 30 x 30 mm",
        calls=[
            {"tool": "cad_file_create", "args": {"filename": "103.json", "unit": "mm"}},
            {
                "tool": "cad_object_create",
                "args": {
                    "type": "box",
                    "params": {"origin": [0, 0, 0], "dimensions": [30, 30, 30]},
                    "layer": "Body",
                },
            },
        ],
    ),
]


# -----------------------------------------------------------------------
# MCP helper
# -----------------------------------------------------------------------

async def call_tool(session: ClientSession, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call an MCP tool with the (flattened) top-level args and return JSON."""
    result = await session.call_tool(tool, args)
    text = result.content[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": str(text)}


def _resolve(obj_id: str, created: dict[str, str]) -> str:
    """Resolve ``__last_<kind>__`` sentinels to the matching created id."""
    if obj_id.startswith("__last_"):
        kind = obj_id[len("__last_") : -len("__")]
        return created.get(kind) or created["object"]
    return obj_id


async def build_one(
    session: ClientSession, sample: Sample, created: dict[str, str]
) -> dict[str, Any]:
    """Execute a sample's build steps against the live server."""
    report: dict[str, Any] = {"id": sample.sample_id, "status": "ok"}
    for step in sample.calls:
        args = dict(step["args"])
        if "target_id" in args:
            args["target_id"] = _resolve(args["target_id"], created)
        if "tool_ids" in args:
            args["tool_ids"] = [_resolve(t, created) for t in args["tool_ids"]]
        out = await call_tool(session, step["tool"], args)
        # Record newly created object ids for the __last__ sentinels.
        if step["tool"] == "cad_object_create":
            oid = out.get("object_id")
            if oid:
                created["object"] = oid
                obj_type = args.get("type") or out.get("type")
                if obj_type:
                    created[obj_type] = oid
        if out.get("status") == "error":
            report["status"] = "error"
            report["error"] = out.get("message", "unknown")
            break
    return report


# -----------------------------------------------------------------------
# Validity check (mirrors CADGenBench's gate)
# -----------------------------------------------------------------------

def check_validity(step_path: Path) -> dict[str, Any]:
    """Check that a STEP file loads as a closed, watertight manifold."""
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        return {"is_valid": False, "error": f"trimesh missing: {exc}"}
    mesh = _load_as_trimesh(trimesh, step_path)
    if mesh is None:
        # Fallback: read through our own AP203 importer (no cascadio needed).
        try:
            from cad_mcp_server.io.importers.step import STEPImporter

            doc = STEPImporter().import_file(str(step_path))
            for entity in doc.entities.list():
                params = entity.shape.get("params", {})
                verts, faces = params.get("vertices"), params.get("faces")
                if verts and faces:
                    mesh = trimesh.Trimesh(vertices=verts, faces=faces)
                    break
            if mesh is None:
                return {"is_valid": False, "error": "no mesh loaded"}
        except Exception as exc:
            return {"is_valid": False, "error": f"load failed: {exc}"}
    try:
        is_watertight = bool(mesh.is_watertight)
    except Exception:
        is_watertight = False
    bbox = mesh.bounds
    return {
        "is_valid": is_watertight,
        "is_watertight": is_watertight,
        "volume": float(mesh.volume) if is_watertight else None,
        "bbox": {
            "min": [float(v) for v in (bbox[0] if bbox is not None else [0, 0, 0])],
            "max": [float(v) for v in (bbox[1] if bbox is not None else [0, 0, 0])],
        },
    }


def _load_as_trimesh(trimesh: Any, step_path: Path) -> Any:
    """Load a STEP file with trimesh (needs ``cascadio``); None on failure."""
    try:
        mesh = trimesh.load_mesh(str(step_path), file_type="step")
    except Exception:
        return None
    if hasattr(mesh, "concatenate"):  # Scene — merge to a single watertight body
        try:
            merged = mesh.dump(concatenate=True)
        except Exception:
            merged = None
        if merged is None or getattr(merged, "faces", None) is None:
            return None
        mesh = merged
    return mesh


# -----------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------

async def run_all(out_dir: Path, use_occ: bool) -> dict[str, Any]:
    """Build every sample, export STEP, validate, and write reports."""
    out_dir.mkdir(parents=True, exist_ok=True)
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "cad_mcp_server", "--transport", "stdio"]
    )
    per_sample: dict[str, Any] = {}
    n_valid = 0

    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = sorted(t.name for t in tools.tools)
        for sample in SAMPLES:
            created: dict[str, str] = {}
            build_report = await build_one(session, sample, created)

            state: dict[str, Any] = {"id": sample.sample_id, "task_type": sample.task_type}
            if build_report["status"] != "ok":
                state.update(
                    {
                        "status": "build_error",
                        "error": build_report.get("error"),
                        "cad_score": 0,
                    }
                )
                per_sample[sample.sample_id] = state
                continue

            step_path = out_dir / f"{sample.sample_id}.step"
            try:
                out = await call_tool(
                    session, "cad_file_export", {"format": "step", "path": str(step_path)}
                )
                if out.get("status") == "error":
                    state.update(
                        {
                            "status": "export_error",
                            "error": out.get("message"),
                            "cad_score": 0,
                        }
                    )
                    per_sample[sample.sample_id] = state
                    continue
            except Exception as exc:
                state.update({"status": "export_error", "error": str(exc), "cad_score": 0})
                per_sample[sample.sample_id] = state
                continue

            valid = check_validity(step_path)
            state["status"] = "valid" if valid["is_valid"] else "invalid"
            state["cad_score"] = 1.0 if valid["is_valid"] else 0.0
            state["validation"] = {"is_watertight": valid.get("is_watertight")}
            if valid.get("volume") is not None:
                state["validation"]["volume"] = valid["volume"]
            state["validation"]["bbox"] = valid.get("bbox")
            if valid.get("error"):
                state["validation"]["error"] = valid["error"]
            if valid["is_valid"]:
                n_valid += 1
            per_sample[sample.sample_id] = state

    n_samples = len(SAMPLES)
    summary: dict[str, Any] = {
        "runner": "cad-mcp-server (offline demo harness)",
        "backend": "occ" if use_occ else "analytic (AP203 faceted)",
        "aggregate_score": round(n_valid / n_samples, 4) if n_samples else 0.0,
        "validity_rate": round(n_valid / n_samples, 4) if n_samples else 0.0,
        "n_samples": n_samples,
        "n_valid": n_valid,
        "tools_registered": len(tool_names),
        "per_sample_scores": per_sample,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist/cadgenbench", help="Output directory")
    parser.add_argument("--occ", action="store_true", help="Use the OCCT kernel for STEP export")
    args = parser.parse_args()
    summary = asyncio.run(run_all(Path(args.out), args.occ))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
