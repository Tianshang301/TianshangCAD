"""STEP importer (planned for the OCCT backend)."""

from __future__ import annotations

from cad_mcp_server.utils.errors import CADImportError


class STEPImporter:
    """Import STEP files (requires the OCCT backend)."""

    def import_file(self, filepath: str) -> None:
        """Import a STEP file into a document."""
        raise CADImportError(
            "STEP import requires the OCCT backend (pip install -e '.[occ]')",
            code="requires_occ",
        )
