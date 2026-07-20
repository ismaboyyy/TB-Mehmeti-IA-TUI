"""Assemblage du graphe LangGraph.

Flux :
    understand --(needs_clarification ?)--> END (on renvoie la question)
                                       \--> retrieve -> synthesize -> END
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.agents.nodes import retrieve_docs, synthesize, understand
from app.agents.state import AgentState


def _route_after_understand(state: AgentState) -> str:
    return "clarify" if state.get("needs_clarification") else "retrieve"


@lru_cache
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("understand", understand)
    g.add_node("retrieve", retrieve_docs)
    g.add_node("synthesize", synthesize)

    g.set_entry_point("understand")
    g.add_conditional_edges(
        "understand",
        _route_after_understand,
        {"clarify": END, "retrieve": "retrieve"},
    )
    g.add_edge("retrieve", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


def run_pipeline(
    question: str,
    history: list[dict] | None = None,
    model: str | None = None,
    callbacks: list | None = None,
    understand_model: str | None = None,
    synthesize_model: str | None = None,
) -> AgentState:
    """Point d'entrée unique appelé par l'API (réponse complète, non streamée)."""
    graph = build_graph()
    return graph.invoke(
        {
            "question": question,
            "history": history or [],
            "model": model,
            "understand_model": understand_model,
            "synthesize_model": synthesize_model,
            "callbacks": callbacks or [],
        }
    )
