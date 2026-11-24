# -*- coding: utf-8 -*-
"""
Logique « métier » du plugin, en Python pur (aucune dépendance QGIS / Qt).
Pure-Python business logic of the plugin (no QGIS / Qt dependency).

- lecture des metadata.txt des plugins installés
- choix / traduction de la description dans la langue demandée
- génération HTML (style par défaut ou personnalisé) et CSV
"""
import configparser
import csv
import html
import io
import os
import re

# ------------------------------------------------------------------------------
# Langues proposées (code Google Translate, libellé). Code vide = pas de traduction
# ------------------------------------------------------------------------------
LANGUES = [
    ("", "Original (sans traduction)"),
    ("fr", "Français (fr)"),
    ("en", "English (en)"),
    ("es", "Español (es)"),
    ("de", "Deutsch (de)"),
    ("it", "Italiano (it)"),
    ("pt", "Português (pt)"),
    ("nl", "Nederlands (nl)"),
    ("pl", "Polski (pl)"),
    ("ru", "Русский (ru)"),
    ("tr", "Türkçe (tr)"),
    ("ar", "العربية (ar)"),
    ("ja", "日本語 (ja)"),
    ("zh-CN", "中文 简体 (zh-CN)"),
]
DEFAULT_LANG_INDEX = 1  # français

LABELS_FR = {
    "titre": "Liste des plugins QGIS installés",
    "entete_nom": "Extension",
    "entete_description": "Description",
    "sans_description": "Pas de description.",
}
LABELS_EN = {
    "titre": "List of installed QGIS plugins",
    "entete_nom": "Plugin",
    "entete_description": "Description",
    "sans_description": "No description.",
}

# ------------------------------------------------------------------------------
# Style HTML par défaut (= style du script d'origine) et modèles
# ------------------------------------------------------------------------------
DEFAULT_CSS = """\
body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; background: white; }
table { width: 100%; border-collapse: separate; border-spacing: 0 10px; }
th { background-color: #cdebff; color: black; padding: 15px; text-align: left; position: sticky; top: 0; }
tr td {
    padding: 15px;
    border-top: 1px solid #eee; border-bottom: 1px solid #eee;
}
th:first-child { border-radius: 10px 0 0 10px; }
th:last-child { border-radius: 0 10px 10px 0; }
td:first-child { border-left: 1px solid #eee; background-image: linear-gradient(90deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 10px 0 0 10px; }
td:last-child { border-right: 1px solid #eee; background-image: linear-gradient(90deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 0 10px 10px 0; }
tr:hover { background: #ffffff !important; }
tr:hover td { background: transparent !important; border-color: #3498db; }"""

DEFAULT_PAGE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <title>{titre}</title>
    <style>
{css}
    </style>
</head>
<body>
    <table>
        <thead>
            <tr><th width="25%">{entete_nom}</th><th width="75%">{entete_description}</th></tr>
        </thead>
        <tbody>
{lignes}
        </tbody>
    </table>
</body>
</html>
"""

DEFAULT_ROW = """\
            <tr>
                <td><strong>{nom}</strong></td>
                <td class="desc-cell">{description}</td>
            </tr>"""

PAGE_TOKENS = ("lang", "titre", "css", "entete_nom", "entete_description", "lignes")
ROW_TOKENS = ("nom", "description", "version", "auteur", "dossier", "homepage")

_TOKEN = re.compile(r"\{(\w+)\}")


def _fill(template, values):
    """Remplace {balise} en un seul passage (les accolades du CSS restent intactes)."""
    return _TOKEN.sub(lambda m: values.get(m.group(1), m.group(0)), template)


# ------------------------------------------------------------------------------
# Lecture des plugins
# ------------------------------------------------------------------------------
def _clean(text):
    return " ".join((text or "").split())


def _norm(code):
    return code.strip().lower().replace("-", "_")


def _base(code):
    return _norm(code).split("_")[0] if code else ""


def collect_plugins(plugins_dir):
    """
    Lit les metadata.txt du dossier des plugins utilisateur.
    Retourne (liste de plugins triée par nom, liste d'avertissements).
    Les plugins `readonly=true` (plugins cœur) sont ignorés, comme avant.
    """
    plugins, warnings = [], []
    for folder in sorted(os.listdir(plugins_dir), key=str.lower):
        meta = os.path.join(plugins_dir, folder, "metadata.txt")
        if not os.path.isfile(meta):
            continue
        try:
            # interpolation=None : un '%' dans une description ne fait plus planter la lecture
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            with open(meta, encoding="utf-8-sig", errors="replace") as fh:
                parser.read_file(fh)
            if not parser.has_section("general"):
                warnings.append((folder, "section [general] absente"))
                continue
            general = dict(parser.items("general"))
        except Exception as exc:  # noqa: BLE001
            warnings.append((folder, str(exc)))
            continue

        if general.get("readonly", "false").strip().lower() == "true":
            continue

        localized = {}
        for key, value in general.items():
            if key.startswith("description[") and key.endswith("]"):
                localized[_norm(key[len("description["):-1])] = _clean(value)

        plugins.append({
            "dossier": folder,
            "nom": _clean(general.get("name")) or folder,
            "description_defaut": _clean(general.get("description")),
            "localized": localized,
            "version": _clean(general.get("version")),
            "auteur": _clean(general.get("author")),
            "homepage": _clean(general.get("homepage")),
        })
    plugins.sort(key=lambda p: p["nom"].lower())
    return plugins, warnings


def _lookup_localized(localized, lang):
    """Cherche description[xx] pour la langue demandée (xx, xx_YY, ou variante régionale)."""
    norm = _norm(lang)
    base = norm.split("_")[0]
    for key in (norm, base):
        if localized.get(key):
            return localized[key]
    if norm == base:  # langue sans région demandée : accepter fr_FR, pt_BR...
        for key, value in localized.items():
            if key.split("_")[0] == base and value:
                return value
    return None


def split_text(text, limit=1200):
    """Découpe un texte long en morceaux (fin de phrase) pour l'API de traduction."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        while len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:limit])
            sentence = sentence[limit:]
        if current and len(current) + 1 + len(sentence) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def build_labels(lang, translate_fn=None):
    """Titre / en-têtes / texte « sans description » dans la langue de sortie."""
    base = _base(lang)
    if not lang or base == "fr":
        return dict(LABELS_FR)
    if base == "en":
        return dict(LABELS_EN)
    labels = {}
    for key, value in LABELS_EN.items():
        translated = None
        if translate_fn:
            try:
                translated = translate_fn(value, lang)
            except Exception:  # noqa: BLE001
                translated = None
        labels[key] = translated or value
    return labels


def resolve_descriptions(plugins, lang, translate_fn=None, labels=None,
                         is_canceled=None, on_progress=None):
    """
    Renseigne p['description'] pour chaque plugin :
      1. description[<lang>] du metadata.txt si elle existe          -> 'natif'
      2. sinon traduction de `description` (langue source détectée)   -> 'traduit'
      3. si la traduction échoue : texte d'origine                    -> 'echec'
    Langue vide : texte d'origine tel quel ('original').
    Langue « en » : `description` est supposée déjà anglaise (convention QGIS).
    """
    labels = labels or LABELS_FR
    stats = {"natif": 0, "traduit": 0, "original": 0, "echec": 0}
    total = len(plugins)
    for p in plugins:
        p["description"] = p["description_defaut"]
        p["how"] = "original"

    for i, p in enumerate(plugins):
        if is_canceled and is_canceled():
            break
        default = p["description_defaut"]
        text, how = default, "original"
        if lang:
            native = _lookup_localized(p["localized"], lang)
            if native:
                text, how = native, "natif"
            elif default and _base(lang) != "en" and translate_fn:
                try:
                    translated = translate_fn(default, lang)
                except Exception:  # noqa: BLE001
                    translated = None
                if translated:
                    text, how = translated, "traduit"
                else:
                    how = "echec"
        p["description"] = text or labels["sans_description"]
        p["how"] = how
        stats[how] += 1
        if on_progress:
            on_progress(i + 1, total)
    return stats


# ------------------------------------------------------------------------------
# Rendus
# ------------------------------------------------------------------------------
def render_html(plugins, labels, lang, css="", page_tpl="", row_tpl=""):
    """HTML statique : plus aucun JavaScript, la traduction est déjà faite."""
    row_tpl = row_tpl.strip() and row_tpl or DEFAULT_ROW
    page_tpl = page_tpl.strip() and page_tpl or DEFAULT_PAGE

    rows = []
    for p in plugins:
        values = {k: html.escape(p.get(k, "") or "") for k in ROW_TOKENS}
        values["description"] = html.escape(p.get("description", ""))
        rows.append(_fill(row_tpl, values))

    page_values = {
        "lang": html.escape(lang or "fr"),
        "titre": html.escape(labels["titre"]),
        "css": (css.strip() and css.strip()) or DEFAULT_CSS,
        "entete_nom": html.escape(labels["entete_nom"]),
        "entete_description": html.escape(labels["entete_description"]),
        "lignes": "\n".join(rows),
    }
    return _fill(page_tpl, page_values)


def render_csv(plugins, labels, delimiter=";"):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n")
    writer.writerow([labels["entete_nom"], labels["entete_description"]])
    for p in plugins:
        writer.writerow([p["nom"], p.get("description", "")])
    return buffer.getvalue()
