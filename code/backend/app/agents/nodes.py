"""Nœuds du graphe multi-agents.

Agent 1 (understand)  -> analyse + reformulation + décision de clarification
Agent 2 (retrieve)    -> recherche documentaire RAG dans Qdrant
Agent 3 (synthesize)  -> réponse structurée et sourcée
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import SYNTHESIZE_SYSTEM, UNDERSTAND_SYSTEM
from app.agents.state import AgentState
from app.core.config import settings
from app.llm.ollama_client import get_llm
from app.rag.grouping import group_into_articles
from app.rag.retriever import retrieve_multi


def _parse_json(raw: str) -> dict:
    """Extraction robuste d'un bloc JSON renvoyé par le LLM."""
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


# --------------------------------------------------------------------------- #
# Agent 1 — compréhension de la requête
# --------------------------------------------------------------------------- #
def _format_history(history: list[dict]) -> str:
    """Met en forme l'historique récent pour le prompt de l'agent 1."""
    lines = []
    for m in history:
        who = "Utilisateur" if m.get("role") == "user" else "Assistant"
        lines.append(f"{who} : {m.get('content', '')}")
    return "\n".join(lines)


def _agent_model(state: AgentState, override: str | None) -> str | None:
    """Modèle effectif d'un agent : override par requête, sinon défaut .env, sinon
    le modèle global de la requête (lui-même -> OLLAMA_LLM_MODEL)."""
    return override or state.get("model")


def understand(state: AgentState) -> AgentState:
    model = _agent_model(state, state.get("understand_model") or settings.ollama_understand_model)
    llm = get_llm(model)
    history = state.get("history") or []

    if history:
        user_content = (
            "Historique récent de la conversation :\n"
            f"{_format_history(history)}\n\n"
            f"Nouveau message de l'utilisateur :\n{state['question']}\n\n"
            "En tenant compte du contexte ci-dessus (notamment si ce message répond "
            "à une question complémentaire posée précédemment), produis le JSON demandé."
        )
    else:
        user_content = state["question"]

    resp = llm.invoke(
        [SystemMessage(content=UNDERSTAND_SYSTEM), HumanMessage(content=user_content)],
        config={"callbacks": state.get("callbacks") or [], "run_name": "agent1-comprehension"},
    )
    data = _parse_json(resp.content)
    queries = _extract_queries(data, state["question"])
    return {
        "needs_clarification": bool(data.get("needs_clarification", False)),
        "clarification": data.get("clarification", ""),
        "search_query": queries[0],       # 1re requête : affichage / tracing
        "search_queries": queries,         # jeu complet : récupération multi-requêtes
    }


def _extract_queries(data: dict, question: str) -> list[str]:
    """Extrait le jeu de requêtes de l'agent 1, avec repli robuste.
    Accepte le nouveau format `search_queries` (liste) ; retombe sur l'ancien
    `search_query` (chaîne) puis sur la question brute. Dédupliqué, borné."""
    raw = data.get("search_queries")
    if not isinstance(raw, list):
        raw = [data.get("search_query") or ""]
    seen: list[str] = []
    for q in raw:
        q = str(q).strip()
        if q and q not in seen:
            seen.append(q)
    if not seen:
        seen = [question]
    return seen[: max(1, settings.query_expansion_max)]


# --------------------------------------------------------------------------- #
# Agent 2 — recherche documentaire RAG
# --------------------------------------------------------------------------- #
def retrieve_docs(state: AgentState) -> AgentState:
    # Récupération MULTI-REQUÊTES : chaque reformulation de l'agent 1 est cherchée
    # dans Qdrant, les résultats sont fusionnés (RRF) puis regroupés par article
    # (dédupliqué, ≤ max_articles, ≤ max_passages pages chacun).
    queries = state.get("search_queries") or [state["search_query"]]
    hits = retrieve_multi(queries, top_k=settings.retrieval_pool)
    articles = group_into_articles(
        hits,
        settings.sources_max_articles,
        settings.sources_max_passages,
        min_words=settings.sources_min_passage_words,
    )
    return {"sources": articles}


# --------------------------------------------------------------------------- #
# Agent 3 — synthèse et traçabilité
# --------------------------------------------------------------------------- #
_NO_SOURCE_MSG = (
    "Je n'ai trouvé aucun passage pertinent dans le corpus pour répondre à cette "
    "demande. Reformule ta question ou précise le type d'interaction / le contexte "
    "d'usage visé."
)


def _build_synthesis_messages(state: AgentState):
    """Construit les messages du LLM de synthèse.
    Renvoie (messages, None) ou (None, message_de_repli) s'il n'y a pas de source."""
    sources = state.get("sources", [])
    if not sources:
        return None, _NO_SOURCE_MSG

    # Un bloc [n] par ARTICLE ; ses pages sont listées dessous.
    context_blocks = []
    for i, art in enumerate(sources, start=1):
        ref = art.get("title") or art.get("filename")
        pages = "\n".join(f"Page {p.get('page')} : {p.get('text', '')}" for p in art.get("passages", []))
        context_blocks.append(f"[{i}] ({ref})\n{pages}")
    context = "\n\n".join(context_blocks)

    user_prompt = (
        f"QUESTION DE L'UTILISATEUR :\n{state['question']}\n\n"
        f"CONTEXTE (extraits du corpus, numérotés) :\n{context}\n\n"
        "Rédige la réponse en respectant les règles. Cite les extraits avec [n]."
    )
    return [SystemMessage(content=SYNTHESIZE_SYSTEM), HumanMessage(content=user_prompt)], None


def synthesize(state: AgentState) -> AgentState:
    """Synthèse complète (non streamée), utilisée par le pipeline /chat."""
    messages, fallback = _build_synthesis_messages(state)
    if messages is None:
        return {"answer": fallback}
    model = _agent_model(state, state.get("synthesize_model") or settings.ollama_synthesize_model)
    resp = get_llm(model).invoke(
        messages,
        config={"callbacks": state.get("callbacks") or [], "run_name": "agent3-synthese"},
    )
    return {"answer": resp.content}


def synthesize_stream(state: AgentState):
    """Synthèse streamée (token par token), utilisée par /chat/stream.
    Génère successivement des fragments de texte de la réponse."""
    messages, fallback = _build_synthesis_messages(state)
    if messages is None:
        yield fallback
        return
    model = _agent_model(state, state.get("synthesize_model") or settings.ollama_synthesize_model)
    cfg = {"callbacks": state.get("callbacks") or [], "run_name": "agent3-synthese"}
    for chunk in get_llm(model).stream(messages, config=cfg):
        text = getattr(chunk, "content", "") or ""
        if text:
            yield text
