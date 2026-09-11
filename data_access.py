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