"""Prometheus metrics for the CAD MCP Server.

Exposes operation duration/count histograms and entity counters in the
Prometheus text format. Tool dispatch in the HTTP transport is instrumented
via :func:`observe_operation`; the metric labels are bounded (``tool_name``
below 50, ``status`` in {success, error}).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

OPERATION_DURATION = Histogram(
    "tianshangcad_operation_duration_seconds",
    "Duration of TianshangCAD MCP tool operations",
    ["tool_name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

OPERATION_COUNT = Counter(
    "tianshangcad_operations_total",
    "Total number of TianshangCAD MCP tool operations",
    ["tool_name", "status"],
)

ENTITY_COUNT = Counter(
    "tianshangcad_entities_total",
    "Total number of TianshangCAD entities created",
    ["entity_type"],
)


def observe_operation(tool_name: str) -> None:
    """Record a successful tool operation."""
    OPERATION_COUNT.labels(tool_name=tool_name, status="success").inc()


def observe_error(tool_name: str) -> None:
    """Record a failed tool operation."""
    OPERATION_COUNT.labels(tool_name=tool_name, status="error").inc()


def observe_entity(entity_type: str) -> None:
    """Record creation of an entity of the given type."""
    ENTITY_COUNT.labels(entity_type=entity_type).inc()


@contextmanager
def track_operation(tool_name: str) -> Iterator[None]:
    """Time and record a tool operation, tagging success or error."""
    started = time.perf_counter()
    try:
        yield
        observe_operation(tool_name)
    except BaseException:
        observe_error(tool_name)
        raise
    finally:
        OPERATION_DURATION.labels(tool_name=tool_name).observe(
            time.perf_counter() - started
        )


def metrics_endpoint(request: object) -> object:
    """Starlette route handler serving the Prometheus text format."""
    from starlette.responses import Response

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
