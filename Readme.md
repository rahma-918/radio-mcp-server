Serveur MCP — Exploration d'un corpus de comptes rendus radiologiques

Serveur MCP (Model Context Protocol) permettant à un assistant IA (Claude) d'interroger en langage naturel un corpus de comptes rendus de TDM cérébrale : recherche par mot-clé, comptage d'occurrences, et statistiques globales sur le corpus.

Pourquoi ce projet

Ce projet a été développé dans un but d'apprentissage du protocole MCP et de l'orchestration d'agents IA, en l'appliquant à un cas concret : rendre un corpus médical texte interrogeable en langage naturel sans écrire de requêtes techniques.

Note sur les données : le corpus utilisé pendant le développement contient des données médicales réelles (anonymisées côté identité patient mais non publiées ici par prudence). Le dossier data/ est volontairement exclu du dépôt (voir .gitignore). Pour reproduire ce projet, il faut fournir son propre fichier au format attendu (voir section Structure des données).