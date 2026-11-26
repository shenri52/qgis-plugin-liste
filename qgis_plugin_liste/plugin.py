# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtGui import QAction, QIcon

from .dialog import ExportDialog, cleanup_previews
from .i18n import tr


class ListePluginPlugin:
    """Plugin QGIS autonome : entrée dans Extensions et icône de barre d'outils."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.toolbar = None

    def initGui(self):  # noqa: N802
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()
        self.action = QAction(icon, tr("Liste des plugins installés"), self.iface.mainWindow())
        self.action.setObjectName("ListePluginAction")
        self.action.setToolTip(tr("Exporter la liste des plugins installés en HTML ou CSV"))
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(tr("&Liste Plugin"), self.action)
        self.iface.addToolBarIcon(self.action)

    def run(self):
        main_win = self.iface.mainWindow() if self.iface else None
        dialog = ExportDialog(main_win)
        execute = getattr(dialog, "exec", None) or dialog.exec_
        execute()

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(tr("&Liste Plugin"), self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        cleanup_previews()
