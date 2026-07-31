"""STL importer (planned for a later phase)."""

from __future__ import annotations

from cad_mcp_server.utils.errors import CADImportError


class STLImporter:
    """Import STL meshes (planned for a later phase)."""

    def import_file(self, filepath: str) -> None:
        """Import an STL mesh into a document."""
        raise CADImportError("STL import is planned for a later phase", code="unsupported")
