"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  sendChatStream,
  listModels,
  getMe,
  listConversations,
  listMessages,
  deleteConversation as deleteConversationApi,
} from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import type { Conversation, ChatMessage as Msg, AgentStep, StepKey, StepStatus } from "@/lib/types";

const UNDERSTAND_MODEL_KEY = "tui_understand_model";
const SYNTHESIZE_MODEL_KEY = "tui_synthesize_model";
const uid = () => Math.random().toString(36).slice(2, 10);

interface ChatContextType {
  conversations: Conversation[];
  activeId: string | null;
  loading: boolean;
  models: string[];
  understandModels: string[];
  synthesizeModels: string[];
  understandModel: string | null;
  synthesizeModel: string | null;
  email: string | null;
  ready: boolean;
  input: string;
  setInput: (v: string) => void;
  selectConversation: (id: string) => Promise<void>;
  newConversation: () => string;
  deleteConversation: (id: string) => void;
  submit: (question: string) => Promise<void>;
  logout: () => void;
  notifyLogin: () => void;
  pickUnderstandModel: (m: string) => void;
  pickSynthesizeModel: (m: string) => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [understandModels, setUnderstandModels] = useState<string[]>([]);
  const [synthesizeModels, setSynthesizeModels] = useState<string[]>([]);
  const [understandModel, setUnderstandModel] = useState<string | null>(null);
  const [synthesizeModel, setSynthesizeModel] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [authVersion, setAuthVersion] = useState(0);
  const router = useRouter();
  const pathname = usePathname();

  // Redirige vers /login si aucun jeton valide (hors page de login)
  useEffect(() => {
    if (pathname === "/login") return;
    if (!getToken()) router.replace("/login");
  }, [pathname, router]);

  // Initialisation de la session (conversations + modèles) — relancée à chaque login/logout
  useEffect(() => {
    // Garde d'annulation : si l'effet est relancé (logout/login) ou démonté
    // pendant qu'une requête est en vol, on ignore son résultat pour ne pas
    // réécrire l'état d'une session périmée.
    let cancelled = false;
    const token = getToken();
    if (!token) {
      setReady(false);
      setEmail(null);
      setConversations([]);
      return;
    }
    setReady(false);
    getMe()
      .then(async (u) => {
        if (cancelled) return;
        setEmail(u.email);
        try {
          const convs = await listConversations();
          if (cancelled) return;
          const mapped: Conversation[] = convs.map((c) => ({
            localId: c.id,
            backendId: c.id,
            title: c.title || "Conversation",
            messages: [],
            createdAt: new Date(c.created_at).getTime(),
          }));
          setConversations(mapped);
          if (mapped.length) {
            setActiveId(mapped[0].localId);
            const msgs = await listMessages(mapped[0].backendId as string);
            if (cancelled) return;
            setConversations((prev) =>
              prev.map((c) =>
                c.localId === mapped[0].localId
                  ? { ...c, messages: msgs.map((m) => ({ role: m.role, content: m.content, sources: m.sources })) }
                  : c,
              ),
            );
          }
        } catch {
          /* historique indisponible */
        }
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        if (cancelled) return;
        clearToken();
        router.replace("/login");
      });

    listModels()
      .then((info) => {
        if (cancelled) return;
        setModels(info.available);
        // Listes par agent (repli sur la liste commune si backend ancien).
        const uList = info.understand?.available ?? info.available;
        const sList = info.synthesize?.available ?? info.available;
        const uDefault = info.understand?.default ?? info.default;
        const sDefault = info.synthesize?.default ?? info.default;
        setUnderstandModels(uList);
        setSynthesizeModels(sList);
        const savedU = localStorage.getItem(UNDERSTAND_MODEL_KEY);
        const savedS = localStorage.getItem(SYNTHESIZE_MODEL_KEY);
        setUnderstandModel(savedU && uList.includes(savedU) ? savedU : uDefault);
        setSynthesizeModel(savedS && sList.includes(savedS) ? savedS : sDefault);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [authVersion, router]);

  function notifyLogin() {
    setAuthVersion((v) => v + 1);
  }

  function logout() {
    clearToken();
    setConversations([]);
    setActiveId(null);
    setEmail(null);
    setReady(false);
    setInput("");
    setAuthVersion((v) => v + 1);
    router.replace("/login");
  }

  function pickUnderstandModel(m: string) {
    setUnderstandModel(m);
    localStorage.setItem(UNDERSTAND_MODEL_KEY, m);
  }

  function pickSynthesizeModel(m: string) {
    setSynthesizeModel(m);
    localStorage.setItem(SYNTHESIZE_MODEL_KEY, m);
  }

  async function selectConversation(id: string) {
    setActiveId(id);
    const conv = conversations.find((c) => c.localId === id);
    if (conv?.backendId && conv.messages.length === 0) {
      try {
        const msgs = await listMessages(conv.backendId);
        setConversations((prev) =>
          prev.map((c) =>
            c.localId === id
              ? { ...c, messages: msgs.map((m) => ({ role: m.role, content: m.content, sources: m.sources })) }
              : c,
          ),
        );
      } catch {
        /* ignore */
      }
    }
  }

  function newConversation(): string {
    const conv: Conversation = {
      localId: uid(),
      backendId: null,
      title: "Nouvelle conversation",
      messages: [],
      createdAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.localId);
    return conv.localId;
  }

  function deleteConversation(id: string) {
    const conv = conversations.find((c) => c.localId === id);
    if (conv?.backendId) {
      deleteConversationApi(conv.backendId).catch(() => {});
    }
    const next = conversations.filter((c) => c.localId !== id);
    setConversations(next);
    if (id === activeId) setActiveId(next[0]?.localId ?? null);
  }

  function patch(localId: string, fn: (c: Conversation) => Conversation) {
    setConversations((prev) => prev.map((c) => (c.localId === localId ? fn(c) : c)));
  }

  function updateLast(localId: string, fn: (m: Msg) => Msg) {
    patch(localId, (c) => ({
      ...c,
      messages: c.messages.map((m, i) => (i === c.messages.length - 1 ? fn(m) : m)),
    }));
  }

  function setStep(steps: AgentStep[], key: StepKey, status: StepStatus, detail?: string): AgentStep[] {
    return steps.map((s) => (s.key === key ? { ...s, status, ...(detail ? { detail } : {}) } : s));
  }

  async function submit(question: string) {
    const q = question.trim();
    if (!q || loading) return;

    let convId = activeId;
    let existing = conversations.find((c) => c.localId === convId);
    if (!convId || !existing) {
      convId = newConversation();
      existing = undefined;
    }
    const localId = convId;
    // On capture le backendId depuis le snapshot AVANT le patch d'état : lire
    // `conversations` après `patch()` renverrait un instantané périmé (React
    // n'a pas encore appliqué la mise à jour).
    const backendId = existing?.backendId ?? null;

    const initialSteps: AgentStep[] = [
      { key: "understand", status: "active" },
      { key: "retrieve", status: "idle" },
      { key: "synthesize", status: "idle" },
    ];
    const userMsg: Msg = { role: "user", content: q };
    const pendingMsg: Msg = { role: "assistant", content: "", pending: true, steps: initialSteps };

    patch(localId, (c) => ({
      ...c,
      title: c.messages.length === 0 ? q.slice(0, 48) : c.title,
      messages: [...c.messages, userMsg, pendingMsg],
    }));
    setInput("");
    setLoading(true);

    try {
      await sendChatStream(
        q,
        backendId,
        (e) => {
          if (e.type === "step") {
            updateLast(localId, (m) => {
              let steps = m.steps ?? initialSteps;
              if (e.agent === "understand") {
                if (e.data.needs_clarification) {
                  steps = setStep(steps, "understand", "done", "clarification nécessaire");
                  steps = setStep(steps, "retrieve", "skipped");
                  steps = setStep(steps, "synthesize", "skipped");
                } else {
                  steps = setStep(steps, "understand", "done", e.data.search_query || undefined);
                  steps = setStep(steps, "retrieve", "active");
                }
              } else if (e.agent === "retrieve") {
                steps = setStep(steps, "retrieve", "done", `${e.data.num_sources ?? 0} article(s)`);
                steps = setStep(steps, "synthesize", "active");
              } else if (e.agent === "synthesize") {
                steps = setStep(steps, "synthesize", "done");
              }
              return { ...m, steps };
            });
          } else if (e.type === "token") {
            updateLast(localId, (m) => ({
              ...m,
              steps: m.steps ? setStep(m.steps, "synthesize", "active") : m.steps,
              content: (m.content || "") + e.content,
            }));
          } else if (e.type === "final") {
            patch(localId, (c) => ({ ...c, backendId: e.conversation_id }));
            updateLast(localId, (m) => ({
              ...m,
              pending: false,
              clarification: e.needs_clarification,
              content: e.needs_clarification
                ? e.clarification || "Peux-tu préciser ton besoin ?"
                : e.answer || m.content || "",
              sources: e.sources,
              steps: m.steps ? setStep(m.steps, "synthesize", "done") : m.steps,
            }));
          } else if (e.type === "error") {
            updateLast(localId, (m) => ({ ...m, pending: false, content: `Erreur : ${e.message}` }));
          }
        },
        understandModel,
        synthesizeModel,
      );
    } catch (e) {
      updateLast(localId, (m) => ({ ...m, pending: false, content: `Erreur : ${(e as Error).message}` }));
    } finally {
      setLoading(false);
    }
  }

  return (
    <ChatContext.Provider
      value={{
        conversations,
        activeId,
        loading,
        models,
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
        notifyLogin,
        pickUnderstandModel,
        pickSynthesizeModel,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used within ChatProvider");
  return ctx;
}
