# -*- coding: utf-8 -*-
"""
Algorithme Processing : export de la liste des plugins installés (HTML ou CSV),
avec traduction réalisée par le script (le HTML produit est statique).

Processing algorithm: export the list of installed plugins (HTML or CSV),
translation is done by the script (the produced HTML is static).

Compatible QGIS 3.28+ (Qt5) et QGIS 4 (Qt6) : uniquement `qgis.PyQt`,
énumérations qualifiées, pas de exec_().
"""
import json
import os
import re
from urllib.parse import quote, urlencode

from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import (
    QgsApplication,
    QgsBlockingNetworkRequest,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)

from . import core


def _enum(cls, name, member):
    """Accès à une énumération QGIS en Qt5 (non qualifiée) comme en Qt6 (qualifiée)."""
    return getattr(getattr(cls, name, cls), member)


# ------------------------------------------------------------------------------
# Traducteur (utilise le réseau de QGIS => respecte les paramètres de proxy)
# ------------------------------------------------------------------------------
class GoogleTranslator:
    URL = "https://translate.googleapis.com/translate_a/single"
    MAX_CONSECUTIVE_FAILS = 3

    def __init__(self, feedback):
        self.feedback = feedback
        self.cache = {}
        self.fails = 0
        self.disabled = False

    def __call__(self, text, lang):
        key = (text, lang)
        if key in self.cache:
            return self.cache[key]
        if self.disabled:
            return None

        parts = []
        for chunk in core.split_text(text):
            part = self._request(chunk, lang)
            if part is None:
                self.fails += 1
                if self.fails >= self.MAX_CONSECUTIVE_FAILS:
                    self.disabled = True
                    self.feedback.reportError(
                        QCoreApplication.translate(
                            "ListePlugin",
                            "Service de traduction injoignable : les descriptions "
                            "restantes seront exportées sans traduction."),
                        False)
                return None
            parts.append(part)

        self.fails = 0
        result = " ".join(parts).strip() or None
        self.cache[key] = result
        return result

    def _request(self, text, lang):
        params = {"client": "gtx", "sl": "auto", "tl": lang, "dt": "t", "q": text}
        url = f"{self.URL}?{urlencode(params, quote_via=quote)}"
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0 (QGIS)")
        blocking = QgsBlockingNetworkRequest()
        error = blocking.get(request, False, self.feedback)
        if error != _enum(QgsBlockingNetworkRequest, "ErrorCode", "NoError"):
            return None
        try:
            data = json.loads(bytes(blocking.reply().content()).decode("utf-8"))
            return "".join(seg[0] for seg in data[0] if seg and seg[0])
        except Exception:  # noqa: BLE001
            return None


# ------------------------------------------------------------------------------
# Algorithme
# ------------------------------------------------------------------------------
class ExportPluginsAlgorithm(QgsProcessingAlgorithm):
    LANGUE = "LANGUE"
    FORMAT = "FORMAT"
    SORTIE = "SORTIE"
    LANGUE_PERSO = "LANGUE_PERSO"
    SEPARATEUR = "SEPARATEUR"
    CSS_PERSO = "CSS_PERSO"
    MODELE_PAGE = "MODELE_PAGE"
    MODELE_LIGNE = "MODELE_LIGNE"

    def tr(self, string):
        return QCoreApplication.translate("ListePlugin", string)

    def createInstance(self):
        return self.__class__()

    def name(self):
        return "liste_plugin"

    def displayName(self):
        return self.tr("Liste des plugins installés")

    def group(self):
        return self.tr("Mes outils")

    def groupId(self):
        return "mesoutils"

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))

    def shortHelpString(self):
        return (
            "<b>FR</b><br>"
            "Liste les plugins installés et exporte le résultat en HTML ou en CSV.<br>"
            "La description est donnée dans la langue choisie : celle du plugin "
            "(<i>description[xx]</i> de son metadata.txt) si elle existe, sinon elle est "
            "traduite par l'algorithme. Le fichier HTML produit est statique "
            "(aucune traduction dans le navigateur).<br>"
            "Les paramètres avancés permettent de personnaliser le style (CSS) et les "
            "balises HTML (modèles de page et de ligne).<br><br>"
            "<b>EN</b><br>"
            "Lists the installed plugins and exports the result as HTML or CSV.<br>"
            "The description is provided in the chosen language: the plugin's own "
            "(<i>description[xx]</i> in its metadata.txt) when available, otherwise it is "
            "translated by the algorithm. The generated HTML file is static "
            "(no in-browser translation).<br>"
            "Advanced parameters let you customise the style (CSS) and the HTML tags "
            "(page and row templates)."
        )

    # ------------------------------------------------------------------
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            self.LANGUE,
            self.tr("Langue des descriptions"),
            options=[label for _code, label in core.LANGUES],
            allowMultiple=False,
            defaultValue=core.DEFAULT_LANG_INDEX))

        self.addParameter(QgsProcessingParameterEnum(
            self.FORMAT,
            self.tr("Format d'export"),
            options=["HTML", "CSV"],
            allowMultiple=False,
            defaultValue=0))

        # Pas de valeur par défaut : l'utilisateur choisit toujours le fichier
        self.addParameter(QgsProcessingParameterFileDestination(
            self.SORTIE,
            self.tr("Fichier de sortie"),
            fileFilter="HTML (*.html);;CSV (*.csv)"))

        # ---- paramètres avancés ----
        advanced = _enum(QgsProcessingParameterDefinition, "Flag", "FlagAdvanced")

        def add_advanced(parameter):
            parameter.setFlags(parameter.flags() | advanced)
            self.addParameter(parameter)

        add_advanced(QgsProcessingParameterString(
            self.LANGUE_PERSO,
            self.tr("Code langue personnalisé (ex. : sv, ko, pt-BR) – remplace la liste ci-dessus"),
            defaultValue="", optional=True))

        add_advanced(QgsProcessingParameterString(
            self.SEPARATEUR,
            self.tr("Séparateur CSV (un caractère, ou \\t pour tabulation)"),
            defaultValue=";", optional=True))

        add_advanced(QgsProcessingParameterString(
            self.CSS_PERSO,
            self.tr("HTML : CSS personnalisé – remplace le style par défaut"),
            multiLine=True, optional=True))

        add_advanced(QgsProcessingParameterString(
            self.MODELE_PAGE,
            self.tr("HTML : modèle de page – balises : {lang} {titre} {css} "
                    "{entete_nom} {entete_description} {lignes} ({lignes} obligatoire)"),
            multiLine=True, optional=True))

        add_advanced(QgsProcessingParameterString(
            self.MODELE_LIGNE,
            self.tr("HTML : modèle d'une ligne – balises : {nom} {description} "
                    "{version} {auteur} {dossier} {homepage}"),
            multiLine=True, optional=True))

    # ------------------------------------------------------------------
    def checkParameterValues(self, parameters, context):
        page = (self.parameterAsString(parameters, self.MODELE_PAGE, context) or "").strip()
        if page and "{lignes}" not in page:
            return False, self.tr("Le modèle de page doit contenir la balise {lignes}.")

        perso = (self.parameterAsString(parameters, self.LANGUE_PERSO, context) or "").strip()
        if perso and not re.fullmatch(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?", perso):
            return False, self.tr("Code langue invalide (exemples valides : fr, sv, pt-BR, zh-CN).")

        sep = self.parameterAsString(parameters, self.SEPARATEUR, context)
        if sep and sep not in ("\\t",) and len(sep) != 1:
            return False, self.tr("Le séparateur CSV doit être un seul caractère (ou \\t).")

        return super().checkParameterValues(parameters, context)

    # ------------------------------------------------------------------
    def processAlgorithm(self, parameters, context, feedback):
        is_csv = self.parameterAsEnum(parameters, self.FORMAT, context) == 1
        lang_index = self.parameterAsEnum(parameters, self.LANGUE, context)
        lang = core.LANGUES[lang_index][0]
        perso = (self.parameterAsString(parameters, self.LANGUE_PERSO, context) or "").strip()
        if perso:
            lang = perso

        sortie = self.parameterAsFileOutput(parameters, self.SORTIE, context)
        if not sortie:
            raise QgsProcessingException(self.tr("Aucun fichier de sortie n'a été choisi."))

        # L'extension suit le format choisi
        wanted = ".csv" if is_csv else ".html"
        root, current = os.path.splitext(sortie)
        ok = current.lower() == wanted or (not is_csv and current.lower() == ".htm")
        if not ok:
            if current.lower() in (".html", ".htm", ".csv"):
                sortie = root + wanted
                feedback.pushWarning(self.tr("Extension ajustée au format choisi : ") + sortie)
            else:
                sortie += wanted

        plugins_dir = os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins")
        if not os.path.isdir(plugins_dir):
            raise QgsProcessingException(
                self.tr("Dossier des plugins introuvable : ") + plugins_dir)

        plugins, warnings = core.collect_plugins(plugins_dir)
        for folder, message in warnings:
            feedback.pushWarning(f"{folder} : {message}")
        if not plugins:
            feedback.pushWarning(self.tr("Aucun plugin utilisateur trouvé."))

        translator = GoogleTranslator(feedback) if lang else None
        labels = core.build_labels(lang, translator)

        def on_progress(done, total):
            feedback.setProgress(int(100 * done / max(total, 1)))

        stats = core.resolve_descriptions(
            plugins, lang, translator, labels,
            is_canceled=feedback.isCanceled, on_progress=on_progress)
        if feedback.isCanceled():
            return {}

        try:
            os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
            if is_csv:
                sep = self.parameterAsString(parameters, self.SEPARATEUR, context) or ";"
                if sep == "\\t":
                    sep = "\t"
                content = core.render_csv(plugins, labels, sep)
                # utf-8-sig : accents corrects à l'ouverture dans Excel
                with open(sortie, "w", encoding="utf-8-sig", newline="") as fh:
                    fh.write(content)
            else:
                content = core.render_html(
                    plugins, labels, lang,
                    css=self.parameterAsString(parameters, self.CSS_PERSO, context) or "",
                    page_tpl=self.parameterAsString(parameters, self.MODELE_PAGE, context) or "",
                    row_tpl=self.parameterAsString(parameters, self.MODELE_LIGNE, context) or "")
                with open(sortie, "w", encoding="utf-8") as fh:
                    fh.write(content)
        except OSError as exc:
            raise QgsProcessingException(self.tr("Écriture impossible : ") + str(exc))

        feedback.pushInfo(
            f"{len(plugins)} plugin(s) -> {sortie}  "
            f"[natif: {stats['natif']}, traduit: {stats['traduit']}, "
            f"original: {stats['original']}, échec traduction: {stats['echec']}]")
        return {self.SORTIE: sortie}
