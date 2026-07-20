// Client d'appel au backend FastAPI.
import type { Article } from "./types";
import { authHeaders } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ----- Authentification -----
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export interface UserInfo {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export async function register(email: string, password: string): Promise<UserInfo> {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `Erreur API (${res.status})`);
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  // OAuth2PasswordRequestForm attend du x-www-form-urlencoded (username/password).
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/auth/jwt/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || "Email ou mot de passe incorrect");
  }
  return res.json();
}

export async function getMe(): Promise<UserInfo> {
  const res = await fetch(`${API_URL}/users/me`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}

export interface ChatResponse {
  conversation_id: string;
  needs_clarification: boolean;
  clarification?: string | null;
  answer?: string | null;
  sources: Article[];
}

export async function sendChat(
  question: string,
  conversationId: string | null,
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}

// ----- Variante streamée : reçoit l'état des agents en temps réel -----
export interface StepEvent {
  type: "step";
  agent: "understand" | "retrieve" | "synthesize";
  data: { needs_clarification?: boolean; search_query?: string; num_sources?: number };
}
export interface TokenEvent {
  type: "token";
  content: string;
}
export interface FinalEvent {
  type: "final";
  conversation_id: string;
  needs_clarification: boolean;
  clarification?: string | null;
  answer?: string | null;
  sources?: Article[];
}
export interface ErrorEvent {
  type: "error";
  message: string;
}
type StreamEvent = StepEvent | TokenEvent | FinalEvent | ErrorEvent;

export async function sendChatStream(
  question: string,
  conversationId: string | null,
  onEvent: (e: StreamEvent) => void,
  understandModel?: string | null,
  synthesizeModel?: string | null,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      understand_model: understandModel,
      synthesize_model: synthesizeModel,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`Erreur API (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Les événements SSE sont séparés par une ligne vide
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as StreamEvent);
      } catch {
        /* ignore les fragments incomplets */
      }
    }
  }
}

// ----- Historique (conversations / messages côté serveur) -----
export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
}
export interface ServerMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Article[];
  created_at: string;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_URL}/conversations`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}

export async function listMessages(conversationId: string): Promise<ServerMessage[]> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/messages`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
}

export interface DocumentOut {
  id: string;
  filename: string;
  title: string | null;
  year: number | null;
  source: string | null;
  n_pages: number | null;
  n_chunks: number;
  status: string;
}

export interface AgentModels {
  default: string;
  available: string[];
}

export interface ModelsInfo {
  default: string;
  available: string[];
  // Listes par agent (optionnelles : absentes si backend plus ancien).
  understand?: AgentModels;
  synthesize?: AgentModels;
}

export async function listModels(): Promise<ModelsInfo> {
  const res = await fetch(`${API_URL}/models`);
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}

export async function listDocuments(): Promise<DocumentOut[]> {
  const res = await fetch(`${API_URL}/documents`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${documentId}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
}

// Import + indexation d'un PDF (multipart). Renvoie le document créé.
export async function uploadDocument(
  file: File,
  opts: { year?: number; source?: string } = {},
): Promise<DocumentOut> {
  const form = new FormData();
  form.append("file", file);
  if (opts.year != null) form.append("year", String(opts.year));
  if (opts.source) form.append("source", opts.source);

  const res = await fetch(`${API_URL}/documents`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (!res.ok) throw new Error(`Erreur API (${res.status})`);
  return res.json();
}
