"""Pipeline d'indexation d'un PDF :
   extraction (PyMuPDF) -> nettoyage -> chunking (overlap) -> embeddings -> Qdrant
   et enregistrement des métadonnées du document dans PostgreSQL.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.models import PointStruct
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document
from app.rag.embeddings import get_embedder
from app.rag.vectorstore import delete_by_document_id, ensure_collection, upsert_chunks


# Flags d'extraction PyMuPDF : on active la DÉ-CÉSURE native (recolle "vir-\ntual"
# -> "virtual"), en plus des flags par défaut.
_TEXT_FLAGS = fitz.TEXTFLAGS_TEXT | fitz.TEXT_DEHYPHENATE
_BLOCKS_FLAGS = fitz.TEXTFLAGS_BLOCKS | fitz.TEXT_DEHYPHENATE


def _clean(text: str) -> str:
    """Normalise les espaces (la dé-césure est gérée nativement par PyMuPDF
    via TEXT_DEHYPHENATE à l'extraction, cf. _TEXT_FLAGS / _BLOCKS_FLAGS)."""
    return re.sub(r"\s+", " ", text).strip()


def _is_meaningful(text: str) -> bool:
    """Filtre anti-charabia : rejette les chunks issus de pages mal extraites
    (polices sans table Unicode -> caractères isolés). On garde un chunk si son
    texte ressemble à du langage naturel.

    Ce filtre sert à supprimer les morceaux de PDF mal extraits, 
    tout en gardant les textes courts qui peuvent être des titres ou des légendes.

    Heuristique sur les tokens :
      - part de tokens très courts (<= 2 caractères) faible,
      - présence suffisante de « vrais mots » (>= 4 lettres).
    Les chunks courts (titres, légendes) sont conservés sans jugement.
    """
    tokens = re.findall(r"\S+", text)
    if len(tokens) < 8:
        return True
    short_ratio = sum(1 for t in tokens if len(t) <= 2) / len(tokens)
    word_ratio = sum(1 for t in tokens if len(t) >= 4 and any(c.isalpha() for c in t)) / len(tokens)
    return short_ratio < 0.5 and word_ratio > 0.2


def _extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Retourne [(numéro_page, texte_nettoyé), ...]."""
    pages: list[tuple[int, str]] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            txt = _clean(page.get_text("text", flags=_TEXT_FLAGS))
            if txt:
                pages.append((i, txt))
    return pages


def _extract_pages_blocks(pdf_path: Path) -> list[tuple[int, str]]:
    """Extraction par BLOCS triés en ordre de lecture (stratégie "blocks").

    Pour chaque page : on récupère les blocs de texte de PyMuPDF, on les nettoie
    et on écarte le charabia, puis on les TRIE dans l'ordre de lecture
    (colonne gauche de haut en bas, puis colonne droite). Les blocs sont recollés
    avec des sauts de paragraphe : le découpeur coupera ainsi de préférence AUX
    frontières de blocs (séparateur "\\n\\n"), au lieu de couper en plein milieu.

    Corrige les deux défauts du texte aplati : ordre de lecture (titre avant le
    bandeau de bas de page) et entrelacement des colonnes. Heuristique de colonne :
    un bloc large (> 60 % de la page) est traité comme pleine largeur.

    Pour résumé : La stratégie blocks essaie de reconstruire un 
    ordre de lecture plus naturel pour les PDF multi-colonnes, 
    afin que les chunks soient moins mélangés et plus utiles pour le RAG.
    """
    pages: list[tuple[int, str]] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            mid_x = page.rect.width / 2
            items: list[tuple[int, float, str]] = []
            for x0, y0, x1, y1, text, _no, block_type in page.get_text("blocks", flags=_BLOCKS_FLAGS):
                if block_type != 0:  # 1 = image -> ignoré
                    continue
                cleaned = _clean(text)
                if not cleaned or not _is_meaningful(cleaned):
                    continue
                is_full_width = (x1 - x0) > 0.6 * page.rect.width
                column = 0 if is_full_width else (0 if (x0 + x1) / 2 < mid_x else 1)
                items.append((column, y0, cleaned))
            items.sort(key=lambda it: (it[0], it[1]))
            page_text = "\n\n".join(t for _c, _y, t in items)
            if page_text:
                pages.append((i, page_text))
    return pages


# --------------------------------------------------------------------------- #
# Exclusion des sections bibliographiques (voir scripts/detect_references_dryrun.py)
#   Deux règles combinées, au niveau du BLOC :
#     1. titre "References/Bibliographie/..." dans le dernier tiers du document
#        -> tout ce qui suit (ordre de lecture) est de la bibliographie ;
#     2. motif fort d'une entrée (année + initiales/DOI + plage de pages)
#        -> attrape les références numérotées même sans titre.
#   Le corps qui PRÉCÈDE le titre est préservé (coupe bloc par bloc).
# --------------------------------------------------------------------------- #

_DOI_RE = re.compile(r"\b(10\.\d{4,}/[^\s\"'<>\]]+)")
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
# Année proche d'une mention de copyright, Ex : (« © 2019 ACM », « Copyright 2018 »)
_YEAR_COPYRIGHT_RE = re.compile(r"(?:©|copyright|\(c\))[^\n]{0,40}?((?:19|20)\d{2})", re.I)

# Titres qu'on trouve parfois dans le champ Info d'un PDF, Ex : (« Microsoft Word », « .docx », « .pdf », « .rtf », « .tex », « untitled »)
_JUNK_TITLE_RE = re.compile(r"(microsoft word|\.docx?\b|\.pdf\b|\.rtf\b|\.tex\b|untitled)", re.I)
_GENERIC_TITLES = {"background", "introduction", "abstract", "title", "untitled",
                   "document", "paper", "article", "manuscript"}


def _is_junk_title(t: str | None) -> bool:
    """Vrai si le titre est inexploitable (trop court, nom de fichier .docx,
    section générique comme « Background »…)."""
    t = (t or "").strip()
    if len(t) <= 4:
        return True
    if _JUNK_TITLE_RE.search(t):
        return True
    return t.lower() in _GENERIC_TITLES


def _title_from_first_page(doc) -> str | None:
    """Extrait le titre depuis la 1re page : les lignes ayant la plus GRANDE
    police, situées dans la moitié haute (méthode classique). Un titre sur
    plusieurs lignes est recollé dans l'ordre vertical."""
    if len(doc) == 0:
        return None
    page = doc[0]
    lines: list[tuple[float, float, str]] = []  # (taille, y, texte)
    for block in page.get_text("dict", flags=_TEXT_FLAGS).get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            txt = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if not txt:
                continue
            size = max((s.get("size", 0.0) for s in line.get("spans", [])), default=0.0)
            lines.append((size, line.get("bbox", [0, 0, 0, 0])[1], txt))
    if not lines:
        return None
    max_size = max(s for s, _y, _t in lines)
    top = 0.5 * page.rect.height
    big = [(y, t) for s, y, t in lines if s >= 0.95 * max_size and y < top] \
        or [(y, t) for s, y, t in lines if s >= 0.95 * max_size]
    big.sort()
    title = re.sub(r"\s+", " ", " ".join(t for _y, t in big)).strip()
    return title or None


def _extract_pdf_metadata(pdf_path: Path) -> dict:
    """Lit les métadonnées d'un article (titre, auteurs, DOI, année) via PyMuPDF.

    - Titre / auteurs / DOI : d'abord les champs XMP/Info du PDF (souvent bien
      remplis pour les articles ACM), puis regex DOI sur les premières pages.
    - Année : cherchée dans le texte des premières pages — mention de copyright
      en priorité, sinon l'année la plus fréquente — avec repli sur la date PDF.
      (Le dossier ESTIA n'a pas de sous-dossier année, d'où cette extraction.)
    """
    import datetime
    from collections import Counter

    result: dict = {"title": None, "authors": None, "doi": None, "year": None}
    now = datetime.date.today().year
    try:
        with fitz.open(pdf_path) as doc:
            meta = doc.metadata or {}
            raw_title = (meta.get("title") or "").strip()
            raw_author = (meta.get("author") or "").strip()
            raw_doi = (meta.get("doi") or "").strip()

            # Titre : la métadonnée PDF si elle est exploitable, sinon on
            # l'extrait de la 1re page (le champ Info est parfois pas bonne).
            if not _is_junk_title(raw_title):
                result["title"] = raw_title
            else:
                fp = _title_from_first_page(doc)
                result["title"] = fp if not _is_junk_title(fp) else None
            if raw_author:
                result["authors"] = raw_author
            if raw_doi:
                result["doi"] = raw_doi

            # Texte des 3 premières pages, réutilisé pour le DOI ET l'année
            head = ""
            for page in doc[:3]:
                head += page.get_text("text", flags=_TEXT_FLAGS) + "\n"

            if not result["doi"]:
                m = _DOI_RE.search(head)
                if m:
                    result["doi"] = m.group(1).rstrip(".,;)>⟩»")

            # Année : mention de copyright d'abord, sinon la plus fréquente,
            # sinon la date des métadonnées PDF.
            m = _YEAR_COPYRIGHT_RE.search(head)
            if m and 1980 <= int(m.group(1)) <= now:
                result["year"] = int(m.group(1))
            else:
                cands = [int(y) for y in _YEAR_RE.findall(head) if 1980 <= int(y) <= now]
                if cands:
                    result["year"] = max(Counter(cands).items(), key=lambda kv: (kv[1], kv[0]))[0]
                else:
                    for key in ("creationDate", "modDate"):
                        ym = _YEAR_RE.search(meta.get(key) or "")
                        if ym and 1980 <= int(ym.group(0)) <= now:
                            result["year"] = int(ym.group(0))
                            break
    except Exception:  # noqa: BLE001
        pass
    return result


_REF_HEADING = re.compile(
    r"^(?:\d+\.?\s*)?(references|bibliography|référence?s|bibliographie|referencias|works cited)\b",
    re.I,
)
_REF_YEAR = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")       # (2005), (2008a)
_REF_YEAR_ANY = re.compile(r"\b(?:19|20)\d{2}")            # année sous toute forme (2005, 2008a)
_REF_INITIALS = re.compile(r"\b[A-Z]\.(?:\s*[A-Z]\.)*")   # initiales : E.  R. J. K.
_REF_PAGERANGE = re.compile(r"\b\d{1,4}\s?[–-]\s?\d{1,4}\b")  # 133–148


def _is_ref_heading(block: str) -> bool:
    return bool(_REF_HEADING.match(block.strip())) and len(block.split()) <= 3


def _ref_like(block: str) -> bool:
    """Bloc RESSEMBLANT à une entrée de référence (critère large, pour VALIDER
    qu'un titre "References" est bien suivi d'une bibliographie)."""
    ini = len(_REF_INITIALS.findall(block)) # cmb d'initiales ?
    yb = len(_REF_YEAR_ANY.findall(block)) # cmb d'années ?
    pr = len(_REF_PAGERANGE.findall(block)) # cmb de plages de pages ?
    return ini >= 1 and (yb >= 1 or pr >= 1) # au moins une initiale ou une année ou une plage de pages ?


def _looks_like_ref(text: str) -> bool:
    """Entrée de bibliographie ISOLÉE (repli quand aucun titre n'est détecté).
    Gère l'année entre parenthèses ET sans parenthèses (styles FR/EN)."""
    ini = len(_REF_INITIALS.findall(text))
    pr = len(_REF_PAGERANGE.findall(text))
    yp = len(_REF_YEAR.findall(text))
    yb = len(_REF_YEAR_ANY.findall(text))
    doi = "doi" in text.lower()
    return (yp >= 2) or (ini >= 2 and yb >= 1 and (pr >= 1 or doi))


def _strip_references(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Retire les blocs de bibliographie pour qu'ils ne soient jamais indexés.

    Deux mécanismes complémentaires, sur la séquence de blocs en ordre de lecture :
      1. titre "References/Bibliographie/..." VALIDÉ par le contenu qui suit
         (les blocs d'après ressemblent à des références) -> tout ce qui suit est
         de la bibliographie. La validation par contenu évite les faux positifs
         (ex. "Bibliographie" dans un sommaire) sans seuil de position rigide.
      2. motif d'entrée isolée (repli si aucun titre détecté).
    """
     # (1) Mettre tous les blocs bout à bout, dans l'ordre de lecture
    seq: list[tuple[int, str]] = []
    for pno, ptext in pages: # pour chaque page
        for b in ptext.split("\n\n"): # chaque bloc de texte (séparés par \n\n)
            if b.strip():
                seq.append((pno, b)) # on garde (n° page, texte du bloc)
    total = len(seq) # ex. 320 blocs
 
    
    # (2) Chercher le panneau "References" et décider où couper
    cut = None
    for idx, (_pno, b) in enumerate(seq): # idx = position du bloc (0..319)
        if idx < 0.4 * total or not _is_ref_heading(b):
            continue # trop tôt, ou pas un titre -> on ignore
        following = [x for _p, x in seq[idx + 1 : idx + 6]] # les 5 blocs suivants
        validated = bool(following) and sum(_ref_like(x) for x in following) >= max(2, len(following) // 2)
        if idx >= 0.6 * total or validated: # accepté par POSITION ou par CONTENU
            cut = idx # on coupe ici
            break

    # (3) Reconstruire en jetant les références
    kept: dict[int, list[str]] = {}
    for idx, (pno, b) in enumerate(seq):
        if (cut is not None and idx >= cut) or _looks_like_ref(b):
            continue  # # bloc de biblio -> jeté
        kept.setdefault(pno, []).append(b) # sinon on garde, rangé par page
    return [(pno, "\n\n".join(bl)) for pno, bl in kept.items() if bl]


def ingest_pdf(
    pdf_path: str | Path,
    db: Session,
    *,
    filename: str | None = None,
    title: str | None = None,
    authors: str | None = None,
    year: int | None = None,
    doi: str | None = None,
    source: str | None = None,
) -> Document:
    """Indexe un PDF et renvoie l'objet Document persisté.

    `filename` : nom LOGIQUE du document (par défaut le nom du fichier sur disque).
    À passer explicitement lors d'un upload : le PDF est alors sauvé sous un nom
    TEMPORAIRE, et sans ça le garde-fou anti-doublon et la métadonnée seraient faux.
    """
    pdf_path = Path(pdf_path)
    fname = filename or pdf_path.name
    ensure_collection()

    # Extraction automatique des métadonnées (titre réel, auteurs, DOI) depuis
    # les champs PDF XMP/Info + regex sur les premières pages. Les valeurs
    # passées explicitement ont la priorité.
    auto_meta = _extract_pdf_metadata(pdf_path)
    title = title or auto_meta["title"] or pdf_path.stem
    authors = authors or auto_meta["authors"]
    doi = doi or auto_meta["doi"]
    # Année : priorité à la valeur explicite (déduite du chemin pour ACM),
    # sinon l'année extraite du document (indispensable pour ESTIA).
    year = year or auto_meta["year"]

    # Idempotence : si ce fichier est déjà indexé, on remplace l'ancienne
    # version (ses chunks Qdrant + sa ligne PostgreSQL) au lieu d'ajouter un
    # doublon. Permet de relancer l'ingestion (ex. après changement de
    # CHUNK_STRATEGY) sans gonfler l'index.
    for old in db.query(Document).filter(Document.filename == fname).all():
        delete_by_document_id(old.id)
        db.delete(old)
    db.flush()

    # Stratégie d'extraction (cf. settings.chunk_strategy) :
    #   "blocks" -> blocs PyMuPDF triés en ordre de lecture (par défaut)
    #   sinon    -> texte aplati
    if settings.chunk_strategy == "blocks":
        pages = _extract_pages_blocks(pdf_path)
        # Exclut la bibliographie de l'index (nécessite la structure en blocs).
        if settings.exclude_references:
            pages = _strip_references(pages)
    else:
        pages = _extract_pages(pdf_path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    # Enregistre d'abord le document pour obtenir son id
    document = Document(
        filename=fname,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        source=source,
        n_pages=len(pages),
        status="pending",
    )
    db.add(document)
    db.flush()  # document.id disponible

    embedder = get_embedder()
    points: list[PointStruct] = []
    chunk_index = 0

    for page_no, page_text in pages:
        # Découpage puis filtre anti-charabia : on n'indexe que les chunks
        # ressemblant à du texte (écarte les pages à police mal encodée).
        chunks = [c for c in splitter.split_text(page_text) if _is_meaningful(c)]
        if not chunks:
            continue
        vectors = embedder.embed_documents(chunks)
        for chunk, vector in zip(chunks, vectors):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "document_id": document.id,
                        "filename": document.filename,
                        "title": document.title,
                        "authors": document.authors,
                        "year": document.year,
                        "doi": document.doi,
                        "page": page_no,
                        "chunk_index": chunk_index,
                        "text": chunk,
                    },
                )
            )
            chunk_index += 1

    if points:
        upsert_chunks(points)

    document.n_chunks = chunk_index
    document.status = "indexed"
    try:
        db.commit()
    except Exception:
        # Le commit a échoué après l'upsert Qdrant : la ligne Document est
        # rollbackée, mais les vecteurs viennent d'être écrits. On les purge
        # pour ne pas laisser de points orphelins pointant vers un document_id
        # inexistant (sinon ils remonteraient comme sources dans la recherche).
        db.rollback()
        delete_by_document_id(document.id)
        raise
    db.refresh(document)
    return document
