# Guide d'import Anki

Ce guide explique comment importer les fichiers `.anki.csv` ou `.anki.txt`
générés par md-converter dans Anki Desktop.

## Prérequis

- [Anki Desktop](https://apps.ankiweb.net/) installé (version 2.1+)

## Import d'un fichier CSV

1. Ouvrir Anki Desktop
2. Menu **Fichier → Importer…** (ou `Ctrl+I` / `Cmd+I`)
3. Sélectionner votre fichier `.anki.csv`
4. Dans la fenêtre d'import :
   - **Type de note** : Basic
   - **Deck** : choisir ou créer un deck (ex : `Cours > Maths`)
   - **Séparateur de champs** : Point-virgule (`;`)
   - **Encodage** : UTF-8
   - Cocher **Autoriser le HTML dans les champs**
5. Vérifier le mapping des colonnes :
   - Colonne 1 (`front`) → **Recto**
   - Colonne 2 (`back`) → **Verso**
   - Colonnes 3-5 (`tags`, `source`, `card_type`) → **Ignorer** ou mapper vers Tag
6. Cliquer **Importer**

## Import d'un fichier TXT

Même procédure, avec **Séparateur de champs** : Tabulation.

## Conseils

- Créez un deck par matière pour mieux organiser vos révisions.
- Les tags `section:*` et `source:*` permettent de filtrer par chapitre dans le navigateur Anki.
- Après import, utilisez **Outils → Vérifier la base de données** si vous constatez des anomalies.

## Réglages recommandés pour les nouveaux decks

| Paramètre | Valeur recommandée |
|---|---|
| Nouvelles cartes / jour | 20 |
| Révisions maximales / jour | 200 |
| Intervalle de graduation | 1 jour |
| Multiplicateur d'intervalle | 2.5 |
