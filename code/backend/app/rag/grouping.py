"""Regroupe les chunks récupérés en ARTICLES (un par document, dédupliqué).

Les chunks arrivent triés par score décroissant (ordre de fusion RRF renvoyé par
retrieve_multi). On les regroupe par document en conservant l'ordre de première
apparition : les articles sont donc classés du plus pertinent au moins pertinent.
Pour chaque article on garde au plus `max_passages` pages distinctes (les mieux
notées), ce qui borne le contexte.
"""
from __future__ import annotations


def _norm(text: str) -> str:
    """Normalise un texte pour comparer deux passages (espaces + casse)."""
    return " ".join((text or "").lower().split())


def group_into_articles(
    hits: list[dict], max_articles: int, max_passages: int, min_words: int = 0
) -> list[dict]:
    articles: dict[str, dict] = {}  # clé document -> article
    order: list[str] = []           # ordre d'apparition (= ordre de score)

    for h in hits:
        text = (h.get("text") or "").strip()
        # Filtre longueur : écarte les passages trop courts (en-têtes / titres
        # courants réindexés à chaque page). On ne crée même pas l'article pour eux.
        if min_words and len(text.split()) < min_words:
            continue

        key = h.get("document_id") or h.get("filename", "")
        if key not in articles:
            articles[key] = {
                "document_id": h.get("document_id", ""),
                "title": h.get("title"),
                "authors": h.get("authors"),
                "filename": h.get("filename", ""),
                "year": h.get("year"),
                "doi": h.get("doi"),
                "score": h.get("score", 0.0),  # meilleur score (1er vu)
                "passages": [],
            }
            order.append(key)

        art = articles[key]
        if len(art["passages"]) >= max_passages:
            continue
        # Déduplication par PAGE et par TEXTE : un même en-tête présent sur
        # plusieurs pages ne doit pas occuper deux emplacements de passage.
        seen_pages = {p["page"] for p in art["passages"]}
        seen_texts = {_norm(p.get("text", "")) for p in art["passages"]}
        if h.get("page") in seen_pages or _norm(text) in seen_texts:
            continue
        art["passages"].append(
            {"page": h.get("page"), "text": text, "score": h.get("score", 0.0)}
        )

    # On ne renvoie que les articles ayant au moins un passage retenu.
    kept = [articles[k] for k in order if articles[k]["passages"]]
    return kept[:max_articles]
