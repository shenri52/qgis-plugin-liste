# -*- coding: utf-8 -*-
"""Fenêtre principale de Liste Plugin (menu Extensions et barre d'outils)."""
import os
import re
import shutil
import tempfile

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import (
    QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QSyntaxHighlighter, QTextCharFormat,
)
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)
from qgis.core import QgsApplication, QgsSettings

from . import core
from .i18n import is_french, tr
from .translator import Translator

SETTINGS_PREFIX = "ListePlugin/"
OTHER_LANGUAGE = "__other__"
COLUMN_NAMES = {
    "nom": "Nom",
    "description": "Description",
    "version": "Version",
    "auteur": "Auteur",
    "dossier": "Dossier",
    "homepage": "Site web",
}
_BOLD = getattr(QFont.Weight.Bold, "value", QFont.Weight.Bold)


class _PreviewStore:
    """Dossier temporaire (créé à la demande) contenant la page d'aperçu."""
    directory = None

    @classmethod
    def path(cls):
        if not cls.directory or not os.path.isdir(cls.directory):
            cls.directory = tempfile.mkdtemp(prefix="liste_plugin_")
        return os.path.join(cls.directory, "apercu.html")

    @classmethod
    def cleanup(cls):
        if cls.directory:
            shutil.rmtree(cls.directory, ignore_errors=True)
            cls.directory = None


def cleanup_previews():
    """Supprime les fichiers d'aperçu temporaires (appelé au déchargement du plugin)."""
    _PreviewStore.cleanup()


class HtmlHighlighter(QSyntaxHighlighter):
    """Coloration simple du HTML, des balises {{...}} et des marqueurs LIGNE / CHAMP."""
    _TAG = re.compile(r"</?[A-Za-z][\w:-]*|/?>")
    _ATTR = re.compile(r"\s([A-Za-z_:][\w:.-]*)(?==)")
    _STRING = re.compile(r"\"[^\"]*\"|'[^']*'")
    _TOKEN = re.compile(r"\{\{\w+\}\}")
    _MARKER = re.compile(r"<!--\s*/?\s*(?:LIGNE|ROW|CHAMP|FIELD)\b[^>]*-->", re.I)

    def __init__(self, document):
        super().__init__(document)
        self._formats = {
            "tag": self._format("#2f7bbf"),
            "attr": self._format("#b8860b"),
            "string": self._format("#2e8b57"),
            "token": self._format("#d2591b", bold=True),
            "comment": self._format("#7f8c8d", italic=True),
            "marker": self._format("#a21caf", bold=True),
        }

    @staticmethod
    def _format(color, bold=False, italic=False):
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(color))
        if bold:
            text_format.setFontWeight(_BOLD)
        if italic:
            text_format.setFontItalic(True)
        return text_format

    def highlightBlock(self, text):  # noqa: N802 (nom imposé par Qt)
        for pattern, key, group in (
                (self._TAG, "tag", 0), (self._ATTR, "attr", 1),
                (self._STRING, "string", 0), (self._TOKEN, "token", 0)):
            for match in pattern.finditer(text):
                self.setFormat(match.start(group), match.end(group) - match.start(group), self._formats[key])
        # commentaires (éventuellement sur plusieurs lignes) : état 1 = commentaire ouvert
        self.setCurrentBlockState(0)
        position = 0
        if self.previousBlockState() == 1:
            end = text.find("-->")
            if end == -1:
                self.setFormat(0, len(text), self._formats["comment"])
                self.setCurrentBlockState(1)
                return
            self.setFormat(0, end + 3, self._formats["comment"])
            position = end + 3
        while True:
            start = text.find("<!--", position)
            if start == -1:
                break
            end = text.find("-->", start + 4)
            if end == -1:
                self.setFormat(start, len(text) - start, self._formats["comment"])
                self.setCurrentBlockState(1)
                break
            segment = text[start:end + 3]
            kind = "marker" if self._MARKER.fullmatch(segment) else "comment"
            self.setFormat(start, end + 3 - start, self._formats[kind])
            position = end + 3


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._canceled = False
        self._running = False
        self._browsed_path = ""
        self._edit_key = None
        self._edit_dirty = False
        self._loading_editor = False
        self._current_labels = dict(core.LABELS_FR)
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self._icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()
        self.setWindowTitle(tr("Liste des plugins installés"))
        if not self._icon.isNull():
            self.setWindowIcon(self._icon)
        self.setMinimumWidth(700)
        self._build_ui()
        self._load_settings()
        self._load_into_editor(self.edit_combo.currentData())
        self._update_state()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        if not self._icon.isNull():
            logo = QLabel()
            logo.setPixmap(self._icon.pixmap(32, 32))
            header.addWidget(logo)
        app_name = QLabel(tr("Liste des plugins installés"))
        app_name.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(app_name)
        header.addStretch(1)
        layout.addLayout(header)

        help_label = QLabel(tr(
            "Exporte la liste des extensions QGIS installées en HTML ou CSV. Les descriptions sont "
            "utilisées dans la langue choisie lorsqu’elles existent, sinon elles sont traduites "
            "automatiquement."))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_export_tab(), tr("Export"))
        self.tabs.addTab(self._build_html_tab(), tr("Apparence HTML"))
        self.tabs.addTab(self._build_editor_tab(), tr("Modifier un modèle"))
        layout.addWidget(self.tabs, 1)

        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.export_button = QPushButton(tr("Exporter"))
        self.export_button.clicked.connect(self._export)
        self.cancel_or_close_button = QPushButton(tr("Fermer"))
        self.cancel_or_close_button.clicked.connect(self._on_cancel_or_close)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.cancel_or_close_button)
        layout.addLayout(buttons)

        self._refresh_models()

    def _build_export_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "CSV"])
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        form.addRow(tr("Format d'export"), self.format_combo)

        language_row = QHBoxLayout()
        self.language_combo = QComboBox()
        for code, label in core.LANGUES:
            self.language_combo.addItem(tr(label), code)
        self.language_combo.addItem(tr("Autre langue (saisir le code)…"), OTHER_LANGUAGE)
        self.language_combo.setCurrentIndex(1 if is_french() else 2)
        self.language_combo.currentIndexChanged.connect(self._update_state)
        self.custom_language = QLineEdit()
        self.custom_language.setPlaceholderText(tr("code : sv, ko, pt-BR…"))
        self.custom_language.setMaximumWidth(150)
        language_row.addWidget(self.language_combo, 1)
        language_row.addWidget(self.custom_language)
        form.addRow(tr("Langue des descriptions"), language_row)

        self.verify_native_checkbox = QCheckBox(tr(
            "Vérifier la langue des descriptions déjà localisées (requêtes réseau supplémentaires)"))
        form.addRow("", self.verify_native_checkbox)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(tr("Choisir le fichier de destination…"))
        self.browse_button = QPushButton(tr("Parcourir…"))
        self.browse_button.clicked.connect(self._browse)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.browse_button)
        form.addRow(tr("Fichier de sortie"), output_row)
        layout.addLayout(form)

        fields_group = QGroupBox(tr("Champs à exporter"))
        fields_layout = QGridLayout(fields_group)
        self.field_checks = {}
        for index, column in enumerate(core.CSV_COLUMNS):
            check = QCheckBox(tr(COLUMN_NAMES[column]))
            check.setChecked(column in core.DEFAULT_CSV_COLUMNS)
            self.field_checks[column] = check
            fields_layout.addWidget(check, index // 3, index % 3)
        layout.addWidget(fields_group)

        self.csv_group = QGroupBox(tr("Options CSV"))
        csv_layout = QFormLayout(self.csv_group)
        self.separator = QLineEdit(";")
        self.separator.setMaxLength(2)
        self.separator.setMaximumWidth(60)
        csv_layout.addRow(tr("Séparateur CSV (un caractère ou \\t)"), self.separator)
        layout.addWidget(self.csv_group)

        layout.addStretch(1)
        return tab

    def _build_html_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.model_combo = QComboBox()
        form.addRow(tr("Modèle"), self.model_combo)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.import_button = QPushButton(tr("Importer un modèle…"))
        self.import_button.clicked.connect(self._import_model)
        self.folder_button = QPushButton(tr("Ouvrir le dossier de mes modèles"))
        self.folder_button.clicked.connect(self._open_models_folder)
        self.preview_button = QPushButton(tr("Aperçu dans le navigateur"))
        self.preview_button.clicked.connect(self._preview)
        actions.addWidget(self.import_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.preview_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addWidget(self._tokens_help_label())

        layout.addWidget(QLabel(tr("CSS additionnel (optionnel, ajouté après le style du modèle)")))
        self.extra_css = QPlainTextEdit()
        self.extra_css.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.extra_css.setMinimumHeight(70)
        layout.addWidget(self.extra_css, 1)
        return tab

    @staticmethod
    def _tokens_help_label():
        label = QLabel(tr(
            "Un modèle est une page HTML normale. Les balises s'écrivent entre doubles accolades : "
            "{{titre}} {{nombre}} {{libelle_nombre}} {{date}} {{lang}} et les en-têtes {{entete_nom}} "
            "{{entete_description}} {{entete_version}} {{entete_auteur}} {{entete_dossier}} "
            "{{entete_homepage}}. Le bloc placé entre les marqueurs LIGNE est répété pour chaque "
            "plugin et peut utiliser {{nom}} {{description}} {{version}} {{auteur}} {{dossier}} "
            "{{homepage}} {{numero}}. Un bloc entouré des marqueurs CHAMP suivis du nom d'un champ "
            "n'apparaît que si ce champ est coché."))
        label.setWordWrap(True)
        return label

    def _build_editor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.edit_combo = QComboBox()
        self.edit_combo.currentIndexChanged.connect(self._on_edit_combo_changed)
        form.addRow(tr("Modèle à modifier"), self.edit_combo)
        layout.addLayout(form)

        self.edit_info = QLabel()
        self.edit_info.setWordWrap(True)
        layout.addWidget(self.edit_info)

        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.editor.setMinimumHeight(220)
        self.highlighter = HtmlHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._on_editor_changed)
        layout.addWidget(self.editor, 1)

        actions = QHBoxLayout()
        self.new_button = QPushButton(tr("Nouveau"))
        self.new_button.clicked.connect(self._editor_new)
        self.save_button = QPushButton(tr("Enregistrer"))
        self.save_button.clicked.connect(self._editor_save)
        self.save_as_button = QPushButton(tr("Enregistrer sous…"))
        self.save_as_button.clicked.connect(self._editor_save_as)
        self.delete_button = QPushButton(tr("Supprimer"))
        self.delete_button.clicked.connect(self._editor_delete)
        self.editor_preview_button = QPushButton(tr("Aperçu dans le navigateur"))
        self.editor_preview_button.clicked.connect(self._editor_preview)
        for button in (self.new_button, self.save_button, self.save_as_button,
                       self.delete_button, self.editor_preview_button):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return tab

    # ------------------------------------------------------------------
    # Réglages mémorisés
    # ------------------------------------------------------------------
    def _load_settings(self):
        settings = QgsSettings()
        fmt_idx = settings.value(SETTINGS_PREFIX + "format_index", 0, type=int)
        if 0 <= fmt_idx < self.format_combo.count():
            self.format_combo.setCurrentIndex(fmt_idx)
        lang_idx = settings.value(SETTINGS_PREFIX + "lang_index", self.language_combo.currentIndex(), type=int)
        if 0 <= lang_idx < self.language_combo.count():
            self.language_combo.setCurrentIndex(lang_idx)
        output_path = settings.value(SETTINGS_PREFIX + "output_path", "", type=str)
        if output_path:
            self.output_edit.setText(output_path)
        self.custom_language.setText(settings.value(SETTINGS_PREFIX + "custom_language", "", type=str))
        self.separator.setText(settings.value(SETTINGS_PREFIX + "separator", ";", type=str) or ";")
        self.verify_native_checkbox.setChecked(
            settings.value(SETTINGS_PREFIX + "verify_native_lang", False, type=bool))

        model_key = settings.value(SETTINGS_PREFIX + "model", core.DEFAULT_MODEL, type=str)
        self._refresh_models(export_key=model_key, edit_key=model_key)
        self.extra_css.setPlainText(settings.value(SETTINGS_PREFIX + "extra_css", "", type=str))
        saved = settings.value(SETTINGS_PREFIX + "fields", "", type=str) \
            or settings.value(SETTINGS_PREFIX + "csv_columns", "", type=str)
        if saved:
            chosen = saved.split(",")
            for column, check in self.field_checks.items():
                check.setChecked(column in chosen)

    def _save_settings(self):
        settings = QgsSettings()
        settings.setValue(SETTINGS_PREFIX + "format_index", self.format_combo.currentIndex())
        settings.setValue(SETTINGS_PREFIX + "lang_index", self.language_combo.currentIndex())
        settings.setValue(SETTINGS_PREFIX + "output_path", self.output_edit.text().strip())
        settings.setValue(SETTINGS_PREFIX + "custom_language", self.custom_language.text().strip())
        settings.setValue(SETTINGS_PREFIX + "separator", self.separator.text())
        settings.setValue(SETTINGS_PREFIX + "verify_native_lang", self.verify_native_checkbox.isChecked())
        settings.setValue(SETTINGS_PREFIX + "model", self.model_combo.currentData())
        settings.setValue(SETTINGS_PREFIX + "extra_css", self.extra_css.toPlainText())
        settings.setValue(SETTINGS_PREFIX + "fields", ",".join(self._selected_fields()))

    # ------------------------------------------------------------------
    # État de l'interface
    # ------------------------------------------------------------------
    def _is_csv(self):
        return self.format_combo.currentIndex() == 1

    def _selected_fields(self):
        return [c for c in core.CSV_COLUMNS if self.field_checks[c].isChecked()]

    def _selected_language(self):
        data = self.language_combo.currentData()
        if data == OTHER_LANGUAGE:
            return self.custom_language.text().strip()
        return data or ""

    @staticmethod
    def _user_dir():
        return os.path.join(QgsApplication.qgisSettingsDirPath(), "ListePlugin", "modeles")

    def _update_state(self, *_args):
        is_csv = self._is_csv()
        self.csv_group.setVisible(is_csv)
        self.tabs.setTabEnabled(1, not is_csv)
        if is_csv and self.tabs.currentIndex() == 1:
            self.tabs.setCurrentIndex(0)
        self.custom_language.setVisible(self.language_combo.currentData() == OTHER_LANGUAGE)

    def _format_changed(self, _index):
        path = self.output_edit.text().strip()
        if path:
            self.output_edit.setText(core.fix_extension(path, self._is_csv()))
        self._update_state()

    def _request_cancel(self):
        self._canceled = True
        self.cancel_or_close_button.setEnabled(False)
        self.progress_label.setText(tr("Annulation en cours…"))

    def _on_cancel_or_close(self):
        if self._running:
            self._request_cancel()
        else:
            self.reject()

    def reject(self):
        if self._running:
            self._request_cancel()
            return
        if self._edit_dirty and not self._confirm(
                tr("Le modèle en cours d'édition n'est pas enregistré. Fermer quand même ?")):
            return
        super().reject()

    def _warn(self, text):
        QMessageBox.warning(self, self.windowTitle(), text)

    def _confirm(self, text):
        answer = QMessageBox.question(
            self, self.windowTitle(), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------
    # Fichier de sortie
    # ------------------------------------------------------------------
    def _browse(self):
        is_csv = self._is_csv()
        suffix = ".csv" if is_csv else ".html"
        current = self.output_edit.text().strip()
        if not current:
            current = os.path.join(QgsApplication.qgisSettingsDirPath(), "plugins_installes" + suffix)
        filters = (
            tr("Fichiers CSV (*.csv);;Tous les fichiers (*)")
            if is_csv
            else tr("Fichiers HTML (*.html *.htm);;Tous les fichiers (*)")
        )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, tr("Enregistrer la liste des plugins"), current, filters)
        if path:
            path = core.fix_extension(path, is_csv)
            self._browsed_path = path
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # Liste des modèles (fournis + les miens)
    # ------------------------------------------------------------------
    def _refresh_models(self, export_key=None, edit_key=None):
        export_key = export_key or self.model_combo.currentData() or core.DEFAULT_MODEL
        edit_key = edit_key or self.edit_combo.currentData() or core.DEFAULT_MODEL
        mine = core.user_models(self._user_dir())
        for combo, key in ((self.model_combo, export_key), (self.edit_combo, edit_key)):
            combo.blockSignals(True)
            combo.clear()
            for model_key, _filename, label in core.MODELS:
                combo.addItem(tr(label), model_key)
            for model_key, name, _path in mine:
                combo.addItem(tr("Mon modèle") + " – " + name, model_key)
            index = combo.findData(key)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    @staticmethod
    def _template_error_message(error):
        if error.key == "err_tpl_ext":
            return tr("Le modèle doit être un fichier .html ou .htm.")
        if error.key == "err_tpl_missing":
            return tr("Modèle introuvable : ") + error.detail
        if error.key == "err_tpl_size":
            return tr("Modèle trop volumineux (1 Mo maximum) : ") + error.detail
        if error.key == "err_tpl_name":
            return tr("Nom de modèle invalide.")
        return tr("Modèle invalide : il doit contenir un bloc entre deux marqueurs LIGNE.")

    def _template_text(self):
        return core.load_model_any(self.model_combo.currentData(), self._user_dir())

    def _import_model(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, tr("Importer un modèle…"), os.path.expanduser("~"), tr("Fichiers HTML (*.html *.htm)"))
        if not path:
            return
        try:
            key, saved_path = core.import_model(path, self._user_dir())
        except core.TemplateError as error:
            self._warn(self._template_error_message(error))
            return
        except OSError as error:
            QMessageBox.critical(self, self.windowTitle(), tr("Écriture impossible : ") + str(error))
            return
        self._refresh_models(export_key=key)
        QMessageBox.information(
            self, self.windowTitle(), tr("Modèle importé : ") + os.path.basename(saved_path))

    def _open_models_folder(self):
        directory = self._user_dir()
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(self, self.windowTitle(), tr("Écriture impossible : ") + str(error))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))

    # ------------------------------------------------------------------
    # Aperçu
    # ------------------------------------------------------------------
    def _open_preview(self, template):
        css = self.extra_css.toPlainText()
        if core.check_css(css):
            self._warn(tr("Le CSS additionnel ne doit pas contenir le caractère « < »."))
            return
        fields = self._selected_fields()
        if not fields:
            self._warn(tr("Cochez au moins un champ."))
            return
        lang = self._selected_language()
        labels = core.build_labels(lang)
        french = (lang or "fr").lower().startswith("fr")
        try:
            content = core.render_html(
                core.sample_plugins(french), labels, lang, template, css, fields=fields)
        except core.TemplateError as error:
            self._warn(self._template_error_message(error))
            return
        path = _PreviewStore.path()
        try:
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
        except OSError as error:
            QMessageBox.critical(self, self.windowTitle(), tr("Écriture impossible : ") + str(error))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _preview(self):
        try:
            template = self._template_text()
        except core.TemplateError as error:
            self._warn(self._template_error_message(error))
            return
        self._open_preview(template)

    # ------------------------------------------------------------------
    # Éditeur de modèle
    # ------------------------------------------------------------------
    def _on_editor_changed(self):
        if not self._loading_editor:
            self._edit_dirty = True
            self._update_editor_buttons()

    def _update_editor_buttons(self):
        user = core.is_user_model(self._edit_key)
        self.delete_button.setEnabled(user)
        if user:
            info = os.path.join(self._user_dir(), self._edit_key[len(core.USER_PREFIX):])
        elif self._edit_key is None:
            info = tr("Nouveau modèle (non enregistré).")
        else:
            info = tr("Modèle fourni : pour le modifier, utilisez « Enregistrer sous… » "
                      "(votre copie sera rangée dans votre profil QGIS).")
        if self._edit_dirty:
            info += " " + tr("(modifié)")
        self.edit_info.setText(info)

    def _load_into_editor(self, key):
        try:
            text = core.load_model_any(key, self._user_dir())
        except core.TemplateError as error:
            self._warn(self._template_error_message(error))
            return False
        self._loading_editor = True
        self.editor.setPlainText(text)
        self._loading_editor = False
        self._edit_key = key
        self._edit_dirty = False
        self._update_editor_buttons()
        return True

    def _discard_changes_ok(self):
        return not self._edit_dirty or self._confirm(
            tr("Les modifications non enregistrées seront perdues. Continuer ?"))

    def _select_edit_key(self, key):
        self.edit_combo.blockSignals(True)
        index = self.edit_combo.findData(key)
        if index >= 0:
            self.edit_combo.setCurrentIndex(index)
        self.edit_combo.blockSignals(False)

    def _on_edit_combo_changed(self, _index):
        if not self._discard_changes_ok():
            self._select_edit_key(self._edit_key)
            return
        self._load_into_editor(self.edit_combo.currentData())

    def _editor_new(self):
        if not self._discard_changes_ok():
            return
        self._loading_editor = True
        self.editor.setPlainText(core.NEW_MODEL_TEXT)
        self._loading_editor = False
        self._edit_key = None
        self._edit_dirty = True
        self._update_editor_buttons()

    def _after_save(self, key):
        self._refresh_models(export_key=key, edit_key=key)
        self._edit_key = key
        self._edit_dirty = False
        self._update_editor_buttons()

    def _write_model(self, filename):
        try:
            key, _path = core.save_user_model(self._user_dir(), filename, self.editor.toPlainText())
        except core.TemplateError as error:
            self._warn(self._template_error_message(error))
            return False
        except OSError as error:
            QMessageBox.critical(self, self.windowTitle(), tr("Écriture impossible : ") + str(error))
            return False
        self._after_save(key)
        return True

    def _editor_save(self):
        if core.is_user_model(self._edit_key):
            self._write_model(self._edit_key[len(core.USER_PREFIX):])
        else:
            self._editor_save_as()

    def _editor_save_as(self):
        if core.is_user_model(self._edit_key):
            default = os.path.splitext(self._edit_key[len(core.USER_PREFIX):])[0]
        elif self._edit_key is None:
            default = "mon_modele"
        else:
            default = self.edit_combo.currentText() + " (copie)"
        name, accepted = QInputDialog.getText(
            self, tr("Enregistrer le modèle"), tr("Nom du modèle :"), QLineEdit.EchoMode.Normal, default)
        if not accepted:
            return
        filename = core.safe_filename(name)
        if not filename:
            self._warn(tr("Nom de modèle invalide."))
            return
        exists = os.path.exists(os.path.join(self._user_dir(), filename))
        same = core.is_user_model(self._edit_key) and self._edit_key[len(core.USER_PREFIX):] == filename
        if exists and not same and not self._confirm(tr("Un modèle de ce nom existe déjà. Le remplacer ?")):
            return
        self._write_model(filename)

    def _editor_delete(self):
        if not core.is_user_model(self._edit_key):
            return
        if not self._confirm(tr("Supprimer définitivement ce modèle ?")):
            return
        try:
            core.delete_user_model(self._user_dir(), self._edit_key)
        except (core.TemplateError, OSError) as error:
            self._warn(str(error))
            return
        self._edit_dirty = False
        self._refresh_models(export_key=core.DEFAULT_MODEL, edit_key=core.DEFAULT_MODEL)
        self._load_into_editor(core.DEFAULT_MODEL)

    def _editor_preview(self):
        template = self.editor.toPlainText()
        try:
            core.parse_template(template)
        except core.TemplateError as error:
            self._warn(self._template_error_message(error))
            return
        self._open_preview(template)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _validate_export_inputs(self):
        is_csv = self._is_csv()
        output = self.output_edit.text().strip()
        if not output:
            self._warn(tr("Veuillez choisir un fichier de sortie."))
            return None
        output = core.fix_extension(output, is_csv)
        self.output_edit.setText(output)

        lang = self._selected_language()
        if self.language_combo.currentData() == OTHER_LANGUAGE and not lang:
            self._warn(tr("Saisissez un code de langue (exemples : fr, sv, pt-BR, zh-CN)."))
            return None
        error_key = core.check_options(lang, self.separator.text())
        if error_key == "err_lang":
            self._warn(tr("Code langue invalide (exemples : fr, sv, pt-BR, zh-CN)."))
            return None
        if is_csv and error_key == "err_sep":
            self._warn(tr("Le séparateur CSV doit être un seul caractère ou \\t."))
            return None

        fields = self._selected_fields()
        if not fields:
            self._warn(tr("Cochez au moins un champ."))
            return None
        template = ""
        css = ""
        if not is_csv:
            try:
                template = self._template_text()
            except core.TemplateError as error:
                self._warn(self._template_error_message(error))
                return None
            css = self.extra_css.toPlainText()
            if core.check_css(css):
                self._warn(tr("Le CSS additionnel ne doit pas contenir le caractère « < »."))
                return None

        plugins_dir = os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins")
        if not os.path.isdir(plugins_dir):
            QMessageBox.critical(self, self.windowTitle(), tr("Dossier des plugins introuvable : ") + plugins_dir)
            return None

        if os.path.exists(output) and os.path.abspath(output) != os.path.abspath(self._browsed_path or ""):
            if not self._confirm(tr("Le fichier existe déjà. Le remplacer ?")):
                return None

        return {
            "output": output,
            "is_csv": is_csv,
            "lang": lang,
            "sep": core.normalize_separator(self.separator.text()),
            "fields": fields,
            "template": template,
            "css": css,
            "plugins_dir": plugins_dir,
        }

    def _write_output_file(self, options, plugins):
        output = options["output"]
        target_dir = os.path.dirname(os.path.abspath(output))
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        if options["is_csv"]:
            content = core.render_csv(plugins, self._current_labels, options["sep"], options["fields"])
            with open(output, "w", encoding="utf-8-sig", newline="") as stream:
                stream.write(content)
        else:
            content = core.render_html(
                plugins, self._current_labels, options["lang"], options["template"], options["css"],
                fields=options["fields"])
            with open(output, "w", encoding="utf-8") as stream:
                stream.write(content)

    @staticmethod
    def _label_keys(options):
        if options["is_csv"]:
            return {core.COLUMN_LABEL_KEY[c] for c in options["fields"]}
        return core.template_label_keys(options["template"], options["fields"])

    def _set_running(self, running):
        self._running = running
        self.export_button.setEnabled(not running)
        self.cancel_or_close_button.setText(tr("Annuler") if running else tr("Fermer"))
        self.cancel_or_close_button.setEnabled(True)
        self.progress_bar.setVisible(running)
        self.progress_label.setVisible(running)

    def _export(self):
        options = self._validate_export_inputs()
        if not options:
            return
        self._save_settings()
        self._canceled = False
        self._set_running(True)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(tr("Lecture des extensions installées…"))
        QApplication.processEvents()

        lang = options["lang"]
        # sans le champ « description », inutile de traduire les descriptions
        description_lang = lang if "description" in options["fields"] else ""
        try:
            plugins, warnings = core.collect_plugins(options["plugins_dir"])
            translator = Translator() if lang else None
            self._current_labels = core.build_labels(lang, translator, self._label_keys(options))
            self.progress_bar.setRange(0, max(1, len(plugins)))
            self.progress_bar.setValue(0)
            self.progress_label.setText(tr("Analyse et traduction des descriptions…"))
            QApplication.processEvents()

            def update_progress(current, total):
                self.progress_bar.setRange(0, max(1, total))
                self.progress_bar.setValue(current)
                self.progress_label.setText(
                    tr("Traitement des extensions : {current}/{total}").format(current=current, total=total))
                QApplication.processEvents()

            stats = core.resolve_descriptions(
                plugins, description_lang, translator, self._current_labels,
                is_canceled=lambda: self._canceled,
                on_progress=update_progress,
                verify_native_lang=self.verify_native_checkbox.isChecked(),
            )
            if self._canceled:
                QMessageBox.information(self, self.windowTitle(), tr("Export annulé."))
                return

            self.progress_label.setText(tr("Création du fichier d’export…"))
            QApplication.processEvents()
            self._write_output_file(options, plugins)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self.windowTitle(), tr("Échec de l'export : ") + str(exc))
            return
        finally:
            self._set_running(False)

        message = tr(
            "Export terminé : {n} plugin(s).\nFichier : {path}\n"
            "Descriptions : {native} natives, {translated} traduites, {failed} non traduites."
        ).format(n=len(plugins), path=options["output"],
                 native=stats["natif"], translated=stats["traduit"], failed=stats["echec"])
        if warnings:
            message += (
                "\n\n" + tr("Métadonnées ignorées ou incomplètes :") + "\n"
                + "\n".join(f"{folder} : {reason}" for folder, reason in warnings[:10])
            )

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(self.windowTitle())
        msg_box.setText(message)
        open_btn = msg_box.addButton(tr("Ouvrir le fichier"), QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton(QMessageBox.StandardButton.Ok)
        exec_fn = getattr(msg_box, "exec", None) or msg_box.exec_
        exec_fn()
        if msg_box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(options["output"])))
