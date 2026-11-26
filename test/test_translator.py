# -*- coding: utf-8 -*-
"""Tests du traducteur (réseau QGIS simulé)."""
import pytest

import qgis_stubs

qgis_stubs.install("PyQt6")
from qgis_plugin_liste import translator  # noqa: E402

Fake = qgis_stubs.FakeBlockingRequest


@pytest.fixture(autouse=True)
def reset():
    Fake.calls.clear()
    Fake.error = 0
    Fake.payload = b'[[["Bonjour le monde","Hello world"]],null,"en"]'


def test_decode_payload():
    assert translator.decode_translation_payload(Fake.payload) == ("Bonjour le monde", "en")
    assert translator.decode_translation_payload(b"pas du json") is None
    assert translator.decode_translation_payload(b"[[]]") is None
    assert translator.decode_translation_payload(b'[[["a",null],["b",null]],null,"de"]') == ("ab", "de")


def test_translate_cache_and_source_language():
    tr = translator.Translator()
    assert tr("Hello world", "fr") == "Bonjour le monde"
    assert tr.last_source_language == "en"
    assert tr("Hello world", "fr") == "Bonjour le monde"
    assert len(Fake.calls) == 1, "second appel servi par le cache"
    assert "tl=fr" in Fake.calls[0] and "sl=auto" in Fake.calls[0]


def test_url_is_percent_encoded():
    translator.Translator()("a&b=c+d #e", "fr")
    url = Fake.calls[0]
    assert "q=a%26b%3Dc%2Bd%20%23e" in url


def test_network_error_retries_then_returns_none():
    Fake.error = 1
    assert translator.Translator()("Hello", "fr") is None
    assert len(Fake.calls) == 2, "une nouvelle tentative"


def test_invalid_payload_returns_none():
    Fake.payload = b"<html>captcha</html>"
    assert translator.Translator()("Hello", "fr") is None
