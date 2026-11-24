# -*- coding: utf-8 -*-
"""Fenêtre principale de Liste Plugin (menu Extensions et barre d'outils)."""
import json
import os
from urllib.parse import quote, urlencode

from qgis.PyQt.QtCore import QLocale, QUrl, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QPlainTextEdit, QVBoxLayout,
    QProgressBar, QApplication, QSplitter, QWidget,
)
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import (
    QgsApplication, QgsBlockingNetworkRequest,
)

from . import core


class _Translator:
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
        # Deux tentatives : une panne ponctuelle ne condamne pas la description.
        for _ in range(2):
            blocking = QgsBlockingNetworkRequest()
            error = blocking.get(request, False)
            if error == getattr(getattr(QgsBlockingNetworkRequest, "ErrorCode", QgsBlockingNetworkRequest), "NoError"):
                try:
                    data = json.loads(bytes(blocking.reply().content()).decode("utf-8"))
                    result = "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
                    self.last_source_language = data[2] if len(data) > 2 else None
                    if result:
                        return result
                except Exception:  # noqa: BLE001
                    pass
        return None


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Liste des plugins installés"))
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.png")))
        self.setMinimumWidth(650)
        self.setMaximumWidth(760)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        is_french = QLocale.system().name().lower().startswith("fr")

        # Compact application header: plugin icon and application name.
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(os.path.join(os.path.dirname(__file__), "icon.png")).pixmap(32, 32))
        header.addWidget(logo)
        app_name = QLabel(self.tr("Liste des plugins installés"))
        app_name.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(app_name)
        header.addStretch(1)
        layout.addLayout(header)
        help_text = ("Exporte la liste des extensions QGIS installées en HTML ou CSV. "
                     "Les descriptions sont utilisées dans la langue choisie lorsqu’elles existent, "
                     "sinon elles sont traduites automatiquement." if is_french else
                     "Exports the list of installed QGIS plugins as HTML or CSV. "
                     "Descriptions use the selected language when available and are otherwise "
                     "translated automatically.")
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        form = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "CSV"])
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        form.addRow(self.tr("Format d'export"), self.format_combo)

        self.language_combo = QComboBox()
        for code, label in core.LANGUES:
            self.language_combo.addItem(label, code)
        default = 1 if QLocale.system().name().lower().startswith("fr") else 2
        self.language_combo.setCurrentIndex(default)
        form.addRow(self.tr("Langue des descriptions"), self.language_combo)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(self.tr("Choisir le fichier de destination…"))
        self.browse_button = QPushButton(self.tr("Parcourir…"))
        self.browse_button.clicked.connect(self._browse)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.browse_button)
        form.addRow(self.tr("Fichier de sortie"), output_row)
        layout.addLayout(form)

        self.advanced_toggle = QPushButton(self.tr("Options avancées ▸"))
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        layout.addWidget(self.advanced_toggle)

        self.advanced = QVBoxLayout()
        self.advanced_widgets = []
        self.custom_language = QLineEdit()
        self.custom_language.setPlaceholderText("fr, sv, pt-BR…")
        self.separator = QLineEdit(";")
        self.separator.setMaxLength(2)
        self.css = QPlainTextEdit()
        self.css.setPlaceholderText(self.tr("CSS personnalisé (HTML uniquement)"))
        # Préremplir les champs avec les paramètres réellement utilisés par
        # l'export HTML lorsque l'utilisateur ne fournit aucune personnalisation.
        self.css.setPlainText(core.DEFAULT_CSS)
        self.page_template = QPlainTextEdit()
        self.page_template.setPlaceholderText(self.tr("Modèle de page HTML (balises : {lang} {titre} {css} {entete_nom} {entete_description} {lignes})"))
        self.page_template.setPlainText(core.DEFAULT_PAGE)
        self.row_template = QPlainTextEdit()
        self.row_template.setPlaceholderText(self.tr("Modèle de ligne HTML (balises : {nom} {description} {version} {auteur} {dossier} {homepage})"))
        self.row_template.setPlainText(core.DEFAULT_ROW)
        for label, widget in [
            (self.tr("Code langue personnalisé"), self.custom_language),
            (self.tr("Séparateur CSV (un caractère ou \\t)"), self.separator),
        ]:
            label_widget = QLabel(label)
            self.advanced.addWidget(label_widget)
            self.advanced.addWidget(widget)
            self.advanced_widgets.extend([label_widget, widget])

        # Les trois zones HTML sont placées dans un séparateur vertical :
        # l'utilisateur peut déplacer les poignées entre les zones pour
        # agrandir celle qu'il souhaite modifier.
        self.html_editors_splitter = QSplitter(Qt.Vertical)
        self.html_editors_splitter.setChildrenCollapsible(False)
        for label, editor in [
            (self.tr("CSS personnalisé"), self.css),
            (self.tr("Modèle de page HTML"), self.page_template),
            (self.tr("Modèle de ligne HTML"), self.row_template),
        ]:
            editor_group = QWidget()
            editor_layout = QVBoxLayout(editor_group)
            editor_layout.setContentsMargins(0, 2, 0, 2)
            editor_layout.setSpacing(3)
            label_widget = QLabel(label)
            editor_layout.addWidget(label_widget)
            editor.setMinimumHeight(85)
            editor.setLineWrapMode(QPlainTextEdit.NoWrap)
            editor_layout.addWidget(editor, 1)
            self.html_editors_splitter.addWidget(editor_group)
            self.advanced_widgets.append(editor_group)
        self.html_editors_splitter.setSizes([130, 180, 130])
        self.advanced.addWidget(self.html_editors_splitter, 1)
        self.advanced_widgets.append(self.html_editors_splitter)
        layout.addLayout(self.advanced)
        self._toggle_advanced(False)

        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.export_button = QPushButton(self.tr("Exporter"))
        self.export_button.clicked.connect(self._export)
        close_button = QPushButton(self.tr("Fermer"))
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self.export_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _toggle_advanced(self, checked):
        self.advanced_toggle.setText(self.tr("Options avancées ▾") if checked else self.tr("Options avancées ▸"))
        for widget in self.advanced_widgets:
            widget.setVisible(checked)

    def _suffix(self):
        return ".csv" if self.format_combo.currentIndex() == 1 else ".html"

    def _format_changed(self, _index):
        path = self.output_edit.text().strip()
        if path:
            root, ext = os.path.splitext(path)
            if ext.lower() in (".csv", ".html", ".htm"):
                self.output_edit.setText(root + self._suffix())

    def _browse(self):
        suffix = self._suffix()
        current = self.output_edit.text().strip()
        if not current:
            current = os.path.join(QgsApplication.qgisSettingsDirPath(), "plugins_installes" + suffix)
        filters = self.tr("Fichiers CSV (*.csv);;Tous les fichiers (*)") if suffix == ".csv" else self.tr("Fichiers HTML (*.html *.htm);;Tous les fichiers (*)")
        path, selected_filter = QFileDialog.getSaveFileName(self, self.tr("Enregistrer la liste des plugins"), current, filters)
        if path:
            root, ext = os.path.splitext(path)
            # L'extension est toujours cohérente avec le format sélectionné.
            if ext.lower() in (".csv", ".html", ".htm"):
                path = root + suffix
            elif not ext:
                path += suffix
            self.output_edit.setText(path)

    def _export(self):
        output = self.output_edit.text().strip()
        if not output:
            QMessageBox.warning(self, self.windowTitle(), self.tr("Veuillez choisir un fichier de sortie."))
            return
        suffix = self._suffix()
        root, ext = os.path.splitext(output)
        if ext.lower() in (".csv", ".html", ".htm"):
            output = root + suffix
        elif not ext:
            output += suffix
        self.output_edit.setText(output)

        lang = (self.custom_language.text().strip() or self.language_combo.currentData() or "")
        if lang and not __import__("re").fullmatch(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?", lang):
            QMessageBox.warning(self, self.windowTitle(), self.tr("Code langue invalide (exemples : fr, sv, pt-BR, zh-CN)."))
            return
        sep = self.separator.text()
        if sep == r"\t":
            sep = "\t"
        if not sep:
            sep = ";"
        if len(sep) != 1:
            QMessageBox.warning(self, self.windowTitle(), self.tr("Le séparateur CSV doit être un seul caractère ou \\t."))
            return
        page_tpl = self.page_template.toPlainText().strip()
        if page_tpl and "{lignes}" not in page_tpl:
            QMessageBox.warning(self, self.windowTitle(), self.tr("Le modèle de page doit contenir la balise {lignes}."))
            return

        plugins_dir = os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins")
        if not os.path.isdir(plugins_dir):
            QMessageBox.critical(self, self.windowTitle(), self.tr("Dossier des plugins introuvable : ") + plugins_dir)
            return
        self.export_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(self.tr("Lecture des extensions installées…"))
        QApplication.processEvents()
        try:
            plugins, warnings = core.collect_plugins(plugins_dir)
            translator = _Translator() if lang else None
            labels = core.build_labels(lang, translator)
            self.progress_bar.setRange(0, max(1, len(plugins)))
            self.progress_bar.setValue(0)
            self.progress_label.setText(self.tr("Analyse et traduction des descriptions…"))
            QApplication.processEvents()

            def update_progress(current, total):
                self.progress_bar.setRange(0, max(1, total))
                self.progress_bar.setValue(current)
                self.progress_label.setText(
                    self.tr("Traitement des extensions : {current}/{total}").format(
                        current=current, total=total
                    )
                )
                QApplication.processEvents()

            stats = core.resolve_descriptions(
                plugins, lang, translator, labels, on_progress=update_progress
            )
            self.progress_label.setText(self.tr("Création du fichier d’export…"))
            QApplication.processEvents()
            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
            if suffix == ".csv":
                content = core.render_csv(plugins, labels, sep)
                with open(output, "w", encoding="utf-8-sig", newline="") as stream:
                    stream.write(content)
            else:
                content = core.render_html(plugins, labels, lang,
                    css=self.css.toPlainText(), page_tpl=page_tpl,
                    row_tpl=self.row_template.toPlainText())
                with open(output, "w", encoding="utf-8") as stream:
                    stream.write(content)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self.windowTitle(), self.tr("Échec de l'export : ") + str(exc))
            return
        finally:
            self.export_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

        message = self.tr("Export terminé : {n} plugin(s).\nFichier : {path}\nDescriptions : {native} natives, {translated} traduites, {failed} non traduites.").format(
            n=len(plugins), path=output, native=stats["natif"], translated=stats["traduit"], failed=stats["echec"])
        if warnings:
            message += "\n\n" + self.tr("Métadonnées ignorées ou incomplètes :") + "\n" + "\n".join(f"{folder} : {reason}" for folder, reason in warnings[:10])
        QMessageBox.information(self, self.windowTitle(), message)
