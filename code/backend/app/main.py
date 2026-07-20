"""Point d'entrée FastAPI."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_auth, routes_chat, routes_conversations, routes_documents
from app.core.config import settings
from app.db.models import Base
from app.db.session import engine
from app.rag.vectorstore import ensure_collection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables PostgreSQL et la collection Qdrant au démarrage.
    Base.metadata.create_all(bind=engine)
    try:
        ensure_collection()
    except Exception as exc:  # Qdrant peut ne pas être prêt : on log sans crasher
        print(f"[startup] Qdrant non disponible : {exc}")
    yield


app = FastAPI(
    title="Assistant TUI — API",
    version="0.1.0",
    lifespan=lifespan,
    # Derrière un proxy sous-chemin (prod), fait pointer /docs vers le bon
    # /openapi.json (vide en local -> comportement inchangé).
    root_path=settings.root_path,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_chat.router)
app.include_router(routes_conversations.router)
app.include_router(routes_documents.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/models", tags=["chat"])
def models() -> dict:
    """Modèles LLM proposés dans l'interface.

    `available`/`default` : liste commune (compatibilité ascendante).
    `understand`/`synthesize` : listes et présélection PAR AGENT (l'UI propose
    des modèles différents pour la reformulation et pour la synthèse).
    """
    return {
        "default": settings.ollama_llm_model,
        "available": settings.ollama_models_list,
        "understand": {
            "default": settings.ollama_understand_default,
            "available": settings.ollama_understand_models_list,
        },
        "synthesize": {
            "default": settings.ollama_synthesize_default,
            "available": settings.ollama_synthesize_models_list,
        },
    }
