# -*- coding: utf-8 -*-
"""Tests de la logique du plugin (sans QGIS) : pytest tests/"""
import ast
import os
import re
from html.parser import HTMLParser

import pytest

from qgis_plugin_liste import core, i18n

PLUGIN_DIR = os.path.dirname(core.__file__)


def write_plugin(root, folder, content):
    path = root / folder
    path.mkdir()
    (path / "metadata.txt").write_text(content, encoding="utf-8")


def plugin(name="P", description="Hello the world and the data", **extra):
    data = {"nom": name, "description_defaut": description, "localized": {}, "version": "1.0",
            "auteur": "Bob", "dossier": name.lower(), "homepage": "https://example.org",
            "description": description}
    data.update(extra)
    return data


# ---------------------------------------------------------------- lecture
def test_collect_plugins(tmp_path):
    write_plugin(tmp_path, "a", "[general]\nname=Alpha\ndescription=100% <b>great</b>\n"
                                "description[fr]=Très bien\nversion=1.2\nauthor=Bob\n")
    write_plugin(tmp_path, "core", "[general]\nname=Core\nreadonly=true\ndescription=x\n")
    write_plugin(tmp_path, "bad", "pas de section\n")
    write_plugin(tmp_path, "nom", "[general]\ndescription=sans nom\n")
    (tmp_path / "vide").mkdir()
    plugins, warnings = core.collect_plugins(str(tmp_path))
    assert [p["nom"] for p in plugins] == ["Alpha", "nom"]
    assert plugins[0]["localized"] == {"fr": "Très bien"}
    assert plugins[0]["description_defaut"].startswith("100%")
    assert [w[0] for w in warnings] == ["bad"]


def test_collect_plugins_missing_dir():
    assert core.collect_plugins("/nope/nope") == ([], [])


# ---------------------------------------------------------------- descriptions
def test_resolve_descriptions_native_translated_failed():
    plugins = [
        plugin("A", "English text of the plugin and the data", localized={"fr": "Texte français"}),
        plugin("B", "English text of the plugin and the data"),
        plugin("C", "English text of the plugin and the data"),
    ]

    def translate(text, lang):
        return None if plugins[2]["nom"] == "C" and lang == "xx" else f"[{lang}] {text}"

    stats = core.resolve_descriptions(plugins, "fr", translate, core.LABELS_FR)
    assert plugins[0]["description"] == "Texte français" and plugins[0]["how"] == "natif"
    assert plugins[1]["how"] == "traduit" and plugins[1]["description"].startswith("[fr]")
    assert stats["natif"] == 1 and stats["traduit"] == 2

    failing = [plugin("D", "English text")]
    stats = core.resolve_descriptions(failing, "fr", lambda t, l: None, core.LABELS_FR)
    assert failing[0]["how"] == "echec" and stats["echec"] == 1


def test_resolve_descriptions_english_and_original_never_translate():
    called = []
    plugins = [plugin("A", "English text")]
    core.resolve_descriptions(plugins, "en", lambda t, l: called.append(t), core.LABELS_EN)
    core.resolve_descriptions(plugins, "", lambda t, l: called.append(t), core.LABELS_FR)
    assert called == []


def test_resolve_descriptions_empty_uses_placeholder_and_cancel():
    plugins = [plugin("A", ""), plugin("B", "x")]
    core.resolve_descriptions(plugins, "", None, core.LABELS_FR)
    assert plugins[0]["description"] == core.LABELS_FR["sans_description"]
    plugins = [plugin("A"), plugin("B")]
    seen = []
    core.resolve_descriptions(plugins, "fr", lambda t, l: "x", core.LABELS_FR,
                              is_canceled=lambda: bool(seen), on_progress=lambda i, t: seen.append(i))
    assert seen == [1]


def test_regional_variants():
    plugins = [plugin("A", "x", localized={"pt_br": "Olá"})]
    core.resolve_descriptions(plugins, "pt-BR", None, core.LABELS_FR)
    assert plugins[0]["description"] == "Olá"
    plugins = [plugin("A", "x", localized={"fr_fr": "Salut"})]
    core.resolve_descriptions(plugins, "fr", None, core.LABELS_FR)
    assert plugins[0]["description"] == "Salut"


def test_build_labels_translates_only_requested_keys():
    asked = []

    def translate(text, lang):
        asked.append(text)
        return "T:" + text

    labels = core.build_labels("sv", translate)
    assert sorted(asked) == sorted(core.LABELS_EN[k] for k in core.BASE_LABEL_KEYS)
    assert labels["entete_version"] == core.LABELS_EN["entete_version"]
    asked.clear()
    labels = core.build_labels("sv", translate, {"entete_auteur"})
    assert labels["entete_auteur"] == "T:Author"
    assert core.build_labels("fr") == core.LABELS_FR and core.build_labels("en") == core.LABELS_EN
    assert core.build_labels("", None) == core.LABELS_FR


def test_split_text():
    chunks = core.split_text("Phrase. " * 300, 1200)
    assert all(len(c) <= 1200 for c in chunks) and len(chunks) >= 2
    assert core.split_text("court") == ["court"]


# ---------------------------------------------------------------- modèles HTML
@pytest.mark.parametrize("key", [m[0] for m in core.MODELS])
def test_bundled_models_render(key):
    text = core.load_model(key)
    html_out = core.render_html(core.sample_plugins(True), core.LABELS_FR, "fr", text, today="2026-01-01")
    assert html_out.startswith("<!DOCTYPE html>") and 'lang="fr"' in html_out
    assert "Exemple de plugin A" in html_out and "Exemple de plugin C" in html_out
    assert "{{" not in html_out, "balise non remplacée"
    assert "<script" not in html_out.lower()
    assert not re.search(r"(src|href)\s*=\s*[\"']https?:", html_out, re.I)
    assert "@import" not in html_out and "url(http" not in html_out.lower()
    # structure HTML équilibrée pour les balises de structure
    parser = _TagCounter()
    parser.feed(html_out)
    for tag in ("html", "head", "body", "table", "tbody", "main", "article", "style"):
        assert parser.opened.get(tag, 0) == parser.closed.get(tag, 0), tag


class _TagCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.opened, self.closed = {}, {}

    def handle_starttag(self, tag, attrs):
        self.opened[tag] = self.opened.get(tag, 0) + 1

    def handle_endtag(self, tag):
        self.closed[tag] = self.closed.get(tag, 0) + 1


def test_render_escapes_values_and_does_not_reexpand():
    evil = plugin("<img src=x onerror=alert(1)>", "{{titre}} <script>alert(1)</script> & \"q\"",
                  homepage="javascript:alert(1)", auteur="{{nom}}")
    text = "<html><head></head><body><!-- LIGNE --><p>{{nom}}|{{description}}|{{homepage}}|{{auteur}}</p><!-- /LIGNE --></body></html>"
    out = core.render_html([evil], core.LABELS_FR, "fr", text)
    assert "<script" not in out and "<img" not in out
    assert "&lt;script&gt;" in out and "&amp;" in out
    assert "{{titre}}" in out  # contenu inséré tel quel, jamais réinterprété
    assert "javascript:" not in out
    assert "||{{nom}}</p>" in out  # homepage dangereuse vidée, auteur inséré tel quel


def test_homepage_http_kept():
    text = "<html><head></head><body><!-- LIGNE -->{{homepage}}<!-- /LIGNE --></body></html>"
    assert "https://example.org/a?b=1&amp;c=2" in core.render_html(
        [plugin(homepage="https://example.org/a?b=1&c=2")], core.LABELS_FR, "fr", text)


def test_render_page_values_and_numbering():
    text = ("<html lang=\"{{lang}}\"><head><title>{{titre}}</title></head><body>{{nombre}}|{{date}}|{{entete_nom}}"
            "<!-- ROW -->[{{numero}}:{{nom}}]<!-- /ROW --></body></html>")
    out = core.render_html([plugin("A"), plugin("B")], core.LABELS_EN, "en", text, today="2026-02-03")
    assert "2|2026-02-03|Plugin[1:A][2:B]" in out and 'lang="en"' in out
    assert "<title>List of installed QGIS plugins</title>" in out


def test_legacy_single_brace_and_lignes_token():
    legacy = "<html><head></head><body>{lignes}</body></html>"
    out = core.render_html([plugin("A", "desc A")], core.LABELS_FR, "fr", legacy)
    assert "<strong>A</strong>" in out and "desc A" in out
    old_block = "<html><head></head><body><!-- LIGNE --><i>{nom}</i><!-- /LIGNE --></body></html>"
    assert "<i>A</i>" in core.render_html([plugin("A")], core.LABELS_FR, "fr", old_block)


def test_template_without_markers_is_rejected():
    with pytest.raises(core.TemplateError) as err:
        core.parse_template("<html><body>rien</body></html>")
    assert err.value.key == "err_tpl_invalid"


def test_extra_css_injection():
    text = core.load_model("defaut")
    out = core.render_html([plugin()], core.LABELS_FR, "fr", text, "body{color:red}")
    assert out.index("body{color:red}") < out.index("</head>")
    assert out.count("<style>") == 2
    no_head = "<table><!-- LIGNE --><tr><td>{{nom}}</td></tr><!-- /LIGNE --></table>"
    assert core.render_html([plugin()], core.LABELS_FR, "fr", no_head, "a{b:c}").startswith("<style>")
    assert core.check_css("a{b:c}") is None and core.check_css("</style><script>") == "err_css"


def test_read_template_file(tmp_path):
    good = tmp_path / "m.html"
    good.write_text(core.load_model("sobre"), encoding="utf-8")
    assert "LIGNE" in core.read_template_file(str(good))
    for name, key in (("m.txt", "err_tpl_ext"), ("absent.html", "err_tpl_missing")):
        path = tmp_path / name
        if name == "m.txt":
            path.write_text("x")
        with pytest.raises(core.TemplateError) as err:
            core.read_template_file(str(path))
        assert err.value.key == key
    big = tmp_path / "big.html"
    big.write_text("<!-- LIGNE -->" + "x" * (core.MAX_TEMPLATE_BYTES + 1), encoding="utf-8")
    with pytest.raises(core.TemplateError) as err:
        core.read_template_file(str(big))
    assert err.value.key == "err_tpl_size"
    invalid = tmp_path / "inv.html"
    invalid.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(core.TemplateError):
        core.read_template_file(str(invalid))
    with pytest.raises(core.TemplateError):
        core.model_path("inconnu")


def test_template_label_keys():
    all_keys = {"entete_version", "entete_auteur", "entete_dossier", "entete_homepage"}
    assert core.template_label_keys(core.load_model("etat")) == all_keys
    assert core.template_label_keys(core.load_model("etat"), ["nom", "auteur"]) == {"entete_auteur"}
    assert "entete_version" in core.template_label_keys(core.load_model("sobre"))
    assert core.template_label_keys(core.load_model("sobre"), ["nom", "description"]) == {
        "entete_nom", "entete_description"}


# ---------------------------------------------------------------- sélection des champs
FIELD_TEXTS = {"nom": "Exemple de plugin A", "description": "Description courte du premier",
               "version": "1.0.0", "auteur": "Auteur", "dossier": "exemple_0", "homepage": "example.org"}


@pytest.mark.parametrize("key", [m[0] for m in core.MODELS])
def test_models_follow_selected_fields(key):
    text = core.load_model(key)
    samples = core.sample_plugins(True)
    everything = core.render_html(samples, core.LABELS_FR, "fr", text, today="2026-01-01")
    for field, sample in FIELD_TEXTS.items():
        assert sample in everything, (key, field)
    for chosen in (["nom", "version"], ["description"], ["nom", "auteur", "homepage"], ["dossier"]):
        out = core.render_html(samples, core.LABELS_FR, "fr", text, today="2026-01-01", fields=chosen)
        assert "{{" not in out and "CHAMP" not in out.split("</style>")[-1]
        for field, sample in FIELD_TEXTS.items():
            if field in chosen:
                assert sample in out, (key, chosen, field)
            else:
                assert sample not in out, (key, chosen, field)
        # libellés : seuls ceux des champs choisis subsistent dans le corps de la page
        body = out.split("<body>")[-1]
        for field, label_key in core.COLUMN_LABEL_KEY.items():
            label = core.LABELS_FR[label_key]
            if field in chosen:
                continue
            assert f">{label}<" not in body and f"{label} " not in body.replace("<span>", ""), (key, chosen, field)


def test_table_models_have_one_column_per_selected_field():
    for key in ("defaut", "sobre", "sombre"):
        text = core.load_model(key)
        everything = core.render_html(core.sample_plugins(True), core.LABELS_FR, "fr", text)
        assert len(re.findall(r"<th[ >]", everything)) == 6
        out = core.render_html(core.sample_plugins(True), core.LABELS_FR, "fr", text, fields=["nom", "dossier"])
        assert len(re.findall(r"<th[ >]", out)) == 2 and len(re.findall(r"<td[ >]", out)) == 6


def test_unselected_tokens_are_blank_in_templates_without_markers():
    text = "<html><head></head><body><!-- LIGNE -->[{{nom}}|{{version}}|{{entete_version}}]<!-- /LIGNE --></body></html>"
    out = core.render_html([plugin("A")], core.LABELS_FR, "fr", text, fields=["nom"])
    assert "[A||]" in out
    assert "[A|1.0|Version]" in core.render_html([plugin("A")], core.LABELS_FR, "fr", text)


def test_apply_fields_rules():
    text = "a<!-- CHAMP version -->V<!-- /CHAMP -->b<!-- field NOM -->N<!-- /field -->c<!-- CHAMP inconnu -->U<!-- /CHAMP -->"
    assert core.apply_fields(text, ["nom"]) == "abNcU"
    assert core.apply_fields(text, []) == "abcU"
    assert core.apply_fields(text) == "aVbNcU"
    multi = "x\n<!-- CHAMP auteur -->\n  <p>{{auteur}}</p>\n<!-- /CHAMP -->\ny\n"
    assert core.apply_fields(multi, []) == "x\ny\n"
    assert core.apply_fields(multi, ["auteur"]) == "x\n  <p>{{auteur}}</p>\ny\n"


def test_labels_for_unselected_fields_are_not_needed_for_translation():
    asked = []
    core.build_labels("sv", lambda text, lang: asked.append(text) or text,
                      core.template_label_keys(core.load_model("sobre"), ["nom", "description"]))
    assert "Version" not in asked and "Author" not in asked


# ---------------------------------------------------------------- modèles de l'utilisateur
def test_user_models_lifecycle(tmp_path):
    directory = str(tmp_path / "modeles")
    assert core.user_models(directory) == []
    key, path = core.save_user_model(directory, "Mon style", core.NEW_MODEL_TEXT)
    assert key == "user:Mon style.html" and os.path.isfile(path)
    assert core.is_user_model(key) and not core.is_user_model("defaut")
    assert [(k, n) for k, n, _p in core.user_models(directory)] == [(key, "Mon style")]
    assert core.load_model_any(key, directory) == core.NEW_MODEL_TEXT
    assert core.load_model_any("defaut", directory) == core.load_model("defaut")
    out = core.render_html([plugin("A")], core.LABELS_FR, "fr", core.load_model_any(key, directory), fields=["nom"])
    assert "<td>A</td>" in out and "<th>Extension</th>" in out and "Description" not in out.split("<body>")[-1]
    core.delete_user_model(directory, key)
    assert core.user_models(directory) == []
    with pytest.raises(core.TemplateError):
        core.delete_user_model(directory, key)


def test_user_models_reject_bad_input(tmp_path):
    directory = str(tmp_path)
    with pytest.raises(core.TemplateError) as err:
        core.save_user_model(directory, "x", "<html>pas de marqueurs</html>")
    assert err.value.key == "err_tpl_invalid"
    with pytest.raises(core.TemplateError) as err:
        core.save_user_model(directory, "///", core.NEW_MODEL_TEXT)
    assert err.value.key == "err_tpl_name"
    with pytest.raises(core.TemplateError) as err:
        core.save_user_model(directory, "gros", "<!-- LIGNE --><!-- /LIGNE -->" + "x" * (core.MAX_TEMPLATE_BYTES + 1))
    assert err.value.key == "err_tpl_size"
    for bad in ("user:../secret.html", "user:", "user:a/b.html", "user:..\\x.html"):
        with pytest.raises(core.TemplateError):
            core.load_model_any(bad, directory)
        with pytest.raises(core.TemplateError):
            core.delete_user_model(directory, bad)
    assert os.listdir(directory) == []


def test_safe_filename_and_unique_filename(tmp_path):
    assert core.safe_filename("Mon modèle (v2)") == "Mon modèle (v2).html"
    assert core.safe_filename("../../etc/passwd") == "passwd.html"
    assert core.safe_filename("a\\b\\c.html") == "c.html"
    assert core.safe_filename("<>:\"|?*") is None and core.safe_filename("  ") is None and core.safe_filename(None) is None
    assert core.safe_filename("CON") == "CON_.html"
    assert len(core.safe_filename("x" * 300)) == 85
    (tmp_path / "a.html").write_text("x")
    (tmp_path / "a (2).html").write_text("x")
    assert core.unique_filename(str(tmp_path), "a.html") == "a (3).html"
    assert core.unique_filename(str(tmp_path), "b.html") == "b.html"


def test_import_model(tmp_path):
    source = tmp_path / "source.html"
    source.write_text(core.load_model("sobre"), encoding="utf-8")
    directory = str(tmp_path / "profil" / "modeles")
    key, path = core.import_model(str(source), directory)
    key2, _path2 = core.import_model(str(source), directory)
    assert key == "user:source.html" and key2 == "user:source (2).html"
    assert open(path, encoding="utf-8").read() == core.load_model("sobre")
    bad = tmp_path / "bad.html"
    bad.write_text("<html></html>")
    with pytest.raises(core.TemplateError):
        core.import_model(str(bad), directory)
    with pytest.raises(core.TemplateError):
        core.import_model(str(tmp_path / "x.txt"), directory)


def test_new_model_text_is_a_valid_template():
    assert core.parse_template(core.NEW_MODEL_TEXT)[1] is not None
    out = core.render_html(core.sample_plugins(False), core.LABELS_EN, "en", core.NEW_MODEL_TEXT)
    assert "{{" not in out and "Sample plugin" not in out and "Exemple de plugin A" in out


# ---------------------------------------------------------------- CSV
def test_csv_columns_separator_and_bom_free_content():
    data = [plugin("A", "desc; avec point-virgule", version="2.0")]
    out = core.render_csv(data, core.LABELS_FR, ";", ("nom", "version"))
    assert out == "Extension;Version\r\nA;2.0\r\n"
    out = core.render_csv(data, core.LABELS_EN, "\t", core.CSV_COLUMNS)
    assert out.splitlines()[0].split("\t") == ["Plugin", "Description", "Version", "Author", "Folder", "Website"]
    assert core.render_csv(data, core.LABELS_FR, ";", ()).startswith("Extension;Description")


def test_csv_formula_neutralisation():
    data = [plugin("=cmd|' /C calc'!A0", "+1", auteur="@SUM(1)", version="-2")]
    out = core.render_csv(data, core.LABELS_FR, ";", core.CSV_COLUMNS)
    row = out.splitlines()[1]
    assert not any(cell[:1] in "=+-@" for cell in row.split(";") if cell)


# ---------------------------------------------------------------- options
def test_options_and_extensions():
    assert core.check_options("sv", ";") is None and core.check_options("pt-BR", "\\t") is None
    assert core.check_options("x1234", ";") == "err_lang"
    assert core.check_options("fr", ";;") == "err_sep"
    assert core.normalize_separator("\\t") == "\t" and core.normalize_separator("") == ";"
    assert core.fix_extension("/a/b.html", True) == "/a/b.csv"
    assert core.fix_extension("/a/b.csv", False) == "/a/b.html"
    assert core.fix_extension("/a/b", True) == "/a/b.csv"
    assert core.fix_extension("/a/b.htm", False) == "/a/b.htm"
    assert core.fix_extension("/a/b.txt", False) == "/a/b.txt.html"


# ---------------------------------------------------------------- i18n
def _literals(filename):
    tree = ast.parse(open(os.path.join(PLUGIN_DIR, filename), encoding="utf-8").read())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "tr" and node.args:
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.append(node.args[0].value)
            elif isinstance(node.args[0], ast.Name):
                continue
    return found


@pytest.mark.parametrize("filename", ["dialog.py", "plugin.py"])
def test_every_ui_string_has_an_english_version(filename):
    literals = _literals(filename)
    assert literals
    missing = [s for s in literals if s not in i18n.EN]
    assert not missing, missing


def test_language_names_and_model_names_are_translatable():
    for _code, label in core.LANGUES:
        assert i18n.tr(label, True) == label
    for _key, _file, label in core.MODELS:
        assert label in i18n.EN
    for text in i18n.EN:
        assert i18n.tr(text, True) == text and i18n.tr(text, False) == i18n.EN[text]


def test_english_strings_keep_format_placeholders():
    for fr_text, en_text in i18n.EN.items():
        assert sorted(re.findall(r"\{\w+\}", fr_text)) == sorted(re.findall(r"\{\w+\}", en_text)), fr_text


# ---------------------------------------------------------------- hygiène du paquet
def test_package_hygiene():
    banned = re.compile(r"(?<![\w.])(eval|exec|compile|__import__|pickle|marshal|subprocess|os\.system|os\.popen|input)\s*\(")
    for name in os.listdir(PLUGIN_DIR):
        if name.endswith(".py"):
            source = open(os.path.join(PLUGIN_DIR, name), encoding="utf-8").read()
            assert not banned.search(source), name
            assert "# nosec" not in source, name
            assert "http://" not in source, name
    meta = open(os.path.join(PLUGIN_DIR, "metadata.txt"), encoding="utf-8").read()
    assert "supportsQt6" not in meta
    assert re.search(r"^qgisMaximumVersion=3\.99$", meta, re.M)


def test_label_sets_are_complete_and_subtitle_is_labelled():
    assert set(core.LABELS_FR) == set(core.LABELS_EN) and set(core.BASE_LABEL_KEYS) <= set(core.LABELS_FR)
    out = core.render_html(core.sample_plugins(True), core.LABELS_FR, "fr", core.load_model("etat"), today="2026-01-01")
    assert "3 extension(s) - 2026-01-01" in out
    out = core.render_html(core.sample_plugins(False), core.LABELS_EN, "en", core.load_model("sobre"), today="2026-01-01")
    assert "3 plugin(s) - 2026-01-01" in out
