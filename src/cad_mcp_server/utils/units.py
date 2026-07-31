"""Unit conversion helpers.

All internal geometry is stored in millimetres (mm). Conversion factors
map a unit name to its millimetre equivalent.
"""

from cad_mcp_server.utils.errors import CADValidationError

UNIT_SCALE_MM: dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}

SUPPORTED_UNITS = tuple(UNIT_SCALE_MM.keys())


def validate_unit(unit: str) -> str:
    """Return ``unit`` if supported, otherwise raise ``CADValidationError``."""
    normalized = unit.lower().strip()
    if normalized not in UNIT_SCALE_MM:
        raise CADValidationError(
            f"Unsupported unit {unit!r}. Supported: {', '.join(SUPPORTED_UNITS)}",
            code="invalid_unit",
        )
    return normalized


def to_mm(value: float, unit: str) -> float:
    """Convert ``value`` from ``unit`` to millimetres."""
    return value * UNIT_SCALE_MM[validate_unit(unit)]


def from_mm(value: float, unit: str) -> float:
    """Convert ``value`` from millimetres to ``unit``."""
    return value / UNIT_SCALE_MM[validate_unit(unit)]


def scale_factor(from_unit: str, to_unit: str) -> float:
    """Return the factor to convert a length from ``from_unit`` to ``to_unit``."""
    return UNIT_SCALE_MM[validate_unit(from_unit)] / UNIT_SCALE_MM[validate_unit(to_unit)]
