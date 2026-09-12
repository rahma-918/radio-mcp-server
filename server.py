"""
Serveur MCP exposant des outils de recherche, de statistiques et de
classification sur le corpus de CR radiologiques.

Ce fichier NE CONTIENT PAS la logique métier elle-même (elle est dans
data_access.py et categorize_corpus.py). Son seul rôle est de "déclarer"
cette logique sous forme d'outils qu'un client MCP peut appeler.
"""

import os

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from data_access import (
    charger_corpus,
    chercher_mot_cle,
    compter_occurrences,
    charger_categories,
    obtenir_repartition_categories,
)
from categorize_corpus import classifier_un_cr

# Charge les variables définies dans .env (notamment GEMINI_API_KEY) dans
# l'environnement du processus, exactement comme categorize_corpus.py le
# fait déjà. Nécessaire ici aussi car Claude Desktop lance ce fichier comme
# un processus séparé, qui ne connaît pas les variables déjà chargées
# ailleurs.
load_dotenv()

mcp_server = MCPServer(
    name="radio-cr-server",
    instructions=(
        "Ce serveur donne accès à un corpus de comptes rendus de TDM cérébrale. "
        "Utilise ces outils pour répondre aux questions sur le contenu du corpus."
    ),
)

CORPUS = charger_corpus()

# Le client Gemini n'est PAS créé ici au niveau module, contrairement à
# CORPUS. Pourquoi : les 3 premiers outils (recherche, comptage, répartition)
# ne dépendent d'aucune clé API et doivent continuer à fonctionner même si
# GEMINI_API_KEY est absente. On ne crée le client Gemini qu'au moment où
# l'outil qui en a besoin est réellement appelé (voir classify_new_report).


@mcp_server.tool()
def search_reports(mot_cle: str) -> str:
    """
    Cherche un mot-clé dans les comptes rendus de TDM cérébrale et retourne
    jusqu'à 5 résultats correspondants.

    Utilise cet outil quand l'utilisateur demande des exemples de comptes
    rendus mentionnant une pathologie ou un terme précis, par exemple
    "montre-moi des CR qui parlent de méningiome".
    """
    resultats = chercher_mot_cle(CORPUS, mot_cle, max_resultats=5)

    if not resultats:
        return f"Aucun compte rendu ne contient le mot-clé '{mot_cle}'."

    lignes = [f"{len(resultats)} résultat(s) trouvé(s) pour '{mot_cle}' :\n"]
    for i, r in enumerate(resultats, start=1):
        lignes.append(f"--- Résultat {i} ---")
        lignes.append(f"Contexte clinique : {r['rens_clinique']}")
        lignes.append(f"Compte rendu : {r['contrendu'][:300]}...")
        lignes.append(f"Conclusion : {r['conclusion']}")
        lignes.append("")

    return "\n".join(lignes)


@mcp_server.tool()
def count_reports(mot_cle: str) -> str:
    """
    Compte le nombre de comptes rendus contenant un mot-clé donné,
    sans retourner leur contenu détaillé.

    Utilise cet outil quand l'utilisateur pose une question de type
    "combien de CR mentionnent X ?", plutôt que search_reports qui
    est plus adapté quand il veut voir des exemples concrets.
    """
    nb = compter_occurrences(CORPUS, mot_cle)
    total = len(CORPUS)
    return f"{nb} compte(s) rendu(s) sur {total} mentionnent '{mot_cle}'."


@mcp_server.tool()
def get_category_breakdown() -> str:
    """
    Donne la répartition des catégories cliniques (traumatique, vasculaire,
    tumoral, post-operatoire, normal, autre) sur l'échantillon du corpus
    déjà classifié par le script categorize_corpus.py.

    Utilise cet outil quand l'utilisateur pose une question générale sur
    la répartition des types de pathologies dans le corpus, par exemple
    "quelle proportion des CR est vasculaire ?" ou "donne-moi la répartition
    des catégories cliniques".

    Ne relance AUCUN appel à l'API : cette information est lue depuis un
    fichier déjà calculé, donc la réponse est quasi instantanée.
    """
    df_categories = charger_categories()

    if df_categories is None:
        return (
            "Aucune classification n'a encore été calculée. "
            "Il faut d'abord exécuter le script categorize_corpus.py."
        )

    stats = obtenir_repartition_categories(df_categories)

    lignes = [
        f"Répartition calculée sur un échantillon de {stats['taille_echantillon']} "
        f"comptes rendus (pas l'intégralité du corpus).\n"
    ]

    if stats["echecs_techniques"] > 0:
        lignes.append(
            f"({stats['echecs_techniques']} CR n'ont pas pu être classifiés "
            f"à cause d'une erreur technique, exclus du calcul ci-dessous.)\n"
        )

    repartition_triee = sorted(
        stats["repartition"].items(),
        key=lambda item: item[1]["nombre"],
        reverse=True,
    )
    for categorie, info in repartition_triee:
        lignes.append(f"  - {categorie} : {info['nombre']} CR ({info['pourcentage']}%)")

    return "\n".join(lignes)


@mcp_server.tool()
def classify_new_report(rens_clinique: str, contrendu: str) -> str:
    """
    Classifie en temps réel un nouveau compte rendu de TDM cérébrale fourni
    par l'utilisateur, dans l'une des catégories : traumatique, vasculaire,
    tumoral, post-operatoire, normal, autre.

    Utilise cet outil quand l'utilisateur fournit lui-même le texte d'un
    compte rendu (qui ne fait pas forcément partie du corpus existant) et
    demande dans quelle catégorie il se classerait, par exemple
    "dans quelle catégorie classerais-tu ce compte rendu : [texte]".

    Contrairement à get_category_breakdown, cet outil appelle l'API Gemini
    à chaque utilisation, donc la réponse prend quelques secondes.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return (
            "Cet outil nécessite une clé API Gemini configurée "
            "(variable d'environnement GEMINI_API_KEY absente ou introuvable)."
        )

    # Import local (pas en haut du fichier) : google.genai n'est nécessaire
    # que pour cet outil précis, donc on ne le charge qu'au moment où
    # on en a réellement besoin.
    from google import genai

    client = genai.Client(api_key=api_key)

    try:
        categorie = classifier_un_cr(client, rens_clinique, contrendu)
    except Exception as e:
        return f"Erreur lors de l'appel à l'API de classification : {e}"

    return f"Catégorie proposée : {categorie}"


if __name__ == "__main__":
    # "stdio" veut dire que le serveur communique via l'entrée/sortie standard
    # du terminal. C'est le mode utilisé par Claude Desktop pour les serveurs
    # locaux : Claude Desktop lance ce script lui-même et lui parle via stdio.
    mcp_server.run(transport="stdio")