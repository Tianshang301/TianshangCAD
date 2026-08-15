# -*- mode: python ; coding: utf-8 -*-
"""Portable PyInstaller spec for ``tianshangcad``.

Resolves all paths relative to the repository root so the same spec works
locally and in GitHub Actions. Invoke with::

    pyinstaller --noconfirm --distpath dist/exe packaging/tianshangcad.spec
"""

from pathlib import Path

_ROOT = Path(SPECPATH).resolve().parent
_SRC = _ROOT / "src"
_PKG = _SRC / "tianshangcad"

a = Analysis(
    [str(_ROOT / "packaging" / "entry_cli.py")],
    pathex=[str(_SRC)],
    binaries=[],
    datas=[
        (str(_PKG / "templates"), "tianshangcad/templates"),
        (str(_PKG / "config"), "tianshangcad/config"),
        (str(_PKG / "py.typed"), "tianshangcad"),
    ],
    hiddenimports=[
        "tianshangcad.plugins.gltf.plugin",
        "tianshangcad.plugins.cam.plugin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="tianshangcad",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
