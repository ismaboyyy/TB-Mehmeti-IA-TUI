"""Visualisation de la structure d'extraction PyMuPDF d'un PDF.

But : voir CONCRÈTEMENT ce que l'extraction « voit » sur chaque page.
PyMuPDF découpe une page en BLOCS (`page.get_text("blocks")`) — paragraphes,
titres, légendes, images. L'ingestion par DÉFAUT (stratégie "blocks") s'appuie
justement sur ces blocs (triés en ordre de lecture) ; la stratégie "char"
optionnelle, elle, part du texte brut aplati (`get_text("text")`). Dans les deux
cas le filtre `_is_meaningful` écarte les morceaux peu lisibles. Ce script
visualise les blocs pour diagnostiquer la qualité d'extraction.

Pour chaque page, il produit :
  1. une image PNG annotée : chaque bloc est encadré et numéroté, et coloré
       - VERT  -> bloc de texte CONSERVÉ par le filtre `_is_meaningful` ;
       - ROUGE -> bloc de texte ÉCARTÉ (charabia, page mal encodée) ;
       - BLEU  -> bloc image (jamais indexé) ;
  2. un rapport JSON détaillé (bbox, type, nb de caractères, police dominante,
     aperçu du texte) ;
  3. un résumé lisible sur la sortie standard.

NB : `_is_meaningful` est appliqué ici bloc par bloc, alors que l'ingestion
l'applique sur des « chunks » (texte de la page recoupé à 900 caractères). La
couleur est donc une bonne APPROXIMATION de ce qui sera gardé, pas la vérité
exacte au chunk près.

Usage (depuis le conteneur backend) :
    docker compose exec backend python scripts/analyze_pdf.py \
        /data/files/estia/archeotui_vast07.pdf --pages 1-3

Sortie : ./pdf_analysis/<nom_du_pdf>/ (dans le conteneur = backend/ côté hôte).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

# Permet d'importer le package app quand on lance le script directement.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.ingestion import _clean, _is_meaningful  # noqa: E402

# Couleurs (RGB normalisé 0..1, attendu par PyMuPDF).
GREEN = (0.0, 0.6, 0.0)   # texte conservé
RED = (0.85, 0.0, 0.0)    # texte écarté
BLUE = (0.0, 0.0, 0.85)   # image
WHITE = (1.0, 1.0, 1.0)


def _parse_pages(spec: str | None, n_pages: int) -> list[int]:
    """Convertit '1-3' ou '2,5' (1-indexé) en indices 0-indexés. None -> tout."""
    if not spec:
        return list(range(n_pages))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a) - 1, int(b)))
        elif part:
            out.add(int(part) - 1)
    return sorted(i for i in out if 0 <= i < n_pages)


def _dominant_font(page: fitz.Page, block_no: int) -> dict | None:
    """Police/taille dominante d'un bloc de texte (via le mode 'dict')."""
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("number") != block_no or block.get("type") != 0:
            continue
        sizes: Counter = Counter()
        fonts: Counter = Counter()
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                sizes[round(span.get("size", 0), 1)] += len(span.get("text", ""))
                fonts[span.get("font", "?")] += len(span.get("text", ""))
        if not sizes:
            return None
        return {"font": fonts.most_common(1)[0][0], "size": sizes.most_common(1)[0][0]}
    return None


def analyze_page(page: fitz.Page, zoom: float) -> tuple[fitz.Pixmap, list[dict]]:
    """Annoter une page et renvoyer (image rendue, rapport des blocs)."""
    blocks = page.get_text("blocks")  # [(x0, y0, x1, y1, text, block_no, type), ...]
    report: list[dict] = []

    for x0, y0, x1, y1, text, block_no, block_type in blocks:
        is_image = block_type == 1
        cleaned = _clean(text) if not is_image else ""
        kept = bool(cleaned) and _is_meaningful(cleaned)

        if is_image:
            color = BLUE
        elif kept:
            color = GREEN
        else:
            color = RED

        idx = len(report) + 1
        rect = fitz.Rect(x0, y0, x1, y1)

        # Cadre du bloc + pastille numérotée en haut à gauche.
        page.draw_rect(rect, color=color, width=1.2)
        label = str(idx)
        badge = fitz.Rect(x0, y0, x0 + 7 * len(label) + 6, y0 + 13)
        page.draw_rect(badge, color=color, fill=color)
        page.insert_text(fitz.Point(x0 + 3, y0 + 10), label, fontsize=9, color=WHITE)

        report.append(
            {
                "index": idx,
                "block_no": block_no,
                "type": "image" if is_image else "text",
                "kept_by_filter": None if is_image else kept,
                "bbox": [round(v, 1) for v in (x0, y0, x1, y1)],
                "n_chars": len(cleaned),
                "font": None if is_image else _dominant_font(page, block_no),
                "text_preview": cleaned[:160],
            }
        )

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualise les blocs PyMuPDF d'un PDF.")
    parser.add_argument("pdf", help="Chemin du PDF (ex: /data/files/estia/archeotui_vast07.pdf)")
    parser.add_argument("--pages", help="Pages à analyser, 1-indexé (ex: '1-3' ou '2,5'). Défaut: toutes.")
    parser.add_argument("--out", default="pdf_analysis", help="Dossier de sortie (défaut: ./pdf_analysis).")
    parser.add_argument("--zoom", type=float, default=2.0, help="Facteur de rendu (2.0 ~ 144 dpi).")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"PDF introuvable : {pdf_path}")

    out_dir = Path(args.out) / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    full_report: dict = {"pdf": str(pdf_path), "pages": []}

    with fitz.open(pdf_path) as doc:
        page_indices = _parse_pages(args.pages, doc.page_count)
        print(f"PDF : {pdf_path.name} — {doc.page_count} pages, analyse de {len(page_indices)} page(s)\n")

        for i in page_indices:
            page = doc[i]
            raw_chars = len(_clean(page.get_text("text")))
            pix, report = analyze_page(page, args.zoom)

            png_path = out_dir / f"page_{i + 1:03d}.png"
            pix.save(png_path)

            n_text = sum(1 for b in report if b["type"] == "text")
            n_kept = sum(1 for b in report if b["kept_by_filter"])
            n_img = sum(1 for b in report if b["type"] == "image")
            block_chars = sum(b["n_chars"] for b in report)

            full_report["pages"].append(
                {
                    "page": i + 1,
                    "image": png_path.name,
                    "n_blocks": len(report),
                    "n_text_blocks": n_text,
                    "n_kept": n_kept,
                    "n_image_blocks": n_img,
                    "chars_text_mode": raw_chars,
                    "chars_blocks_mode": block_chars,
                    "blocks": report,
                }
            )

            print(
                f"Page {i + 1:>3} : {len(report):>2} blocs "
                f"(texte {n_text}, dont gardés {n_kept} ; images {n_img}) "
                f"| {raw_chars} car. -> {png_path}"
            )

    json_path = out_dir / "report.json"
    json_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapport JSON : {json_path}")
    print(f"Images annotées : {out_dir}/page_*.png")
    print("Légende : VERT = texte gardé, ROUGE = texte écarté, BLEU = image.")


if __name__ == "__main__":
    main()
