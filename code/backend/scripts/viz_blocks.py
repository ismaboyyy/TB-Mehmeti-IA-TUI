"""Visualise le découpage en BLOCS de PyMuPDF sur une vraie page.

Dessine, sur chaque page choisie :
  - un rectangle VERT autour de chaque bloc de texte CONSERVÉ, avec son numéro
    dans l'ordre de lecture reconstruit (colonne gauche puis droite) ;
  - un rectangle ROUGE (fin) autour des blocs ÉCARTÉS (charabia / vides) ;
  - un rectangle GRIS autour des blocs IMAGE.

Reproduit exactement la logique de rag/ingestion.py:_extract_pages_blocks
(détection de colonne au centre horizontal, tri (colonne, y0), filtre
_is_meaningful) pour montrer "comment le fichier est découpé".

Usage (dans le conteneur backend) :
    python scripts/viz_blocks.py <pdf> <out.pdf> [pages]
    ex: python scripts/viz_blocks.py /data/files/estia/cairnform-peripheral_tei2019.pdf \
                                     /app/pymupdf_blocks_cairnform.pdf 0,1
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

# Permet d'importer le package app quand on lance le script directement.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.ingestion import _clean, _is_meaningful  # noqa: E402

_FLAGS = fitz.TEXTFLAGS_BLOCKS | fitz.TEXT_DEHYPHENATE

GREEN = (0.10, 0.55, 0.20)   # bloc conservé
RED = (0.85, 0.15, 0.15)     # bloc écarté (charabia/vide)
GRAY = (0.55, 0.55, 0.55)    # bloc image


def annotate_page(page: fitz.Page) -> None:
    mid_x = page.rect.width / 2
    kept = []      # (column, y0, rect)
    dropped = []   # rect
    images = []    # rect

    for x0, y0, x1, y1, text, _no, block_type in page.get_text("blocks", flags=_FLAGS):
        rect = fitz.Rect(x0, y0, x1, y1)
        if block_type != 0:
            images.append(rect)
            continue
        cleaned = _clean(text)
        if not cleaned or not _is_meaningful(cleaned):
            dropped.append(rect)
            continue
        is_full_width = (x1 - x0) > 0.6 * page.rect.width
        column = 0 if is_full_width else (0 if (x0 + x1) / 2 < mid_x else 1)
        kept.append((column, y0, rect))

    # Tri = ordre de lecture reconstruit (comme à l'ingestion)
    kept.sort(key=lambda it: (it[0], it[1]))

    for rect in images:
        page.draw_rect(rect, color=GRAY, width=0.8, dashes="[3] 0")
    for rect in dropped:
        page.draw_rect(rect, color=RED, width=0.8, dashes="[3] 0")
    for idx, (_c, _y, rect) in enumerate(kept, start=1):
        page.draw_rect(rect, color=GREEN, width=1.3)
        # pastille numérotée en haut-gauche du bloc (ordre de lecture)
        p = fitz.Point(rect.x0 + 2, rect.y0 + 11)
        page.draw_circle(fitz.Point(rect.x0 + 7, rect.y0 + 7), 8, color=GREEN, fill=(1, 1, 1), width=1)
        page.insert_text(p, str(idx), fontsize=9, color=GREEN)

    # Légende en haut de page
    page.insert_text(fitz.Point(20, 14), "PyMuPDF blocks — vert=conserve+ordre  rouge=ecarte  gris=image",
                     fontsize=8, color=(0, 0, 0))


def main() -> None:
    src, out = sys.argv[1], sys.argv[2]
    pages = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [0, 1]
    doc = fitz.open(src)
    for i in pages:
        if 0 <= i < len(doc):
            annotate_page(doc[i])
    doc.select([i for i in pages if 0 <= i < len(doc)])
    doc.save(out, deflate=True)
    print(f"OK -> {out}  ({len(pages)} page(s), source={src})")


if __name__ == "__main__":
    main()
