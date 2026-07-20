"""Embeddings BGE-M3 (multilingue, open source, exécuté localement).

On encapsule FlagEmbedding dans une petite classe singleton pour ne charger
le modèle qu'une seule fois (il est lourd ~2 Go).
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings


class BGEM3Embedder:
    def __init__(self, model_name: str) -> None:
        # Import différé : évite de charger torch tant que ce n'est pas nécessaire
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(model_name, use_fp16=True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out = self._model.encode(texts, batch_size=16, max_length=1024)
        return [vec.tolist() for vec in out["dense_vecs"]]

    def embed_query(self, text: str) -> list[float]:
        out = self._model.encode([text], max_length=1024)
        return out["dense_vecs"][0].tolist()


@lru_cache
def get_embedder() -> BGEM3Embedder:
    return BGEM3Embedder(settings.embedding_model)
