"""Endpoints d'historique : conversations et messages de l'utilisateur connecté.

L'historique vit côté serveur (PostgreSQL) et est filtré par `user_id` :
chaque utilisateur n'accède qu'à ses propres conversations.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.models import Conversation, Message, User
from app.db.session import get_db
from app.schemas import ConversationOut, MessageOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _normalize_sources(raw: list[dict]) -> list[dict]:
    """Rend les sources stockées compatibles avec le format ARTICLE.
    Les anciens messages contiennent des chunks plats (clés page/text) : on les
    emballe en articles à une seule page pour qu'ils restent affichables."""
    out: list[dict] = []
    for s in raw:
        if "passages" in s:  # déjà au nouveau format article
            out.append(s)
        else:                # ancien chunk plat -> article 1 page
            out.append({
                "document_id": s.get("document_id", ""),
                "title": s.get("title"),
                "filename": s.get("filename", ""),
                "year": s.get("year"),
                "score": s.get("score", 0.0),
                "passages": [{"page": s.get("page"), "text": s.get("text", ""), "score": s.get("score", 0.0)}],
            })
    return out


def _get_owned(db: Session, conversation_id: str, user: User) -> Conversation:
    """Charge une conversation et vérifie qu'elle appartient à l'utilisateur."""
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return conv


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    """Liste les conversations de l'utilisateur, de la plus récente à la plus ancienne."""
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        )
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    """Messages d'une conversation (du plus ancien au plus récent)."""
    _get_owned(db, conversation_id, user)
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    ).all()
    out: list[MessageOut] = []
    for m in rows:
        sources = []
        if m.sources_json:
            try:
                sources = _normalize_sources(json.loads(m.sources_json))
            except json.JSONDecodeError:
                sources = []
        out.append(
            MessageOut(id=m.id, role=m.role, content=m.content, sources=sources, created_at=m.created_at)
        )
    return out


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Supprime une conversation (et ses messages, en cascade)."""
    conv = _get_owned(db, conversation_id, user)
    db.delete(conv)
    db.commit()
    return {"status": "deleted"}
