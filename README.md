Conception d'un agent IA assistant pour l'aide à la conception d'interfaces tangibles (TUI)
=============

Infos générales
---------------

- **Étudiant** : Ismail Mehmeti - ismail.mehmeti@hes-so.ch
- **Professeur** : Omar Abou Khaled (HEIA-FR)
- **Professeure** : Nadine Couture (ESTIA)
- **Expert** : Raphaël Guisolan
- **Expert** : Marc Wuergler
- **Type de projet** : Travail de bachelor (TB)
- **Année académique** : 2025-2026
- **Dates** : du 26.05.2026 au 17.07.2026 (rendu du rapport)
- **Mandant** : ESTIA — École Supérieure des Technologies Industrielles Avancées (Bidart, France), en collaboration avec le HumanTech Institute (HEIA-FR)


Description
-----------

Le but de ce projet est de concevoir et développer une application web intégrant un agent IA capable d'assister les utilisateurs (chercheurs et concepteurs) dans la conception d'interfaces tangibles (TUI), à partir d'une base de connaissances issue de la littérature scientifique.

Les interfaces tangibles permettent d'interagir avec des systèmes numériques à travers des objets physiques manipulables. Leur conception nécessite des connaissances techniques et théoriques dispersées dans de nombreux travaux de recherche, ce qui rend leur exploitation complexe. Le système développé s'appuie sur une architecture **RAG (Retrieval-Augmented Generation)** : il recherche, cite et synthétise des passages d'un corpus scientifique de TUI (collections ACM CHI/TEI + travaux de recherche ESTIA), et ne répond **jamais** à partir de connaissances générales — uniquement à partir des documents indexés.

Les objectifs fixés au début du projet sont les suivants :

**Objectifs principaux :**
 - Développement d'un agent IA conversationnel dédié à la conception d'interfaces tangibles
 - Mise en place d'un système RAG (indexation, base vectorielle, recherche sémantique)
 - Développement de l'application web (interface conversationnelle et affichage des sources)
 - Évaluation du système (métriques de récupération et de qualité de réponse)
 - Déploiement et maintenance du système

**Objectifs secondaires :**
 - Enrichissement de la base de connaissances
 - Amélioration de l'expérience utilisateur
 - Administration et évolution du système

## Réalisation et Technologies

Ce projet a permis de mettre en place, de A à Z, un assistant conversationnel sourcé reposant sur un pipeline multi-agents et une recherche documentaire vectorielle. Le système développé utilise une architecture moderne et entièrement conteneurisée composée de :

- **Pipeline multi-agents** : orchestration **LangGraph** en 3 nœuds (compréhension/reformulation → recherche documentaire → synthèse sourcée)
- **Backend API** : Service REST développé avec **FastAPI** (Python), authentification **JWT** et streaming **Server-Sent Events**
- **LLM** : modèles exécutés localement via **Ollama** (qwen2.5, llama3.2, mistral), sélectionnables par requête
- **Système RAG** : embeddings **BGE-M3** (multilingue, local) + base vectorielle **Qdrant**, récupération multi-requêtes avec fusion **RRF** et regroupement des sources par article
- **Base de données** : **PostgreSQL** pour les métadonnées des documents et l'historique des conversations
- **Frontend** : Interface utilisateur développée en **Next.js 14 / React TypeScript** avec **Tailwind CSS** et **shadcn/ui**
- **Observabilité & évaluation** : traçage **Langfuse** et métriques **DeepEval** pour comparer les modèles
- **Déploiement** : Architecture containerisée avec **Docker Compose**

## Résultats

Le système livré est entièrement fonctionnel et propose :

- **Assistant conversationnel sourcé** : chaque réponse cite ses sources avec la notation `[n]` renvoyant aux articles du corpus, et signale explicitement les informations manquantes plutôt que d'inventer
- **Pipeline multi-agents** : analyse de l'intention et détection des demandes de clarification, expansion de requête (multi-query + fusion RRF), puis synthèse structurée (synthèse / pistes de conception / limites)
- **Ingestion documentaire** : extraction PyMuPDF en blocs triés en ordre de lecture, exclusion automatique des bibliographies, découpage, embeddings et indexation dans Qdrant
- **Application web complète** : authentification, historique des conversations par utilisateur, sélection du modèle LLM, affichage en direct de la progression des agents et panneau de citations
- **API REST documentée** avec interface **Swagger** interactive
- **Cadre d'évaluation** : campagnes comparant plusieurs modèles de reformulation et de synthèse (récupération, fidélité, pertinence) avec juge local et scores remontés dans Langfuse

### Déploiement

Le projet peut être exécuté de deux manières :

**1. Reproduction en local** — pour rejouer le projet sur une machine de développement (Docker Compose : PostgreSQL, Qdrant, Ollama, backend, frontend). L'ensemble se lance avec quelques commandes `make` (`make up`, `make pull-models`, `make ingest`). Guide détaillé pas à pas dans [`code/README.md`](code/README.md#-déploiement-local-reproduction).

**2. Déploiement en production sur le serveur ESTIA** — l'application est déployée sur le serveur **Apache mutualisé** de l'ESTIA, sous le sous-chemin `https://devweb.estia.fr/tui_assistant` : le backend tourne en Docker, exposé uniquement sur la loopback (`127.0.0.1:18000`), et le frontend est servi comme export statique Next.js relié à l'API via un `.htaccess` (proxy `mod_proxy`). Procédure résumée dans [`code/README.md`](code/README.md#-déploiement-sur-le-serveur-estia) et **runbook complet** (transfert, secrets, `.htaccess`/vhost, mises à jour, dépannage) dans [`code/deploy/DEPLOY.md`](code/deploy/DEPLOY.md).

## Futures évolutions

Les perspectives d'amélioration identifiées incluent :
- Recherche **hybride** (dense + lexicale) et **reranking** des passages récupérés pour améliorer la pertinence
- Boucle de couverture (auto-vérification que la réponse couvre bien la question)
- Mise à jour automatique du corpus à partir des nouvelles publications (ACM, travaux ESTIA)
- Migration du schéma de base de données vers Alembic pour un usage en production
- Enrichissement continu de la base de connaissances et administration avancée des documents


Contenu du dépôt
-------

Ce dépôt contient l'ensemble du projet organisé comme suit :

### 📁 `code/`
Contient le code source complet de l'application :

- **`backend/`** : API REST FastAPI, pipeline LangGraph multi-agents, système RAG (Qdrant, BGE-M3), authentification JWT et scripts d'ingestion/évaluation
- **`frontend/`** : Interface utilisateur Next.js 14 / React TypeScript avec composants UI modernes (Tailwind, shadcn/ui)
- **`deploy/`** : configuration et runbook de déploiement (Apache sous sous-chemin, `DEPLOY.md`)
- **`docker-compose.yml` / `docker-compose.deploy.yml`** : orchestration complète des services (PostgreSQL, Qdrant, Ollama, backend, frontend)
- **`Makefile`** : commandes d'installation, de lancement, d'ingestion et d'évaluation
- **`README.md`** : guide complet d'installation, de déploiement et de développement

### 📁 `docs/`
Documentation complète du projet :

- **`cahier_des_charges/`** : Cahier des charges (Word et PDF)
- **`rapport/`** : Rapport final du projet
- **`PVs/`** : Procès-verbaux des séances de suivi (superviseurs et experts)
- **`presentation/`** : Slides des présentations (cahier des charges et projet)
- **`planning/`** : Planning et diagramme de Gantt
- **`tests_utilisateurs/`** : Protocole et résultats des tests utilisateurs
- **`SUS/`** : Calcul du score System Usability Scale
- **`flyer/`** : Flyer de présentation du projet
- **`diagrammes/` & `images/`** : Diagrammes d'architecture et illustrations


### Contact et support

Pour toute question technique ou fonctionnelle :
- **Étudiant** : Ismail Mehmeti — ismail.mehmeti@hes-so.ch
- **Documentation** : Rapport complet dans `docs/rapport/`
- **Installation & lancement** : Guide détaillé dans [`code/README.md`](code/README.md)
- **Code source** : Entièrement documenté dans `code/`
