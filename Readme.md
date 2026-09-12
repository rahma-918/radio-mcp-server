# Serveur MCP — Exploration et structuration d'un corpus de comptes rendus radiologiques

Serveur MCP (Model Context Protocol) permettant à un assistant IA (Claude) d'interroger en langage naturel un corpus de comptes rendus de TDM cérébrale, et de le structurer automatiquement par catégorisation zero-shot via LLM.

## Problématique

Un corpus de comptes rendus radiologiques est une masse de **texte libre non structuré** : des milliers de rapports rédigés en langage naturel, sans champs structurés exploitables directement (pas de code diagnostique standardisé, pas de champ "pathologie"). Cette information existe, mais elle est enfermée dans du texte : pour en extraire la moindre connaissance, il faut soit lire chaque CR un par un, soit écrire des requêtes techniques rigides qui ratent les formulations différentes d'une même idée.

C'est un problème réel dans les services de radiologie : une richesse d'information clinique accumulée au fil des années, mais difficile à interroger, auditer ou analyser à grande échelle sans un travail manuel long et coûteux. Les approches classiques ont chacune une limite :
- La **recherche par mot-clé** est rigide et rate les synonymes ou reformulations et meme les fautes de frappes.
- Une **classification manuelle** donnerait une vraie structuration, mais serait trop coûteuse en temps à cette échelle.
- Un **NLP supervisé classique** demanderait d'abord de constituer un jeu de données annoté avant d'obtenir un premier résultat.

Ce projet explore deux réponses complémentaires à ce problème :
1. **Rendre le corpus interrogeable en langage naturel**, via un serveur MCP connecté à Claude — sans syntaxe de requête à apprendre.
2. **Structurer automatiquement le corpus sans annotation manuelle préalable**, via une classification zero-shot par LLM — en s'appuyant sur la capacité de compréhension du langage médical déjà intégrée aux modèles actuels, plutôt que d'entraîner un modèle depuis zéro.

Au-delà du cas d'usage radiologique, le projet sert de terrain d'apprentissage à une problématique plus générale en IA appliquée : comment donner à un LLM la capacité d'agir de façon fiable sur des données réelles et spécifiques à un domaine (sorties structurées, gestion des erreurs, séparation entre traitement en lot et traitement à la demande), plutôt que de se limiter à une réponse générée sans ancrage dans les données.

**Note sur les données** : le corpus utilisé pendant le développement contient des données médicales réelles (anonymisées côté identité patient mais non publiées ici par prudence). Le dossier `data/` est volontairement exclu du dépôt (voir `.gitignore`). Pour reproduire ce projet, il faut fournir son propre fichier au format attendu (voir section Structure des données).

## Fonctionnalités

Le serveur expose les outils suivants :

| Outil | Description |
|---|---|
| `search_reports(mot_cle)` | Recherche un mot-clé dans les comptes rendus et retourne jusqu'à 5 exemples correspondants |
| `count_reports(mot_cle)` | Compte le nombre de comptes rendus contenant un mot-clé donné |
| `get_category_breakdown()` | Répartition des catégories cliniques sur l'échantillon classifié (voir module de classification ci-dessous) |
| `classify_new_report(rens_clinique, contrendu)` | Classifie en temps réel un nouveau compte rendu fourni par l'utilisateur |

## Architecture

Le projet sépare volontairement deux responsabilités dans deux fichiers distincts :

- **`data_access.py`** — logique métier pure (chargement des données, recherche, statistiques), sans aucune dépendance au protocole MCP. Testable indépendamment.
- **`server.py`** — déclaration des outils MCP, qui appellent la logique de `data_access.py`.

Cette séparation permet de tester et faire évoluer la logique de traitement des données sans toucher à la couche protocole, et inversement.

## Module de classification automatique (zero-shot)

En complément de la recherche par mot-clé, le projet inclut un module de catégorisation automatique du corpus par LLM (Gemini 3.1 Flash-Lite), sans annotation manuelle ni entraînement préalable :

- **`categorize_corpus.py`** — script exécuté séparément du serveur MCP, qui classe un échantillon du corpus dans l'une des catégories suivantes : `traumatique`, `vasculaire`, `tumoral`, `post-operatoire`, `normal`, `autre`. Le résultat est sauvegardé dans `data/categories.csv`, relu ensuite par le serveur MCP sans jamais rappeler l'API pendant une conversation.

**Choix méthodologiques** :
- La classification s'appuie sur une **sortie structurée forcée** (JSON Schema via Pydantic) plutôt que sur une validation de texte libre après coup : le modèle est contraint de répondre avec l'une des catégories autorisées, ce qui élimine le besoin de valider manuellement chaque réponse.
- Le script inclut une gestion des erreurs transitoires (quota dépassé, surcharge du service) avec réessais automatiques à délai croissant, et un mécanisme de reprise qui évite de retraiter les CR déjà classifiés lors d'une exécution interrompue.
- La classification est réalisée sur un **échantillon aléatoire** du corpus (400 CR) plutôt que sur son intégralité, par choix assumé : le plan gratuit de l'API impose un débit limité, rendant un traitement du corpus complet long (plusieurs heures) pour un gain de précision statistique marginal à ce stade du projet. Voir la section Limites connues.

Deux outils MCP exploitent ce module :

| Outil | Description |
|---|---|
| `get_category_breakdown()` | Donne la répartition des catégories sur l'échantillon déjà classifié (lecture de `categories.csv`, aucun appel API) |
| `classify_new_report(rens_clinique, contrendu)` | Classifie en temps réel un nouveau compte rendu fourni par l'utilisateur (appel direct à l'API Gemini) |

Cette double implémentation illustre une distinction d'architecture volontaire : un traitement **par lot pré-calculé** (rapide, gratuit à l'usage, pour explorer le corpus existant) face à un traitement **à la demande** (plus coûteux en latence et en quota, mais flexible pour tout nouveau texte).

## Structure des données attendue

Un fichier Excel (`data/TDM_cérébrale.xlsx`, feuille `Sheet1`) avec les colonnes suivantes :

| Colonne | Contenu |
|---|---|
| `RENS_CLINIQUE` | Motif clinique de l'examen |
| `TECHNIQUE` | Protocole d'acquisition |
| `CONTRENDU` | Corps du compte rendu |
| `CONCLUSION` | Synthèse du compte rendu |

## Installation

```bash
git clone <url-de-ce-depot>
cd radio_mcp_server
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Place ensuite ton propre fichier de données dans `data/TDM_cérébrale.xlsx`.

Pour utiliser le module de classification (script `categorize_corpus.py` et outil `classify_new_report`), configure ta clé API Gemini (obtenue gratuitement sur [Google AI Studio](https://aistudio.google.com)) :

```bash
# macOS / Linux
export GEMINI_API_KEY="ta-clé-ici"
# Windows (PowerShell)
$env:GEMINI_API_KEY = "ta-clé-ici"
```

Lance ensuite la catégorisation initiale du corpus (facultatif, nécessaire uniquement pour `get_category_breakdown`) :

```bash
python categorize_corpus.py
```

## Utilisation avec Claude Desktop

Ajoute ce bloc dans le fichier de configuration de Claude Desktop (accessible via **Settings → Developer → Edit config**) :

```json
{
  "mcpServers": {
    "radio-cr-server": {
      "command": "/chemin/absolu/vers/radio_mcp_server/venv/bin/python",
      "args": ["/chemin/absolu/vers/radio_mcp_server/server.py"]
    }
  }
}
```

Redémarre complètement Claude Desktop, puis pose une question en langage naturel dans une conversation, par exemple :

> Combien de comptes rendus mentionnent un méningiome ?

## Tester sans Claude Desktop (MCP Inspector)

```bash
npx @modelcontextprotocol/inspector python server.py
```

Ouvre l'interface web fournie pour appeler chaque outil manuellement et vérifier son bon fonctionnement.

## Limites connues et pistes d'amélioration

- La recherche par mot-clé est une correspondance textuelle simple (pas de recherche sémantique) — une évolution possible serait d'indexer le corpus par embeddings pour une recherche par sens plutôt que par mot exact.
- Les statistiques de `get_corpus_stats()` reposent sur une liste de mots-clés prédéfinie, distincte de la classification par catégorie clinique du module de classification.
- La classification par catégorie (`get_category_breakdown`) porte sur un échantillon aléatoire de 400 CR, pas sur l'intégralité du corpus (10 568 CR) — un choix assumé au vu du débit limité du plan gratuit de l'API utilisée. Passer au corpus complet est possible avec le même script, au prix d'un temps d'exécution de plusieurs heures.
- `classify_new_report` nécessite une clé API valide (variable d'environnement `GEMINI_API_KEY`) et n'est pas fonctionnel sans elle, contrairement aux autres outils qui ne dépendent d'aucun service externe.
- Le corpus est chargé entièrement en mémoire au démarrage, ce qui convient à ce volume de données (environ 10 000 lignes) mais ne serait pas adapté à un corpus beaucoup plus volumineux sans passer par une base de données.

## Stack technique

- Python 3.12
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- pandas / openpyxl pour la lecture des données
- google-genai (Gemini 3.1 Flash-Lite) pour la classification zero-shot
- Pydantic pour le typage et la validation des sorties structurées

## Avertissement

Ce projet est à but d'apprentissage et de démonstration. Il ne doit pas être utilisé pour prendre des décisions cliniques réelles.