# CADGenBench Local Test Set

A local 50-fixture CAD generation test set in the [CADGenBench](https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench) format.

## Files

| File | Description |
|------|-------------|
| `fixtures.json` | 50 generation tasks: id, task_type, difficulty, description |
| `ground_truth.json` | Reference MCP tool call sequences for each fixture |
| `run_summary.json` | Generated after running the harness (gitignored) |

## Fixture categories

| Difficulty | Count | Description |
|------------|-------|-------------|
| **Easy** | 15 | Single primitives, simple boolean (plate+hole, boss+block) |
| **Medium** | 15 | Multi-hole plates, patterns, brackets, multi-step builds |
| **Hard** | 20 | Complex multi-feature parts, enclosures, manifolds, assemblies |

## Ground truth format

Each fixture's ground truth is a sequence of MCP tool calls using `__N__` index-based sentinels to reference previously created objects. Example:

```
create box → index 0
create cylinder (hole) → index 1
boolean subtract target=__0__ tool_ids=[__1__]
```

Supported sentinels: `__N__` (stack index), `__last_<type>__` (last object of type), `__last__` (most recent object).

## Running

```bash
# All 50 fixtures
python scripts/cadgenbench_harness.py --out dist/cadgenbench

# First 5 only
python scripts/cadgenbench_harness.py --limit 5
```

## Relationship to official CADGenBench

This dataset mirrors the `cadgenbench-data` format (private HF dataset) used by the [CADGenBench leaderboard](https://huggingface.co/spaces/HuggingAI4Engineering/CADGenBench). No HF token or HuggingFace account is required for local use.
