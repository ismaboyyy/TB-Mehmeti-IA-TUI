"""Nettoyage one-shot des documents indexés en double.

Un même fichier (même `filename`) a pu être indexé plusieurs fois — l'ancien
pipeline n'avait pas de garde-fou (corrigé depuis dans ingest_pdf). Ce script
garde, pour chaque filename, la copie la PLUS ANCIENNE et supprime les autres,
à la fois dans PostgreSQL (table documents) et dans Qdrant (points/chunks).

Usage (depuis le conteneur backend) :
    docker compose exec backend python scripts/dedup_corpus.py          # aperçu (dry-run)
    docker compose exec backend python scripts/dedup_corpus.py --apply  # applique
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func  # noqa: E402

from app.db.models import Document  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.rag.vectorstore import delete_by_document_id  # noqa: E402


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        # filenames présents plus d'une fois
        dup_names = [
            row[0]
            for row in db.query(Document.filename)
            .group_by(Document.filename)
            .having(func.count(Document.id) > 1)
            .all()
        ]
        if not dup_names:
            print("Aucun doublon. Rien à faire.")
            return

        total_removed = 0
        for name in dup_names:
            copies = (
                db.query(Document)
                .filter(Document.filename == name)
                .order_by(Document.created_at.asc())  # la plus ancienne d'abord
                .all()
            )
            keep, drop = copies[0], copies[1:]
            print(f"{name} : {len(copies)} copies -> on garde {keep.id[:8]}…, "
                  f"on supprime {len(drop)}")
            for doc in drop:
                if apply:
                    delete_by_document_id(doc.id)  # purge Qdrant
                    db.delete(doc)                 # purge Postgres
                total_removed += 1

        if apply:
            db.commit()
            print(f"\nAppliqué. {total_removed} document(s) en double supprimé(s).")
        else:
            print(f"\n[DRY-RUN] {total_removed} document(s) seraient supprimés. "
                  f"Relance avec --apply pour exécuter.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
