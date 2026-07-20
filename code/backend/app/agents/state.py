"""État partagé qui circule entre les nœuds du graphe LangGraph."""
from __future__ import annotations

from typing import TypedDict


class Passage(TypedDict):
    page: int | None
    text: str
    score: float


class Source(TypedDict):
    # Une source = un ARTICLE (document), regroupé par `group_into_articles` :
    # ses passages (pages) sont dans `passages`. Cf. schemas.py:ArticleOut.
    document_id: str
    title: str | None
    authors: str | None
    filename: str
    year: int | None
    doi: str | None
    score: float
    passages: list[Passage]


class AgentState(TypedDict, total=False):
    # Entrée
    question: str
    history: list[dict]  # tours précédents : [{"role": "user"|"assistant", "content": str}, ...]
    model: str | None    # modèle Ollama choisi (None -> défaut)
    understand_model: str | None  # modèle de l'agent 1 (None/"" -> retombe sur model)
    synthesize_model: str | None  # modèle de l'agent 3 (None/"" -> retombe sur model)
    callbacks: list      # callbacks LangChain (ex: Langfuse) pour le tracing

    # Agent 1 — compréhension
    needs_clarification: bool   # True -> on renvoie une question complémentaire
    clarification: str          # question à poser si besoin incomplet
    search_query: str           # 1re requête reformulée (affichage / tracing)
    search_queries: list[str]   # jeu de requêtes pour la récupération multi-requêtes

    # Agent 2 — recherche documentaire
    sources: list[Source]

    # Agent 3 — synthèse
    answer: str
