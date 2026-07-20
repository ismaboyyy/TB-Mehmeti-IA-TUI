"""Visualise le DÉCOUPAGE en chunks SUR la page (surlignage couleur par chunk).

Important : les chunks n'ont pas de coordonnées (le découpage se fait sur le
texte aplati). On reconstruit donc une correspondance mot -> chunk via les
boîtes des mots (page.get_text("words")) et on surligne :
  - une COULEUR par chunk,
  - les zones de RECOUVREMENT (mot appartenant à 2 chunks) en ROUGE.

C'est une approximation « basée mots » du découpage réel (qui, lui, part de
get_text("text") + _clean) : les frontières sont très proches, pas identiques
au caractère près. Idéal pour VOIR comment la page est carrelée en chunks.

Usage (conteneur backend) :
    docker compose exec backend python scripts/visualize_chunks.py \
        /data/files/estia/archeotui_vast07.pdf --page 2

Sortie : pdf_analysis/<pdf>/chunks_page_NNN.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.rag.ingestion import _clean, _is_meaningful  # noqa: E402

# Palette (RGB 0..1) ; le rouge est réservé aux recouvrements.
PALETTE = [
    (0.95, 0.82, 0.20),  # jaune
    (0.30, 0.60, 0.95),  # bleu
    (0.30, 0.78, 0.42),  # vert
    (0.95, 0.58, 0.20),  # orange
    (0.62, 0.42, 0.85),  # violet
    (0.20, 0.75, 0.75),  # cyan
]
OVERLAP = (0.95, 0.20, 0.20)  # rouge


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _chunk_ranges(text: str, chunks: list[str]) -> list[tuple[int, int]]:
    """Position [début, fin) de chaque chunk dans `text` (chunks = sous-chaînes)."""
    ranges: list[tuple[int, int]] = []
    lo = 0
    for c in chunks:
        pos = text.find(c, lo)
        if pos == -1:
            pos = text.find(c)  # repli
        ranges.append((pos, pos + len(c)))
        lo = pos + 1
    return ranges


def visualize_page(page: fitz.Page, splitter, zoom: float) -> tuple[fitz.Pixmap, int, int]:
    words = page.get_text("words")  # (x0,y0,x1,y1, mot, bloc, ligne, n°)
    if not words:
        return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)), 0, 0

    # Texte aplati + offset caractère de chaque mot
    word_text = " ".join(w[4] for w in words)
    offsets: list[tuple[int, int]] = []
    pos = 0
    for w in words:
        offsets.append((pos, pos + len(w[4])))
        pos += len(w[4]) + 1  # +1 pour l'espace de jointure

    chunks = splitter.split_text(word_text)
    ranges = _chunk_ranges(word_text, chunks)

    overlaps = 0
    for (wx0, wy0, wx1, wy1, *_), (ws, we) in zip(words, offsets):
        mid = (ws + we) // 2
        owning = [i for i, (a, b) in enumerate(ranges) if a <= mid < b]
        if not owning:
            continue
        color = OVERLAP if len(owning) >= 2 else PALETTE[owning[0] % len(PALETTE)]
        if len(owning) >= 2:
            overlaps += 1
        annot = page.add_highlight_annot(fitz.Rect(wx0, wy0, wx1, wy1))
        annot.set_colors(stroke=color)
        annot.update()

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix, len(chunks), overlaps


def visualize_page_blocks(page: fitz.Page, splitter, zoom: float) -> tuple[fitz.Pixmap, int, int]:
    """Vue pour la stratégie "blocks" : blocs nettoyés/filtrés/triés en ordre de
    lecture, puis colorés selon le chunk auquel ils appartiennent (rouge = bloc à
    cheval sur 2 chunks). Reproduit la logique de _extract_pages_blocks."""
    mid_x = page.rect.width / 2
    items: list[tuple[int, float, str, fitz.Rect]] = []
    for x0, y0, x1, y1, text, _no, block_type in page.get_text("blocks"):
        if block_type != 0:
            continue
        cleaned = _clean(text)
        if not cleaned or not _is_meaningful(cleaned):
            continue
        is_full_width = (x1 - x0) > 0.6 * page.rect.width
        column = 0 if is_full_width else (0 if (x0 + x1) / 2 < mid_x else 1)
        items.append((column, y0, cleaned, fitz.Rect(x0, y0, x1, y1)))
    items.sort(key=lambda it: (it[0], it[1]))
    if not items:
        return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)), 0, 0

    # Texte en ordre de lecture (blocs recollés par "\n\n") + offset de chaque bloc
    parts = [it[2] for it in items]
    text = "\n\n".join(parts)
    offsets: list[tuple[int, int]] = []
    pos = 0
    for p in parts:
        offsets.append((pos, pos + len(p)))
        pos += len(p) + 2  # "\n\n"

    chunks = splitter.split_text(text)
    ranges = _chunk_ranges(text, chunks)

    overlaps = 0
    for (_col, _y, _txt, rect), (bs, be) in zip(items, offsets):
        mid = (bs + be) // 2
        owning = [i for i, (a, b) in enumerate(ranges) if a <= mid < b]
        if not owning:
            continue
        color = OVERLAP if len(owning) >= 2 else PALETTE[owning[0] % len(PALETTE)]
        if len(owning) >= 2:
            overlaps += 1
        annot = page.add_highlight_annot(rect)
        annot.set_colors(stroke=color)
        annot.update()

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix, len(chunks), overlaps


def main() -> None:
    p = argparse.ArgumentParser(description="Surligne les chunks sur les pages d'un PDF.")
    p.add_argument("pdf")
    p.add_argument("--page", type=int, help="Limiter à une page (1-indexée).")
    p.add_argument("--strategy", choices=["char", "blocks"], default="char",
                   help="char = texte aplati (mots) ; blocks = blocs triés en ordre de lecture.")
    p.add_argument("--out", default="pdf_analysis", help="Dossier de sortie.")
    p.add_argument("--zoom", type=float, default=2.0, help="Facteur de rendu (2.0 ~ 144 dpi).")
    args = p.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        sys.exit(f"PDF introuvable : {pdf}")

    out_dir = Path(args.out) / pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    splitter = _splitter()
    render = visualize_page_blocks if args.strategy == "blocks" else visualize_page
    unit = "blocs" if args.strategy == "blocks" else "mots"

    print(f"PDF : {pdf.name} | stratégie={args.strategy} | "
          f"chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap}\n")
    with fitz.open(pdf) as doc:
        indices = [args.page - 1] if args.page else range(doc.page_count)
        for i in indices:
            if not (0 <= i < doc.page_count):
                continue
            page = doc[i]
            pix, n_chunks, n_overlap = render(page, splitter, args.zoom)
            png = out_dir / f"chunks_{args.strategy}_page_{i + 1:03d}.png"
            pix.save(png)
            print(f"Page {i + 1:>3} : {n_chunks} chunks, {n_overlap} {unit} en recouvrement -> {png}")

    print(f"\nLégende : 1 couleur = 1 chunk (cycle de 6 teintes) ; "
          f"ROUGE = recouvrement ({unit[:-1] if unit.endswith('s') else unit} dans 2 chunks).")


if __name__ == "__main__":
    main()
