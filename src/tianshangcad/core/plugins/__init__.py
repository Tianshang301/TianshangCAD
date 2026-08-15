"""Plugin SDK and manager for TianshangCAD.

The SDK (``sdk.py``) defines the plugin contract: a
:class:`~tianshangcad.core.plugins.sdk.PluginManifest` declaring a plugin's
identity and permissions, plus the :class:`~tianshangcad.core.plugins.sdk.CADPlugin`
base class with the four extension points and the ``load -> initialize ->
run -> shutdown`` lifecycle.

The manager (``manager.py``) discovers plugins through the
``tianshangcad.plugins`` entry-point group, validates their permission
declarations, drives their lifecycle and aggregates the tools / commands /
kernels / solvers they contribute into the running server and CLI.
"""

from tianshangcad.core.plugins.manager import PluginManager
from tianshangcad.core.plugins.sdk import CADPlugin, PluginManifest, PluginPermission

__all__ = ["CADPlugin", "PluginManager", "PluginManifest", "PluginPermission"]
