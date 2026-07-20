"use client";
import { useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, ExternalLink } from "lucide-react";
import type { Article } from "@/lib/types";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function ArticleCard({
  index,
  article,
  highlighted,
}: {
  index: number;
  article: Article;
  highlighted: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const n = article.passages.length;

  useEffect(() => {
    if (highlighted && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlighted]);

  return (
    <Card
      ref={ref}
      id={`citation-${index}`}
      className={cn(
        "bg-muted/40 p-3 shadow-none transition-colors duration-500",
        highlighted && "ring-2 ring-primary bg-primary/5",
      )}
    >
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger className="flex w-full items-start justify-between gap-2 text-left">
          <span className="text-sm font-medium leading-snug">
            [{index}] {article.title || article.filename}
          </span>
          <Badge variant="success" className="shrink-0">
            {article.score.toFixed(2)}
          </Badge>
        </CollapsibleTrigger>

        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          {article.authors && (
            <span className="truncate max-w-[18rem]" title={article.authors}>
              {article.authors}
            </span>
          )}
          {article.authors && <span>·</span>}
          <span>{article.year ?? "année n.c."}</span>
          <span>·</span>
          <span>{n} page{n > 1 ? "s" : ""} identifiée{n > 1 ? "s" : ""}</span>
          {article.doi && (
            <>
              <span>·</span>
              <a
                href={`https://doi.org/${article.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                DOI <ExternalLink className="h-2.5 w-2.5" />
              </a>
            </>
          )}
          <ChevronDown className={cn("h-3 w-3 transition-transform ml-auto", open && "rotate-180")} />
        </div>

        <CollapsibleContent className="mt-2 space-y-2">
          {article.passages.map((p, i) => (
            <div key={i} className="border-l-2 pl-2">
              <div className="text-xs font-medium text-muted-foreground">
                {p.page ? `page ${p.page}` : "page n.c."}
              </div>
              <p className="mt-0.5 line-clamp-3 text-xs leading-relaxed text-muted-foreground">
                {p.text}
              </p>
            </div>
          ))}
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

export interface DisplayedSource {
  index: number; // numéro [n] tel que cité dans la synthèse
  article: Article;
}

export function Sources({
  sources,
  activeCitation,
}: {
  sources: DisplayedSource[];
  activeCitation?: number | null;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (activeCitation != null) {
      setOpen(true);
    }
  }, [activeCitation]);

  if (!sources.length) return null;

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-4">
      <CollapsibleTrigger className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent">
        <BookOpen className="h-3.5 w-3.5" />
        {sources.length} source{sources.length > 1 ? "s" : ""} scientifique{sources.length > 1 ? "s" : ""}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </CollapsibleTrigger>

      <CollapsibleContent className="mt-2 grid gap-2 sm:grid-cols-2">
        {sources.map(({ index, article }) => (
          <ArticleCard
            key={index}
            index={index}
            article={article}
            highlighted={activeCitation === index}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
