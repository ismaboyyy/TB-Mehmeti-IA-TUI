# =====================================================================
# Raccourcis de démarrage local. Usage : make <cible>
#   make help        liste les cibles
# Prérequis : Docker + Docker Compose v2.
# =====================================================================
.DEFAULT_GOAL := help
COMPOSE := docker compose
SAMPLE := /data/files/2025/acm_pdfs_1780919421048

COMPOSE_DEPLOY := docker compose -f docker-compose.deploy.yml

# Déploiement sous-chemin (devweb.estia.fr/tui_assistant) — surchargeable :
#   make front-build FRONT_API_URL=https://autre-hote/tui_assistant/api
DEPLOY_BASE_PATH := /tui_assistant
FRONT_API_URL := https://devweb.estia.fr/tui_assistant/api

.PHONY: help env up down restart build logs ps pull-models ingest ingest-sample eval eval-deepeval clean rebuild-front \
        deploy-up deploy-down deploy-clean deploy-logs deploy-ps deploy-pull-models deploy-ingest front-build

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Crée le fichier .env à partir de .env.example (s'il n'existe pas)
	@test -f .env || (cp .env.example .env && echo ".env créé")

up: env ## Démarre toute la stack (postgres, qdrant, ollama, backend, frontend)
	$(COMPOSE) up -d --build

down: ## Arrête la stack (les volumes/données sont conservés)
	$(COMPOSE) down

restart: ## Redémarre la stack
	$(COMPOSE) restart

rebuild-front: ## Reconstruit le frontend et renouvelle son node_modules (fix dépendances)
	$(COMPOSE) up -d --build --force-recreate --renew-anon-volumes frontend

build: ## Reconstruit les images
	$(COMPOSE) build

logs: ## Suit les logs du backend
	$(COMPOSE) logs -f backend

ps: ## État des services
	$(COMPOSE) ps

pull-models: ## Télécharge les modèles Ollama (3B d'abord, puis 7B)
	$(COMPOSE) exec ollama ollama pull llama3.2:3b
	$(COMPOSE) exec ollama ollama pull qwen2.5:7b
	$(COMPOSE) exec ollama ollama pull mistral:7b

ingest: ## Indexe tout le corpus PDF (/data/files)
	$(COMPOSE) exec backend python scripts/ingest_corpus.py /data/files

ingest-sample: ## Indexe un petit échantillon pour tester rapidement
	$(COMPOSE) exec backend python scripts/ingest_corpus.py $(SAMPLE)

eval: ## Lance l'évaluation DANS le conteneur backend (pousse les scores dans Langfuse)
	## Variables optionnelles (comparer des configs) :
	##   EVAL_UNDERSTAND_MODEL=<m>  modèle agent 1 (reformulation)
	##   EVAL_SYNTHESIZE_MODEL=<m>  modèle agent 3 (synthèse)
	##   EVAL_LABEL=<nom>           étiquette du run (Langfuse + nom de fichier)
	##   EVAL_SKIP_JUDGE=1          métriques déterministes seulement (sans juge, rapide)
	$(COMPOSE) exec -e EVAL_UNDERSTAND_MODEL -e EVAL_SYNTHESIZE_MODEL -e EVAL_LABEL -e EVAL_SKIP_JUDGE \
		backend python scripts/evaluate.py

eval-deepeval: ## (Optionnel) ajoute DeepEval dans le conteneur pour les métriques LLM
	$(COMPOSE) exec backend pip install -r requirements-eval.txt
	@echo "Configure le juge local (DeepEval 2.x, via l'API compatible OpenAI d'Ollama) :"
	@echo "  docker compose exec backend deepeval set-local-model --model-name qwen2.5:7b --base-url http://ollama:11434/v1 --api-key ollama"

clean: ## Arrête et SUPPRIME les volumes (efface DB + index Qdrant + modèles)
	$(COMPOSE) down -v

# ---------------------------------------------------------------------
# Cibles de DÉPLOIEMENT (devweb.estia.fr, Apache + front statique)
#   -> backend seul en Docker (127.0.0.1:8000), voir deploy/DEPLOY.md
# ---------------------------------------------------------------------
deploy-up: env ## Démarre la stack de déploiement (backend sur 127.0.0.1:8000)
	$(COMPOSE_DEPLOY) up -d --build

deploy-down: ## Arrête la stack de déploiement (volumes conservés -> données gardées)
	$(COMPOSE_DEPLOY) down

deploy-clean: ## DANGER : arrête ET supprime les volumes (efface DB + index + modèles)
	$(COMPOSE_DEPLOY) down -v

deploy-logs: ## Suit les logs backend (déploiement)
	$(COMPOSE_DEPLOY) logs -f backend

deploy-ps: ## État des services (déploiement)
	$(COMPOSE_DEPLOY) ps

deploy-pull-models: ## Télécharge les modèles Ollama (déploiement)
	$(COMPOSE_DEPLOY) exec ollama ollama pull llama3.2:3b
	$(COMPOSE_DEPLOY) exec ollama ollama pull qwen2.5:7b
	$(COMPOSE_DEPLOY) exec ollama ollama pull mistral:7b

deploy-ingest: ## Indexe tout le corpus PDF (déploiement)
	$(COMPOSE_DEPLOY) exec backend python scripts/ingest_corpus.py /data/files

front-build: ## Build le frontend en export statique -> frontend/out/ (Node Docker jetable)
	docker run --rm -v "$(CURDIR)/frontend":/app -w /app \
	  -e NEXT_OUTPUT=export \
	  -e NEXT_PUBLIC_BASE_PATH=$(DEPLOY_BASE_PATH) \
	  -e NEXT_PUBLIC_API_URL=$(FRONT_API_URL) \
	  node:20-alpine sh -lc "npm ci && npm run build"
