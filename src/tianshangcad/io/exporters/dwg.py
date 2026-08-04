"""DWG exporter (via ODA File Converter bridge).

DWG is a closed proprietary format. The exporter writes a temporary DXF with
the ezdxf-based DXF exporter and converts it to DWG using the ODA File
Converter application bridged by ``ezdxf.addons.odafc``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from tianshangcad.core.document import DocumentState
from tianshangcad.io.exporters.dxf import DXFExporter
from tianshangcad.utils.errors import CADExportError


class DWGExporter:
    """Export a document to a DWG file via ODA File Converter."""

    def export_document(self, doc: DocumentState, filepath: str) -> None:
        """Write ``doc`` to a DWG file."""
        self._check_oda()
        target = Path(filepath).expanduser().absolute()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                dxf_path = Path(temp_dir) / "export.dxf"
                DXFExporter().export_document(doc, str(dxf_path))
                from ezdxf.addons import odafc

                odafc.convert(dxf_path, target, replace=True)  # type: ignore[attr-defined]
        except CADExportError:
            raise
        except Exception as exc:
            raise CADExportError(
                f"Failed to write DWG {filepath}: {exc}", code="write_failed"
            ) from exc

    @staticmethod
    def _check_oda() -> None:
        """Verify the ODA File Converter is available."""
        from ezdxf.addons import odafc

        if not odafc.is_installed():  # type: ignore[attr-defined]
            raise CADExportError(
                "DWG export requires the ODA File Converter; "
                "install it and set ODAFC_PATH (or TIANSHANGCAD_ODAFC_PATH in the "
                "tianshangcad config) to the converter executable",
                code="requires_odafc",
            )
