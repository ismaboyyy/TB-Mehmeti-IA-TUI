"""Visualise le DÉCOUPAGE en chunks d'un PDF (les morceaux réellement embeddés).

Distinction :
  - PyMuPDF (fitz) EXTRAIT le texte, page par page.
  - Le DÉCOUPAGE est fait par RecursiveCharacterTextSplitter (langchain),
    à chunk_size / chunk_overlap (cf. .env), PAR PAGE.
Ce script rejoue la branche "char" de l'ingestion (_extract_pages -> split
-> _is_meaningful) et affiche les chunks finaux, pour juger la qualité :
longueurs, coupures en pleine phrase, chunks écartés.

NB : l'ingestion utilise par DÉFAUT la stratégie "blocks" (_extract_pages_blocks,
cf. settings.chunk_strategy) et, si exclude_references est activé, retire aussi la
bibliographie. Ce script montre donc uniquement le découpage en mode texte aplati
("char"), pas le pipeline blocks par défaut. Pour visualiser les blocs, voir
viz_blocks.py / visualize_chunks.py --strategy blocks.

Usage (dans le conteneur backend) :
    docker compose exec backend python scripts/show_chunks.py \
        /data/files/estia/archeotui_vast07.pdf --page 2
    # texte complet de chaque chunk :
    ... show_chunks.py <pdf> --page 2 --full
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.rag.ingestion import _extract_pages, _is_meaningful  # noqa: E402


def _splitter() -> RecursiveCharacterTextSplitter:
    # Config IDENTIQUE à celle de l'ingestion (app/rag/ingestion.py).
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _ends_cleanly(text: str) -> bool:
    """Le chunk se termine-t-il sur une ponctuation de fin de phrase ?"""
    return text.rstrip().endswith((".", "!", "?", ":", ";", ")", '"'))


def main() -> None:
    p = argparse.ArgumentParser(description="Montre les chunks produits pour un PDF.")
    p.add_argument("pdf")
    p.add_argument("--page", type=int, help="Limiter à une page (1-indexée).")
    p.add_argument("--full", action="store_true", help="Afficher le texte complet de chaque chunk.")
    p.add_argument("--max-chunks", type=int, default=12, help="Nb de chunks affichés (défaut 12).")
    args = p.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        sys.exit(f"PDF introuvable : {pdf}")

    splitter = _splitter()
    print(f"PDF : {pdf.name}")
    print(f"Découpage : chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap} (par page)\n")

    pages = _extract_pages(pdf)  # [(page_no, texte_nettoyé)]  <- extraction PyMuPDF + _clean
    if args.page:
        pages = [pg for pg in pages if pg[0] == args.page]

    lengths: list[int] = []
    kept = dropped = shown = 0

    for page_no, page_text in pages:
        for c in splitter.split_text(page_text):
            keep = _is_meaningful(c)
            if keep:
                kept += 1
                lengths.append(len(c))
            else:
                dropped += 1

            if shown < args.max_chunks:
                shown += 1
                etat = "gardé ✓" if keep else "ÉCARTÉ ✗"
                coupe = "" if _ends_cleanly(c) else "   ⚠ se termine en pleine phrase"
                print(f"─── chunk {shown} │ page {page_no} │ {len(c)} car. │ {etat}{coupe} ───")
                if args.full:
                    print(c)
                else:
                    print(f"  DÉBUT : {c[:120].replace(chr(10), ' ')!r}")
                    print(f"  FIN   : ...{c[-120:].replace(chr(10), ' ')!r}")
                print()

    total = kept + dropped
    if lengths:
        avg = sum(lengths) // len(lengths)
        print(f"RÉSUMÉ : {total} chunks ({kept} gardés, {dropped} écartés) | "
              f"longueur des gardés : min={min(lengths)}, moy={avg}, max={max(lengths)} car.")
    else:
        print(f"RÉSUMÉ : {total} chunks (aucun gardé)")


if __name__ == "__main__":
    main()
