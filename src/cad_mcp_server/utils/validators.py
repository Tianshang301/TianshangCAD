"""Common validation helpers shared by CLI and MCP tooling."""

from collections.abc import Iterable, Sequence

from cad_mcp_server.utils.errors import CADValidationError


def parse_point(text: str, dims: int = 3) -> list[float]:
    """Parse a point string such as ``"1,2,3"`` or ``"1, 2"`` into floats.

    The result is padded with zeros up to ``dims`` dimensions. Values are
    returned in the order x, y, z.
    """
    parts = [part.strip() for part in text.replace(";", ",").split(",")]
    if len(parts) > dims:
        raise CADValidationError(
            f"Point {text!r} has {len(parts)} coordinates, expected at most {dims}",
            code="invalid_point",
        )
    try:
        values = [float(part) for part in parts]
    except ValueError as exc:
        raise CADValidationError(
            f"Invalid numeric point: {text!r}", code="invalid_point"
        ) from exc
    if len(values) < dims:
        values = values + [0.0] * (dims - len(values))
    return values


def parse_point_list(text: str, dims: int = 3) -> list[list[float]]:
    """Parse a space separated list of points, e.g. ``"0,0 10,0 10,10"``."""
    chunks = [chunk for chunk in text.split() if chunk]
    if not chunks:
        raise CADValidationError("Expected at least one point", code="invalid_points")
    return [parse_point(chunk, dims) for chunk in chunks]


def require_positive(value: float, name: str = "value") -> float:
    """Validate that ``value`` is strictly positive."""
    if value <= 0:
        raise CADValidationError(f"{name} must be > 0, got {value}", code="not_positive")
    return value


def require_non_negative(value: float, name: str = "value") -> float:
    """Validate that ``value`` is greater than or equal to zero."""
    if value < 0:
        raise CADValidationError(f"{name} must be >= 0, got {value}", code="negative")
    return value


def ensure_iterable(values: Iterable[float], name: str = "values") -> list[float]:
    """Convert an iterable of numbers to a list of floats."""
    try:
        result = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise CADValidationError(
            f"{name} must be numeric", code="invalid_values"
        ) from exc
    return result


def ensure_list(values: Sequence[float]) -> list[float]:
    """Return ``values`` as a float list."""
    return [float(value) for value in values]
