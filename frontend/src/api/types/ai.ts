// `api/types.ts` dan ajratildi — domen bo'yicha.

export type AIChatMessage = {
  role: "user" | "assistant";
  text: string;
  created_at: string;
};

export type AIChatHistory = { history: AIChatMessage[] };

export type AIChatAnswer = { ok: boolean; answer: string; source: "openai" | "local" };

export type AIStatus = {
  ok: boolean;
  build: string;
  business_id: number;
  openai_enabled: boolean;
  local_fallback: boolean;
};

export type AIDocumentDraftRequest = {
  prompt: string;
  direction?: string;
  doc_type?: string;
  title?: string;
  number?: string;
  doc_date?: string;
  contractor_id?: number | null;
  firm_name?: string;
  director?: string;
  inn?: string;
};

export type AIDocumentDraft = {
  ok: boolean;
  source: "openai" | "local";
  direction: string;
  doc_type: string;
  title: string;
  number: string;
  doc_date: string;
  body: string;
  note: string;
};
