# Liste Plugin

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-green)](https://qgis.org/)

## Français

**Liste Plugin** est une extension QGIS qui exporte la liste des extensions installées au format **HTML** ou **CSV**. Elle est accessible depuis **Extensions → Liste Plugin** et depuis une icône dans la barre d’outils.

La fenêtre d’export s’affiche dans une présentation compacte. Les options avancées permettent de personnaliser la langue des descriptions, le séparateur CSV, le CSS et les modèles HTML. Les descriptions localisées fournies par les extensions sont utilisées en priorité. Si la description localisée est absente ou manifestement rédigée dans une autre langue, une traduction automatique est tentée. Une erreur de traduction sur une extension n’interrompt pas l’export des autres.

### Fonctionnalités

- Export de la liste des extensions installées en HTML ou CSV.
- Choix de la langue des descriptions et code de langue personnalisé.
- Traduction automatique de secours, avec gestion individuelle des erreurs.
- Barre de progression pendant l’analyse, la traduction et la génération du fichier.
- Personnalisation du séparateur CSV, du CSS et des modèles HTML.
- Accès depuis le menu Extensions et la barre d’outils QGIS.

### Installation

1. Téléchargez l’archive ZIP depuis la page [Releases](https://github.com/shenri52/qgis-plugin-liste/releases).
2. Dans QGIS, ouvrez **Extensions → Installer/Gérer les extensions → Installer depuis un ZIP**.
3. Sélectionnez l’archive téléchargée.

### Historique des versions

- **1.2.6** – Correction des alertes d’analyse de sécurité (Bandit) et sécurisation de la gestion des fichiers et dossiers.
- **1.2.5** – Correction des avertissements d'analyse de sécurité (Bandit) et compatibilité Qt6 renforcée.
- **1.2.4** – Poignées de redimensionnement visibles et fenêtre agrandie à l’ouverture des options avancées pour ajuster les zones de texte.
- **1.2.3** – Les zones de texte du CSS et des modèles HTML peuvent être agrandies indépendamment en déplaçant les séparateurs.
- **1.2.2** – Les champs CSS, modèle de page et modèle de ligne des options avancées sont préremplis avec les paramètres HTML par défaut actuellement utilisés.
- **1.2.1** – Suppression du changelog bilingue dupliqué dans les métadonnées ; ajout des coordonnées et liens du projet ; documentation mise à jour.
- **1.2.0** – Fenêtre compacte avec icône et titre ; barre de progression ; détection des descriptions localisées dans une langue incorrecte ; correction de l’affichage des options avancées.
- **1.1.0** – Entrée dans le menu Extensions et icône de barre d’outils ; aide adaptée à la langue du système ; correction de l’extension du fichier CSV ; traduction automatique plus robuste.
- **1.0.0** – Première version.

## English

**Liste Plugin** is a QGIS plugin that exports the list of installed plugins to **HTML** or **CSV**. It is available from **Plugins → Liste Plugin** and from a toolbar icon.

The export dialog opens in a compact layout. Advanced options let users customize description language, CSV delimiter, CSS and HTML templates. Localized descriptions supplied by plugins are preferred. If a localized description is missing or appears to be written in a different language, automatic translation is attempted. A translation failure for one plugin does not stop the export of the others.

### Features

- Export installed plugins to HTML or CSV.
- Select the description language or provide a custom language code.
- Automatic fallback translation with per-plugin error handling.
- Progress indicator during scanning, translation and file generation.
- Customize the CSV delimiter, CSS and HTML templates.
- Access from the QGIS Plugins menu and toolbar.

### Installation

1. Download the ZIP archive from the [Releases page](https://github.com/shenri52/qgis-plugin-liste/releases).
2. In QGIS, open **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the downloaded archive.

### Version history
- **1.2.6** – Resolve Bandit static analysis findings and harden file/directory handling.
- **1.2.5** – Fix security scan warnings (Bandit) and improve Qt6 compatibility.
- **1.2.4** – Visible resize handles and dialog expansion when advanced options are opened, allowing the text areas to be resized.
- **1.2.3** – CSS and HTML template text areas can be resized independently by dragging the splitters.
- **1.2.2** – Advanced CSS, page template and row template fields are prefilled with the currently active HTML defaults.
- **1.2.1** – Remove duplicated bilingual changelog text from metadata; add project links and author details; update documentation.
- **1.2.0** – Compact dialog with icon and title; progress indicator; detection of localized descriptions written in the wrong language; advanced options visibility fix.
- **1.1.0** – Plugins menu entry and toolbar icon; system-language dialog help; CSV file extension fix; more resilient automatic translation.
- **1.0.0** – Initial release.

## License

GPL-2.0. See [LICENSE](LICENSE).

## Project links

- Source code: https://github.com/shenri52/qgis-plugin-liste
- Issue tracker: https://github.com/shenri52/qgis-plugin-liste/issues
