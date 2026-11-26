# -*- coding: utf-8 -*-
"""
Logique « métier » du plugin, en Python pur (aucune dépendance QGIS / Qt).
Pure-Python business logic of the plugin (no QGIS / Qt dependency).

- lecture des metadata.txt des plugins installés
- choix / traduction de la description dans la langue demandée
- génération HTML à partir d'un modèle (fichier .html) et génération CSV
"""
import configparser
import csv
import datetime
import html
import io
import os
import re
from urllib.parse import urlsplit

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
    "entete_version": "Version",
    "entete_auteur": "Auteur",
    "entete_dossier": "Dossier",
    "entete_homepage": "Site web",
    "libelle_nombre": "extension(s)",
    "sans_description": "Pas de description.",
}
LABELS_EN = {
    "titre": "List of installed QGIS plugins",
    "entete_nom": "Plugin",
    "entete_description": "Description",
    "entete_version": "Version",
    "entete_auteur": "Author",
    "entete_dossier": "Folder",
    "entete_homepage": "Website",
    "libelle_nombre": "plugin(s)",
    "sans_description": "No description.",
}
# Étiquettes toujours traduites ; les autres (version, auteur...) seulement si utilisées
BASE_LABEL_KEYS = ("titre", "entete_nom", "entete_description", "libelle_nombre", "sans_description")

# ------------------------------------------------------------------------------
# Colonnes (CSV) et balises (HTML)
# ------------------------------------------------------------------------------
CSV_COLUMNS = ("nom", "description", "version", "auteur", "dossier", "homepage")
DEFAULT_CSV_COLUMNS = ("nom", "description")
COLUMN_LABEL_KEY = {
    "nom": "entete_nom",
    "description": "entete_description",
    "version": "entete_version",
    "auteur": "entete_auteur",
    "dossier": "entete_dossier",
    "homepage": "entete_homepage",
}
PAGE_TOKENS = ("lang", "titre", "nombre", "libelle_nombre", "date") + tuple(COLUMN_LABEL_KEY.values())
ROW_TOKENS = ("numero",) + CSV_COLUMNS

# ------------------------------------------------------------------------------
# Modèles HTML fournis avec le plugin (dossier templates/)
# ------------------------------------------------------------------------------
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
MODELS = (
    ("defaut", "defaut.html", "Style actuel (dégradé bleu)"),
    ("sobre", "sobre.html", "Sobre"),
    ("etat", "design_etat.html", "Type Design System de l'État"),
    ("sombre", "sombre.html", "Sombre"),
)
DEFAULT_MODEL = "defaut"
MAX_TEMPLATE_BYTES = 1000000
USER_PREFIX = "user:"
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"}

# Modèle vierge proposé par « Nouveau » dans l'éditeur
NEW_MODEL_TEXT = """<!DOCTYPE html>
<html lang="{{lang}}">
<head>
    <meta charset="UTF-8">
    <title>{{titre}}</title>
    <style>
        body { font-family: sans-serif; margin: 24px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #ccc; padding: 6px 10px; text-align: left; }
    </style>
</head>
<body>
    <h1>{{titre}}</h1>
    <table>
        <tr>
<!-- CHAMP nom -->
            <th>{{entete_nom}}</th>
<!-- /CHAMP -->
<!-- CHAMP description -->
            <th>{{entete_description}}</th>
<!-- /CHAMP -->
        </tr>
<!-- LIGNE -->
        <tr>
<!-- CHAMP nom -->
            <td>{{nom}}</td>
<!-- /CHAMP -->
<!-- CHAMP description -->
            <td>{{description}}</td>
<!-- /CHAMP -->
        </tr>
<!-- /LIGNE -->
    </table>
</body>
</html>
"""

# Modèle de ligne utilisé quand un ancien modèle de page (balise {lignes}) est chargé
LEGACY_ROW = """\
<tr>
    <td><strong>{nom}</strong></td>
    <td class="desc-cell">{description}</td>
</tr>
"""

_TOKEN = re.compile(r"\{\{(\w+)\}\}|\{(\w+)\}")
_ROW_BLOCK = re.compile(
    r"<!--\s*(?:LIGNE|ROW)\s*-->(.*?)<!--\s*/\s*(?:LIGNE|ROW)\s*-->", re.S | re.I
)
_LEGACY_LINES = re.compile(r"\{\{lignes\}\}|\{lignes\}")
_HEAD_END = re.compile(r"</head\s*>", re.I)
# Bloc conditionnel : conservé seulement si le champ est coché (marqueurs toujours retirés)
_FIELD_BLOCK = re.compile(
    r"[ \t]*<!--\s*(?:CHAMP|FIELD)\s+(\w+)\s*-->[ \t]*\n?(.*?)[ \t]*<!--\s*/\s*(?:CHAMP|FIELD)\s*-->[ \t]*\n?",
    re.S | re.I,
)


class TemplateError(Exception):
    """Erreur de modèle ; `key` identifie le message à afficher."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key} {detail}".strip())
        self.key = key
        self.detail = detail


def _fill(template, values):
    """
    Remplace {{balise}} (et l'ancienne forme {balise}) en un seul passage :
    les balises inconnues, les accolades du CSS et le contenu inséré restent intacts.
    """
    def repl(match):
        key = match.group(1) or match.group(2)
        return values[key] if key in values else match.group(0)
    return _TOKEN.sub(repl, template)


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
    Les plugins `readonly=true` (plugins cœur) sont ignorés.
    """
    plugins, warnings = [], []
    if not plugins_dir or not os.path.isdir(plugins_dir):
        return plugins, warnings

    for folder in sorted(os.listdir(plugins_dir), key=str.lower):
        meta = os.path.join(plugins_dir, folder, "metadata.txt")
        if not os.path.isfile(meta):
            continue
        try:
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
    if norm == base:
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


def _safe_translate(translate_fn, text, lang):
    """Appelle translate_fn de manière isolée et retourne None en cas d'erreur."""
    try:
        return translate_fn(text, lang)
    except Exception as exc:  # noqa: BLE001
        _ = exc
        return None


def _resolve_single_description(plugin, lang, translate_fn, verify_native_lang):
    """Détermine le texte et l'origine ('original', 'natif', 'traduit', 'echec') d'un plugin."""
    default = plugin["description_defaut"]
    if not lang:
        return default, "original"

    native = _lookup_localized(plugin["localized"], lang)
    if native:
        if verify_native_lang and translate_fn and _base(lang) != "en":
            checked = _safe_translate(translate_fn, native, lang)
            detected = getattr(translate_fn, "last_source_language", None)
            if checked and detected and _base(detected) != _base(lang):
                return checked, "traduit"
        return native, "natif"

    if default and _base(lang) != "en" and translate_fn:
        translated = _safe_translate(translate_fn, default, lang)
        if translated:
            return translated, "traduit"
        return default, "echec"

    return default, "original"


def build_labels(lang, translate_fn=None, keys=None):
    """
    Titre / en-têtes / texte « sans description » dans la langue de sortie.
    `keys` : étiquettes supplémentaires à traduire (version, auteur...) ;
    les étiquettes de base sont toujours traduites.
    """
    base = _base(lang)
    if not lang or base == "fr":
        return dict(LABELS_FR)
    if base == "en":
        return dict(LABELS_EN)
    wanted = set(BASE_LABEL_KEYS) | set(keys or ())
    labels = dict(LABELS_EN)
    if translate_fn:
        for key, english in LABELS_EN.items():
            if key not in wanted:
                continue
            translated = _safe_translate(translate_fn, english, lang)
            if translated:
                labels[key] = translated
    return labels


def resolve_descriptions(plugins, lang, translate_fn=None, labels=None,
                         is_canceled=None, on_progress=None, verify_native_lang=False):
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
        raw_text, how = _resolve_single_description(p, lang, translate_fn, verify_native_lang)
        p["description"] = raw_text or labels["sans_description"]
        p["how"] = how
        stats[how] += 1
        if on_progress:
            on_progress(i + 1, total)
    return stats


# ------------------------------------------------------------------------------
# Modèles HTML
# ------------------------------------------------------------------------------
def model_path(key):
    for model_key, filename, _label in MODELS:
        if model_key == key:
            return os.path.join(TEMPLATES_DIR, filename)
    raise TemplateError("err_tpl_missing", key)


def read_template_file(path):
    """Lit un modèle (.html/.htm, 1 Mo max) ; lève TemplateError sinon."""
    path = os.path.abspath(os.path.expanduser(path or ""))
    if os.path.splitext(path)[1].lower() not in (".html", ".htm"):
        raise TemplateError("err_tpl_ext", path)
    if not os.path.isfile(path):
        raise TemplateError("err_tpl_missing", path)
    if os.path.getsize(path) > MAX_TEMPLATE_BYTES:
        raise TemplateError("err_tpl_size", path)
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        text = handle.read()
    parse_template(text)
    return text


def load_model(key=DEFAULT_MODEL):
    return read_template_file(model_path(key))


def parse_template(text):
    """
    Retourne (avant, modèle_de_ligne, après).
    Modèle de ligne = contenu entre les marqueurs LIGNE (ou ROW) ; à défaut, ancien
    format avec la balise lignes (modèle_de_ligne = None). Sinon TemplateError.
    """
    match = _ROW_BLOCK.search(text)
    if match:
        return text[:match.start()], match.group(1), text[match.end():]
    if _LEGACY_LINES.search(text):
        return text, None, ""
    raise TemplateError("err_tpl_invalid")


def apply_fields(text, fields=None):
    """
    Retire les blocs CHAMP dont le champ n'est pas sélectionné (fields=None : tous gardés).
    Un nom de champ inconnu garde son contenu. Les marqueurs eux-mêmes disparaissent toujours.
    """
    wanted = set(CSV_COLUMNS if fields is None else fields)

    def repl(match):
        name = match.group(1).lower()
        return match.group(2) if (name in wanted or name not in CSV_COLUMNS) else ""
    return _FIELD_BLOCK.sub(repl, text)


def template_label_keys(text, fields=None):
    """Étiquettes (entete_*) réellement utilisées par un modèle, pour les champs choisis."""
    used = set()
    allowed = {COLUMN_LABEL_KEY[f] for f in (CSV_COLUMNS if fields is None else fields) if f in COLUMN_LABEL_KEY}
    for match in _TOKEN.finditer(apply_fields(text, fields)):
        key = match.group(1) or match.group(2)
        if key in allowed:
            used.add(key)
    return used


# ------------------------------------------------------------------------------
# Modèles de l'utilisateur (dossier du profil QGIS)
# ------------------------------------------------------------------------------
def is_user_model(key):
    return bool(key) and key.startswith(USER_PREFIX)


def user_models(directory):
    """Liste [(clé, nom affiché, chemin)] des modèles de l'utilisateur, triée par nom."""
    try:
        names = sorted(os.listdir(directory), key=str.lower)
    except OSError:
        return []
    found = []
    for name in names:
        path = os.path.join(directory, name)
        if os.path.splitext(name)[1].lower() in (".html", ".htm") and os.path.isfile(path):
            found.append((USER_PREFIX + name, os.path.splitext(name)[0], path))
    return found


def safe_filename(name):
    """Nom de fichier .html sûr (pas de chemin, caractères simples) ou None."""
    base = os.path.basename((name or "").strip().replace("\\", "/"))
    if base.lower().endswith((".html", ".htm")):
        base = os.path.splitext(base)[0]
    cleaned = re.sub(r"[^\w\-. ()]", "", base).strip(" .")[:80]
    if not cleaned:
        return None
    if cleaned.upper() in _RESERVED_NAMES:
        cleaned += "_"
    return cleaned + ".html"


def unique_filename(directory, filename):
    root, ext = os.path.splitext(filename)
    candidate, number = filename, 2
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{root} ({number}){ext}"
        number += 1
    return candidate


def save_user_model(directory, filename, text):
    """Enregistre un modèle valide dans le dossier de l'utilisateur. -> (clé, chemin)."""
    name = safe_filename(filename)
    if not name:
        raise TemplateError("err_tpl_name")
    parse_template(text)
    if len(text.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise TemplateError("err_tpl_size", name)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return USER_PREFIX + name, path


def delete_user_model(directory, key):
    name = key[len(USER_PREFIX):] if is_user_model(key) else ""
    if not name or name != os.path.basename(name):
        raise TemplateError("err_tpl_missing", key or "")
    path = os.path.join(directory, name)
    if not os.path.isfile(path):
        raise TemplateError("err_tpl_missing", name)
    os.remove(path)


def import_model(source_path, directory):
    """Copie un fichier modèle (validé) dans le dossier de l'utilisateur. -> (clé, chemin)."""
    text = read_template_file(source_path)
    name = safe_filename(os.path.basename(source_path)) or "modele.html"
    return save_user_model(directory, unique_filename(directory, name), text)


def load_model_any(key, user_dir):
    """Texte d'un modèle fourni (clé simple) ou de l'utilisateur (clé « user:nom.html »)."""
    if is_user_model(key):
        name = key[len(USER_PREFIX):]
        if not name or name != os.path.basename(name):
            raise TemplateError("err_tpl_missing", key)
        return read_template_file(os.path.join(user_dir, name))
    return load_model(key)


def check_css(css):
    """CSS additionnel : le caractère '<' est refusé (pas de fermeture de balise)."""
    return "err_css" if "<" in (css or "") else None


def _safe_url(url):
    """Seules les adresses http(s) sont conservées (pas de javascript:, data:...)."""
    url = (url or "").strip()
    try:
        scheme = urlsplit(url).scheme.lower()
    except ValueError:
        return ""
    return url if scheme in ("http", "https") else ""


def _inject_css(page, css):
    css = (css or "").strip()
    if not css:
        return page
    block = "<style>\n" + css + "\n</style>\n"
    match = _HEAD_END.search(page)
    if match:
        return page[:match.start()] + block + page[match.start():]
    return block + page


def _blank_unselected(values, fields):
    """Champs non choisis : valeur et libellé vides."""
    for column in CSV_COLUMNS:
        if column not in fields:
            values[column] = ""
            values[COLUMN_LABEL_KEY[column]] = ""


def render_html(plugins, labels, lang, template, extra_css="", today=None, fields=None):
    """
    HTML statique construit à partir d'un modèle ; valeurs échappées.
    `fields` : champs à afficher (None = tous) ; les blocs CHAMP des autres disparaissent.
    """
    selected = set(CSV_COLUMNS if fields is None else fields)
    before, row_tpl, after = parse_template(apply_fields(template, fields))
    page_values = {
        "lang": html.escape(lang or "fr"),
        "nombre": str(len(plugins)),
        "date": html.escape(today or datetime.date.today().isoformat()),
    }
    for key in ("titre", "libelle_nombre") + tuple(COLUMN_LABEL_KEY.values()):
        page_values[key] = html.escape(labels.get(key, ""))
    _blank_unselected(page_values, selected)

    rows = []
    for number, plugin in enumerate(plugins, 1):
        # les balises de page (en-têtes, titre...) restent utilisables dans chaque ligne
        values = dict(page_values)
        values.update({col: html.escape(plugin.get(col, "") or "") for col in CSV_COLUMNS})
        values["homepage"] = html.escape(_safe_url(plugin.get("homepage", "")))
        values["numero"] = str(number)
        _blank_unselected(values, selected)
        rows.append(_fill(row_tpl if row_tpl is not None else LEGACY_ROW, values))
    joined = "".join(rows) if row_tpl is not None else "\n".join(rows)

    if row_tpl is None:
        page = _fill(before, dict(page_values, lignes=joined))
    else:
        page = _fill(before, page_values) + joined + _fill(after, page_values)
    return _inject_css(page, extra_css)


def sample_plugins(french):
    """Plugins fictifs pour l'aperçu du modèle."""
    texts = (
        ("Exemple de plugin A", "Description courte du premier plugin d'exemple.",
         "Short description of the first sample plugin."),
        ("Exemple de plugin B", "Une description un peu plus longue pour vérifier le retour à la ligne "
         "et l'aspect général de la page exportée.",
         "A slightly longer description to check wrapping and the overall look of the exported page."),
        ("Exemple de plugin C", "Troisième plugin d'exemple.", "Third sample plugin."),
    )
    return [
        {"dossier": f"exemple_{i}", "nom": name, "description": fr if french else en,
         "version": f"1.{i}.0", "auteur": "Auteur" if french else "Author",
         "homepage": "https://example.org"}
        for i, (name, fr, en) in enumerate(texts)
    ]


# ------------------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------------------
def _csv_safe(value):
    """Neutralise les formules (=, +, -, @) interprétées par Excel/LibreOffice."""
    value = value or ""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def render_csv(plugins, labels, delimiter=";", columns=DEFAULT_CSV_COLUMNS):
    columns = [c for c in CSV_COLUMNS if c in columns] or list(DEFAULT_CSV_COLUMNS)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n")
    writer.writerow([labels[COLUMN_LABEL_KEY[c]] for c in columns])
    for plugin in plugins:
        writer.writerow([_csv_safe(plugin.get(c, "")) for c in columns])
    return buffer.getvalue()


# ------------------------------------------------------------------------------
# Validation des options et du fichier de sortie
# ------------------------------------------------------------------------------
_LANG_RE = re.compile(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?")


def normalize_separator(sep):
    sep = sep or ";"
    return "\t" if sep in ("\\t", "\t") else sep


def check_options(lang_code="", separator=";"):
    """Retourne None si tout est valide, sinon une clé d'erreur."""
    if lang_code and not _LANG_RE.fullmatch(lang_code.strip()):
        return "err_lang"
    if len(normalize_separator(separator)) != 1:
        return "err_sep"
    return None


def fix_extension(path, is_csv):
    """Force l'extension du fichier de sortie au format choisi."""
    wanted = ".csv" if is_csv else ".html"
    root, ext = os.path.splitext(path)
    low = ext.lower()
    if low == wanted or (not is_csv and low == ".htm"):
        return path
    if low in (".html", ".htm", ".csv"):
        return root + wanted
    return path + wanted
