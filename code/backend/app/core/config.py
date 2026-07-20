"""Configuration centralisée, lue depuis les variables d'environnement (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL
    postgres_user: str = "tui"
    postgres_password: str = "tui_password"
    postgres_db: str = "tui_assistant"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "tui_chunks"

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_llm_model: str = "qwen2.5:7b"
    # Modèles proposés dans l'interface (séparés par des virgules)
    ollama_models: str = "llama3.2:3b,qwen2.5:7b,mistral:7b"
    # Modèles par agent (optionnels). Vide -> on retombe sur le modèle de la requête
    # (lui-même -> ollama_llm_model). Permet, ex., un petit modèle pour la
    # reformulation (agent 1) et un plus gros pour la synthèse (agent 3).
    ollama_understand_model: str = ""   # agent 1 : reformulation
    ollama_synthesize_model: str = ""   # agent 3 : synthèse
    # Listes de modèles proposées PAR AGENT dans l'interface (séparées par des
    # virgules). Vide -> on retombe sur OLLAMA_MODELS (liste unique commune).
    # Permet ex. d'imposer un gros modèle pour la reformulation et d'en offrir
    # plusieurs pour la synthèse.
    ollama_understand_models: str = ""  # choix agent 1 (reformulation)
    ollama_synthesize_models: str = ""  # choix agent 3 (synthèse)

    # Embeddings
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # RAG
    chunk_size: int = 900
    chunk_overlap: int = 150
    retrieval_top_k: int = 6
    # Sources regroupées par article : on récupère un pool de chunks puis on les
    # regroupe par document (≤ max_articles), en gardant ≤ max_passages pages.
    retrieval_pool: int = 24
    # Expansion de requête (multi-query + fusion RRF) : nombre max de reformulations
    # générées par l'agent 1. 1 = comportement mono-requête (désactive l'expansion).
    query_expansion_max: int = 4
    sources_max_articles: int = 8
    sources_max_passages: int = 2
    # Longueur minimale (en mots) d'un passage retenu comme source. Écarte les
    # en-têtes / titres courants réindexés à chaque page (bruit sans contenu).
    # 0 = pas de filtre.
    sources_min_passage_words: int = 12
    # Stratégie de découpage à l'ingestion :
    #   "blocks" -> blocs PyMuPDF triés en ordre de lecture, puis découpés (par défaut)
    #   "char"   -> texte aplati découpé par caractères
    chunk_strategy: str = "blocks"
    # Exclut les sections bibliographiques de l'index (stratégie "blocks" uniquement) :
    # les blocs de références ne sont jamais indexés -> l'agent 2 ne peut pas tomber dessus.
    exclude_references: bool = True

    # Préfixe d'URL quand l'API est servie derrière un reverse-proxy sous un
    # sous-chemin (ex. Apache : /tui_assistant/api). Vide en local. Sert à ce que
    # Swagger (/docs) référence le bon /openapi.json à travers le proxy.
    root_path: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Authentification (JWT)
    jwt_secret: str = "dev-secret-change-me"        # À SURCHARGER en production
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24       # 24 h

    # Langfuse (tracing optionnel) — actif uniquement si les clés sont fournies
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ollama_models_list(self) -> list[str]:
        models = [m.strip() for m in self.ollama_models.split(",") if m.strip()]
        # garantit que le modèle par défaut figure dans la liste
        if self.ollama_llm_model not in models:
            models.insert(0, self.ollama_llm_model)
        return models

    @staticmethod
    def _split_models(raw: str) -> list[str]:
        return [m.strip() for m in raw.split(",") if m.strip()]

    @property
    def ollama_understand_models_list(self) -> list[str]:
        """Modèles offerts pour l'agent 1 (repli sur la liste commune si vide)."""
        return self._split_models(self.ollama_understand_models) or self.ollama_models_list

    @property
    def ollama_synthesize_models_list(self) -> list[str]:
        """Modèles offerts pour l'agent 3 (repli sur la liste commune si vide)."""
        return self._split_models(self.ollama_synthesize_models) or self.ollama_models_list

    @property
    def ollama_understand_default(self) -> str:
        """Modèle de reformulation présélectionné : défaut explicite, sinon 1er de la liste."""
        return self.ollama_understand_model or self.ollama_understand_models_list[0]

    @property
    def ollama_synthesize_default(self) -> str:
        """Modèle de synthèse présélectionné : défaut explicite, sinon 1er de la liste."""
        return self.ollama_synthesize_model or self.ollama_synthesize_models_list[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
