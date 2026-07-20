"""Recherche sémantique : embedding de la requête + search Qdrant.
Renvoie une liste de passages avec leurs métadonnées (sources)."""
from __future__ import annotations

from app.core.config import settings
from app.rag.embeddings import get_embedder
from app.rag.vectorstore import search


def retrieve(query: str, top_k: int | None = None, year: int | None = None) -> list[dict]:
    top_k = top_k or settings.retrieval_top_k
    query_vector = get_embedder().embed_query(query)
    return search(query_vector, top_k=top_k, year=year)


# Constante standard de la Reciprocal Rank Fusion (amortit le poids des rangs).
_RRF_K = 60


def retrieve_multi(
    queries: list[str], top_k: int | None = None, year: int | None = None
) -> list[dict]:
    """Récupération multi-requêtes avec fusion RRF (Reciprocal Rank Fusion).

    Chaque requête est cherchée séparément dans Qdrant ; les résultats sont
    fusionnés en additionnant, pour chaque chunk, 1 / (RRF_K + rang) sur toutes
    les requêtes où il apparaît. Un chunk trouvé par PLUSIEURS reformulations
    remonte donc naturellement. Déduplication par (document_id, chunk_index).
    Renvoie les chunks triés par score de fusion décroissant.
    """
    top_k = top_k or settings.retrieval_pool
    queries = [q for q in (q.strip() for q in queries) if q] or [""]
    embedder = get_embedder()

    fused: dict[tuple, dict] = {}
    for q in queries:
        hits = search(embedder.embed_query(q), top_k=top_k, year=year)
        for rank, h in enumerate(hits):
            key = (h.get("document_id"), h.get("chunk_index"))
            if key not in fused:
                fused[key] = {**h, "rrf_score": 0.0}
            fused[key]["rrf_score"] += 1.0 / (_RRF_K + rank)

    merged = sorted(fused.values(), key=lambda h: h["rrf_score"], reverse=True)
    return merged[:top_k]
