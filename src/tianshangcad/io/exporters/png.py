"""PNG exporter (planned for Phase 4+)."""

from __future__ import annotations

from tianshangcad.utils.errors import CADExportError


class PNGExporter:
    """Export a drawing to PNG (planned for Phase 4)."""

    def export_document(self, doc: object, filepath: str) -> None:
        """Export a document to a PNG file."""
        raise CADExportError("PNG export is planned for Phase 4", code="unsupported")
