# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .algorithm import ExportPluginsAlgorithm


class ListePluginProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(ExportPluginsAlgorithm())

    def id(self):
        return "listeplugin"

    def name(self):
        return "Liste Plugin"

    def longName(self):
        return self.name()

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
