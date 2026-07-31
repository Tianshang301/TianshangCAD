"""Layer management."""

from __future__ import annotations

import re
from typing import Any

from cad_mcp_server.utils.errors import LayerError

_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
_DEFAULT_COLOR = "#FFFFFF"


class LayerRecord:
    """A layer definition."""

    def __init__(
        self,
        name: str,
        color: str = _DEFAULT_COLOR,
        linetype: str = "Continuous",
        linewidth: float = 0.25,
        visible: bool = True,
        locked: bool = False,
    ) -> None:
        """Initialize a layer record."""
        if not name:
            raise LayerError("Layer name cannot be empty", code="invalid_name")
        if not _COLOR_PATTERN.match(color):
            raise LayerError(f"Invalid color {color!r}; expected #RRGGBB", code="invalid_color")
        self.name = name
        self.color = color
        self.linetype = linetype
        self.linewidth = float(linewidth)
        self.visible = visible
        self.locked = locked

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "name": self.name,
            "color": self.color,
            "linetype": self.linetype,
            "linewidth": self.linewidth,
            "visible": self.visible,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LayerRecord:
        """Reconstruct from a serialized dict."""
        return cls(
            name=str(data["name"]),
            color=str(data.get("color", _DEFAULT_COLOR)),
            linetype=str(data.get("linetype", "Continuous")),
            linewidth=float(data.get("linewidth", 0.25)),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
        )

    def __repr__(self) -> str:
        """Return a compact string representation."""
        return f"LayerRecord({self.name})"


class LayerManager:
    """Manages layers for a document. Layer ``0`` always exists."""

    def __init__(self) -> None:
        """Initialize the layer manager with the default layer ``0``."""
        self._layers: dict[str, LayerRecord] = {"0": LayerRecord("0")}
        self._current: str = "0"

    def create(
        self,
        name: str,
        color: str = _DEFAULT_COLOR,
        linetype: str = "Continuous",
        linewidth: float = 0.25,
        visible: bool = True,
        locked: bool = False,
    ) -> LayerRecord:
        """Create a new layer."""
        if name in self._layers:
            raise LayerError(f"Layer already exists: {name}", code="layer_exists")
        layer = LayerRecord(name, color, linetype, linewidth, visible, locked)
        self._layers[name] = layer
        return layer

    def read(self, name: str) -> LayerRecord:
        """Return a layer or raise ``LayerError``."""
        layer = self._layers.get(name)
        if layer is None:
            raise LayerError(f"Layer not found: {name}", code="layer_not_found")
        return layer

    def update(self, name: str, **kwargs: Any) -> LayerRecord:
        """Update layer attributes by keyword (color, linetype, ...)."""
        layer = self.read(name)
        for key, value in kwargs.items():
            if key == "name" and value not in self._layers:
                raise LayerError("Renaming a layer is not supported", code="unsupported")
            if not hasattr(layer, key):
                raise LayerError(f"Unknown layer attribute: {key}", code="unknown_attribute")
            setattr(layer, key, value)
        if "color" in kwargs:
            # Re-validate through constructor logic.
            self._validate_color(layer.color)
        return layer

    @staticmethod
    def _validate_color(color: str) -> None:
        if not _COLOR_PATTERN.match(color):
            raise LayerError(f"Invalid color {color!r}; expected #RRGGBB", code="invalid_color")

    def delete(self, name: str) -> None:
        """Delete a layer (layer ``0`` cannot be deleted)."""
        if name == "0":
            raise LayerError("Layer 0 cannot be deleted", code="protected_layer")
        self.read(name)
        del self._layers[name]
        if self._current == name:
            self._current = "0"

    def list(self) -> list[LayerRecord]:
        """Return all layers."""
        return list(self._layers.values())

    def set_current(self, name: str) -> None:
        """Set the current layer."""
        self.read(name)
        self._current = name

    def get_current(self) -> LayerRecord:
        """Return the current layer."""
        return self._layers[self._current]

    def snapshot(self) -> dict[str, Any]:
        """Return a deep snapshot for undo/redo."""
        return {
            "layers": {name: layer.to_dict() for name, layer in self._layers.items()},
            "current": self._current,
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore from a snapshot produced by :meth:`snapshot`."""
        self._layers = {
            name: LayerRecord.from_dict(data)
            for name, data in snapshot["layers"].items()
        }
        self._current = str(snapshot["current"])
