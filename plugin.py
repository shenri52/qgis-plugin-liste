# -*- coding: utf-8 -*-
from qgis.core import QgsApplication

from .provider import ListePluginProvider


class ListePluginPlugin:
    """Plugin « fournisseur Processing » : l'algorithme apparaît dans la boîte à outils."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):  # noqa: N802
        if self.provider is None:
            self.provider = ListePluginProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):  # noqa: N802
        self.initProcessing()

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
