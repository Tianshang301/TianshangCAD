"""Build a Debian ``.deb`` package for cad-mcp-server without a Linux host.

The ``.deb`` format is an ``ar`` archive containing ``debian-binary``,
``control.tar.gz`` and ``data.tar.gz``.  This script assembles those by
hand so the package can be produced on Windows and installed on any
Debian/Ubuntu host with ``sudo dpkg -i``.

Output: ``dist/cad-mcp-server_<version>_all.deb``
"""

from __future__ import annotations

import hashlib
import io
import os
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "cad_mcp_server"
DIST = ROOT / "dist"
PACKAGE = "cad-mcp-server"


def _current_version() -> str:
    """Read the package version from ``__init__.py``."""
    init = SRC / "__init__.py"
    text = init.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("version not found in __init__.py")


VERSION = _current_version()
MAINTAINER = "Tianshang301 <Tianshang301@outlook.com>"
LICENSE_NAME = "Apache-2.0"
COPYRIGHT = "Copyright 2026 Tianshang301"
DESCRIPTION = (
    "Modern CAD CLI + MCP Server system (2D/3D drawing, editing, "
    "measurement, JSON-driven)"
)
PREFIX = "/usr/lib/cad-mcp-server"

PIP_DEPENDENCIES = "typer pydantic pydantic-settings numpy ezdxf structlog pyyaml mcp"

CONTROL_TEXT = f"""Package: {PACKAGE}
Version: {VERSION}
Section: graphics
Priority: optional
Architecture: all
Maintainer: {MAINTAINER}
Depends: python3 (>= 3.11), python3-pip
Copyright: {COPYRIGHT}
License: {LICENSE_NAME}
Description: {DESCRIPTION}
 JSON-driven CAD operations via command line (cad-cli) and an MCP server
 (cad-mcp-server). Provides file, drawing, editing, measurement, layer and
 batch tools.
"""

POSTINST = f"""#!/bin/sh
set -e
if command -v pip3 >/dev/null 2>&1; then
  pip3 install --break-system-packages --quiet {PIP_DEPENDENCIES} \\
    || pip3 install --quiet {PIP_DEPENDENCIES}
fi
exit 0
"""

CLI_WRAPPER = f"""#!/bin/sh
export PYTHONPATH={PREFIX}/src
exec python3 -m cad_mcp_server.cli.main "$@"
"""

SERVER_WRAPPER = f"""#!/bin/sh
export PYTHONPATH={PREFIX}/src
exec python3 -m cad_mcp_server "$@"
"""


def _source_files() -> list[Path]:
    """Return all package data files under ``src/cad_mcp_server``."""
    files: list[Path] = []
    for root, _dirs, names in os.walk(SRC):
        root_path = Path(root)
        for name in names:
            if (
                name.endswith((".py", ".j2"))
                or name in ("py.typed", "default.yaml", "mcp.json")
            ):
                files.append(root_path / name)
    return sorted(files)


def _add_tar_file(
    archive: tarfile.TarFile,
    arcname: str,
    data: bytes,
    mode: int = 0o644,
) -> None:
    """Add an in-memory file to the tar archive."""
    info = tarfile.TarInfo(arcname)
    info.size = len(data)
    info.mode = mode
    info.mtime = int(time.time())
    info.uid = info.gid = 0
    archive.addfile(info, io.BytesIO(data))


def _build_control_tar_gz(md5sums: list[tuple[str, str]]) -> bytes:
    """Build ``control.tar.gz`` (control, md5sums, postinst)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        _add_tar_file(tar, "./control", CONTROL_TEXT.encode(), 0o644)
        md5_text = "".join(f"{digest}  {path}\n" for path, digest in md5sums).encode()
        _add_tar_file(tar, "./md5sums", md5_text, 0o644)
        _add_tar_file(tar, "./postinst", POSTINST.encode(), 0o755)
    return buffer.getvalue()


def _build_data_tar_gz() -> tuple[bytes, list[tuple[str, str]]]:
    """Build ``data.tar.gz`` and return it together with md5sums."""
    buffer = io.BytesIO()
    md5sums: list[tuple[str, str]] = []

    def add(arcname: str, data: bytes, mode: int = 0o644) -> None:
        path = arcname.removeprefix("./")
        digest = hashlib.md5(data).hexdigest()  # noqa: S324 - dpkg md5sums, not security
        md5sums.append((path, digest))
        _add_tar_file(tar, arcname, data, mode)

    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for source in _source_files():
            relative = source.relative_to(SRC)
            arcname = f"./{PREFIX}/src/cad_mcp_server/{relative.as_posix()}"
            add(arcname, source.read_bytes(), 0o644)
        license_path = ROOT / "LICENSE"
        if license_path.exists():
            add(
                "./usr/share/doc/cad-mcp-server/LICENSE",
                license_path.read_bytes(),
                0o644,
            )
        third_party = ROOT / "THIRD_PARTY_LICENSES.md"
        if third_party.exists():
            add(
                "./usr/share/doc/cad-mcp-server/THIRD_PARTY_LICENSES.md",
                third_party.read_bytes(),
                0o644,
            )
        add("./usr/bin/cad-cli", CLI_WRAPPER.encode(), 0o755)
        add("./usr/bin/cad-mcp-server", SERVER_WRAPPER.encode(), 0o755)
    return buffer.getvalue(), md5sums


def _ar_member(
    name: str, data: bytes, mtime: int = 0, mode: int = 0o100644
) -> bytes:
    """Build a single ``ar`` archive member."""
    header = (
        f"{name:<16}{mtime:<12}{0:<6}{0:<6}{mode:8o}{len(data):<10}`\n"
    ).encode("ascii")
    if len(data) % 2:
        data += b"\n"
    return header + data


def build_deb() -> Path:
    """Assemble the ``.deb`` file and return its path."""
    data_tar, md5sums = _build_data_tar_gz()
    control_tar = _build_control_tar_gz(md5sums)

    archive = bytearray(b"!<arch>\n")
    archive += _ar_member("debian-binary", b"2.0\n")
    archive += _ar_member("control.tar.gz", control_tar)
    archive += _ar_member("data.tar.gz", data_tar)

    DIST.mkdir(parents=True, exist_ok=True)
    output = DIST / f"{PACKAGE}_{VERSION}_all.deb"
    output.write_bytes(bytes(archive))
    return output


def main() -> None:
    """Build and report the package."""
    output = build_deb()
    print(f"Built {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
