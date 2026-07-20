"""Schémas d'entrée/sortie de l'API (validation Pydantic)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PassageOut(BaseModel):
    page: int | None = None
    text: str
    score: float = 0.0


class ArticleOut(BaseModel):
    """Une source = un article (document), avec les pages qui l'ont référencé."""
    document_id: str
    title: str | None = None
    authors: str | None = None
    filename: str
    year: int | None = None
    doi: str | None = None
    score: float
    passages: list[PassageOut] = []


class UserCreate(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: str
    email: str
    is_active: bool
    is_superuser: bool
    is_verified: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None  # None -> nouvelle conversation
    model: str | None = None            # None -> modèle par défaut (.env)
    # Modèles par agent (optionnels). None -> retombe sur `model`.
    understand_model: str | None = None  # agent 1 : reformulation
    synthesize_model: str | None = None  # agent 3 : synthèse


class ModelsResponse(BaseModel):
    default: str
    available: list[str]


class ChatResponse(BaseModel):
    conversation_id: str
    needs_clarification: bool
    clarification: str | None = None
    answer: str | None = None
    sources: list[ArticleOut] = []


class ConversationOut(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[ArticleOut] = []
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    filename: str
    title: str | None = None
    year: int | None = None
    source: str | None = None
    n_pages: int | None = None
    n_chunks: int
    status: str

    class Config:
        from_attributes = True
