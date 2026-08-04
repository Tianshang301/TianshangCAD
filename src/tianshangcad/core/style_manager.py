"""Style management (dimension, text, leader, table styles)."""

from __future__ import annotations

from typing import Any

from tianshangcad.utils.errors import StyleError

SUPPORTED_STYLE_TYPES = ("dim", "text", "leader", "table")


class StyleRecord:
    """A named style definition."""

    def __init__(self, name: str, type: str, properties: dict[str, Any] | None = None) -> None:  # noqa: A002
        """Initialize a style record."""
        if not name:
            raise StyleError("Style name cannot be empty", code="invalid_name")
        if type not in SUPPORTED_STYLE_TYPES:
            raise StyleError(
                f"Invalid style type {type!r}; supported: {', '.join(SUPPORTED_STYLE_TYPES)}",
                code="invalid_type",
            )
        self.name = name
        self.type = type
        self.properties: dict[str, Any] = dict(properties or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {"name": self.name, "type": self.type, "properties": dict(self.properties)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleRecord:
        """Reconstruct from a serialized dict."""
        return cls(
            name=str(data["name"]),
            type=str(data["type"]),
            properties=dict(data.get("properties") or {}),
        )

    def __repr__(self) -> str:
        """Return a compact string representation."""
        return f"StyleRecord({self.name}, {self.type})"


class StyleManager:
    """Manages named styles for a document."""

    def __init__(self) -> None:
        """Initialize an empty style manager."""
        self._styles: dict[str, StyleRecord] = {}

    def create(self, name: str, type: str, properties: dict[str, Any] | None = None) -> StyleRecord:  # noqa: A002
        """Create a new style."""
        if name in self._styles:
            raise StyleError(f"Style already exists: {name}", code="style_exists")
        style = StyleRecord(name, type, properties)
        self._styles[name] = style
        return style

    def read(self, name: str) -> StyleRecord:
        """Return a style or raise ``StyleError``."""
        style = self._styles.get(name)
        if style is None:
            raise StyleError(f"Style not found: {name}", code="style_not_found")
        return style

    def update(self, name: str, properties: dict[str, Any]) -> StyleRecord:
        """Replace the properties of a style."""
        style = self.read(name)
        style.properties.update(properties)
        return style

    def delete(self, name: str) -> None:
        """Delete a style."""
        self.read(name)
        del self._styles[name]

    def list(self) -> list[StyleRecord]:
        """Return all styles."""
        return list(self._styles.values())
