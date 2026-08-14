import { useEffect, useRef, useState } from "react";
import type { AIChatMessage } from "../api/types";
import "./AIAssistant.css";

export type AIAssistantApi = {
  getAIChatHistory(limit?: number): Promise<{ history: AIChatMessage[] }>;
  sendAIChatMessage(message: string, allowExternalProcessing?: boolean): Promise<{ answer: string }>;
};

const CHIPS = ["Bugungi xulosa", "Ombor holati", "Qarzlar qancha", "Eng ko'p sotilgan", "Buyurtmalar"];

export function AIAssistant({ api, onBack }: { api: AIAssistantApi; onBack: () => void }) {
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [externalProcessing, setExternalProcessing] = useState(false);
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
    setInput(""); setSending(true);
    const user: AIChatMessage = { role: "user", text: message, created_at: new Date().toISOString() };
    setMessages((current) => [...current, user]);
    try {
      const result = await api.sendAIChatMessage(message, externalProcessing);
      setMessages((current) => [...current, { role: "assistant", text: result.answer || "(javob yo'q)", created_at: new Date().toISOString() }]);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "so'rov bajarilmadi";
      setMessages((current) => [...current, {
        role: "assistant",
        text: `Xatolik: ${message}`,
        created_at: new Date().toISOString(),
      }]);
    } finally { setSending(false); }
  }

  return <section className="ai1656">
    <header><button type="button" onClick={onBack}>← Orqaga</button><h1>AI yordamchi</h1></header>
    <div className="ai1656__list" ref={listRef} aria-live="polite">
      {loading ? <p className="ai1656__muted idesc">Yuklanmoqda...</p> : null}
      {!loading && !messages.length ? <div className="ai1656__empty"><span>🤖</span><strong>AI yordamchi</strong><p className="idesc">Savdo, ombor, qarz va buyurtmalar bo'yicha savol bering. Masalan: "Bugun qanday?"</p></div> : null}
      {messages.map((message, index) => <div key={`${message.created_at}-${index}`} className={`ai1656__row ai1656__row--${message.role}`}><div>{message.text}</div></div>)}
      {sending ? <div className="ai1656__row ai1656__row--assistant"><div className="ai1656__muted">yozmoqda...</div></div> : null}
    </div>
    <div className="ai1656__chips">{CHIPS.map((chip) => <button type="button" className="seg-b" key={chip} disabled={sending} onClick={() => void send(chip)}>{chip}</button>)}</div>
    <label className="ai1656__note idesc"><input type="checkbox" checked={externalProcessing} onChange={(event) => setExternalProcessing(event.currentTarget.checked)} /> Biznes kontekstini tashqi AI xizmatiga yuborishga roziman.</label>
    <form className="ai1656__composer chat-compose" onSubmit={(event) => { event.preventDefault(); void send(); }}><div className="chat-bar"><input className="chat-input" aria-label="Savol yozing" value={input} onChange={(event) => setInput(event.target.value)} maxLength={1000} placeholder="Savol yozing..." autoComplete="off"/><button className="chat-send" type="submit" disabled={sending || !input.trim()} aria-label="Yuborish"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button></div></form>
    <p className="ai1656__note idesc">AI ma'lumotlarni o'qiydi va tushuntiradi. O'zi o'zgartirish kiritmaydi.</p>
  </section>;
}
