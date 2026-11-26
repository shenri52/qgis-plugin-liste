# -*- coding: utf-8 -*-
"""Traduction des descriptions via le réseau de QGIS (respecte le proxy configuré)."""
import json
from urllib.parse import quote, urlencode

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import QgsBlockingNetworkRequest

from . import core


def decode_translation_payload(raw_content):
    """Décode la réponse JSON de traduction et retourne (texte, langue_source) ou None."""
    try:
        data = json.loads(bytes(raw_content).decode("utf-8"))
        result = "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
        source = data[2] if len(data) > 2 else None
        return (result, source) if result else None
    except Exception as exc:  # noqa: BLE001
        _ = exc
        return None


class Translator:
    """Traduction via le réseau QGIS, avec échecs isolés par description."""
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self):
        self.cache = {}
        self.last_source_language = None

    def __call__(self, text, lang):
        key = (text, lang)
        if key in self.cache:
            result, source = self.cache[key]
            self.last_source_language = source
            return result
        parts = []
        detected_sources = []
        for chunk in core.split_text(text):
            translated = self._request(chunk, lang)
            if not translated:
                return None
            parts.append(translated)
            if self.last_source_language:
                detected_sources.append(self.last_source_language)
        result = " ".join(parts).strip() or None
        source = detected_sources[0] if detected_sources else None
        self.last_source_language = source
        self.cache[key] = (result, source)
        return result

    def _request(self, text, lang):
        self.last_source_language = None
        params = {"client": "gtx", "sl": "auto", "tl": lang, "dt": "t", "q": text}
        url = f"{self.URL}?{urlencode(params, quote_via=quote)}"
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0 (QGIS)")
        no_error = getattr(getattr(QgsBlockingNetworkRequest, "ErrorCode", QgsBlockingNetworkRequest), "NoError")
        for _ in range(2):
            blocking = QgsBlockingNetworkRequest()
            error = blocking.get(request, False)
            if error == no_error:
                decoded = decode_translation_payload(blocking.reply().content())
                if decoded:
                    result, source = decoded
                    self.last_source_language = source
                    return result
        return None
