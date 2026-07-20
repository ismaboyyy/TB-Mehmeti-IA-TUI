"use client";
import { useCallback, useMemo, useRef, useState } from "react";
import { Sparkles, HelpCircle } from "lucide-react";
import type { ChatMessage as Msg } from "@/lib/types";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Markdown } from "./Markdown";
import { Sources, type DisplayedSource } from "./Sources";
import { AgentSteps } from "./AgentSteps";

function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span key={i} className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
      ))}
    </span>
  );
}

// Extrait les numéros [n] et [n, m, ...] effectivement cités dans la synthèse
// (déduplication + tri croissant).
function extractCitedIndices(content: string): number[] {
  if (!content) return [];
  const seen = new Set<number>();
  for (const match of content.matchAll(/\[(\d+(?:\s*,\s*\d+)*)\]/g)) {
    for (const raw of match[1].split(",")) {
      const n = parseInt(raw.trim(), 10);
      if (Number.isFinite(n)) seen.add(n);
    }
  }
  return [...seen].sort((a, b) => a - b);
}

export function ChatMessage({ message }: { message: Msg }) {
  const isUser = message.role === "user";
  const [activeCitation, setActiveCitation] = useState<number | null>(null);
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleCitationClick = useCallback((n: number) => {
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
    setActiveCitation(n);
    highlightTimer.current = setTimeout(() => setActiveCitation(null), 2000);
  }, []);

  // Ne conserve dans le panneau que les sources effectivement citées dans la
  // synthèse (préserve les indices d'origine, pour cohérence texte <-> panneau).
  const displayedSources = useMemo<DisplayedSource[]>(() => {
    if (!message.sources || !message.sources.length) return [];
    const cited = new Set(extractCitedIndices(message.content));
    if (!cited.size) return [];
    return message.sources
      .map((article, i) => ({ index: i + 1, article }))
      .filter(({ index }) => cited.has(index));
  }, [message.sources, message.content]);

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-secondary px-4 py-2.5 text-[15px] leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      <Avatar className={message.clarification ? "bg-amber-500" : "bg-primary"}>
        <AvatarFallback className="bg-transparent text-white">
          {message.clarification ? <HelpCircle className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 pt-1">
        {message.steps && message.steps.length > 0 && <AgentSteps steps={message.steps} />}
        {message.clarification && (
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-600">
            Question complémentaire
          </div>
        )}
        {message.pending && !message.content ? (
          <TypingDots />
        ) : (
          message.content && (
            <Markdown
              content={message.content}
              onCitationClick={displayedSources.length ? handleCitationClick : undefined}
            />
          )
        )}
        <Sources sources={displayedSources} activeCitation={activeCitation} />
      </div>
    </div>
  );
}
