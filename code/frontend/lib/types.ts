// Types partagés du frontend.
// Une source = un ARTICLE (document), avec les pages qui l'ont référencé.
export interface Passage {
  page: number | null;
  text: string;
  score: number;
}
export interface Article {
  document_id: string;
  title: string | null;
  authors: string | null;
  filename: string;
  year: number | null;
  doi: string | null;
  score: number;
  passages: Passage[];
}

export type StepKey = "understand" | "retrieve" | "synthesize";
export type StepStatus = "idle" | "active" | "done" | "skipped";

export interface AgentStep {
  key: StepKey;
  status: StepStatus;
  detail?: string; // ex: requête reformulée, nombre de passages
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Article[];
  clarification?: boolean;
  pending?: boolean;       // message assistant en cours de génération
  steps?: AgentStep[];     // état des 3 agents
}

export interface Conversation {
  localId: string;            // identifiant côté client
  backendId: string | null;   // conversation_id renvoyé par l'API
  title: string;
  messages: ChatMessage[];
  createdAt: number;
}
