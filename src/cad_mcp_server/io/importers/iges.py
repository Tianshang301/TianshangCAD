"""IGES importer (planned for the OCCT backend)."""

from __future__ import annotations

from cad_mcp_server.utils.errors import CADImportError


class IGESImporter:
    """Import IGES files (requires the OCCT backend)."""

    def import_file(self, filepath: str) -> None:
        """Import an IGES file into a document."""
        raise CADImportError(
            "IGES import requires the OCCT backend (pip install -e '.[occ]')",
            code="requires_occ",
        )
