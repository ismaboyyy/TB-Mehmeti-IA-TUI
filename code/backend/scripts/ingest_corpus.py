"""Indexation en masse du corpus PDF présent dans /data/files (monté en lecture seule).

Usage (depuis le conteneur backend) :
    docker compose exec backend python scripts/ingest_corpus.py /data/files
ou en local :
    python scripts/ingest_corpus.py ../files
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permet d'importer le package app quand on lance le script directement
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.rag.ingestion import ingest_pdf  # noqa: E402


def main(root: str) -> None:
    Base.metadata.create_all(bind=engine)
    pdfs = sorted(Path(root).rglob("*.pdf"))
    print(f"{len(pdfs)} PDF trouvés dans {root}")

    db = SessionLocal()
    ok, errors = 0, 0
    try:
        for i, pdf in enumerate(pdfs, start=1):
            # Année déduite du chemin si présent (ex: .../files/2025/...)
            year = next((int(p) for p in pdf.parts if p.isdigit() and len(p) == 4), None)
            try:
                doc = ingest_pdf(pdf, db, year=year, source="ACM")
                ok += 1
                print(f"[{i}/{len(pdfs)}] OK  {pdf.name} -> {doc.n_chunks} chunks")
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"[{i}/{len(pdfs)}] ERREUR {pdf.name} : {exc}")
    finally:
        db.close()
    print(f"\nTerminé. Indexés : {ok}, erreurs : {errors}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/data/files")
