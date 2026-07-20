"use client";
import { useEffect, useRef, useState } from "react";
import { PanelLeft, LogOut } from "lucide-react";
import { useChatContext } from "@/lib/chat-context";
import { Sidebar } from "@/components/Sidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { Composer } from "@/components/Composer";
import { EmptyState } from "@/components/EmptyState";
import { ModelSelector } from "@/components/ModelSelector";
import { Button } from "@/components/ui/button";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    conversations,
    activeId,
    loading,
    understandModels,
    synthesizeModels,
    understandModel,
    synthesizeModel,
    email,
    ready,
    input,
    setInput,
    selectConversation,
    newConversation,
    deleteConversation,
    submit,
    logout,
    pickUnderstandModel,
    pickSynthesizeModel,
  } = useChatContext();

  const active = conversations.find((c) => c.localId === activeId) || null;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [active?.messages]);

  if (!ready) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onNew={newConversation}
          onSelect={selectConversation}
          onDelete={deleteConversation}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center gap-2 border-b px-3">
          {!sidebarOpen && (
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setSidebarOpen(true)}>
              <PanelLeft className="h-4 w-4" />
            </Button>
          )}
          <span className="flex-1 truncate text-sm font-medium text-muted-foreground">
            {active?.title ?? "Assistant TUI"}
          </span>
          <ModelSelector
            models={understandModels}
            value={understandModel}
            onChange={pickUnderstandModel}
            disabled={loading}
            label="Reformulation"
          />
          <ModelSelector
            models={synthesizeModels}
            value={synthesizeModel}
            onChange={pickSynthesizeModel}
            disabled={loading}
            label="Synthèse"
          />
          {email && (
            <span className="hidden max-w-[160px] truncate text-xs text-muted-foreground sm:inline">
              {email}
            </span>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={logout}
            title="Se déconnecter"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {!active || active.messages.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
              {active.messages.map((m, i) => (
                <ChatMessage key={i} message={m} />
              ))}
            </div>
          )}
        </div>

        <div className="px-4 pb-4 pt-2">
          <Composer value={input} onChange={setInput} onSubmit={() => submit(input)} disabled={loading} />
        </div>
      </div>
    </div>
  );
}
