"""3D view definition management."""

from __future__ import annotations

import uuid
from typing import Any

from tianshangcad.schemas.view3d import (
    View3DDefinition,
    named_view,
)
from tianshangcad.utils.errors import ViewError


def new_view_id() -> str:
    """Generate a unique view id."""
    return f"view_{uuid.uuid4().hex[:8]}"


class ViewManager:
    """Manages named 3D views for a single document."""

    def __init__(self) -> None:
        """Initialize an empty view manager."""
        self._views: dict[str, View3DDefinition] = {}

    def create(
        self,
        name: str,
        definition: View3DDefinition | None = None,
        view_id: str | None = None,
    ) -> str:
        """Create a view definition and return its id."""
        if not name:
            raise ViewError("View name cannot be empty", code="invalid_name")
        if self.get_by_name(name) is not None:
            raise ViewError(f"View already exists: {name}", code="duplicate_name")
        view = definition or named_view(name)
        if definition is not None and definition.name != name:
            view = definition.model_copy(update={"name": name})
        target_id = view_id or new_view_id()
        view = view.model_copy(update={"view_id": target_id})
        self._views[target_id] = view
        return target_id

    def get(self, view_id: str) -> View3DDefinition:
        """Return the view with ``view_id`` or raise ``ViewError``."""
        view = self._views.get(view_id)
        if view is None:
            raise ViewError(f"View not found: {view_id}", code="view_not_found")
        return view

    def get_by_name(self, name: str) -> View3DDefinition | None:
        """Return the view with the given name, or ``None``."""
        for view in self._views.values():
            if view.name == name:
                return view
        return None

    def update(
        self,
        view_id: str,
        **changes: Any,
    ) -> View3DDefinition:
        """Update fields of a view definition."""
        current = self.get(view_id)
        name = changes.pop("name", None)
        if name is not None and name != current.name and self.get_by_name(name) is not None:
            raise ViewError(f"View already exists: {name}", code="duplicate_name")
        data = current.model_dump(exclude_unset=False)
        data.update(changes)
        updated = View3DDefinition.model_validate(data)
        if name is not None:
            updated = updated.model_copy(update={"name": name})
        self._views[view_id] = updated
        return updated

    def delete(self, view_id: str) -> None:
        """Delete a view definition."""
        self.get(view_id)
        del self._views[view_id]

    def list(self) -> list[View3DDefinition]:
        """List all view definitions in creation order."""
        return list(self._views.values())

    def count(self) -> int:
        """Return the number of view definitions."""
        return len(self._views)

    def snapshot(self) -> dict[str, Any]:
        """Return a deep snapshot of view definitions."""
        return {view_id: view.to_dict() for view_id, view in self._views.items()}

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore view definitions from a snapshot dict."""
        self._views = {
            view_id: View3DDefinition.model_validate(data)
            for view_id, data in snapshot.items()
        }
