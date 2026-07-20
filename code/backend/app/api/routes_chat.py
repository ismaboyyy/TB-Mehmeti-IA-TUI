"""Endpoints de conversation : exécute le graphe multi-agents et persiste l'échange."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import run_pipeline
from app.agents.nodes import retrieve_docs, synthesize_stream, understand
from app.auth.deps import get_current_user
from app.core.config import settings
from app.db.models import Conversation, Message, User
from app.db.session import SessionLocal, get_db
from app.observability.langfuse_tracing import PipelineTrace, get_callback_handler
from app.schemas import ArticleOut, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

# Nombre de messages précédents transmis aux agents comme contexte.
HISTORY_LIMIT = 6


def _get_or_create_conversation(
    db: Session, conversation_id: str | None, question: str, user_id: str
) -> Conversation:
    conv = db.get(Conversation, conversation_id) if conversation_id else None
    # On ne réutilise une conversation existante que si elle appartient à l'utilisateur.
    if conv is None or conv.user_id != user_id:
        conv = Conversation(title=question[:80], user_id=user_id)
        db.add(conv)
        db.flush()
    return conv


def _load_history(db: Session, conversation_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    """Derniers messages de la conversation (du plus ancien au plus récent),
    transmis à l'agent 1 pour gérer la clarification en contexte."""
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


def _sse(payload: dict) -> str:
    """Formate un événement Server-Sent Events."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _save_message(conversation_id: str, role: str, content: str, sources_json: str | None) -> None:
    """Persiste un message avec une session DÉDIÉE.
    Le générateur de streaming s'exécute après le handler : on n'y réutilise pas
    la session de la requête (qui peut être détachée) mais une session propre."""
    db = SessionLocal()
    try:
        db.add(Message(conversation_id=conversation_id, role=role, content=content, sources_json=sources_json))
        db.commit()
    finally:
        db.close()


@router.post("/stream", tags=["chat"])
def chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Variante streamée (SSE) : émet l'état de chaque agent, puis la réponse de
    synthèse TOKEN PAR TOKEN, puis un événement final avec les sources."""
    conv = _get_or_create_conversation(db, req.conversation_id, req.question, user.id)
    conv_id: str = conv.id  # capturé en chaîne tant que la session est active
    history = _load_history(db, conv_id)  # avant d'ajouter le nouveau message
    db.add(Message(conversation_id=conv_id, role="user", content=req.question))
    db.commit()

    model_name = req.model or settings.ollama_llm_model

    def event_stream():
        # Une seule trace Langfuse par requête (no-op si Langfuse désactivé) :
        # toute la tuyauterie d'observabilité est encapsulée dans PipelineTrace.
        trace = PipelineTrace(req.question, session_id=conv_id, model=model_name)
        state: dict = {
            "question": req.question, "history": history,
            "model": req.model,
            "understand_model": req.understand_model,
            "synthesize_model": req.synthesize_model,
            "callbacks": trace.callbacks,
        }
        try:
            # Agent 1 - compréhension
            state.update(understand(state))
            yield _sse({
                "type": "step", "agent": "understand",
                "data": {
                    "needs_clarification": bool(state.get("needs_clarification")),
                    "search_query": state.get("search_query"),
                },
            })

            if state.get("needs_clarification"):
                clarification = state.get("clarification") or "Peux-tu préciser ton besoin ?"
                _save_message(conv_id, "assistant", clarification, None)
                trace.finalize(needs_clarification=True, clarification=clarification)
                yield _sse({
                    "type": "final", "conversation_id": conv_id,
                    "needs_clarification": True, "clarification": clarification,
                })
                return

            # Agent 2 - recherche documentaire (multi-requêtes + fusion RRF)
            queries = state.get("search_queries") or [state.get("search_query")]
            with trace.span(
                "agent2-recherche", search_queries=queries, num_queries=len(queries)
            ) as out:
                state.update(retrieve_docs(state))
                out["num_sources"] = len(state.get("sources", []))
                out["titles"] = [s.get("title") for s in state.get("sources", [])]
            yield _sse({
                "type": "step", "agent": "retrieve",
                "data": {"num_sources": len(state.get("sources", []))},
            })

            # Agent 3 - synthèse streamée token par token
            parts: list[str] = []
            for token in synthesize_stream(state):
                parts.append(token)
                yield _sse({"type": "token", "content": token})

            answer = "".join(parts)
            sources = [ArticleOut(**s).model_dump() for s in state.get("sources", [])]
            _save_message(conv_id, "assistant", answer, json.dumps(sources, ensure_ascii=False))
            trace.finalize(answer=answer, num_sources=len(sources))
            yield _sse({
                "type": "final", "conversation_id": conv_id,
                "needs_clarification": False, "answer": answer, "sources": sources,
            })
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    # 1. Récupère ou crée la conversation
    conv = _get_or_create_conversation(db, req.conversation_id, req.question, user.id)

    # 2. Historique (avant le nouveau message) puis persistance du message utilisateur
    history = _load_history(db, conv.id)
    db.add(Message(conversation_id=conv.id, role="user", content=req.question))

    # 3. Exécute le pipeline multi-agents avec le contexte
    handler = get_callback_handler(session_id=conv.id)
    result = run_pipeline(
        req.question, history, req.model, [handler] if handler else [],
        req.understand_model, req.synthesize_model,
    )

    # 4a. Cas clarification : on ne stocke pas de sources
    if result.get("needs_clarification"):
        clarification = result.get("clarification") or "Peux-tu préciser ton besoin ?"
        db.add(Message(conversation_id=conv.id, role="assistant", content=clarification))
        db.commit()
        return ChatResponse(
            conversation_id=conv.id,
            needs_clarification=True,
            clarification=clarification,
        )

    # 4b. Cas réponse complète
    answer = result.get("answer", "")
    sources = [ArticleOut(**s) for s in result.get("sources", [])]
    db.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content=answer,
            sources_json=json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
        )
    )
    db.commit()
    return ChatResponse(
        conversation_id=conv.id,
        needs_clarification=False,
        answer=answer,
        sources=sources,
    )
