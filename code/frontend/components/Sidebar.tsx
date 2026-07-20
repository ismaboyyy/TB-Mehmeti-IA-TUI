"use client";
import Link from "next/link";
import { Plus, MessageSquare, Trash2, Library, PanelLeftClose } from "lucide-react";
import type { Conversation } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
}

export function Sidebar({ conversations, activeId, onNew, onSelect, onDelete, onClose }: Props) {
  return (
    <aside className="flex h-full w-64 flex-col bg-[hsl(var(--sidebar))] text-[hsl(var(--sidebar-foreground))]">
      <div className="flex items-center justify-between gap-2 p-3">
        <span className="px-1 text-sm font-semibold">Assistant TUI</span>
        {onClose && (
          <Button variant="ghost" size="icon" className="h-8 w-8 text-white/70 hover:bg-white/10 hover:text-white" onClick={onClose}>
            <PanelLeftClose className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="px-3">
        <Button
          onClick={onNew}
          variant="outline"
          className="w-full justify-start gap-2 border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
        >
          <Plus className="h-4 w-4" /> Nouvelle conversation
        </Button>
      </div>

      <ScrollArea className="mt-3 flex-1 px-2">
        <div className="space-y-0.5 pb-2">
          {conversations.length === 0 && (
            <p className="px-3 py-6 text-center text-xs text-white/40">Aucune conversation</p>
          )}
          {conversations.map((c) => (
            <div
              key={c.localId}
              className={cn(
                "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                c.localId === activeId ? "bg-white/15" : "hover:bg-white/10",
              )}
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-white/60" />
              <button onClick={() => onSelect(c.localId)} className="min-w-0 flex-1 truncate text-left text-white/90">
                {c.title}
              </button>
              <button
                onClick={() => onDelete(c.localId)}
                className="opacity-0 transition-opacity group-hover:opacity-100"
                aria-label="Supprimer"
              >
                <Trash2 className="h-3.5 w-3.5 text-white/50 hover:text-red-400" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-white/10 p-2">
        <Link
          href="/documents"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-white/80 transition-colors hover:bg-white/10"
        >
          <Library className="h-4 w-4" /> Corpus documentaire
        </Link>
      </div>
    </aside>
  );
}
