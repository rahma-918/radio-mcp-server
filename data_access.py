"""
Module d'accès aux données du corpus de comptes rendus (CR) radiologiques.
Permet de faire deux choses :
1. Charger les CR depuis le fichier Excel
2. Chercher un mot-clé dedans

"""

import pandas as pd
from pathlib import Path

# Chemin vers le fichier de données, relatif à ce fichier Python.
DATA_PATH = Path(__file__).parent / "data" / "TDM_cérébrale.xlsx"


def charger_corpus() -> pd.DataFrame:
    """
    Charge le corpus de CR depuis le fichier Excel et retourne un DataFrame pandas.

    On appelle cette fonction à chaque démarrage du serveur, une seule fois,
    pour garder les données en mémoire plutôt que de relire le fichier
    à chaque recherche (ce qui serait lent).
    """
    df = pd.read_excel(DATA_PATH, sheet_name="Sheet1")
    return df


def chercher_mot_cle(df: pd.DataFrame, mot_cle: str, max_resultats: int = 5) -> list[dict]:
    """
    Cherche un mot-clé (insensible à la casse) dans la colonne CONTRENDU.
    """
    if not mot_cle or not mot_cle.strip():
        return []

    masque = df["CONTRENDU"].str.contains(mot_cle, case=False, na=False)
    resultats = df[masque].head(max_resultats)

    sortie = []
    for _, ligne in resultats.iterrows():
        sortie.append({
            "rens_clinique": str(ligne["RENS_CLINIQUE"]),
            "contrendu": str(ligne["CONTRENDU"]),
            "conclusion": str(ligne["CONCLUSION"]),
        })
    return sortie


def compter_occurrences(df: pd.DataFrame, mot_cle: str) -> int:
    """
    Compte combien de CR contiennent le mot-clé, sans retourner leur contenu.
    Utile pour répondre à des questions du type "combien de CR mentionnent X ?"
    sans surcharger la réponse avec du texte inutile.
    """
    if not mot_cle or not mot_cle.strip():
        return 0
    masque = df["CONTRENDU"].str.contains(mot_cle, case=False, na=False)
    return int(masque.sum())


# Chemin vers le fichier de catégories généré par categorize_corpus.py
CATEGORIES_PATH = Path(__file__).parent / "data" / "categories.csv"

# Valeur utilisée dans categorize_corpus.py pour signaler un échec technique
# (pas une vraie catégorie clinique) — répétée ici pour que les deux fichiers
# reconnaissent la même convention sans dépendre l'un de l'autre.
ECHEC_TECHNIQUE = "echec_technique"


def charger_categories() -> pd.DataFrame | None:
    """
    Charge le fichier de catégories généré par categorize_corpus.py.
    """
    if not CATEGORIES_PATH.exists():
        return None
    return pd.read_csv(CATEGORIES_PATH)


def obtenir_repartition_categories(df_categories: pd.DataFrame) -> dict:
    """
    Calcule la répartition des catégories cliniques sur l'échantillon classifié.

    Les lignes marquées comme échec technique sont comptées séparément
    et exclues du calcul des pourcentages : elles ne représentent aucune
    vraie catégorie clinique, les inclure fausserait la répartition.
    """
    total = len(df_categories)

    nb_echecs = int((df_categories["categorie"] == ECHEC_TECHNIQUE).sum())
    df_valides = df_categories[df_categories["categorie"] != ECHEC_TECHNIQUE]
    total_valides = len(df_valides)

    comptes = df_valides["categorie"].value_counts()
    repartition = {}
    for categorie, nombre in comptes.items():
        repartition[categorie] = {
            "nombre": int(nombre),
            "pourcentage": round(100 * nombre / total_valides, 1) if total_valides else 0.0,
        }

    return {
        "taille_echantillon": total,
        "echecs_techniques": nb_echecs,
        "repartition": repartition,
    }