# Assistant IA pour l'aide à la conception d'interfaces tangibles (TUI)

Application web **RAG** (Retrieval-Augmented Generation) qui aide à concevoir des interfaces tangibles en retrouvant, synthétisant et **citant** les passages pertinents d'un corpus scientifique (collections ACM CHI/TEI + travaux ESTIA). Ce n'est pas un chatbot généraliste : l'assistant s'appuie **uniquement** sur les documents indexés et indique toujours ses sources.

## 🏗️ Architecture

L'application repose sur un pipeline multi-agents et une recherche documentaire vectorielle, orchestrés par Docker Compose :

- **Frontend Web** : interface conversationnelle React / **Next.js 14** (TypeScript, Tailwind, shadcn/ui)
- **Backend API** : service REST **FastAPI** (Python 3.11) orchestrant un graphe **LangGraph** à 3 agents (compréhension → recherche RAG → synthèse sourcée), avec authentification JWT et streaming SSE
- **PostgreSQL** : métadonnées des documents + historique des conversations et messages
- **Qdrant** : base vectorielle des chunks (embeddings **BGE-M3**, 1024 dim) et de leur payload
- **Ollama** : exécution locale des LLM (qwen2.5:7b, llama3.2:3b, mistral:7b), modèle configurable par requête
- **Adminer** *(option)* : interface web de consultation de PostgreSQL
- **Langfuse** *(option)* : traçage des exécutions du pipeline et scores d'évaluation

```
Navigateur ─► Frontend Next.js :3000 ─► Backend FastAPI :8000
                                           │
                     ┌─────────────────────┼──────────────────────┐
                     ▼                     ▼                       ▼
              PostgreSQL :5432       Qdrant :6333            Ollama :11434
            (docs + historique)   (vecteurs BGE-M3)         (LLM local)
```

## 🚀 Déploiement local (reproduction)

Cette section décrit l'installation **en local** pour reproduire le projet sur
une machine de développement. Pour la mise en ligne sur le serveur mutualisé de
l'ESTIA, voir plus bas la section [Déploiement sur le serveur ESTIA](#-déploiement-sur-le-serveur-estia).

### Prérequis

- Docker Engine 20.10+
- Docker Compose 2.0+
- ~10 Go d'espace disque (images + modèles Ollama + BGE-M3 ~2 Go)
- 16 Go de RAM recommandés (les modèles 7B sont gourmands ; sans GPU, privilégier `llama3.2:3b` pour les tests)
- Ports libres : `3000`, `3001`, `5432`, `6333`, `8000`, `8080`, `11434`

### Installation

Un **Makefile** regroupe les commandes courantes (`make help` pour la liste complète) :

```bash
# Cloner le repository puis se placer dans le dossier code
cd code

# 1. Démarrer toute la stack (crée .env si absent, build + up)
make up

# 2. Télécharger les modèles Ollama (une seule fois)
make pull-models

# 3. Indexer le corpus PDF (le 1er lancement télécharge BGE-M3 ~2 Go, normal)
make ingest            # tout le corpus
# make ingest-sample   # ou un petit échantillon pour tester rapidement

# Vérifier le statut des services
make ps
```

Équivalent sans Makefile :

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec backend python scripts/ingest_corpus.py /data/files
```

### Accès aux services

Une fois déployé, les services sont accessibles à :

| Service | URL | Description |
|---------|-----|-------------|
| 🖥️ **Application principale** | http://localhost:3000 | Interface conversationnelle (Next.js) |
| 🔧 **API REST** | http://localhost:8000 | Endpoints du backend |
| 📚 **Documentation API** | http://localhost:8000/docs | Interface Swagger interactive |
| 🗄️ **Dashboard Qdrant** | http://localhost:6333/dashboard | Inspection de la base vectorielle |
| 🐘 **Adminer** | http://localhost:8080 | Consultation de PostgreSQL |
| 📈 **Langfuse** | http://localhost:3001 | Traces des agents (`admin@tui.local` / `tuiadmin123`) |

## 📊 Fonctionnalités

- **Assistant sourcé** : chaque réponse cite ses sources avec la notation `[n]` renvoyant aux articles du corpus, et signale explicitement quand l'information manque plutôt que d'inventer
- **Pipeline multi-agents** : analyse d'intention + détection des demandes de clarification, expansion de requête (multi-query + fusion **RRF**), puis synthèse structurée (synthèse / pistes de conception / limites)
- **Streaming en temps réel** : `/chat/stream` diffuse la progression de chaque agent puis la réponse token par token (SSE)
- **Authentification** : inscription / connexion JWT ; conversations et historique persistés par utilisateur
- **Gestion documentaire** : upload + indexation de PDF à chaud, listing du corpus indexé
- **Sélection du modèle LLM** par requête depuis l'interface
- **Évaluation** : campagnes de comparaison de modèles (récupération, fidélité, pertinence) avec scores remontés dans Langfuse

## 🔧 Configuration

### Variables d'environnement

La configuration se fait dans un fichier `.env` (copié depuis `.env.example`). Principales variables :

```bash
# LLM (Ollama)
OLLAMA_LLM_MODEL=qwen2.5:7b       # modèle par défaut (llama3.2:3b pour tester vite)
OLLAMA_UNDERSTAND_MODEL=          # modèle agent 1 (vide = OLLAMA_LLM_MODEL)
OLLAMA_SYNTHESIZE_MODEL=          # modèle agent 3 (vide = OLLAMA_LLM_MODEL)

# Embeddings & RAG
EMBEDDING_MODEL=BAAI/bge-m3       # embeddings locaux (1024 dim)
RETRIEVAL_TOP_K=6                 # chunks récupérés par requête
CHUNK_STRATEGY=blocks             # blocks (défaut, ordre de lecture) | char (texte aplati)
EXCLUDE_REFERENCES=true           # exclut les bibliographies de l'index

# Authentification
JWT_SECRET=dev-secret-change-me   # ⚠️ à changer en production (valeur longue et aléatoire)
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # durée de vie du jeton (24 h)

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Stratégie d'ingestion

L'indexation extrait le texte des PDF via **PyMuPDF** (blocs triés en ordre de lecture pour corriger les titres/colonnes), exclut automatiquement les sections bibliographiques, découpe en chunks (900 caractères, chevauchement 150), embed avec BGE-M3 et upsert dans Qdrant. Métadonnées (titre, auteurs, année, DOI) extraites automatiquement.

## 🛠️ Développement

### Structure du projet

```
code/
├── Makefile                     # raccourcis (make help)
├── docker-compose.yml           # postgres, adminer, qdrant, ollama, backend, frontend, langfuse
├── docker-compose.deploy.yml    # stack de déploiement (backend seul, sous-chemin Apache)
├── .env.example                 # configuration à copier en .env
├── files/                       # corpus PDF (monté en lecture seule dans le backend)
├── deploy/                      # runbook et configuration de déploiement (DEPLOY.md)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt         # dépendances runtime de l'API
│   ├── requirements-eval.txt    # dépendances d'évaluation (DeepEval, Langfuse)
│   ├── app/
│   │   ├── main.py              # point d'entrée FastAPI
│   │   ├── schemas.py           # I/O Pydantic
│   │   ├── core/config.py       # settings (.env)
│   │   ├── auth/                # sécurité JWT + dépendances
│   │   ├── db/                  # session + modèles SQLAlchemy
│   │   ├── rag/                 # embeddings, vectorstore, ingestion, retriever, grouping
│   │   ├── llm/ollama_client.py
│   │   ├── agents/              # state, prompts, nodes, graph (LangGraph)
│   │   ├── observability/       # tracing Langfuse (optionnel)
│   │   └── api/                 # routes_chat, routes_auth, routes_conversations, routes_documents
│   ├── eval/questions.json      # jeu de questions de référence
│   └── scripts/                 # ingest_corpus.py, evaluate.py, outils de diagnostic
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── app/                     # layout, page (chat), login, documents
    ├── components/              # Sidebar, Sources, AgentSteps, ModelSelector, ChatMessage…
    └── lib/api.ts               # client backend (attache le token, parse le SSE)
```

### Commandes de développement

```bash
# Cycle de vie de la stack
make up                # build + démarrage
make down              # arrêt (données conservées)
make clean             # arrêt + suppression des volumes (efface tout)
make rebuild-front     # force-recreate du frontend (soucis node_modules)

# Observation
make logs              # logs du backend
make ps                # statut des services
docker compose logs -f [service]     # logs d'un service précis
docker exec -it tui_backend bash     # shell dans le conteneur backend
```

### Test rapide de l'API

`/health` et `/models` sont publics ; `/chat` et `/chat/stream` exigent un JWT (s'inscrire / se connecter d'abord) :

```bash
# Santé de l'API
curl http://localhost:8000/health

# Récupérer un token puis poser une question
TOKEN=$(curl -s -X POST http://localhost:8000/auth/jwt/login \
  -d 'username=USER&password=PASS' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"Quels capteurs pour une TUI collaborative sur table ?"}'
```

### Évaluation

DeepEval mesure la qualité du RAG hors API (answer relevancy, faithfulness, hallucination, contextual relevancy). Le jeu de référence est dans `backend/eval/questions.json`, le harnais dans `backend/scripts/evaluate.py`. L'évaluation s'exécute **dans le conteneur backend** et pousse les scores dans Langfuse :

```bash
make eval                      # rappel de mots-clés + récupération (sans juge LLM)

# Ajouter les métriques DeepEval (juge local) :
make eval-deepeval
docker compose exec backend deepeval set-local-model \
  --model-name qwen2.5:7b --base-url http://ollama:11434/v1 --api-key ollama
make eval
```

## 📈 Monitoring

### Endpoints de santé

- `GET /health` : statut de l'API backend (public)
- `GET /models` : modèles LLM disponibles + modèle par défaut (public)

### Traçage

Si `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` sont renseignés, chaque exécution du pipeline est tracée dans Langfuse (http://localhost:3001). Vider ces clés désactive tout le traçage (no-op).

```bash
docker compose logs -f          # logs de tous les services
docker stats                    # utilisation CPU/RAM des conteneurs
docker system df                # espace disque Docker utilisé
```

## 🔒 Déploiement sur le serveur ESTIA

L'application est déployée en production sur le serveur **Apache mutualisé** de
l'ESTIA, sous le sous-chemin `https://devweb.estia.fr/tui_assistant`. La
topologie diffère du local :

```
Navigateur ── https://devweb.estia.fr/tui_assistant/ ──► Apache (déjà en place)
   ├─ /tui_assistant/       → front statique Next.js  (/var/www/html/tui_assistant)
   └─ /tui_assistant/api/   → .htaccess (mod_proxy) → 127.0.0.1:18000 (backend Docker)
```

- **Backend** : stack Docker (`docker-compose.deploy.yml`), backend seul exposé
  **uniquement** sur la loopback (`127.0.0.1:18000`), sans nginx ni frontend bundlé.
- **Frontend** : export statique Next.js (basePath `/tui_assistant`) déposé dans
  la racine Apache ; liaison à l'API via un `.htaccess` (`deploy/apache/`).

Cibles Make dédiées : `make deploy-up`, `deploy-down`, `deploy-logs`,
`deploy-ps`, `deploy-pull-models`, `deploy-ingest`, plus `make front-build`
(export statique du frontend via un conteneur Node jetable).

### Procédure résumée

```bash
# 1. Transférer le code (depuis le poste, à la racine du repo) — .env exclu
rsync -avz --delete --exclude '.git' --exclude '.env' --exclude 'node_modules' \
  --exclude '__pycache__' --exclude '*.zip' code/ "$SERVER:~/tui_assistant/"

# 2. Sur le serveur : configurer les secrets de prod
cd ~/tui_assistant && cp .env.prod.example .env && nano .env
#   -> JWT_SECRET, POSTGRES_PASSWORD, CORS_ORIGINS=https://devweb.estia.fr,
#      NEXT_PUBLIC_API_URL=https://devweb.estia.fr/tui_assistant/api

# 3. Démarrer le backend + indexer le corpus
make deploy-up && make deploy-pull-models && make deploy-ingest
curl -s http://127.0.0.1:18000/health          # -> {"status":"ok"}

# 4. Construire et déposer le front statique dans la racine Apache
make front-build
rm -rf /var/www/html/tui_assistant/_next
cp -r frontend/out/.  /var/www/html/tui_assistant/
cp deploy/apache/tui_assistant.htaccess /var/www/html/tui_assistant/.htaccess

# 5. Vérifier au travers d'Apache
curl -s https://devweb.estia.fr/tui_assistant/api/health   # {"status":"ok"}
```

> **Runbook complet** (prérequis, `.htaccess`/vhost, mises à jour, dépannage
> SSE/proxy) dans **[`deploy/DEPLOY.md`](deploy/DEPLOY.md)**.

Bonnes pratiques :
- Changer `JWT_SECRET` (valeur longue et aléatoire) et les mots de passe PostgreSQL par défaut
- Adapter `CORS_ORIGINS` et `NEXT_PUBLIC_API_URL` au domaine de production (voir `.env.prod.example`)
- En production, remplacer `Base.metadata.create_all` (dev) par des migrations Alembic

## 🆘 Dépannage

**Les services ne démarrent pas / port déjà utilisé :**
```bash
lsof -i :8000                   # identifier le processus occupant un port
make clean && make up           # repartir de zéro (⚠️ efface les volumes)
```

**Modèles Ollama manquants (`model not found`) :**
```bash
make pull-models
docker compose exec ollama ollama list
```

**Réponses lentes :** sans GPU, les modèles 7B sont lents — basculer `OLLAMA_LLM_MODEL=llama3.2:3b` dans `.env` puis `docker compose restart backend`.

**Le frontend ne se met pas à jour (node_modules) :**
```bash
make rebuild-front
```

**Réindexer le corpus après un changement de `CHUNK_STRATEGY` :** `make ingest` (l'ingestion est idempotente, elle remplace l'ancienne version de chaque fichier).

## 📝 Documentation API

L'API REST est documentée automatiquement (Swagger) sur http://localhost:8000/docs après déploiement. Endpoints principaux :

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| `POST` | `/auth/register` | — | Créer un compte |
| `POST` | `/auth/jwt/login` | — | Connexion (formulaire OAuth2), renvoie un JWT |
| `POST` | `/chat` | 🔒 | Question → réponse + sources (ou clarification) |
| `POST` | `/chat/stream` | 🔒 | Idem en streaming SSE (progression des agents + réponse token par token) |
| `GET` | `/conversations` | 🔒 | Historique des conversations de l'utilisateur |
| `GET` | `/documents` | 🔒 | Liste des documents indexés |
| `POST` | `/documents` | 🔒 | Upload + indexation d'un PDF (multipart) |
| `GET` | `/health` · `/models` | — | Statut du service · modèles disponibles |

## 📄 Licence

Projet développé dans le cadre d'un travail de bachelor à la HEIA-FR (HumanTech Institute), en collaboration avec l'ESTIA. Voir le [README racine](../README.md) pour les informations générales du projet.
