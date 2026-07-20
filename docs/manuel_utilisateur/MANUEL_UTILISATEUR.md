# Manuel utilisateur — Assistant IA pour la conception d'interfaces tangibles (TUI)

Guide opérationnel : déploiement, accès et consultation des résultats.

- **Application** : Assistant IA pour la conception d'interfaces tangibles (TUI)
- **Public** : responsable du déploiement, encadrants et utilisateurs de démonstration
- **Environnements** : serveur ESTIA `devweb.estia.fr` (production) et poste local (développement)

## Liens utiles

| Ressource | Lien |
|-----------|------|
| Dépôt Git (GitHub) | https://github.com/ismaboyyy/TB-Mehmeti-IA-TUI/tree/main |
| Application en production | https://devweb.estia.fr/tui_assistant/login/ |
| Langfuse (production, Cloud) | https://cloud.langfuse.com/project/cmrj8dhtq00ayad0cqom2ls5w/ |

## L'essentiel

- En production, l'application est disponible sur https://devweb.estia.fr/tui_assistant/login/.
- En local, l'application est disponible sur http://localhost:3000.
- Il n'existe **pas de compte partagé par défaut** : chaque utilisateur crée son compte avec un email et un mot de passe.
- Une réponse se consulte dans le chat avec ses citations `[n]`, ses sources scientifiques et l'historique de la conversation.
- Les résultats d'évaluation sont enregistrés dans `code/backend/eval/results/`. En production, le tracing est envoyé à Langfuse Cloud ; en local, il peut aussi être consulté dans Langfuse.

---

## 1. Récupérer le code (git clone)

Cloner le dépôt depuis GitHub puis entrer dans le projet :

```bash
git clone https://github.com/ismaboyyy/TB-Mehmeti-IA-TUI.git
```

```bash
cd TB-Mehmeti-IA-TUI
```

> Pour cloner via SSH (si une clé SSH GitHub est configurée) :
> ```bash
> git clone git@github.com:ismaboyyy/TB-Mehmeti-IA-TUI.git
> ```

---

## 2. Déployer sur le serveur ESTIA (production)

### Prérequis serveur

- accès SSH au serveur `65.109.84.104`
- Docker et Docker Compose v2
- port local `127.0.0.1:18000` disponible
- accès en écriture à `/var/www/html/tui_assistant`
- proxy Apache `.htaccess` autorisé, ou intervention IT avec `deploy/apache/vhost-snippet.conf`

### Étape 1 — Transférer le code

Depuis la racine du projet, remplacer `<utilisateur-ssh>` par le compte attribué :

```bash
SERVER=<utilisateur-ssh>@65.109.84.104
```

```bash
rsync -avz --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude 'out' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.tsbuildinfo' \
  --exclude 'pdf_analysis' \
  --exclude '.DS_Store' \
  --exclude '.env' \
  --exclude '*.zip' \
  code/ "$SERVER:~/tui_assistant/"
```

> **Attention** : `--delete` supprime sur le serveur les fichiers absents de la source, à l'exception des éléments exclus. Le fichier `.env` du serveur est explicitement protégé.

### Étape 2 — Configurer la production

Se connecter au serveur :

```bash
ssh "$SERVER"
```

```bash
cd ~/tui_assistant
```

Créer le fichier `.env` de production :

```bash
cp .env.prod.example .env
```

```bash
nano .env
```

Modifier au minimum :

```bash
POSTGRES_PASSWORD=<mot_de_passe_fort>
JWT_SECRET=<secret_long_et_aleatoire>
CORS_ORIGINS=https://devweb.estia.fr
NEXT_PUBLIC_API_URL=https://devweb.estia.fr/tui_assistant/api
```

Générer un secret JWT :

```bash
openssl rand -hex 32
```

> Ne jamais copier les mots de passe de développement en production. Pour activer le tracing Langfuse Cloud en production, renseigner `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` et `LANGFUSE_HOST` avec les clés du projet Langfuse Cloud ; laisser ces variables vides désactive tout tracing.

### Étape 3 — Démarrer le backend et indexer le corpus

```bash
cd ~/tui_assistant
```

```bash
make deploy-up
```

```bash
make deploy-pull-models
```

Nécessaire avec `.env.prod.example`, qui utilise `qwen2.5:14b` pour la synthèse :

```bash
docker compose -f docker-compose.deploy.yml exec ollama ollama pull qwen2.5:14b
```

```bash
make deploy-ingest
```

```bash
make deploy-ps
```

```bash
curl -s http://127.0.0.1:18000/health
```

> Le dernier appel doit retourner `{"status":"ok"}`. Le téléchargement des modèles et l'indexation complète peuvent durer plusieurs minutes.

### Étape 4 — Construire et publier le frontend

```bash
cd ~/tui_assistant
```

```bash
make front-build
```

```bash
mkdir -p /var/www/html/tui_assistant
```

```bash
rm -rf /var/www/html/tui_assistant/_next
```

```bash
cp -r frontend/out/. /var/www/html/tui_assistant/
```

```bash
cp deploy/apache/tui_assistant.htaccess /var/www/html/tui_assistant/.htaccess
```

### Étape 5 — Vérifier la mise en ligne

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://devweb.estia.fr/tui_assistant/
```

```bash
curl -s https://devweb.estia.fr/tui_assistant/api/health
```

```bash
curl -s https://devweb.estia.fr/tui_assistant/api/models
```

Résultats attendus : code HTTP 200, état `ok`, puis liste des modèles disponibles.

Effectuer enfin un test fonctionnel dans le navigateur sur https://devweb.estia.fr/tui_assistant/login/ : créer un compte, poser une question, attendre la synthèse et ouvrir les sources.

### Mettre à jour une version déjà déployée

1. Relancer le transfert `rsync` depuis le poste.
2. Sur le serveur, exécuter `make deploy-up`.
3. Si le frontend a changé, relancer `make front-build`, supprimer l'ancien dossier `_next`, puis recopier `frontend/out/`.
4. Revérifier `/api/health` et effectuer une question de test.

---

## 3. Déployer l'application en local (développement)

### Prérequis

- Docker Engine 20.10 ou plus récent
- Docker Compose v2
- environ 10 Go d'espace disque
- 16 Go de RAM recommandés
- ports 3000, 3001, 5432, 6333, 8000, 8080 et 11434 disponibles

### Installation (commandes une par une)

Entrer dans le dossier `code/` :

```bash
cd code
```

Construire et démarrer la pile complète (crée automatiquement `code/.env` à partir de `.env.example` s'il n'existe pas) :

```bash
make up
```

Télécharger les modèles LLM dans Ollama :

```bash
make pull-models
```

Indexer un échantillon du corpus (validation rapide) :

```bash
make ingest-sample
```

Ou indexer le corpus complet (plus long) :

```bash
make ingest
```

Vérifier l'état des services :

```bash
make ps
```

> Le premier démarrage est plus long : Docker construit les images et le backend télécharge le modèle d'embeddings BGE-M3.

### Vérification

```bash
curl http://localhost:8000/health
```

Résultat attendu : `{"status":"ok"}`

Ouvrir ensuite http://localhost:3000 dans un navigateur.

---

## 4. Ajouter des documents au corpus (ingestion)

Le corpus est l'ensemble des PDF scientifiques que l'assistant peut citer. **L'assistant ne répond qu'à partir des documents indexés** : ajouter un PDF au corpus le rend interrogeable, une fois l'ingestion effectuée. Deux méthodes existent.

### 4.1 Méthode 1 — Dossier du corpus + make ingest (indexation en masse)

Le dossier `code/files/` est monté en lecture seule dans le backend sous `/data/files`. C'est là que vivent les documents.

Étape 1 — Placer les PDF dans `code/files/` (fichiers isolés ou rangés dans des sous-dossiers) :

```bash
cp mon_article.pdf code/files/
```

> Le script parcourt `code/files/` **récursivement** et ne prend que les fichiers `*.pdf`. Une archive `.zip` doit être décompressée au préalable. Si un sous-dossier porte un nom d'année sur 4 chiffres (ex. `code/files/2025/`), l'année est déduite automatiquement du chemin.

Étape 2 — Lancer l'indexation.

En local, indexer **tout** le corpus :

```bash
cd code
```

```bash
make ingest
```

Ou indexer un **sous-dossier précis** (plus rapide, pour n'ajouter qu'un lot) :

```bash
docker compose exec backend python scripts/ingest_corpus.py /data/files/estia
```

En production, sur le serveur (après avoir transféré les PDF avec `rsync`) :

```bash
make deploy-ingest
```

> Chaque PDF est découpé en fragments (chunks), encodé avec BGE-M3 et enregistré dans Qdrant ; les métadonnées (titre, auteurs, année, DOI, pages) vont dans PostgreSQL. Réindexer un document déjà présent le met à jour. Le premier `make ingest` télécharge le modèle d'embeddings (~2 Go) et peut être long.

### 4.2 Méthode 2 — Upload depuis l'interface web (un document à la fois)

1. Se connecter à l'application, puis ouvrir la page **Corpus documentaire** :
   - Local : http://localhost:3000/documents
   - Production : https://devweb.estia.fr/tui_assistant/documents
2. Cliquer sur **Ajouter / Upload**, choisir un fichier PDF.
3. Le document est indexé automatiquement à la réception ; il apparaît ensuite dans la liste et devient interrogeable dans le chat.

> Cette méthode convient pour ajouter ponctuellement un document. Pour un grand nombre de PDF, préférer la méthode 1 (`make ingest`).

---

## 5. Comptes et identifiants (logins / mots de passe)

> **Important** : il n'existe **pas de compte utilisateur préinstallé** pour l'application TUI. Ce n'est pas un identifiant manquant. À la première ouverture, utiliser **Créer un compte** sur la page de connexion. Les comptes de **production** et les comptes **locaux** sont deux ensembles séparés.

### 5.1 Identifiants en production (serveur ESTIA)

| Accès | Adresse | Login / authentification |
|-------|---------|--------------------------|
| Application TUI (production) | https://devweb.estia.fr/tui_assistant/login/ | Compte créé sur la page de connexion de production (**Créer un compte**) |
| Langfuse (Cloud) | https://cloud.langfuse.com/project/cmrj8dhtq00ayad0cqom2ls5w/ | Connexion avec le compte Langfuse Cloud du projet |
| SSH ESTIA | `ssh ismail@65.109.84.104` | Utilisateur `ismail` ; clé SSH ou mot de passe attribué par l'administrateur du serveur (non stocké dans le dépôt) |
| Backend de production (depuis le serveur) | `http://127.0.0.1:18000` | Aucun login pour `/health` et `/models` ; JWT d'un compte TUI pour les routes protégées |
| PostgreSQL de production | Service Docker `postgres:5432` | Utilisateur `tui` ; base `tui_assistant` ; mot de passe = `POSTGRES_PASSWORD` du fichier `~/tui_assistant/.env` |

> Le mot de passe PostgreSQL de production, le secret JWT et les clés Langfuse **ne doivent pas** être copiés dans cette documentation versionnée ; ils restent dans le fichier `.env` du serveur (et dans le compte Langfuse Cloud).

**Pages de production :**

| Page | URL |
|------|-----|
| Chat / connexion | https://devweb.estia.fr/tui_assistant/login/ |
| Corpus documentaire | https://devweb.estia.fr/tui_assistant/documents |
| Swagger (API) | https://devweb.estia.fr/tui_assistant/api/docs |
| Santé / modèles | https://devweb.estia.fr/tui_assistant/api/health et `/models` |

### 5.2 Identifiants en local (développement)

| Accès | Login | Mot de passe |
|-------|-------|--------------|
| Application TUI (chat) | Email choisi à l'inscription | Mot de passe choisi à l'inscription (6 caractères min.) |
| Langfuse local (http://localhost:3001) | `admin@tui.local` | `tuiadmin123` |
| Adminer / PostgreSQL local (http://localhost:8080) | `tui` | `tui_password` |
| PostgreSQL direct (`localhost:5432`) | `tui` | `tui_password` (base `tui_assistant`) |
| Base interne Langfuse (`langfuse-db:5432`) | `langfuse` | `langfuse` (base `langfuse`) |
| Qdrant Dashboard (http://localhost:6333/dashboard) | — | Aucun |
| Ollama API (http://localhost:11434/api/tags) | — | Aucun |
| API FastAPI — `/health`, `/models`, `/docs` | — | Aucun (pages publiques) |
| API FastAPI — routes protégées | Compte TUI (email) | via JWT après connexion |

Détails Adminer : Système `PostgreSQL` ; serveur `postgres` ; utilisateur `tui` ; mot de passe `tui_password` ; base `tui_assistant`.

**Pages locales :**

| Page | URL |
|------|-----|
| Chat | http://localhost:3000/ |
| Connexion / inscription | http://localhost:3000/login |
| Corpus documentaire | http://localhost:3000/documents |
| Swagger (API) | http://localhost:8000/docs |
| Santé / modèles | http://localhost:8000/health et `/models` |

> Après une inscription réussie, la connexion est automatique. Le jeton JWT est conservé dans le navigateur et dure **24 heures** avec la configuration fournie. Pour Swagger, le champ `username` correspond à l'adresse email. Les identifiants fixes de la section 5.2 sont **réservés au développement local** : Langfuse local, Adminer, Qdrant, Ollama et PostgreSQL ne sont pas publiés sur Internet par `docker-compose.deploy.yml`.

---

## 6. Consulter les résultats

### Résultats visibles par l'utilisateur

1. Ouvrir l'application et se connecter.
2. Cliquer sur **Nouvelle conversation**.
3. Saisir une question liée aux interfaces tangibles.
4. Suivre les étapes affichées : compréhension, recherche, puis synthèse.
5. Lire la réponse structurée et repérer les citations `[1]`, `[2]`, etc.
6. Cliquer sur une citation ou ouvrir le bloc **sources scientifiques** pour voir le titre, les auteurs, l'année, le score, les pages retenues et le DOI lorsqu'il existe.
7. Retrouver la réponse plus tard dans l'historique situé à gauche.

> Une réponse sans sources ou demandant une précision n'est pas nécessairement une erreur : le système peut signaler que le corpus ne permet pas de répondre, ou demander une question plus précise.

### Résultats des campagnes d'évaluation

Lancer l'évaluation déterministe :

```bash
cd code
```

```bash
EVAL_SKIP_JUDGE=1 make eval
```

Activer les métriques évaluées par un modèle local :

```bash
make eval-deepeval
```

```bash
docker compose exec backend deepeval set-local-model \
  --model-name qwen2.5:7b \
  --base-url http://ollama:11434/v1 \
  --api-key ollama
```

```bash
make eval
```

Chaque exécution crée un fichier JSON dans `code/backend/eval/results/`. Exemples de lecture :

```bash
cd code
```

```bash
ls -lt backend/eval/results/
```

```bash
jq '.config' backend/eval/results/<fichier>.json
```

```bash
jq -r '.results[] | [.id, (.scores | tojson)] | @tsv' backend/eval/results/<fichier>.json
```

> Le JSON contient la configuration testée, chaque question, la réponse produite et les scores : rappel des mots-clés, précision et rappel du contexte, refus attendu et, si DeepEval est actif, fidélité et pertinence.

### Résultats dans Langfuse

**En production**, le tracing est envoyé à Langfuse Cloud :

1. Ouvrir https://cloud.langfuse.com/project/cmrj8dhtq00ayad0cqom2ls5w/.
2. Se connecter avec le compte Langfuse Cloud du projet.
3. Utiliser **Dashboard / Scores** pour les graphiques de métriques et **Traces** pour inspecter une question, les étapes des agents, les modèles et les temps d'exécution.

**En local** :

1. Ouvrir http://localhost:3001.
2. Se connecter avec `admin@tui.local` / `tuiadmin123`.
3. Ouvrir le projet **Assistant TUI**.
4. Utiliser **Dashboard / Scores** pour les graphiques de métriques.
5. Utiliser **Traces** pour inspecter une question, les étapes des agents, les modèles et les temps d'exécution.
6. Filtrer avec le libellé du run, par exemple `reform_mistral` ou `synth_7b`.

> Le tracing dépend des clés `LANGFUSE_*`. Si elles sont absentes, le JSON local des évaluations reste disponible même sans Langfuse.

---

## 7. Checklist de recette

- [ ] `make deploy-ps` indique que les services sont démarrés et que le backend est sain.
- [ ] L'URL publique renvoie un code HTTP 200.
- [ ] `/tui_assistant/api/health` renvoie `{"status":"ok"}`.
- [ ] Un nouvel utilisateur peut s'inscrire et se reconnecter.
- [ ] Une question produit une réponse, des citations et des sources ouvrables.
- [ ] La conversation réapparaît après actualisation de la page.
- [ ] Aucun secret de production n'est présent dans Git.

---

## 8. Dépannage rapide

| Symptôme | Vérification ou correction |
|----------|----------------------------|
| Le frontend répond, mais l'API renvoie 404 | Vérifier le `.htaccess` et le proxy vers `127.0.0.1:18000`. |
| L'API renvoie 502 | Exécuter `make deploy-ps` puis `make deploy-logs`. |
| Le modèle est introuvable | Vérifier `ollama list` et télécharger le modèle manquant, notamment `qwen2.5:14b` en production. |
| Les assets `_next` renvoient 404 | Relancer `make front-build` et recopier entièrement `frontend/out/`. |
| Connexion refusée | Vérifier l'email, le mot de passe et l'heure du serveur ; recréer le compte si nécessaire. |
| Les résultats n'apparaissent pas dans Langfuse | Vérifier les clés `LANGFUSE_*` ; le JSON local reste disponible même sans Langfuse. |

---

## Références dans le dépôt

- Procédure de production : `code/deploy/DEPLOY.md`
- Commandes : `code/Makefile`
- Configurations : `code/.env.example` et `code/.env.prod.example`
- Guide général : `code/README.md`
- Harnais d'évaluation : `code/backend/scripts/evaluate.py`
