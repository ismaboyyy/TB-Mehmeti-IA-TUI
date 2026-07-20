"""Comparaison des deux stratégies d'extraction de texte AVANT chunking.

  "char"   : get_text("text")  -> _clean                     (stratégie historique)
  "blocks" : get_text("blocks") -> filtre _is_meaningful
            -> tri en ORDRE DE LECTURE (colonne, y) -> recollage  (DÉFAUT actuel)

Depuis le passage de settings.chunk_strategy à "blocks", c'est la seconde
stratégie que fait l'ingestion par défaut ; "char" reste disponible en option.
Le but est de visualiser, côte à côte, l'amélioration de qualité du texte :
remise dans l'ordre de lecture (titre avant le bandeau de bas de page) et
gestion des pages à deux colonnes. Aucune écriture en base, aucun embedding :
c'est purement un diagnostic.

Usage (depuis le conteneur backend) :
    docker compose exec backend python scripts/compare_ingestion.py \
        /data/files/estia/archeotui_vast07.pdf --pages 1,2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.ingestion import _clean, _is_meaningful  # noqa: E402


def current_text(page: fitz.Page) -> str:
    """Stratégie ACTUELLE de l'ingestion : texte brut nettoyé."""
    return _clean(page.get_text("text"))


def reading_order_text(page: fitz.Page) -> str:
    """Stratégie PROPOSÉE : blocs filtrés, triés en ordre de lecture.

    - on ne garde que les blocs de texte « lisibles » (_is_meaningful) ;
    - un bloc large (> 60 % de la page) est traité comme pleine largeur
      (titre, bandeau) et placé dans la colonne de gauche ;
    - sinon il est rangé à gauche/droite selon son centre ;
    - tri final par (colonne, y) = lecture haut->bas, gauche puis droite.
    """
    mid_x = page.rect.width / 2
    items: list[tuple[int, float, str]] = []

    for x0, y0, x1, y1, text, _no, block_type in page.get_text("blocks"):
        if block_type != 0:  # 1 = image -> ignoré
            continue
        cleaned = _clean(text)
        if not cleaned or not _is_meaningful(cleaned):
            continue
        is_full_width = (x1 - x0) > 0.6 * page.rect.width
        column = 0 if is_full_width else (0 if (x0 + x1) / 2 < mid_x else 1)
        items.append((column, y0, cleaned))

    items.sort(key=lambda it: (it[0], it[1]))
    return "\n\n".join(text for _col, _y, text in items)


def _show(title: str, text: str, limit: int) -> None:
    print(title)
    print("-" * len(title))
    print(text[:limit])
    if len(text) > limit:
        print(f"… [{len(text) - limit} caractères de plus]")
    print(f"\n({len(text)} caractères au total)\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare extraction texte brut vs blocs triés.")
    parser.add_argument("pdf")
    parser.add_argument("--pages", help="Pages 1-indexées, ex '1,2' ou '1-3'. Défaut: 1.")
    parser.add_argument("--limit", type=int, default=700, help="Caractères affichés par version.")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"PDF introuvable : {pdf_path}")

    # Petit parseur de pages (1-indexé -> 0-indexé)
    pages: list[int] = []
    spec = args.pages or "1"
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            pages.extend(range(int(a) - 1, int(b)))
        else:
            pages.append(int(part) - 1)

    with fitz.open(pdf_path) as doc:
        for i in pages:
            if not (0 <= i < doc.page_count):
                continue
            page = doc[i]
            print("=" * 72)
            print(f"  PAGE {i + 1}  —  {pdf_path.name}")
            print("=" * 72 + "\n")
            _show("CHAR (historique) — get_text('text') + _clean", current_text(page), args.limit)
            _show("BLOCKS (défaut) — blocs filtrés + triés (ordre de lecture)",
                  reading_order_text(page), args.limit)


if __name__ == "__main__":
    main()
