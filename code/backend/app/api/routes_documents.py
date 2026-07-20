"""Endpoints d'administration des documents : upload + indexation + listing."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.models import Document, User
from app.db.session import SessionLocal, get_db
from app.rag.ingestion import ingest_pdf
from app.rag.vectorstore import delete_by_document_id
from app.schemas import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def _ingest_with_own_session(
    tmp_path: Path, filename: str | None, year: int | None, source: str | None
) -> Document:
    """Indexe le PDF avec une session DB PROPRE au thread de travail.

    `run_in_threadpool` exécute cette fonction dans un thread distinct de la
    boucle async. Les sessions SQLAlchemy ne sont pas partageables entre threads,
    donc on en ouvre une dédiée ici plutôt que de réutiliser celle de la requête.
    Après `ingest_pdf` (qui fait un refresh), les attributs du Document sont
    chargés : l'objet détaché reste sérialisable par DocumentOut.
    """
    db = SessionLocal()
    try:
        return ingest_pdf(tmp_path, db, filename=filename, year=year, source=source)
    finally:
        db.close()


@router.post("", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    year: int | None = Form(None),
    source: str | None = Form(None),
    _user: User = Depends(get_current_user),
) -> Document:
    # Sauvegarde temporaire puis indexation dans un thread (CPU-bound).
    # On passe le VRAI nom (file.filename) : le PDF est sauvé sous un nom
    # temporaire, sans ça le filename stocké et le garde-fou anti-doublon
    # seraient basés sur ce nom temporaire.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        return await run_in_threadpool(
            _ingest_with_own_session, tmp_path, file.filename, year, source
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    # On COMMIT d'abord la suppression PostgreSQL, puis on purge Qdrant : si la
    # purge Qdrant échoue, on n'a que des vecteurs orphelins (poids mort inerte,
    # récupérable) plutôt qu'une ligne fantôme sans vecteurs. L'inverse laisserait
    # un document listé mais introuvable par la recherche.
    db.delete(doc)
    db.commit()
    delete_by_document_id(document_id)
    return Response(status_code=204)
