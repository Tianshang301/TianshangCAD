"""Performance gate: 1000-object document operations under 100ms.

Uses ``pytest-benchmark`` when available; otherwise falls back to a plain
timing assertion so the suite stays runnable in any environment.
"""

from __future__ import annotations

import time

from tianshangcad.core.document import DocumentManager
from tianshangcad.core.kernel import get_kernel

OBJECT_COUNT = 1000
LATENCY_BUDGET_MS = 100.0


def _build_document(manager: DocumentManager) -> None:
    manager.create("bench.json")
    doc = manager.get_current()
    for i in range(OBJECT_COUNT):
        doc.entities.create(
            "box",
            {"origin": [i * 2, 0, 0], "dimensions": [1, 1, 1]},
        )


def _bbox_loop(manager: DocumentManager) -> None:
    """Compute the bounding box of all entities (the gated operation)."""
    doc = manager.get_current()
    kernel = get_kernel()
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for record in doc.entities.list():
        bbox = kernel.get_bbox(record.shape)
        for i in range(3):
            minimum[i] = min(minimum[i], bbox["min"][i])
            maximum[i] = max(maximum[i], bbox["max"][i])


class TestPerformanceGate:
    """Latency budget for large-document operations."""

    def test_bbox_latency_budget(self) -> None:
        """1000-object bbox computation must stay under 100ms."""
        manager = DocumentManager()
        _build_document(manager)
        # Warm up.
        _bbox_loop(manager)
        started = time.perf_counter()
        _bbox_loop(manager)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        assert elapsed_ms < LATENCY_BUDGET_MS, (
            f"1000-object bbox took {elapsed_ms:.1f}ms "
            f"(budget {LATENCY_BUDGET_MS:.0f}ms)"
        )

    def test_benchmark_bbox(self, benchmark) -> None:  # type: ignore[no-untyped-def]
        """pytest-benchmark variant (skipped when the plugin is absent)."""
        manager = DocumentManager()
        _build_document(manager)
        result = benchmark(_bbox_loop, manager)
        assert result is None
        # pytest-benchmark provides ``stats`` only when the plugin runs.
        if hasattr(benchmark, "stats") and benchmark.stats is not None:
            assert benchmark.stats["mean"] < LATENCY_BUDGET_MS / 1000.0
