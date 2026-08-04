"""PDF exporter (planned for Phase 4+)."""

from __future__ import annotations

from tianshangcad.utils.errors import CADExportError


class PDFExporter:
    """Export a drawing to PDF (planned for Phase 4)."""

    def export_document(self, doc: object, filepath: str) -> None:
        """Export a document to a PDF file."""
        raise CADExportError("PDF export is planned for Phase 4", code="unsupported")
