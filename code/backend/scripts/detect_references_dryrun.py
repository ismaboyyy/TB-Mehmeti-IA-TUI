"""Dry-run de détection des sections bibliographiques (aucune ré-indexation).

Passe le détecteur de références sur un dossier de PDF et produit un rapport
Markdown : pour chaque document, le titre de bibliographie détecté, le pourcentage
de texte flaggé comme référence, et des exemples (flaggé vs corps gardé).

Trois règles combinées :
  1. Titre de section (References/Bibliographie/Références...) détecté au niveau du
     BLOC, uniquement dans le dernier tiers du document -> coupe précise.
  2. Motif fort (année + initiales/DOI + plage de pages) -> attrape les références
     numérotées même sans titre.
  3. Tout ce qui précède le titre reste "corps" (préservé).

Usage (dans le conteneur backend) :
    python scripts/detect_references_dryrun.py [/data/files/estia]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.rag.ingestion import _extract_pages_blocks  # noqa: E402

HEADING = re.compile(
    r"^(?:\d+\.?\s*)?(references|bibliography|référence?s|bibliographie|referencias|works cited)\b",
    re.I,
)
YEAR = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")
INITIALS = re.compile(r"\b[A-Z]\.(?:\s*[A-Z]\.)*")
PAGERANGE = re.compile(r"\b\d{1,4}\s?[–-]\s?\d{1,4}\b")


def is_heading(block: str) -> bool:
    return bool(HEADING.match(block.strip())) and len(block.split()) <= 3


def strong_ref(text: str) -> bool:
    y = len(YEAR.findall(text))
    i = len(INITIALS.findall(text))
    return y >= 1 and (i >= 4 or "doi" in text.lower()) and bool(PAGERANGE.search(text))


def analyze(pdf: Path) -> dict:
    pages = _extract_pages_blocks(pdf)
    n = len(pages)
    # 1) position du BLOC titre, uniquement dans le dernier tiers
    hpos = None
    for pno, ptext in pages:
        if pno < 0.70 * n:
            continue
        blocks = [b for b in ptext.split("\n\n") if b.strip()]
        for bi, b in enumerate(blocks):
            if is_heading(b):
                hpos = (pno, bi)
                break
        if hpos:
            break
    # 2) coupe bloc par bloc
    ref_chars = body_chars = 0
    ex_ref: list[tuple[int, str]] = []
    for pno, ptext in pages:
        blocks = [b for b in ptext.split("\n\n") if b.strip()]
        for bi, b in enumerate(blocks):
            in_sec = hpos and (pno > hpos[0] or (pno == hpos[0] and bi >= hpos[1]))
            if in_sec or strong_ref(b):
                ref_chars += len(b)
                if len(ex_ref) < 3:
                    ex_ref.append((pno, b[:160]))
            else:
                body_chars += len(b)
    tot = ref_chars + body_chars or 1
    return {
        "name": pdf.name,
        "pages": n,
        "heading": hpos,
        "pct": round(100 * ref_chars / tot, 1),
        "examples": ex_ref,
    }


def main() -> None:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/data/files/estia")
    pdfs = sorted(base.rglob("*.pdf"))
    rows = []
    for p in pdfs:
        try:
            rows.append(analyze(p))
        except Exception as exc:  # noqa: BLE001
            rows.append({"name": p.name, "pages": 0, "heading": None, "pct": 0.0,
                         "examples": [], "error": str(exc)})

    out = ["# Dry-run — détection des sections bibliographiques", ""]
    out.append(f"Corpus : `{base}` — {len(rows)} PDF. Aucune ré-indexation effectuée.\n")
    out.append("Colonnes : **Titre biblio** = position (page, bloc) du titre détecté ; "
               "**% réf.** = part du texte flaggée comme bibliographie.\n")
    out.append("| Document | Pages | Titre biblio | % réf. |")
    out.append("|---|---:|---|---:|")
    for r in sorted(rows, key=lambda r: r["pct"], reverse=True):
        h = f"{r['heading']}" if r["heading"] else "—"
        out.append(f"| {r['name']} | {r['pages']} | {h} | {r['pct']} % |")

    out.append("\n---\n\n## Exemples de passages flaggés (par document)\n")
    for r in sorted(rows, key=lambda r: r["pct"], reverse=True):
        if not r["examples"]:
            continue
        out.append(f"### {r['name']}  ({r['pct']} %)")
        for pno, txt in r["examples"]:
            out.append(f"- p{pno} : `{txt}`")
        out.append("")

    print("\n".join(out))


if __name__ == "__main__":
    main()
