"""
Serveur MCP exposant des outils de recherche sur le corpus de CR radiologiques.

Ce fichier NE CONTIENT PAS la logique de recherche elle-même (elle est dans
data_access.py). Son seul rôle est de "déclarer" cette logique sous forme
d'outils qu'un client MCP (n'importe quel LLM) peut appeler.
"""

from mcp.server.mcpserver import MCPServer
from data_access import charger_corpus, chercher_mot_cle, compter_occurrences

# On crée le serveur en lui donnant un nom. C'est ce nom qui apparaîtra
# côté client (Claude Desktop) dans la liste des serveurs connectés.
mcp_server = MCPServer(
    name="radio-cr-server",
    instructions=(
        "Ce serveur donne accès à un corpus de comptes rendus de TDM cérébrale. "
        "Utilise ces outils pour répondre aux questions sur le contenu du corpus."
    ),
)

# On charge le corpus UNE SEULE FOIS au démarrage du serveur, pas à chaque
# appel d'outil. Le recharger à chaque fois serait lent et inutile,
# puisque les données ne changent pas pendant l'exécution.
CORPUS = charger_corpus()


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


if __name__ == "__main__":
    # "stdio" veut dire que le serveur communique via l'entrée/sortie standard
    # du terminal. C'est le mode utilisé par Claude Desktop pour les serveurs
    # locaux : Claude Desktop lance ce script lui-même et lui parle via stdio.
    mcp_server.run(transport="stdio")