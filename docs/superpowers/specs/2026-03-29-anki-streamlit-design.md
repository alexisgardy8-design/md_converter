# Spec : Génération de decks Anki + Frontend Streamlit

**Date :** 2026-03-29
**Statut :** Approuvé
**Scope :** Extension du pipeline md-converter — étape `md → Anki` + interface Streamlit localhost

---

## 1. Contexte

Le pipeline existant convertit des PDFs en Markdown structuré (`convert.py` → `pipeline.py`).
Cette extension ajoute deux choses :

1. Un module de génération de cartes Anki à partir du Markdown produit
2. Un frontend Streamlit (localhost) pour uploader un PDF, le convertir et télécharger les résultats

---

## 2. Architecture

```
convert.py
  └─ _convert_one()
       ├─ convert_pdf()                     → (markdown, report)   [existant, inchangé]
       └─ _generate_anki()                  [nouveau]
            ├─ anki_generator.generate_deck(markdown, source_name, options)
            │    └─ list[AnkiCard]
            └─ anki_exporter.export_deck(cards, output_path, format, separator)
                 └─ .anki.csv et/ou .anki.txt

app.py                                      [nouveau — Streamlit localhost]
  └─ appelle convert_pdf() + generate_deck() + export_deck() en mémoire
```

### Nouveaux fichiers

```
md_converter/
  anki_generator.py    # Markdown → list[AnkiCard]
  anki_exporter.py     # list[AnkiCard] → CSV / TXT

tests/
  test_anki_generator.py
  test_anki_exporter.py

app.py                 # Streamlit frontend (localhost)
.streamlit/
  config.toml          # thème custom

docs/
  ANKI_IMPORT_GUIDE.md # guide d'import Anki étape par étape
```

### Flux de données

```
PDF (upload ou input/)
  → convert_pdf()       → markdown (str), report
  → generate_deck()     → list[AnkiCard]
  → export_deck()       → .anki.csv / .anki.txt
```

### Règle de dépendance (inchangée)

`cli/convert.py / app.py → pipeline → {extractor, ocr, cleaner, structure, renderer, optimizer, reporter, anki_generator, anki_exporter}`

---

## 3. Modèle de données

```python
@dataclass
class AnkiCard:
    front: str           # question pédagogique
    back: str            # réponse complète
    card_type: str       # voir section 4
    tags: list[str]      # ["cours", "section:Introduction", "source:Lecture1_TD1"]
    source: str          # "Lecture1_TD1 — Introduction"
```

---

## 4. Génération des cartes — deux niveaux

### Niveau 1 — Extraction d'atomes de connaissance (`KnowledgeUnit`)

Le document Markdown est d'abord segmenté en `Section(heading, content, level)`.
Chaque section est analysée pour détecter les catégories sémantiques suivantes :

| Catégorie | Signaux FR/EN |
|---|---|
| `definition` | "est un/une", "on appelle", "désigne", "is a", "refers to", `X : Y` en gras |
| `theorem` | "théorème", "lemme", "corollaire", "theorem", "lemma", "corollary" |
| `property` | "propriété", "property", "caractéristique" |
| `formula` | `=`, `\`, blocs code, notation mathématique |
| `method` | liste ordonnée + "étapes", "algorithme", "procédure", "steps", "algorithm" |
| `cause` | "parce que", "car", "puisque", "because", "due to", "caused by" |
| `consequence` | "donc", "ainsi", "entraîne", "therefore", "results in", "leads to" |
| `condition` | "si et seulement si", "condition", "hypothèse", "if and only if", "given that" |
| `comparison` | "contrairement à", "alors que", "différence", "vs", "unlike", "whereas" |
| `example` | "par exemple", "exemple :", "e.g.", "for example", "such as" |
| `enumeration` | liste bullet sous un concept |
| `purpose` | "permet de", "sert à", "l'objectif est", "enables", "allows", "used to" |
| `exception` | "sauf", "exception", "limite", "except", "unless", "however" |
| `actor` | noms propres, "fondé par", "créé par", "founded by", "created by" |
| `event_date` | regex années `\b(1[0-9]{3}\|20[0-9]{2})\b`, "en [année]", "in [year]" |
| `application` | "utilisé en", "appliqué à", "used in", "applied to", "domain" |

### Niveau 2 — Bibliothèque de templates de questions (20+)

| Template | Question |
|---|---|
| `what_is` | "Qu'est-ce que {sujet} ?" |
| `define` | "Définir {sujet}" |
| `why` | "À quoi sert {sujet} ?" |
| `how` | "Comment fonctionne {sujet} ?" |
| `when_use` | "Dans quel cas utilise-t-on {sujet} ?" |
| `list_what` | "Quels sont les {éléments} de {sujet} ?" |
| `steps` | "Quelles sont les étapes pour {sujet} ?" |
| `difference` | "Quelle est la différence entre {A} et {B} ?" |
| `give_example` | "Donner un exemple de {sujet}" |
| `consequence` | "Quelles sont les conséquences de {sujet} ?" |
| `condition` | "Quelles sont les conditions pour {sujet} ?" |
| `state_thm` | "Énoncer le théorème / la propriété {nom}" |
| `hypotheses` | "Quelles sont les hypothèses de {sujet} ?" |
| `formula` | "Donner la formule de {sujet}" |
| `prove_why` | "Justifier pourquoi {sujet}" |
| `who_is` | "Qui est {acteur} ?" |
| `who_did` | "Qui a {action} ?" |
| `when_event` | "Quand {événement} ?" |
| `cause_of` | "Quelles sont les causes de {sujet} ?" |
| `limits` | "Quelles sont les limites / exceptions de {sujet} ?" |
| `apply_to` | "Dans quels domaines s'applique {sujet} ?" |
| `recall_key` | "Citer les points clés de {section}" |

Un même paragraphe peut générer 2-3 cartes de types différents (ex: theorem → `state_thm` + `hypotheses` + `condition`).

### Sélection des templates par catégorie détectée

```
definition   → what_is, define, give_example
theorem      → state_thm, hypotheses, condition, prove_why
property     → list_what, condition, limits
formula      → formula, when_use, apply_to
method       → steps, when_use, how
cause        → cause_of, consequence
consequence  → consequence, condition
condition    → condition, when_use, limits
comparison   → difference
example      → give_example, apply_to
enumeration  → list_what, recall_key
purpose      → why, apply_to, how
exception    → limits, when_use
actor        → who_is, who_did
event_date   → when_event, cause_of
application  → apply_to, when_use
(fallback)   → recall_key
```

### Multi-langue

Détection automatique FR/EN par comptage des mots-clés. Patterns et templates disponibles dans les deux langues.

---

## 5. Filtres qualité

| Filtre | Valeur par défaut |
|---|---|
| `front` vide | rejeté |
| `back` < `min_answer_length` chars | rejeté (défaut : 20) |
| Réponse = "oui/non/vrai/faux" seul | rejeté |
| Doublons exacts `(front, back)` | dédupliqués |
| Max cartes par section | 5 (configurable) |

Les cartes excédentaires sont triées par richesse (`len(back)` décroissant) — on garde les plus denses.

---

## 6. Export

### CSV (`.anki.csv`)
- Séparateur configurable (défaut `;`)
- Colonnes : `front;back;tags;source`
- Guillemets doublés pour l'échappement (`"` → `""`)
- Retours ligne dans les champs encodés (`\n` → espace ou `<br>` selon option)
- Encodage UTF-8

### TXT (`.anki.txt`)
- Séparateur configurable (défaut `\t`)
- Même colonnes, même ordre
- Encodage UTF-8

### Nommage des fichiers
```
output/<subpath>/<filename>.anki.csv
output/<subpath>/<filename>.anki.txt
```

---

## 7. CLI — nouveaux flags `convert.py`

| Flag | Défaut | Description |
|---|---|---|
| `--anki` | off | Active la génération de deck |
| `--anki-format csv\|txt\|both` | `csv` | Format(s) d'export |
| `--anki-separator SEP` | `;` | Séparateur CSV/TXT |
| `--anki-regenerate` | off | Régénère même si MD skippé |
| `--anki-max-cards N` | `5` | Max cartes par section |
| `--anki-min-length N` | `20` | Longueur min réponse (chars) |

### Règles d'idempotence

| État | `--anki` | `--anki-regenerate` | Comportement |
|---|---|---|---|
| MD absent | ✓ | any | Convertit MD + génère deck |
| MD présent (skip) | ✓ | off | Skip MD + skip deck |
| MD présent (skip) | ✓ | on | Skip MD + régénère deck depuis .md existant |
| `--force` | ✓ | any | Reconvertit MD + régénère deck |

### Logs

```
[ANKI]  Lecture1_TD1  →  42 cartes générées, 8 filtrées  →  output/Lecture1_TD1.anki.csv
```

---

## 8. Frontend Streamlit (localhost)

### Lancement
```bash
streamlit run app.py
```

### Esthétique — Editorial sombre / académique premium
- Fond : `#0f0f14` (noir profond)
- Accent : `#f0a500` (ambre doré)
- Titres : Playfair Display (serif)
- Corps / labels : IBM Plex Sans
- Code / markdown preview : JetBrains Mono
- CSS injecté via `st.markdown("<style>…</style>", unsafe_allow_html=True)`
- Thème de base dans `.streamlit/config.toml`

### Flux interface

```
┌─────────────────────────────────────────────────┐
│  PDF → Anki   [nav bar élégante]                │
├──────────────┬──────────────────────────────────┤
│  UPLOAD      │  OPTIONS                         │
│  Drop zone   │  Mode : Fidelity / Compact       │
│  stylisée    │  Format : CSV / TXT / Les deux   │
│              │  Max cartes/section [slider]     │
│              │  Longueur min réponse [slider]   │
│              │  [  Convertir  ]                 │
├──────────────┴──────────────────────────────────┤
│  RÉSULTATS                                      │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Markdown     │  │ Cartes Anki              │ │
│  │ preview      │  │ flashcards avec badges   │ │
│  │ (scrollable) │  │ type + front/back        │ │
│  │ [↓ .md]      │  │ [↓ .csv] [↓ .txt]        │ │
│  └──────────────┘  └──────────────────────────┘ │
│  Stats : X cartes, Y filtrées, Z secondes        │
└─────────────────────────────────────────────────┘
```

### Composants clés
- **Drop zone** : animée, border gradient au hover
- **Barre de progression** : étapes nommées (Détection → Extraction → Nettoyage → Anki)
- **Cartes Anki** : affichées comme flashcards avec badge coloré par type
  - `definition` = bleu, `theorem` = rouge, `method` = vert, `formula` = violet, autres = ambre
- **Download buttons** : .md, .anki.csv, .anki.txt
- **Stats** : nombre de cartes générées / filtrées / durée

### Contrainte
- Localhost uniquement — pas de déploiement cloud dans cette version.
- `app.py` appelle les mêmes fonctions que `convert.py` (pas de duplication de logique).

---

## 9. Tests

### Unitaires
- `tests/test_anki_generator.py`
  - détection de chaque catégorie sémantique (définition, théorème, méthode…)
  - génération des templates par catégorie
  - filtres qualité (cartes vides, trop courtes, doublons)
  - déterminisme (deux appels identiques → même résultat)
- `tests/test_anki_exporter.py`
  - export CSV séparateur `;` et `,`
  - export TXT séparateur `\t`
  - échappement guillemets et retours ligne
  - encodage UTF-8

### Intégration
- `tests/test_integration.py` — ajout de :
  - PDF → MD → deck Anki (fichier produit non vide, cartes parsables)
  - idempotence : second run sans `--anki-regenerate` ne recrée pas le deck
  - `--anki-regenerate` recrée bien le deck depuis le MD existant

---

## 10. Documentation

- `README.md` : section Anki (options CLI + exemples) + section Streamlit
- `docs/ANKI_IMPORT_GUIDE.md` : guide import étape par étape dans Anki Desktop
