"""STEP exporter (requires the OCCT backend)."""

from __future__ import annotations

from cad_mcp_server.core.document import DocumentState
from cad_mcp_server.utils.errors import CADExportError


class STEPExporter:
    """Export a document to a STEP file.

    STEP export requires the optional OCCT backend
    (``pip install -e '.[occ]'``). The analytic kernel does not support
    BREP serialization.
    """

    def export_document(self, doc: DocumentState, filepath: str) -> None:
        """Export a document to a STEP file."""
        raise CADExportError(
            "STEP export requires the OCCT backend (pip install -e '.[occ]')",
            code="requires_occ",
        )
