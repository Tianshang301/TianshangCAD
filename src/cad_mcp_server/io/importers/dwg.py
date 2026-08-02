"""DWG importer (via ODA File Converter bridge).

Converts a DWG file to DXF using the ODA File Converter application bridged
by ``ezdxf.addons.odafc`` and reuses the DXF importer to build the document.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from cad_mcp_server.core.document import DocumentState
from cad_mcp_server.io.importers.dxf import DXFImporter
from cad_mcp_server.utils.errors import CADImportError


class DWGImporter:
    """Import DWG files via ODA File Converter."""

    def import_file(self, filepath: str) -> DocumentState:
        """Read a DWG file and build a new document."""
        source = Path(filepath)
        if not source.is_file():
            raise CADImportError(f"File does not exist: {filepath}", code="file_not_found")
        self._check_oda()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                dxf_path = Path(temp_dir) / "import.dxf"
                from ezdxf.addons import odafc

                odafc.convert(source, dxf_path)  # type: ignore[attr-defined]
                return DXFImporter().import_file(str(dxf_path))
        except CADImportError:
            raise
        except Exception as exc:
            raise CADImportError(
                f"Failed to read DWG {filepath}: {exc}", code="read_failed"
            ) from exc

    @staticmethod
    def _check_oda() -> None:
        """Verify the ODA File Converter is available."""
        from ezdxf.addons import odafc

        if not odafc.is_installed():  # type: ignore[attr-defined]
            raise CADImportError(
                "DWG import requires the ODA File Converter; "
                "install it and set the ODAFC_PATH environment variable",
                code="requires_odafc",
            )
