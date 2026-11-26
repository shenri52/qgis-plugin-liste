# -*- coding: utf-8 -*-
"""Test d'intégration de la fenêtre avec une vraie pile Qt : python qt_smoke.py PyQt5|PyQt6 fr|en"""
import os
import re
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

QT, LANG = sys.argv[1], sys.argv[2]
FRENCH = LANG == "fr"
import qgis_stubs  # noqa: E402
mods = qgis_stubs.install(QT)

from qgis_plugin_liste import core, dialog, i18n, plugin as plugin_mod  # noqa: E402

failures = []


def check(condition, message):
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        failures.append(message)


app = mods["QtWidgets"].QApplication([])

# ---- environnement : faux profil QGIS avec 3 plugins
root = tempfile.mkdtemp(prefix="smoke_")
profile = os.path.join(root, "profile")
plugins_dir = os.path.join(profile, "python", "plugins")
for folder, meta in {
    "alpha": "[general]\nname=Alpha\ndescription=Does the work for the users and the data\ndescription[fr]=Fait le travail\nversion=1.2\nauthor=Bob\n",
    "beta": "[general]\nname=Beta\ndescription=Only English text for the plugin and the users 100%\nversion=2.0\nauthor==EVIL()\n",
    "core": "[general]\nname=Core\nreadonly=true\ndescription=hidden\n",
}.items():
    os.makedirs(os.path.join(plugins_dir, folder))
    open(os.path.join(plugins_dir, folder, "metadata.txt"), "w", encoding="utf-8").write(meta)
qgis_stubs.FakeApplication.profile_dir = profile
qgis_stubs.FakeSettings.store.clear()
USER_DIR = os.path.join(profile, "ListePlugin", "modeles")

# ---- doubles de test
LOG = {"warning": [], "critical": [], "information": [], "question": [], "final": [], "urls": []}
FILE_ANSWERS = {"save": [], "open": []}
INPUT_ANSWERS = []
QUESTION_ANSWER = {"value": "yes"}
STD = mods["QtWidgets"].QMessageBox.StandardButton


class FakeMessageBox(mods["QtWidgets"].QMessageBox):
    @staticmethod
    def warning(_parent, _title, text, *a):
        LOG["warning"].append(text)

    @staticmethod
    def critical(_parent, _title, text, *a):
        LOG["critical"].append(text)

    @staticmethod
    def information(_parent, _title, text, *a):
        LOG["information"].append(text)

    @staticmethod
    def question(_parent, _title, text, buttons, default):
        LOG["question"].append(text)
        return STD.Yes if QUESTION_ANSWER["value"] == "yes" else STD.No

    def exec(self):
        LOG["final"].append(self.text())
        return 0

    exec_ = exec

    def clickedButton(self):  # noqa: N802
        return None


class FakeFileDialog:
    @staticmethod
    def getSaveFileName(*_a):  # noqa: N802
        return (FILE_ANSWERS["save"].pop(0) if FILE_ANSWERS["save"] else "", "")

    @staticmethod
    def getOpenFileName(*_a):  # noqa: N802
        return (FILE_ANSWERS["open"].pop(0) if FILE_ANSWERS["open"] else "", "")


class FakeInputDialog:
    @staticmethod
    def getText(*_a):  # noqa: N802
        if INPUT_ANSWERS:
            return INPUT_ANSWERS.pop(0), True
        return "", False


class FakeDesktop:
    @staticmethod
    def openUrl(url):  # noqa: N802
        LOG["urls"].append(url.toLocalFile())
        return True


class FakeTranslator:
    cancel_dialog = None
    calls = 0

    def __init__(self):
        self.last_source_language = "en"

    def __call__(self, text, lang):
        FakeTranslator.calls += 1
        if FakeTranslator.cancel_dialog is not None:
            FakeTranslator.cancel_dialog._canceled = True
        return f"[{lang}] {text}"


dialog.QMessageBox = FakeMessageBox
dialog.QFileDialog = FakeFileDialog
dialog.QInputDialog = FakeInputDialog
dialog.QDesktopServices = FakeDesktop
dialog.Translator = FakeTranslator
dialog.is_french = lambda: FRENCH
i18n.is_french = lambda: FRENCH


def reset_log():
    for key in LOG:
        LOG[key].clear()
    FakeTranslator.calls = 0


def read(path):
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read()


def lang_index(dlg, code):
    return dlg.language_combo.findData(code)


def model_index(combo, key):
    return combo.findData(key)


def set_fields(dlg, chosen):
    for column, box in dlg.field_checks.items():
        box.setChecked(column in chosen)


def th_count(text):
    return len(re.findall(r"<th[ >]", text))


print(f"== {QT} / interface {'FR' if FRENCH else 'EN'} ==")

# ---------------------------------------------------------------- construction
dlg = dialog.ExportDialog()
titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
check(titles == (["Export", "Apparence HTML", "Modifier un modèle"] if FRENCH else ["Export", "HTML appearance", "Edit a template"]),
      f"3 onglets localisés (plus d'onglet Avancé) {titles}")
check(dlg.windowTitle() == ("Liste des plugins installés" if FRENCH else "Installed plugins list"), "titre localisé")
check(dlg.language_combo.currentData() == ("fr" if FRENCH else "en"), "langue par défaut selon le PC")
check(dlg.language_combo.findData(dialog.OTHER_LANGUAGE) == dlg.language_combo.count() - 1, "entrée « Autre langue »")
check(dlg.custom_language.isHidden(), "champ code langue masqué par défaut")
keys = [dlg.model_combo.itemData(i) for i in range(dlg.model_combo.count())]
check(keys == ["defaut", "sobre", "etat", "sombre"] and dlg.model_combo.currentData() == "defaut", f"modèles fournis {keys}")
etat_label = dlg.model_combo.itemText(model_index(dlg.model_combo, "etat"))
check(etat_label == ("Type Design System de l'État" if FRENCH else "French State Design System style"), f"modèle renommé : {etat_label}")
check(dlg.edit_combo.count() == 4, "éditeur : mêmes modèles")
check(dlg.output_edit.text() == "", "aucun chemin de sortie par défaut")
check(set(dlg.field_checks) == set(core.CSV_COLUMNS) and [c for c in core.CSV_COLUMNS if dlg.field_checks[c].isChecked()] == ["nom", "description"],
      "6 cases de champs, nom + description cochés par défaut")
names_ok = all(i18n.tr(v, True) == v and v in i18n.EN for v in dialog.COLUMN_NAMES.values())
check(names_ok, "noms de champs traduisibles")
check(not dlg.field_checks["nom"].isHidden() and dlg.csv_group.isHidden(), "champs visibles en HTML, options CSV masquées")
check(not hasattr(dlg, "verify_native_checkbox") or dlg.verify_native_checkbox.parent() is not None, "case de vérification présente (ex-onglet Avancé)")

# ---------------------------------------------------------------- sortie vide, champs vides
reset_log()
dlg._export()
check(len(LOG["warning"]) == 1, "export sans fichier de sortie refusé")

# ---------------------------------------------------------------- HTML par défaut
out_html = os.path.join(root, "sortie", "liste")
dlg.output_edit.setText(out_html)
dlg.language_combo.setCurrentIndex(lang_index(dlg, "fr"))
reset_log()
dlg._export()
target = out_html + ".html"
check(os.path.isfile(target), "HTML créé (extension .html ajoutée, dossier créé)")
html_text = read(target)
check("Alpha" in html_text and "Beta" in html_text and "Core" not in html_text, "plugins listés, plugin cœur exclu")
check("Fait le travail" in html_text and "[fr] Only English text" in html_text, "description native + traduction faite par le script")
check(th_count(html_text) == 2 and ">Version<" not in html_text and "Bob" not in html_text,
      "seules les colonnes Extension et Description (champs cochés)")
check("<script" not in html_text.lower() and "{{" not in html_text, "HTML statique, aucune balise résiduelle")

# ---------------------------------------------------------------- sélection des champs en HTML
set_fields(dlg, core.CSV_COLUMNS)
reset_log()
dlg._export()
full = read(target)
check(th_count(full) == 6 and ">Version<" in full and ">Auteur<" in full and "Bob" in full, "6 champs cochés : 6 colonnes avec libellés")
check("=EVIL()" in full, "valeur d'auteur affichée (échappée)")

set_fields(dlg, ["nom", "version"])
reset_log()
dlg._export()
part = read(target)
check(th_count(part) == 2 and ">Version<" in part and ">Description<" not in part and "Fait le travail" not in part
      and "Bob" not in part, "nom + version seulement : ni colonne ni libellé des autres champs")
check(FakeTranslator.calls == 0, "sans le champ description : aucune traduction demandée")

set_fields(dlg, [])
reset_log()
dlg._export()
check(len(LOG["warning"]) == 1 and not LOG["final"], "aucun champ coché : refus")

# ---------------------------------------------------------------- modèle « Type Design System de l'État »
dlg.model_combo.setCurrentIndex(model_index(dlg.model_combo, "etat"))
set_fields(dlg, ["nom", "description", "auteur"])
out_etat = os.path.join(root, "etat")
dlg.output_edit.setText(out_etat)
reset_log()
dlg._export()
etat = read(out_etat + ".html")
check(etat.count('class="carte"') == 2 and "carte__titre" in etat and "Auteur" in etat and "Bob" in etat, "modèle État : 2 cartes avec champs choisis")
etat_body = etat.split("<body>")[-1]
check("carte__badge" not in etat_body and "Version" not in etat_body and "Dossier" not in etat_body, "modèle État : pas de libellé pour les champs non choisis")
check("#000091" not in etat and "Marianne" not in etat, "modèle fourni : aucune couleur de marque ni police Marianne")

# ---------------------------------------------------------------- bascule CSV et champs
dlg.format_combo.setCurrentIndex(1)
check(dlg.output_edit.text().endswith(".csv"), "extension passe à .csv au changement de format")
check(not dlg.csv_group.isHidden() and not dlg.tabs.isTabEnabled(1) and not dlg.field_checks["nom"].isHidden(),
      "mode CSV : options CSV visibles, onglet Apparence grisé, champs toujours visibles")
dlg.tabs.setCurrentIndex(0)

set_fields(dlg, ["nom", "version", "auteur"])
dlg.separator.setText(";;")
reset_log()
dlg._export()
check(len(LOG["warning"]) == 1, "séparateur de 2 caractères refusé")
dlg.separator.setText(r"\t")
dlg.language_combo.setCurrentIndex(dlg.language_combo.findData(dialog.OTHER_LANGUAGE))
dlg.custom_language.setText("sv")
reset_log()
dlg._export()
csv_path = out_etat + ".csv"
csv_text = read(csv_path)
lines = csv_text.splitlines()
check(lines[0].split("\t") == ["[sv] Plugin", "[sv] Version", "[sv] Author"], f"CSV : colonnes = champs cochés, en-têtes traduits {lines[0]!r}")
check(any(line.split("\t")[2].startswith("'=") for line in lines[1:]), "formule neutralisée dans le CSV")
check(open(csv_path, "rb").read(3) == b"\xef\xbb\xbf" and open(csv_path, "rb").read().count(b"\r\n") == 3, "CSV UTF-8 avec BOM, CRLF")
set_fields(dlg, ["dossier"])
dlg.language_combo.setCurrentIndex(lang_index(dlg, "fr"))
dlg._export()
check(read(csv_path).splitlines() == ["Dossier", "alpha", "beta"], "CSV un seul champ : une seule colonne")

# ---------------------------------------------------------------- autre langue
dlg.format_combo.setCurrentIndex(0)
dlg.language_combo.setCurrentIndex(dlg.language_combo.findData(dialog.OTHER_LANGUAGE))
check(not dlg.custom_language.isHidden(), "« Autre langue » : le champ code apparaît")
set_fields(dlg, ["nom", "description"])
dlg.custom_language.setText("")
reset_log()
dlg._export()
check(len(LOG["warning"]) == 1, "autre langue sans code : refus")
dlg.custom_language.setText("pas valide!")
reset_log()
dlg._export()
check(len(LOG["warning"]) == 1, "autre langue : code invalide refusé")
dlg.custom_language.setText("sv")
reset_log()
dlg._export()
check("[sv] Only English text" in read(out_etat + ".html"), "autre langue « sv » : traduction demandée")
dlg.language_combo.setCurrentIndex(lang_index(dlg, "fr"))
check(dlg.custom_language.isHidden(), "retour à une langue de la liste : champ code masqué")

# ---------------------------------------------------------------- importer un modèle
external = os.path.join(root, "externe", "Mon import.html")
os.makedirs(os.path.dirname(external))
open(external, "w", encoding="utf-8").write(core.load_model("sobre").replace("#f2f2f2", "#ffeeaa"))
FILE_ANSWERS["open"].append(external)
reset_log()
dlg._import_model()
imported_key = "user:Mon import.html"
check(os.path.isfile(os.path.join(USER_DIR, "Mon import.html")), "import : copié dans le dossier des modèles du profil")
check(dlg.model_combo.currentData() == imported_key and dlg.edit_combo.findData(imported_key) >= 0, "import : modèle ajouté aux listes et sélectionné")
check("ffeeaa" in core.load_model_any(imported_key, USER_DIR), "import : contenu conservé")
check(dlg.model_combo.currentText().endswith("Mon import"), f"libellé de la liste : {dlg.model_combo.currentText()!r}")
bad_import = os.path.join(root, "externe", "mauvais.html")
open(bad_import, "w").write("<html>rien</html>")
FILE_ANSWERS["open"].append(bad_import)
reset_log()
dlg._import_model()
check(len(LOG["warning"]) == 1 and not os.path.exists(os.path.join(USER_DIR, "mauvais.html")), "import d'un fichier invalide refusé")

dlg.output_edit.setText(os.path.join(root, "avec_import"))
set_fields(dlg, ["nom", "version"])
reset_log()
dlg._export()
imp = read(os.path.join(root, "avec_import.html"))
check("ffeeaa" in imp and th_count(imp) == 2, "export avec le modèle importé, champs respectés")

# ---------------------------------------------------------------- éditeur : lecture seule des modèles fournis
dlg.edit_combo.setCurrentIndex(model_index(dlg.edit_combo, "defaut"))
check(dlg.editor.toPlainText() == core.load_model("defaut") and not core.is_user_model(dlg._edit_key), "éditeur : modèle fourni chargé")
check(not dlg.delete_button.isEnabled(), "modèle fourni : suppression impossible")
dlg.highlighter.rehighlight()
colored = sum(1 for n in range(dlg.editor.document().blockCount())
              if dlg.editor.document().findBlockByNumber(n).layout().formats())
check(colored > 10, f"coloration syntaxique appliquée ({colored} lignes colorées)")

# modification + enregistrer (modèle fourni => « enregistrer sous »)
reset_log()
dlg.editor.setPlainText(core.load_model("defaut").replace("#cdebff", "#ffd5d5"))
check(dlg._edit_dirty, "modification détectée")
INPUT_ANSWERS.append("Mon rouge")
dlg._editor_save()
check(os.path.isfile(os.path.join(USER_DIR, "Mon rouge.html")) and "#ffd5d5" in read(os.path.join(USER_DIR, "Mon rouge.html")),
      "enregistrer un modèle fourni modifié : copie créée dans le profil")
check(core.load_model("defaut").count("#ffd5d5") == 0, "le modèle fourni n'est pas modifié")
check(dlg.edit_combo.currentData() == "user:Mon rouge.html" and dlg.model_combo.currentData() == "user:Mon rouge.html"
      and not dlg._edit_dirty, "nouveau modèle sélectionné partout, plus de modification en attente")
check(dlg.delete_button.isEnabled(), "modèle personnel : suppression possible")

# enregistrer en place
dlg.editor.setPlainText(dlg.editor.toPlainText().replace("#ffd5d5", "#d5ffd5"))
dlg._editor_save()
check("#d5ffd5" in read(os.path.join(USER_DIR, "Mon rouge.html")) and not INPUT_ANSWERS, "enregistrer un modèle personnel : écrase sans redemander le nom")

# enregistrer sous un nom existant
reset_log()
QUESTION_ANSWER["value"] = "no"
INPUT_ANSWERS.append("Mon import")
dlg._editor_save_as()
check(len(LOG["question"]) == 1 and "ffeeaa" in core.load_model_any(imported_key, USER_DIR), "nom existant : confirmation, refus respecté")
QUESTION_ANSWER["value"] = "yes"
INPUT_ANSWERS.append("///")
reset_log()
dlg._editor_save_as()
check(len(LOG["warning"]) == 1, "nom de modèle invalide refusé")

# modèle invalide non enregistrable
reset_log()
dlg.editor.setPlainText("<html><body>plus de marqueurs</body></html>")
dlg._editor_save()
check(len(LOG["warning"]) == 1 and "d5ffd5" in read(os.path.join(USER_DIR, "Mon rouge.html")), "modèle sans marqueur LIGNE : non enregistré")
reset_log()
dlg._editor_preview()
check(len(LOG["warning"]) == 1 and not LOG["urls"], "aperçu d'un modèle invalide refusé")

# changement de modèle avec modifications en attente
reset_log()
QUESTION_ANSWER["value"] = "no"
dlg.edit_combo.setCurrentIndex(model_index(dlg.edit_combo, "sombre"))
check(len(LOG["question"]) == 1 and dlg.edit_combo.currentData() == "user:Mon rouge.html" and dlg._edit_dirty,
      "changement de modèle avec modifications : confirmation, refus => on reste")
rejected = []
dlg.rejected.connect(lambda: rejected.append(1))
reset_log()
dlg.reject()
check(len(LOG["question"]) == 1 and not rejected, "fermer avec modifications en attente : confirmation, refus => la fenêtre reste")
QUESTION_ANSWER["value"] = "yes"
dlg.edit_combo.setCurrentIndex(model_index(dlg.edit_combo, "sombre"))
check(dlg.edit_combo.currentData() == "sombre" and not dlg._edit_dirty, "après confirmation : nouveau modèle chargé")

# nouveau modèle + aperçu non enregistré
dlg._editor_new()
check(dlg._edit_key is None and dlg.editor.toPlainText() == core.NEW_MODEL_TEXT and dlg._edit_dirty, "Nouveau : modèle vierge valide")
set_fields(dlg, ["nom"])
reset_log()
dlg._editor_preview()
check(len(LOG["urls"]) == 1, "aperçu depuis l'éditeur (modèle non enregistré)")
apercu = read(LOG["urls"][0])
check("Exemple de plugin A" in apercu and "Description courte" not in apercu and "{{" not in apercu, "aperçu : respecte les champs cochés")
preview_dir = os.path.dirname(LOG["urls"][0])
dlg.extra_css.setPlainText("</style><script>")
reset_log()
dlg._editor_preview()
check(len(LOG["warning"]) == 1 and not LOG["urls"], "aperçu : CSS additionnel dangereux refusé")
dlg.extra_css.setPlainText("")
INPUT_ANSWERS.append("Vierge")
dlg._editor_save()
check(os.path.isfile(os.path.join(USER_DIR, "Vierge.html")) and dlg._edit_key == "user:Vierge.html", "nouveau modèle enregistré")

# suppression
reset_log()
QUESTION_ANSWER["value"] = "no"
dlg._editor_delete()
check(os.path.isfile(os.path.join(USER_DIR, "Vierge.html")), "suppression refusée à la confirmation : fichier conservé")
QUESTION_ANSWER["value"] = "yes"
dlg._editor_delete()
check(not os.path.exists(os.path.join(USER_DIR, "Vierge.html")) and dlg.model_combo.currentData() == "defaut"
      and dlg.edit_combo.currentData() == "defaut" and dlg.editor.toPlainText() == core.load_model("defaut"),
      "suppression : modèle retiré, retour au style par défaut")

# ---------------------------------------------------------------- dossier des modèles, aperçu principal
reset_log()
dlg._open_models_folder()
check(LOG["urls"] == [USER_DIR] and os.path.isdir(USER_DIR), "ouvrir le dossier de mes modèles")
reset_log()
set_fields(dlg, ["nom", "description"])
dlg.model_combo.setCurrentIndex(model_index(dlg.model_combo, "etat"))
dlg._preview()
check(len(LOG["urls"]) == 1 and "carte" in read(LOG["urls"][0]), "aperçu du modèle choisi")

# ---------------------------------------------------------------- écrasement et annulation
reset_log()
QUESTION_ANSWER["value"] = "no"
dlg.format_combo.setCurrentIndex(0)
dlg.output_edit.setText(os.path.join(root, "avec_import.html"))
before = read(os.path.join(root, "avec_import.html"))
dlg._export()
check(len(LOG["question"]) == 1 and read(os.path.join(root, "avec_import.html")) == before and not LOG["final"],
      "fichier existant : confirmation, refus respecté")
QUESTION_ANSWER["value"] = "yes"
FILE_ANSWERS["save"].append(os.path.join(root, "choisi.csv"))
dlg._browse()
check(dlg.output_edit.text().endswith("choisi.html"), "parcourir : l'extension suit le format HTML même si .csv choisi")

reset_log()
dlg.output_edit.setText(os.path.join(root, "annule.html"))
FakeTranslator.cancel_dialog = dlg
dlg.language_combo.setCurrentIndex(lang_index(dlg, "de"))
dlg._export()
FakeTranslator.cancel_dialog = None
check(not os.path.exists(os.path.join(root, "annule.html")) and len(LOG["information"]) == 1, "annulation : aucun fichier écrit")
check(dlg.export_button.isEnabled() and not dlg._running, "interface réactivée après annulation")

# ---------------------------------------------------------------- mémorisation
dlg._save_settings()
dlg2 = dialog.ExportDialog()
check(dlg2.model_combo.currentData() == "etat", "modèle mémorisé")
check([c for c in core.CSV_COLUMNS if dlg2.field_checks[c].isChecked()] == ["nom", "description"], "champs mémorisés")

# ---------------------------------------------------------------- plugin (menu + barre d'outils)
class FakeIface:
    def __init__(self):
        self.calls = []

    def mainWindow(self):  # noqa: N802
        return None

    def addPluginToMenu(self, menu, action):  # noqa: N802
        self.calls.append(("menu+", menu))

    def addToolBarIcon(self, action):  # noqa: N802
        self.calls.append(("toolbar+", action.text()))

    def removePluginMenu(self, menu, action):  # noqa: N802
        self.calls.append(("menu-", menu))

    def removeToolBarIcon(self, action):  # noqa: N802
        self.calls.append(("toolbar-",))


class FakeDialog:
    opened = 0

    def __init__(self, parent=None):
        pass

    def exec(self):
        FakeDialog.opened += 1


plugin_mod.ExportDialog = FakeDialog
iface = FakeIface()
instance = plugin_mod.ListePluginPlugin(iface)
instance.initGui()
check(("menu+", "&Liste Plugin") in iface.calls, "entrée dans le menu Extensions")
check(any(c[0] == "toolbar+" for c in iface.calls) and not instance.action.icon().isNull(), "icône dans la barre d'outils")
instance.action.trigger()
check(FakeDialog.opened == 1, "clic sur l'action : ouvre la fenêtre")
instance.unload()
check(("menu-", "&Liste Plugin") in iface.calls and ("toolbar-",) in iface.calls, "déchargement : menu et icône retirés")
check(not os.path.isdir(preview_dir), "déchargement : fichiers d'aperçu temporaires supprimés")

shutil.rmtree(root, ignore_errors=True)
print(f"-- {len(failures)} échec(s)")
sys.exit(1 if failures else 0)
