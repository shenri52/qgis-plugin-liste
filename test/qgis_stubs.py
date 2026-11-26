# -*- coding: utf-8 -*-
"""Faux module `qgis` (sans QGIS) pour tester le plugin avec PyQt5 ou PyQt6."""
import importlib
import sys
import types


class FakeSettings:
    store = {}

    def value(self, key, default=None, type=None):  # noqa: A002
        value = self.store.get(key, default)
        if type is not None and value is not None and not isinstance(value, type):
            value = type(value)
        return value

    def setValue(self, key, value):  # noqa: N802
        self.store[key] = value


class FakeApplication:
    profile_dir = "/tmp/fake_profile"

    @staticmethod
    def qgisSettingsDirPath():  # noqa: N802
        return FakeApplication.profile_dir


class FakeReply:
    def __init__(self, payload):
        self._payload = payload

    def content(self):
        return self._payload


class FakeBlockingRequest:
    class ErrorCode:
        NoError = 0
        NetworkError = 1

    payload = b'[[["Bonjour","Hello"]],null,"en"]'
    error = 0
    calls = []

    def get(self, request, _force=False):
        FakeBlockingRequest.calls.append(bytes(request.url().toEncoded()).decode())
        return FakeBlockingRequest.error

    def reply(self):
        return FakeReply(FakeBlockingRequest.payload)


def install(qt="PyQt6"):
    mods = {name: importlib.import_module(f"{qt}.{name}")
            for name in ("QtCore", "QtGui", "QtWidgets", "QtNetwork")}
    if not hasattr(mods["QtGui"], "QAction"):  # PyQt5 : l'équivalent de la couche qgis.PyQt
        mods["QtGui"].QAction = mods["QtWidgets"].QAction
    for name in ("qgis", "qgis.PyQt"):
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    for name, module in mods.items():
        sys.modules[f"qgis.PyQt.{name}"] = module
    core = types.ModuleType("qgis.core")
    core.QgsApplication = FakeApplication
    core.QgsSettings = FakeSettings
    core.QgsBlockingNetworkRequest = FakeBlockingRequest
    sys.modules["qgis.core"] = core
    return mods
