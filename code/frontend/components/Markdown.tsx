"use client";
// Rendu léger du markdown renvoyé par l'assistant (sans dépendance externe) :
// paragraphes, listes à puces, titres ###, gras **...** et citations [n] / [n, m].
import { Fragment } from "react";

// Regex de citation : accepte [1] ou [1, 2, 3] ou [1,2,3] (jusqu'à ~10 numéros).
const CITATION_RE = /\[\d+(?:\s*,\s*\d+)*\]/g;
const CITATION_MATCH_RE = /^\[(\d+(?:\s*,\s*\d+)*)\]$/;

function renderInline(
  text: string,
  keyPrefix: string,
  onCitationClick?: (n: number) => void,
) {
  // Découpe sur **gras** ET [n] / [n, m] citations
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+(?:\s*,\s*\d+)*\])/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${keyPrefix}-b${i}`}>{part.slice(2, -2)}</strong>;
    }
    const citMatch = part.match(CITATION_MATCH_RE);
    if (citMatch && onCitationClick) {
      const numbers = citMatch[1]
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => Number.isFinite(n));
      if (!numbers.length) {
        return <Fragment key={`${keyPrefix}-t${i}`}>{part}</Fragment>;
      }
      // Un groupe [1, 2, 3] devient un badge par numéro, entre crochets partagés
      return (
        <span
          key={`${keyPrefix}-c${i}`}
          className="citation-group inline-flex items-center gap-0.5 mx-0.5 align-super"
        >
          {numbers.map((n, k) => (
            <button
              key={k}
              onClick={() => onCitationClick(n)}
              className="citation-ref inline-flex h-4 min-w-4 items-center justify-center rounded bg-primary/10 px-1 text-[10px] font-semibold text-primary hover:bg-primary/20 cursor-pointer"
              title={`Voir source [${n}]`}
            >
              {n}
            </button>
          ))}
        </span>
      );
    }
    return <Fragment key={`${keyPrefix}-t${i}`}>{part}</Fragment>;
  });
}

export function Markdown({
  content,
  onCitationClick,
}: {
  content: string;
  onCitationClick?: (n: number) => void;
}) {
  const lines = content.split("\n");
  const blocks: JSX.Element[] = [];
  let list: string[] = [];
  let key = 0;

  const flushList = () => {
    if (list.length) {
      const items = [...list];
      blocks.push(
        <ul key={`ul${key++}`}>
          {items.map((it, i) => (
            <li key={i}>{renderInline(it, `li${key}-${i}`, onCitationClick)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList();
      continue;
    }
    if (/^[-*•]\s+/.test(line)) {
      list.push(line.replace(/^[-*•]\s+/, ""));
      continue;
    }
    flushList();
    if (line.startsWith("### ")) {
      blocks.push(<h3 key={`h${key++}`}>{renderInline(line.slice(4), `h${key}`, onCitationClick)}</h3>);
    } else if (line.startsWith("## ")) {
      blocks.push(<h3 key={`h${key++}`}>{renderInline(line.slice(3), `h${key}`, onCitationClick)}</h3>);
    } else {
      blocks.push(<p key={`p${key++}`}>{renderInline(line, `p${key}`, onCitationClick)}</p>);
    }
  }
  flushList();

  return <div className="prose-chat text-[15px] text-[#0d0d0d]">{blocks}</div>;
}

export { CITATION_RE };
