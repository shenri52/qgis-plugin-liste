# -*- coding: utf-8 -*-
"""Liste Plugin – QGIS plugin autonome (Qt5 / Qt6)."""


def classFactory(iface):  # noqa: N802
    from .plugin import ListePluginPlugin
    return ListePluginPlugin(iface)
