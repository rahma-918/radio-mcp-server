"""
Script de catégorisation automatique du corpus de CR via Gemini 3.1 Flash-Lite.

Ce script peut être relancé plusieurs fois sans regaspiller de quota :
s'il trouve un fichier de résultats existant, il ne retraite QUE les lignes
manquantes ou en échec technique, pas celles déjà correctement classifiées.
"""

import os
import csv
import time
from pathlib import Path
from typing import Literal

from google import genai
from pydantic import BaseModel

from data_access import charger_corpus
from dotenv import load_dotenv

load_dotenv()

CATEGORIES = [
    "traumatique",
    "vasculaire",
    "tumoral",
    "post-operatoire",
    "normal",
    "autre",
]

# Valeur utilisée quand un CR n'a jamais pu être classifié par le modèle,
# à cause d'une panne technique persistante (pas une vraie catégorie clinique).
ECHEC_TECHNIQUE = "echec_technique"


class CategorieCR(BaseModel):
    categorie: Literal[
        "traumatique", "vasculaire", "tumoral",
        "post-operatoire", "normal", "autre"
    ]


OUTPUT_PATH = Path(__file__).parent / "data" / "categories.csv"
TAILLE_ECHANTILLON = 400
PAUSE_ENTRE_APPELS = 4.5

MAX_TENTATIVES = 4
DELAIS_RETRY = [10, 20, 40, 60]


def construire_prompt(rens_clinique: str, contrendu: str) -> str:
    liste_categories = ", ".join(CATEGORIES)
    return f"""Catégorise ce compte rendu de TDM cérébrale parmi : {liste_categories}

Contexte clinique : {rens_clinique}
Compte rendu : {contrendu[:800]}"""


def est_erreur_transitoire(erreur: Exception) -> bool:
    message = str(erreur)
    return "503" in message or "429" in message


def classifier_un_cr(client: genai.Client, rens_clinique: str, contrendu: str) -> str:
    """
    Envoie un CR à Gemini avec une sortie structurée forcée. Cette fonction
    est réutilisée telle quelle par le serveur MCP (outil classify_new_report),
    pour ne jamais dupliquer la logique de classification à deux endroits.
    """
    prompt = construire_prompt(rens_clinique, contrendu)

    for tentative in range(MAX_TENTATIVES):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": CategorieCR.model_json_schema(),
                },
            )
            resultat = CategorieCR.model_validate_json(response.text)
            return resultat.categorie

        except Exception as e:
            if est_erreur_transitoire(e) and tentative < MAX_TENTATIVES - 1:
                delai = DELAIS_RETRY[tentative]
                print(f"    Erreur transitoire, nouvelle tentative dans {delai}s...")
                time.sleep(delai)
                continue
            raise


def charger_resultats_existants() -> dict[int, str]:
    """
    Charge les résultats déjà sauvegardés lors d'une exécution précédente.

    Toute valeur DIFFÉRENTE de ECHEC_TECHNIQUE est considérée comme un
    résultat valide et définitif (y compris "autre", qui est ici une vraie
    catégorie clinique et non un problème technique) : cette fois, la
    convention est cohérente dès le départ, contrairement à l'exécution
    précédente où on avait mélangé les deux usages du mot "autre".
    """
    if not OUTPUT_PATH.exists():
        return {}

    resultats = {}
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for ligne in reader:
            resultats[int(ligne["index_cr"])] = ligne["categorie"]
    return resultats


def sauvegarder_resultats(resultats: dict[int, str]):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index_cr", "categorie"])
        writer.writeheader()
        for index_cr in sorted(resultats.keys()):
            writer.writerow({"index_cr": index_cr, "categorie": resultats[index_cr]})


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Erreur : GEMINI_API_KEY n'est pas définie.")
        return

    client = genai.Client(api_key=api_key)

    df = charger_corpus()
    if TAILLE_ECHANTILLON is not None:
        df = df.sample(n=TAILLE_ECHANTILLON, random_state=42)

    resultats = charger_resultats_existants()

    lignes_a_traiter = [
        (i, ligne) for i, (_, ligne) in enumerate(df.iterrows())
        if i not in resultats or resultats[i] == ECHEC_TECHNIQUE
    ]

    if not lignes_a_traiter:
        print("Tout l'échantillon est déjà classifié correctement. Rien à faire.")
        return

    print(f"{len(lignes_a_traiter)} CR à traiter "
          f"({len(resultats)} déjà classifiés précédemment, réutilisés tels quels).")

    for n, (i, ligne) in enumerate(lignes_a_traiter):
        rens = str(ligne["RENS_CLINIQUE"])
        cr = str(ligne["CONTRENDU"])

        if n > 0:
            time.sleep(PAUSE_ENTRE_APPELS)

        try:
            categorie = classifier_un_cr(client, rens, cr)
        except Exception as e:
            print(f"  Échec définitif sur la ligne {i} : {e}")
            categorie = ECHEC_TECHNIQUE

        resultats[i] = categorie

        if (n + 1) % 10 == 0:
            print(f"  {n + 1}/{len(lignes_a_traiter)} traités...")
            # Sauvegarde intermédiaire toutes les 10 lignes : si le script
            # est interrompu (fermeture accidentelle du terminal, coupure
            # réseau prolongée...), on ne perd pas tout le travail déjà fait.
            sauvegarder_resultats(resultats)

    sauvegarder_resultats(resultats)
    print(f"\nTerminé. Résultats sauvegardés dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()