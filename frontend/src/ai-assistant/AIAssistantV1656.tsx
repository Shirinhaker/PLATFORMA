import { useEffect, useRef, useState } from "react";
import type { AIChatMessage } from "../api/types";
import "./AIAssistantV1656.css";

export type AIAssistantApi = {
  getAIChatHistory(limit?: number): Promise<{ history: AIChatMessage[] }>;
  sendAIChatMessage(message: string): Promise<{ answer: string }>;
};

const CHIPS = ["Bugungi xulosa", "Ombor holati", "Qarzlar qancha", "Eng ko‘p sotilgan", "Buyurtmalar"];

export function AIAssistantV1656({ api, onBack }: { api: AIAssistantApi; onBack: () => void }) {
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    api.getAIChatHistory(30).then((result) => active && setMessages(result.history)).catch(() => undefined).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, sending]);

  async function send(next = input) {
    const message = next.trim();
    if (!message || sending) return;
    setInput(""); setError(""); setSending(true);
    const user: AIChatMessage = { role: "user", text: message, created_at: new Date().toISOString() };
    setMessages((current) => [...current, user]);
    try {
      const result = await api.sendAIChatMessage(message);
      setMessages((current) => [...current, { role: "assistant", text: result.answer || "(javob yo‘q)", created_at: new Date().toISOString() }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "So‘rov bajarilmadi.");
    } finally { setSending(false); }
  }

  return <section className="ai1656">
    <header><button type="button" onClick={onBack}>← Orqaga</button><h1>AI yordamchi</h1></header>
    <div className="ai1656__list" ref={listRef} aria-live="polite">
      {loading ? <p className="ai1656__muted">Yuklanmoqda...</p> : null}
      {!loading && !messages.length ? <div className="ai1656__empty"><span>🤖</span><strong>AI yordamchi</strong><p>Savdo, ombor, qarz va buyurtmalar bo‘yicha savol bering. Masalan: “Bugun qanday?”</p></div> : null}
      {messages.map((message, index) => <div key={`${message.created_at}-${index}`} className={`ai1656__row ai1656__row--${message.role}`}><div>{message.text}</div></div>)}
      {sending ? <div className="ai1656__row ai1656__row--assistant"><div className="ai1656__muted">yozmoqda...</div></div> : null}
    </div>
    <div className="ai1656__chips">{CHIPS.map((chip) => <button type="button" key={chip} disabled={sending} onClick={() => void send(chip)}>{chip}</button>)}</div>
    {error ? <p className="ai1656__error">Xatolik: {error}</p> : null}
    <form className="ai1656__composer" onSubmit={(event) => { event.preventDefault(); void send(); }}><input aria-label="Savol yozing" value={input} onChange={(event) => setInput(event.target.value)} maxLength={1000} placeholder="Savol yozing..." autoComplete="off"/><button type="submit" disabled={sending || !input.trim()} aria-label="Yuborish">➤</button></form>
    <p className="ai1656__note">AI ma’lumotlarni o‘qiydi va tushuntiradi. O‘zi o‘zgartirish kiritmaydi.</p>
  </section>;
}
