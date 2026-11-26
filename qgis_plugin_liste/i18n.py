# -*- coding: utf-8 -*-
"""Textes de l'interface : français si le PC est en français, anglais sinon."""

EN = {
    # fenêtre
    "Liste des plugins installés": "Installed plugins list",
    "Exporte la liste des extensions QGIS installées en HTML ou CSV. Les descriptions sont "
    "utilisées dans la langue choisie lorsqu’elles existent, sinon elles sont traduites "
    "automatiquement.":
        "Exports the list of installed QGIS plugins as HTML or CSV. Descriptions use the selected "
        "language when available and are otherwise translated automatically.",
    "Export": "Export",
    "Apparence HTML": "HTML appearance",
    "Modifier un modèle": "Edit a template",
    "Exporter": "Export",
    "Fermer": "Close",
    "Annuler": "Cancel",
    # onglet Export
    "Format d'export": "Export format",
    "Langue des descriptions": "Description language",
    "Original (sans traduction)": "Original (no translation)",
    "Autre langue (saisir le code)…": "Other language (enter the code)…",
    "code : sv, ko, pt-BR…": "code: sv, ko, pt-BR…",
    "Vérifier la langue des descriptions déjà localisées (requêtes réseau supplémentaires)":
        "Check the language of already localized descriptions (extra network requests)",
    "Fichier de sortie": "Output file",
    "Choisir le fichier de destination…": "Choose the destination file…",
    "Parcourir…": "Browse…",
    "Champs à exporter": "Fields to export",
    "Nom": "Name",
    "Description": "Description",
    "Version": "Version",
    "Auteur": "Author",
    "Dossier": "Folder",
    "Site web": "Website",
    "Options CSV": "CSV options",
    "Séparateur CSV (un caractère ou \\t)": "CSV separator (one character or \\t)",
    # onglet Apparence HTML
    "Modèle": "Template",
    "Mon modèle": "My template",
    "Style actuel (dégradé bleu)": "Current style (blue gradient)",
    "Sobre": "Plain",
    "Type Design System de l'État": "French State Design System style",
    "Sombre": "Dark",
    "Importer un modèle…": "Import a template…",
    "Ouvrir le dossier de mes modèles": "Open my templates folder",
    "Aperçu dans le navigateur": "Preview in browser",
    "Modèle importé : ": "Template imported: ",
    "CSS additionnel (optionnel, ajouté après le style du modèle)":
        "Additional CSS (optional, added after the template style)",
    "Un modèle est une page HTML normale. Les balises s'écrivent entre doubles accolades : "
    "{{titre}} {{nombre}} {{libelle_nombre}} {{date}} {{lang}} et les en-têtes {{entete_nom}} "
    "{{entete_description}} {{entete_version}} {{entete_auteur}} {{entete_dossier}} "
    "{{entete_homepage}}. Le bloc placé entre les marqueurs LIGNE est répété pour chaque "
    "plugin et peut utiliser {{nom}} {{description}} {{version}} {{auteur}} {{dossier}} "
    "{{homepage}} {{numero}}. Un bloc entouré des marqueurs CHAMP suivis du nom d'un champ "
    "n'apparaît que si ce champ est coché.":
        "A template is a regular HTML page. Tags are written between double curly braces: "
        "{{titre}} {{nombre}} {{libelle_nombre}} {{date}} {{lang}} and the headers {{entete_nom}} "
        "{{entete_description}} {{entete_version}} {{entete_auteur}} {{entete_dossier}} "
        "{{entete_homepage}}. The block placed between the LIGNE markers is repeated for every "
        "plugin and can use {{nom}} {{description}} {{version}} {{auteur}} {{dossier}} "
        "{{homepage}} {{numero}}. A block wrapped in CHAMP markers followed by a field name only "
        "appears when that field is ticked.",
    # onglet Modifier un modèle
    "Modèle à modifier": "Template to edit",
    "Nouveau": "New",
    "Enregistrer": "Save",
    "Enregistrer sous…": "Save as…",
    "Supprimer": "Delete",
    "Enregistrer le modèle": "Save the template",
    "Nom du modèle :": "Template name:",
    "Nouveau modèle (non enregistré).": "New template (not saved).",
    "Modèle fourni : pour le modifier, utilisez « Enregistrer sous… » "
    "(votre copie sera rangée dans votre profil QGIS).":
        "Bundled template: to change it, use “Save as…” (your copy will be stored in your QGIS profile).",
    "(modifié)": "(modified)",
    "Les modifications non enregistrées seront perdues. Continuer ?":
        "Unsaved changes will be lost. Continue?",
    "Supprimer définitivement ce modèle ?": "Permanently delete this template?",
    "Un modèle de ce nom existe déjà. Le remplacer ?": "A template with this name already exists. Replace it?",
    "Le modèle en cours d'édition n'est pas enregistré. Fermer quand même ?":
        "The template being edited is not saved. Close anyway?",
    # fichiers
    "Enregistrer la liste des plugins": "Save the plugins list",
    "Fichiers CSV (*.csv);;Tous les fichiers (*)": "CSV files (*.csv);;All files (*)",
    "Fichiers HTML (*.html *.htm);;Tous les fichiers (*)": "HTML files (*.html *.htm);;All files (*)",
    "Fichiers HTML (*.html *.htm)": "HTML files (*.html *.htm)",
    "Le fichier existe déjà. Le remplacer ?": "The file already exists. Replace it?",
    # erreurs
    "Veuillez choisir un fichier de sortie.": "Please choose an output file.",
    "Saisissez un code de langue (exemples : fr, sv, pt-BR, zh-CN).":
        "Enter a language code (examples: fr, sv, pt-BR, zh-CN).",
    "Code langue invalide (exemples : fr, sv, pt-BR, zh-CN).":
        "Invalid language code (examples: fr, sv, pt-BR, zh-CN).",
    "Le séparateur CSV doit être un seul caractère ou \\t.":
        "The CSV separator must be a single character or \\t.",
    "Cochez au moins un champ.": "Select at least one field.",
    "Le CSS additionnel ne doit pas contenir le caractère « < ».":
        "The additional CSS must not contain the “<” character.",
    "Le modèle doit être un fichier .html ou .htm.": "The template must be an .html or .htm file.",
    "Modèle introuvable : ": "Template not found: ",
    "Modèle trop volumineux (1 Mo maximum) : ": "Template too large (1 MB maximum): ",
    "Nom de modèle invalide.": "Invalid template name.",
    "Modèle invalide : il doit contenir un bloc entre deux marqueurs LIGNE.":
        "Invalid template: it must contain a block between two LIGNE markers.",
    "Dossier des plugins introuvable : ": "Plugins folder not found: ",
    "Écriture impossible : ": "Cannot write: ",
    "Échec de l'export : ": "Export failed: ",
    # progression / résultat
    "Lecture des extensions installées…": "Reading installed plugins…",
    "Analyse et traduction des descriptions…": "Analysing and translating descriptions…",
    "Traitement des extensions : {current}/{total}": "Processing plugins: {current}/{total}",
    "Création du fichier d’export…": "Creating the export file…",
    "Annulation en cours…": "Canceling…",
    "Export annulé.": "Export canceled.",
    "Export terminé : {n} plugin(s).\nFichier : {path}\n"
    "Descriptions : {native} natives, {translated} traduites, {failed} non traduites.":
        "Export finished: {n} plugin(s).\nFile: {path}\n"
        "Descriptions: {native} native, {translated} translated, {failed} not translated.",
    "Métadonnées ignorées ou incomplètes :": "Ignored or incomplete metadata:",
    "Ouvrir le fichier": "Open the file",
    # plugin
    "Exporter la liste des plugins installés en HTML ou CSV":
        "Export the list of installed plugins as HTML or CSV",
}


def is_french():
    try:
        from qgis.PyQt.QtCore import QLocale
        return QLocale.system().name().lower().startswith("fr")
    except Exception:  # noqa: BLE001
        return True


def tr(text, french=None):
    """Retourne le texte français tel quel, ou sa version anglaise."""
    if french is None:
        french = is_french()
    return text if french else EN.get(text, text)
