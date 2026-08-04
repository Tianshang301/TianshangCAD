# Third-Party Licenses

This project (tianshangcad-server) is licensed under the **Apache License 2.0**.
The following third-party packages are used at runtime and remain under
their own licenses. All licenses below are **permissive** and compatible
with Apache-2.0 distribution.

Generated from the installed runtime dependency closure
(direct `dependencies` in `pyproject.toml`, excluding dev/optional extras).

## Runtime dependencies

| Package | Version | License |
|---------|---------|---------|
| annotated-doc | 0.0.4 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.14.2 | MIT |
| APScheduler | 3.11.3 | MIT |
| attrs | 26.1.0 | MIT |
| cachebox | 5.2.3 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| click | 8.4.2 | BSD-3-Clause |
| colorama | 0.4.6 | BSD-3-Clause |
| contourpy | 1.3.3 | BSD-3-Clause |
| cycler | 0.12.1 | BSD-3-Clause (matplotlib project) |
| deepdiff | 9.1.0 | MIT |
| ezdxf | 1.4.4 | MIT |
| fonttools | 4.63.0 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpcore2 | 2.9.1 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx2 | 2.9.1 | BSD-3-Clause |
| idna | 3.18 | BSD-3-Clause |
| imageio | 2.37.4 | BSD-2-Clause |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| kiwisolver | 1.5.0 | BSD-3-Clause |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| matplotlib | 3.11.1 | matplotlib license (PSF-based, BSD-compatible) |
| mcp | 2.0.0 | MIT |
| mcp-types | 2.0.0 | MIT |
| numpy | 2.5.1 | BSD-3-Clause (with 0BSD/MIT/Zlib/CC0-1.0 components) |
| opentelemetry-api | 1.44.0 | Apache-2.0 |
| orderly-set | 5.5.0 | MIT |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| Pillow | 12.3.0 | MIT-CMU (historical permission notice) |
| prometheus-client | 0.26.0 | Apache-2.0 AND BSD-2-Clause |
| pydantic | 2.13.4 | MIT |
| pydantic-core | 2.46.4 | MIT |
| pydantic-settings | 2.14.2 | MIT |
| PyJWT | 2.13.0 | MIT |
| pyparsing | 3.3.2 | MIT |
| python-dateutil | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause (dual) |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pywin32 | 312 | PSF (Windows only) |
| PyYAML | 6.0.3 | MIT |
| referencing | 0.37.0 | MIT |
| rich | 15.0.0 | MIT |
| rpds-py | 2026.6.3 | MIT |
| shellingham | 1.5.4 | ISC |
| six | 1.17.0 | MIT |
| sse-starlette | 3.4.6 | BSD-3-Clause |
| starlette | 1.3.1 | BSD-3-Clause |
| structlog | 26.1.0 | MIT OR Apache-2.0 |
| truststore | 0.10.4 | MIT |
| typer | 0.27.0 | MIT |
| typing-extensions | 4.15.0 | PSF-2.0 |
| typing-inspection | 0.4.2 | MIT |
| tzdata | 2026.3 | Apache-2.0 |
| tzlocal | 5.4.4 | MIT |
| uvicorn | 0.52.0 | BSD-3-Clause |

## Optional dependencies (not distributed with the package)

These are installed on demand via extras and are **not** bundled in the
wheel, the Windows executables, or the `.deb` package:

| Package | Extra | License | Notes |
|---------|-------|---------|-------|
| cadquery | `occ` | Apache-2.0 | Compatible; used only when `CAD_RUNTIME=ocp` |
| FreeCAD | `freecad` | LGPL-2.1 | System dependency; not packaged as a wheel |

### LGPL obligations (FreeCAD / OCCT backends)

When the optional **FreeCAD** (LGPL-2.1) or **OpenCASCADE** (LGPL-2.1)
backends are enabled, their use is governed by the LGPL. In particular:

- The LGPL library must remain re-linkable; the project code itself is
  still distributed under Apache-2.0.
- A copy of the LGPL license text and copyright notices must accompany
  any LGPL-licensed components that are redistributed.
- Modifications to the LGPL-licensed components (if any) must be
  published under the LGPL.

These backends are optional and disabled by default; the default
`AnalyticKernel` is entirely self-authored and under Apache-2.0.

## Notes

- **certifi (MPL-2.0)**: file-level weak copyleft; MPL-2.0 permits
  combination with Apache-2.0 licensed code provided the MPL notices are
  retained. No source modifications are made to certifi.
- Versions listed reflect the current development environment; exact
  versions at release time are pinned by `pip freeze` in the release build.
