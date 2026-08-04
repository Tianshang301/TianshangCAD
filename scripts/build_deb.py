"""Build a real, self-contained Debian package for tianshangcad.

Unlike the earlier hand-rolled re-pack (which pip-installed dependencies at
install time), this package bundles the project's own wheel together with the
pinned runtime dependency wheels under ``/usr/lib/tianshangcad/site``.
Installing the ``.deb`` needs no network access and no ``postinst`` pip hack.

The two entry points (``/usr/bin/tianshangcad`` and ``/usr/bin/tianshangcad-server``)
are thin wrappers that point ``PYTHONPATH`` at the bundled site directory.

Build on a Linux amd64 host with the target CPython (e.g. Python 3.12 on
Ubuntu 24.04):

    python scripts/build_deb.py

Output: ``dist/tianshangcad_<version>_amd64.deb``
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "tianshangcad"
DIST = ROOT / "dist"
PACKAGE = "tianshangcad"
PREFIX = "/usr/lib/tianshangcad"
SITE = f"{PREFIX}/site"

RUNTIME_DEPENDENCIES = [
    "typer>=0.12",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "numpy>=1.26",
    "ezdxf>=1.3",
    "structlog>=24.1",
    "PyYAML>=6.0",
    "mcp>=2.0",
    "apscheduler[sqlalchemy]>=3.10",
    "matplotlib>=3.8",
    "deepdiff>=7.0",
    "prometheus-client>=0.20",
    "imageio>=2.34",
    "httpx>=0.27",
    "jinja2>=3.1",
]


def _current_version() -> str:
    """Read the package version from ``__init__.py``."""
    text = SRC.joinpath("__init__.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("version not found in __init__.py")


VERSION = _current_version()
MAINTAINER = "Tianshang301 <Tianshang301@outlook.com>"
LICENSE_NAME = "Apache-2.0"
COPYRIGHT = "Copyright 2026 Tianshang301"
DESCRIPTION = (
    "Modern CAD CLI + MCP Server system (2D/3D drawing, editing, measurement, JSON-driven)"
)

CONTROL_TEXT = f"""Package: {PACKAGE}
Version: {VERSION}
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: {MAINTAINER}
Depends: python3 (>= 3.12), libc6 (>= 2.28)
Copyright: {COPYRIGHT}
License: {LICENSE_NAME}
Description: {DESCRIPTION}
 JSON-driven CAD operations via command line (tianshangcad) and an MCP server
 (tianshangcad). Self-contained bundle; no network access required at
 install time.
"""

CLI_WRAPPER = f"""#!/bin/sh
export PYTHONPATH={SITE}
exec python3 -m tianshangcad.cli.main "$@"
"""

SERVER_WRAPPER = f"""#!/bin/sh
export PYTHONPATH={SITE}
exec python3 -m tianshangcad "$@"
"""


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    """Run a subprocess, aborting loudly on failure."""
    # Commands are fixed build steps (pip wheel/download), not user input.
    subprocess.run(cmd, cwd=cwd, check=True)  # noqa: S603 - fixed build commands


def _download_wheels(dest: Path) -> None:
    """Fetch every runtime dependency wheel (binary-only) into ``dest``."""
    _run(
        [
            "python",
            "-m",
            "pip",
            "download",
            "--dest",
            str(dest),
            "--only-binary=:all:",
            *RUNTIME_DEPENDENCIES,
        ]
    )


def _build_own_wheel(dest: Path) -> Path:
    """Build our wheel (no deps) into ``dest`` and return its path."""
    _run(["python", "-m", "pip", "wheel", ".", "--no-deps", "-w", str(dest)], cwd=ROOT)
    matches = list(dest.glob("tianshangcad-*.whl"))
    if not matches:
        raise RuntimeError("wheel build produced no tianshangcad wheel")
    return matches[0]


def _unpack_wheels(wheel_dir: Path, site: Path) -> None:
    """Extract every wheel in ``wheel_dir`` into the bundled site dir."""
    site.mkdir(parents=True, exist_ok=True)
    for wheel in wheel_dir.glob("*.whl"):
        # Wheels come from PyPI for this build; extraction is hermetic.
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(site)  # noqa: S202 - pinned build wheels


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
    """Build ``control.tar.gz`` (control, md5sums)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        _add_tar_file(tar, "./control", CONTROL_TEXT.encode(), 0o644)
        md5_text = "".join(f"{digest}  {path}\n" for path, digest in md5sums).encode()
        _add_tar_file(tar, "./md5sums", md5_text, 0o644)
    return buffer.getvalue()


def _build_data_tar_gz(site: Path) -> tuple[bytes, list[tuple[str, str]]]:
    """Build ``data.tar.gz`` and return it together with md5sums."""
    buffer = io.BytesIO()
    md5sums: list[tuple[str, str]] = []

    def add_bytes(arcname: str, data: bytes, mode: int = 0o644) -> None:
        path = arcname.removeprefix("./")
        digest = hashlib.md5(data).hexdigest()  # noqa: S324 - dpkg md5sums, not security
        md5sums.append((path, digest))
        _add_tar_file(tar, arcname, data, mode)

    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for source in sorted(site.rglob("*")):
            if source.is_file():
                relative = source.relative_to(site).as_posix()
                add_bytes(f".{SITE}/{relative}", source.read_bytes(), 0o644)
        for name in ("LICENSE", "THIRD_PARTY_LICENSES.md"):
            doc = ROOT / name
            if doc.exists():
                add_bytes(
                    f"./usr/share/doc/tianshangcad/{name}",
                    doc.read_bytes(),
                    0o644,
                )
        add_bytes("./usr/bin/tianshangcad", CLI_WRAPPER.encode(), 0o755)
        add_bytes("./usr/bin/tianshangcad-server", SERVER_WRAPPER.encode(), 0o755)
    return buffer.getvalue(), md5sums


def _ar_member(name: str, data: bytes, mtime: int = 0, mode: int = 0o100644) -> bytes:
    """Build a single ``ar`` archive member."""
    header = (f"{name:<16}{mtime:<12}{0:<6}{0:<6}{mode:8o}{len(data):<10}`\n").encode("ascii")
    if len(data) % 2:
        data += b"\n"
    return header + data


def build_deb() -> Path:
    """Download wheels, assemble and write the ``.deb`` file."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wheel_dir = tmp_path / "wheels"
        site = tmp_path / "site"
        wheel_dir.mkdir()
        _build_own_wheel(wheel_dir)
        _download_wheels(wheel_dir)
        _unpack_wheels(wheel_dir, site)

        data_tar, md5sums = _build_data_tar_gz(site)
        control_tar = _build_control_tar_gz(md5sums)

        archive = bytearray(b"!<arch>\n")
        archive += _ar_member("debian-binary", b"2.0\n")
        archive += _ar_member("control.tar.gz", control_tar)
        archive += _ar_member("data.tar.gz", data_tar)

        DIST.mkdir(parents=True, exist_ok=True)
        output = DIST / f"{PACKAGE}_{VERSION}_amd64.deb"
        output.write_bytes(bytes(archive))
        return output


def main() -> None:
    """Build and report the package."""
    output = build_deb()
    print(f"Built {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
