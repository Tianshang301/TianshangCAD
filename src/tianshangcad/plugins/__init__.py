"""Official example plugins for TianshangCAD.

These plugins validate the plugin SDK end-to-end: each is a
:class:`~tianshangcad.core.plugins.sdk.CADPlugin` subclass discovered through
the ``tianshangcad.plugins`` entry-point group, registering its own MCP tools
and CLI commands.

- ``gltf`` — bidirectional glTF 2.0 import/export with PBR material mapping.
- ``cam`` — 2.5-axis contour + drilling toolpath generation and G-code export.
"""
