# -*- coding: utf-8 -*-
"""Liste Plugin – QGIS plugin (Qt5 / Qt6)."""


def classFactory(iface):  # noqa: N802 (nom imposé par QGIS)
    from .plugin import ListePluginPlugin
    return ListePluginPlugin(iface)
