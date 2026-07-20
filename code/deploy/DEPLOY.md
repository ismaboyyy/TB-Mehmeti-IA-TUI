# Déploiement — devweb.estia.fr / tui_assistant

Déploiement sur un serveur **Apache partagé** (Debian), sous le sous-chemin
`https://devweb.estia.fr/tui_assistant`, **sans accès à la config Apache**
(dépôt de fichiers + `.htaccess` seulement).

## Architecture

```
Navigateur ── https://devweb.estia.fr/tui_assistant/ ──► Apache (déjà en place)
   ├─ /tui_assistant/         → fichiers statiques   (/var/www/html/tui_assistant)
   └─ /tui_assistant/api/     → .htaccess proxy → 127.0.0.1:18000 (backend Docker)
                                                          │
   Docker (même machine) : backend FastAPI + postgres + qdrant + ollama
```

- **Frontend** : export statique Next.js déposé dans `/var/www/html/tui_assistant`.
- **Backend** : stack Docker, backend exposé **uniquement** sur `127.0.0.1:8000`.
- **Liaison** : `.htaccess` (proxy `mod_proxy`). Repli IT : `deploy/apache/vhost-snippet.conf`.

Deux emplacements sur le serveur :
- `~/tui_assistant/`            → le code + la stack Docker
- `/var/www/html/tui_assistant/` → le front statique servi par Apache

---

## 0. Prérequis (à confirmer une fois)

- [ ] Test proxy `.htaccess` OK (recon : `GET /tui_assistant/probe/` → **200**).
      Sinon → passer par `deploy/apache/vhost-snippet.conf` (demande IT).
- [ ] Docker + Compose v2 présents (`docker --version`) ✅ (vérifié).
- [ ] Port `127.0.0.1:18000` libre (`ss -ltn | grep :18000`). 8000 est déjà pris sur ce serveur.
- [ ] Secrets prêts (générer des valeurs fortes) :
      `JWT_SECRET`, `POSTGRES_PASSWORD`.

```bash
# Définir une fois la cible (adapter l'utilisateur si besoin)
SERVER=ismail@65.109.84.104
```

---

## 1. Transférer le code (depuis ton poste)

`rsync` en **excluant** le superflu et surtout le `.env` local (secrets de dev) :

```bash
cd /Users/ismaboy/Documents/HESSO/bachelor/tb-mehmeti-ia-tui   # racine du repo
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

> `--exclude '.env'` protège aussi le `.env` du serveur contre `--delete`.
> `--exclude '*.zip'` : les PDF sont déjà extraits localement, inutile d'envoyer
> les archives (~3 Go de redondance évités).

---

## 2. Vérifier le corpus (sur le serveur)

Les PDF sont déjà en clair (pas de `.zip` à décompresser) :

```bash
ssh "$SERVER"
cd ~/tui_assistant
find files -name '*.pdf' | wc -l    # doit afficher ~339
```

---

## 3. Configurer le `.env` (sur le serveur)

```bash
cd ~/tui_assistant
cp .env.prod.example .env
nano .env
```

Valeurs **impératives** pour ce déploiement :

```ini
POSTGRES_PASSWORD=<mot_de_passe_fort>
JWT_SECRET=<secret_long_et_aleatoire>          # ex: openssl rand -hex 32
CORS_ORIGINS=https://devweb.estia.fr
NEXT_PUBLIC_API_URL=https://devweb.estia.fr/tui_assistant/api
# Langfuse : laisser vide pour désactiver le tracing (recommandé en prod simple)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

---

## 4. Démarrer le backend (sur le serveur)

```bash
cd ~/tui_assistant
make deploy-up            # build + démarre postgres, qdrant, ollama, backend
make deploy-pull-models   # télécharge les modèles Ollama (long, une seule fois)
make deploy-ingest        # indexe le corpus (long ; BGE-M3 ~2 Go au 1er run)
make deploy-ps            # tout doit être "healthy"/"running"
curl -s http://127.0.0.1:18000/health   # -> {"status":"ok"}
```

---

## 5. Construire et déposer le frontend statique (sur le serveur)

Build via un conteneur Node jetable (aucun Node à installer sur l'hôte) :

```bash
cd ~/tui_assistant
make front-build          # génère frontend/out/ (export statique, basePath /tui_assistant)

# Déposer dans la racine Apache
mkdir -p /var/www/html/tui_assistant
rm -rf /var/www/html/tui_assistant/_next          # purge l'ancien build
cp -r frontend/out/.  /var/www/html/tui_assistant/
cp deploy/apache/tui_assistant.htaccess /var/www/html/tui_assistant/.htaccess
```

---

## 6. Vérification

```bash
# Front (depuis n'importe où)
curl -s -o /dev/null -w "%{http_code}\n" https://devweb.estia.fr/tui_assistant/   # 200
# API au travers d'Apache
curl -s https://devweb.estia.fr/tui_assistant/api/health                          # {"status":"ok"}
curl -s https://devweb.estia.fr/tui_assistant/api/models                          # liste des modèles
```

Puis dans le navigateur : ouvrir `https://devweb.estia.fr/tui_assistant/`,
créer un compte, poser une question, vérifier le streaming + les sources.

---

## 7. Mises à jour ultérieures

```bash
# Sur le poste : re-rsync (étape 1)
# Sur le serveur :
cd ~/tui_assistant
make deploy-up            # rebuild + redémarre le backend
make front-build && rm -rf /var/www/html/tui_assistant/_next && \
  cp -r frontend/out/. /var/www/html/tui_assistant/   # re-déploie le front
```

Le code seul change rarement le schéma DB ; en cas de modèle de données
modifié, voir « contraintes connues » (pas d'Alembic, `create_all` au démarrage).

---

## 8. Dépannage

| Symptôme | Cause probable | Piste |
|---|---|---|
| Front charge mais assets 404 | `NEXT_PUBLIC_BASE_PATH` absent au build | rebuilder avec `make front-build` |
| Appels API échouent (404) | `.htaccess` proxy inactif | test `/probe/` ; sinon vhost-snippet (IT) |
| Appels API bloqués (mixed content) | `NEXT_PUBLIC_API_URL` en http:// | doit être `https://…/tui_assistant/api` |
| 502 sur l'API | backend pas prêt / down | `make deploy-logs`, `make deploy-ps` |
| Streaming saccadé / d'un bloc | buffering proxy SSE | vérifier la règle `no-gzip` du `.htaccess` |
