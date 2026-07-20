"""Accès à Qdrant : création de la collection et opérations upsert / search.

Modèle de payload stocké avec chaque vecteur (chunk) :
    {
        "document_id": str,   # FK vers documents.id (PostgreSQL)
        "filename": str,
        "title": str | None,
        "authors": str | None,
        "year": int | None,
        "doi": str | None,
        "page": int | None,   # page du PDF d'où provient le chunk
        "chunk_index": int,
        "text": str           # texte du chunk (pour l'affichage des sources)
    }
"""
from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings


@lru_cache
def get_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection() -> None:
    """Crée la collection si elle n'existe pas (vecteurs denses, distance cosinus)."""
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )


def upsert_chunks(points: list[PointStruct]) -> None:
    get_client().upsert(collection_name=settings.qdrant_collection, points=points)


def delete_by_document_id(document_id: str) -> None:
    """Supprime tous les points (chunks) d'un document donné.

    Sert à rendre la ré-indexation idempotente : on purge les chunks de
    l'ancienne version avant d'insérer ceux de la nouvelle (cf. ingest_pdf).
    """
    get_client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        ),
    )


def search(query_vector: list[float], top_k: int, year: int | None = None) -> list[dict]:
    """Recherche sémantique. Filtre optionnel par année."""
    flt = None
    if year is not None:
        flt = Filter(must=[FieldCondition(key="year", match=MatchValue(value=year))])

    hits = get_client().search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        limit=top_k,
        query_filter=flt,
        with_payload=True,
    )
    return [{"score": h.score, **h.payload} for h in hits]
