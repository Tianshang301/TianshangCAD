"""CADGenBench local demo harness.

Drives the real ``tianshangcad-server`` over stdio to build 3D mechanical
parts from declarative descriptions, exports each as STEP, and runs a
local validity check that mirrors CADGenBench's validity gate.

The harness reads fixture descriptions from ``datasets/cadgenbench/fixtures.json``
and ground-truth build steps from ``datasets/cadgenbench/ground_truth.json``.
Each fixture is built, exported to STEP, and validated for watertightness.

Usage:
    python scripts/cadgenbench_harness.py [--out dist/cadgenbench] [--occ]
    python scripts/cadgenbench_harness.py --fixtures datasets/cadgenbench/fixtures.json
    python scripts/cadgenbench_harness.py --builtin   # Use the 3 built-in samples

Flags:
    --out           Output directory (default dist/cadgenbench).
    --occ           Use the OCCT kernel for STEP export.
    --fixtures      Path to fixtures.json (default datasets/cadgenbench/fixtures.json).
    --ground-truth  Path to ground_truth.json (default datasets/cadgenbench/ground_truth.json).
    --builtin       Use the 3 built-in samples instead of loading from disk.
    --limit N       Run only the first N fixtures.

Requires: ``pip install -e .`` (and ``trimesh`` for the validity check).
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
# Built-in samples (used with --builtin)
# -----------------------------------------------------------------------

@dataclass
class Sample:
    """One benchmark sample: an id, a human description and the build steps."""

    sample_id: str
    task_type: str
    description: str
    difficulty: str = "easy"
    calls: list[dict[str, Any]] = field(default_factory=list)


SAMPLES: list[Sample] = [
    Sample(
        sample_id="101",
        task_type="generation",
        difficulty="easy",
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
                    "target_id": "__0__",
                    "tool_ids": ["__1__"],
                    "layer": "Body",
                },
            },
        ],
    ),
    Sample(
        sample_id="102",
        task_type="generation",
        difficulty="easy",
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
                    "target_id": "__0__",
                    "tool_ids": ["__1__"],
                    "layer": "Body",
                },
            },
        ],
    ),
    Sample(
        sample_id="103",
        task_type="generation",
        difficulty="easy",
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
# Fixture loader
# -----------------------------------------------------------------------

def load_fixtures(fixtures_path: Path) -> list[dict[str, Any]]:
    """Load fixtures from a JSON file."""
    if not fixtures_path.exists():
        raise FileNotFoundError(f"Fixtures file not found: {fixtures_path}")
    data = json.loads(fixtures_path.read_text(encoding="utf-8"))
    fixtures = data.get("fixtures", [])
    if not fixtures:
        raise ValueError(f"No fixtures found in {fixtures_path}")
    return fixtures


def load_ground_truth(gt_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load ground truth calls from a JSON file."""
    if not gt_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {gt_path}")
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    return data.get("ground_truth", {})


# -----------------------------------------------------------------------
# MCP helpers
# -----------------------------------------------------------------------

async def call_tool(session: ClientSession, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call an MCP tool with the (flattened) top-level args and return JSON."""
    result = await session.call_tool(tool, args)
    text = result.content[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": str(text)}


def _resolve(
    obj_id: str, id_stack: list[str], type_of: dict[int, str]
) -> str:
    """Resolve sentinels to actual object ids from the creation stack.

    Supported sentinels:
        ``__N__``           — N-th object on the creation stack (0-based).
        ``__last__``        — most recently created object on the stack.
        ``__last_<type>__`` — most recently created object of the given type
                              (e.g. ``__last_box__``, ``__last_cylinder__``).
        ``__active__``      — same as ``__last__``.

    Fallback: ``__id__`` with an explicit object id returns the id as-is
    (e.g. ``__abc123__`` → ``abc123``).
    """
    if obj_id == "__last__" or obj_id == "__active__":
        return id_stack[-1] if id_stack else obj_id
    if obj_id.startswith("__") and obj_id.endswith("__"):
        inner = obj_id[2:-2]
        # Try numeric index first (__0__, __1__, ...)
        try:
            idx = int(inner)
            if 0 <= idx < len(id_stack):
                return id_stack[idx]
        except ValueError:
            pass
        # Try type-based lookup (__last_<type>__ → __last_box__ → last box)
        if inner.startswith("last_"):
            kind = inner[5:]
            return _last_of_type(kind, id_stack, type_of)
        # Bare hex-like id passed through `__<id>__` wrap
        return inner
    return obj_id


_TYPE_ALIASES: dict[str, str] = {
    "cyl": "cylinder",
    "rect": "rectangle",
    "poly": "polygon",
}


def _last_of_type(kind: str, id_stack: list[str], type_of: dict[int, str]) -> str:
    """Return the most recently created object of the given type kind."""
    normalized = _TYPE_ALIASES.get(kind, kind)
    for idx in range(len(id_stack) - 1, -1, -1):
        if type_of.get(idx) == normalized:
            return id_stack[idx]
    return id_stack[-1] if id_stack else ""


async def build_one(
    session: ClientSession, sample: Sample
) -> dict[str, Any]:
    """Execute a sample's build steps and return a report."""
    report: dict[str, Any] = {"id": sample.sample_id, "status": "ok"}
    id_stack: list[str] = []
    type_of: dict[int, str] = {}

    for step in sample.calls:
        args = dict(step["args"])
        if "target_id" in args:
            args["target_id"] = _resolve(args["target_id"], id_stack, type_of)
        if "tool_ids" in args:
            args["tool_ids"] = [_resolve(t, id_stack, type_of) for t in args["tool_ids"]]

        out = await call_tool(session, step["tool"], args)

        if out.get("status") == "error":
            report["status"] = "error"
            report["error"] = out.get("message", "unknown")
            return report

        if step["tool"] == "cad_object_create":
            oid = out.get("object_id")
            if oid:
                idx = len(id_stack)
                id_stack.append(oid)
                obj_type = args.get("type") or out.get("type")
                if obj_type:
                    type_of[idx] = obj_type

        if step["tool"] == "cad_object_boolean":
            oid = out.get("result_id")
            if oid:
                id_stack.append(oid)

        if step["tool"].startswith("cad_feature_pattern_") and out.get("object_ids"):
            id_stack.extend(out["object_ids"])

    return report


# -----------------------------------------------------------------------
# Validity check (mirrors CADGenBench's gate)
# -----------------------------------------------------------------------

def check_validity(step_path: Path) -> dict[str, Any]:
    """Check that a STEP file loads as a closed, watertight manifold."""
    try:
        import trimesh
    except ImportError:
        return {"is_valid": False, "error": "trimesh missing"}

    mesh = _load_as_trimesh(trimesh, step_path)
    if mesh is None:
        try:
            from tianshangcad.io.importers.step import STEPImporter
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
    """Load a STEP file with trimesh; None on failure."""
    try:
        mesh = trimesh.load_mesh(str(step_path), file_type="step")
    except Exception:
        return None
    if hasattr(mesh, "concatenate"):
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

async def run_all(
    samples: list[Sample],
    out_dir: Path,
    use_occ: bool = False,
) -> dict[str, Any]:
    """Build every sample, export STEP, validate, and write reports."""
    out_dir.mkdir(parents=True, exist_ok=True)
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "tianshangcad", "--transport", "stdio"]
    )
    per_sample: dict[str, Any] = {}
    n_valid = 0

    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = sorted(t.name for t in tools.tools)

        for sample in samples:
            print(f"  [{sample.sample_id}] {sample.description[:80]}...", end=" ", flush=True)

            build_report = await build_one(session, sample)

            state: dict[str, Any] = {
                "id": sample.sample_id,
                "task_type": sample.task_type,
                "difficulty": sample.difficulty,
            }

            if build_report["status"] != "ok":
                state.update({
                    "status": "build_error",
                    "error": build_report.get("error"),
                    "cad_score": 0,
                })
                per_sample[sample.sample_id] = state
                print("BUILD ERROR")
                continue

            step_path = out_dir / f"{sample.sample_id}.step"
            try:
                export_out = await call_tool(
                    session, "cad_file_export",
                    {"format": "step", "path": str(step_path)}
                )
                if export_out.get("status") == "error":
                    state.update({
                        "status": "export_error",
                        "error": export_out.get("message"),
                        "cad_score": 0,
                    })
                    per_sample[sample.sample_id] = state
                    print("EXPORT ERROR")
                    continue
            except Exception as exc:
                state.update({"status": "export_error", "error": str(exc), "cad_score": 0})
                per_sample[sample.sample_id] = state
                print("EXPORT ERROR")
                continue

            valid = check_validity(step_path)
            if valid["is_valid"]:
                state["status"] = "valid"
                state["cad_score"] = 1.0
                n_valid += 1
                print(f"PASS (volume={valid.get('volume', '?')})")
            else:
                state["status"] = "invalid"
                state["cad_score"] = 0.0
                print(f"FAIL ({valid.get('error', 'not watertight')})")

            state["validation"] = {"is_watertight": valid.get("is_watertight")}
            if valid.get("volume") is not None:
                state["validation"]["volume"] = valid["volume"]
            state["validation"]["bbox"] = valid.get("bbox")
            if valid.get("error"):
                state["validation"]["error"] = valid["error"]
            per_sample[sample.sample_id] = state

    n_samples = len(samples)
    summary: dict[str, Any] = {
        "runner": "tianshangcad-server (offline demo harness)",
        "backend": "occ" if use_occ else "analytic (AP203 faceted)",
        "aggregate_score": round(n_valid / n_samples, 4) if n_samples else 0.0,
        "validity_rate": round(n_valid / n_samples, 4) if n_samples else 0.0,
        "n_samples": n_samples,
        "n_valid": n_valid,
        "tools_registered": len(tool_names),
        "per_sample_scores": per_sample,
    }
    summary_path = out_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist/cadgenbench", help="Output directory")
    parser.add_argument("--occ", action="store_true", help="Use the OCCT kernel for STEP export")
    parser.add_argument(
        "--fixtures",
        default="datasets/cadgenbench/fixtures.json",
        help="Path to fixtures.json",
    )
    parser.add_argument(
        "--ground-truth",
        default="datasets/cadgenbench/ground_truth.json",
        help="Path to ground_truth.json",
    )
    parser.add_argument(
        "--builtin", action="store_true",
        help="Use the 3 built-in samples instead of loading from disk",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Run only the first N fixtures (0 = all)",
    )
    args = parser.parse_args()

    if args.builtin:
        samples = list(SAMPLES)
    else:
        fixtures = load_fixtures(Path(args.fixtures))
        ground_truth = load_ground_truth(Path(args.ground_truth))
        samples = []
        for f in fixtures:
            fid = f["id"]
            if fid not in ground_truth:
                continue
            samples.append(Sample(
                sample_id=fid,
                task_type=f.get("task_type", "generation"),
                description=f["description"],
                difficulty=f.get("difficulty", "easy"),
                calls=ground_truth[fid],
            ))

    if args.limit > 0:
        samples = samples[: args.limit]

    if not samples:
        print("No samples to run.")
        return

    print(f"Running {len(samples)} sample(s) ...")

    summary = asyncio.run(run_all(samples, Path(args.out), args.occ))

    print(f"\n{'='*60}")
    total = summary["n_samples"]
    valid = summary["n_valid"]
    rate = summary["validity_rate"]
    print(f"Results: {valid}/{total} valid ({rate * 100:.1f}%)")
    print(f"Output:  {Path(args.out) / 'run_summary.json'}")


if __name__ == "__main__":
    main()
