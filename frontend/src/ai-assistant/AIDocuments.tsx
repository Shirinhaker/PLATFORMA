import { useRef, useState } from "react";
import type {
  AIAttachment,
  AIDocumentDraft,
  AIDocumentDraftRequest,
  AIDocumentQuestion,
  BusinessDocumentWrite,
} from "../api/types";

export type AIDocumentsApi = {
  askAIDocument?(body: AIDocumentQuestion): Promise<{ answer: string }>;
  generateAIDocumentDraft?(body: AIDocumentDraftRequest): Promise<AIDocumentDraft>;
  createDocument?(body: BusinessDocumentWrite): Promise<{ ok: true; id: number }>;
};
type Turn = AIDocumentQuestion["history"][number];
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "So'rov bajarilmadi. Qayta urining.";

export function AIDocuments({ api }: { api: AIDocumentsApi }) {
  const [file, setFile] = useState<AIAttachment | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState<AIDocumentDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const lock = useRef(false);

  async function chooseFile(selected?: File) {
    if (!selected || lock.current) return;
    setError("");
    setFile(null);
    setTurns([]);
    if (
      !/\.(pdf|docx|txt|png|jpe?g)$/i.test(selected.name) ||
      !selected.size ||
      selected.size > 2 * 1024 * 1024 ||
      selected.name.length > 200
    ) {
      setError("PDF, DOCX, TXT, JPG yoki PNG tanlang. Fayl 2 MB gacha bo'lishi kerak.");
      return;
    }
    lock.current = true;
    setBusy(true);
    try {
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
        reader.onerror = () => reject(new Error("Fayl o'qilmadi. Qayta tanlang."));
        reader.readAsDataURL(selected);
      });
      setFile({ name: selected.name, data });
    } catch (error) {
      setError(errorText(error));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function ask() {
    if (!file || !question.trim() || !api.askAIDocument || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    const message = question.trim();
    try {
      const result = await api.askAIDocument({
        attachment: file,
        message,
        history: turns
          .slice(-6)
          .map((turn) => ({ ...turn, text: turn.text.slice(0, 8000) })),
      });
      setTurns((current) => [
        ...current,
        { role: "user", text: message },
        { role: "assistant", text: result.answer },
      ]);
      setQuestion("");
    } catch (error) {
      setError(errorText(error));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function generate() {
    if (!prompt.trim() || !api.generateAIDocumentDraft || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api.generateAIDocumentDraft({ prompt: prompt.trim() });
      setDraft(result);
      setSaved(false);
    } catch (error) {
      setError(errorText(error));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function save() {
    if (!draft?.body.trim() || !api.createDocument || saved || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await api.createDocument({
        direction:
          draft.direction === "kiruvchi" || draft.direction === "chiquvchi"
            ? draft.direction
            : "ichki",
        doc_type: draft.doc_type,
        title: draft.title,
        number: draft.number,
        doc_date: draft.doc_date,
        contractor_id: null,
        body: draft.body,
      });
      setSaved(true);
    } catch (error) {
      setError(errorText(error));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="ai1656__documents">
      <h2>Hujjat bilan ishlash</h2>
      <p>
        PDF, Word (.docx), TXT yoki hujjat rasmi — 2 MB gacha. Savol yuborilganda fayl
        tahlil uchun OpenAI xizmatiga yuboriladi.
      </p>
      <p>
        Fayl va uning suhbati faqat shu oyna ochiq turganda saqlanadi. Word faylidan
        asosiy matn o'qiladi; rasm va sahifa ko'rinishi uchun PDF yuboring.
      </p>
      <label>
        Hujjat tanlash
        <input
          aria-label="Hujjat tanlash"
          type="file"
          accept=".pdf,.docx,.txt,.jpg,.jpeg,.png"
          disabled={busy || !api.askAIDocument}
          onChange={(event) => {
            void chooseFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </label>
      {file && (
        <div className="ai1656__attachment">
          <span>{file.name}</span>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setFile(null);
              setTurns([]);
              setError("");
            }}
          >
            Faylni olib tashlash
          </button>
        </div>
      )}
      <div aria-live="polite">
        {turns.map((turn, i) => (
          <div key={i} className={`ai1656__row ai1656__row--${turn.role}`}>
            <div>{turn.text}</div>
          </div>
        ))}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask();
        }}
      >
        <label>
          Hujjat bo'yicha savol
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={1000}
            disabled={busy}
            placeholder="Muhim shartlarini tushuntir. To'lov muddati qayerda yozilgan?"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !file || !question.trim() || !api.askAIDocument}
        >
          Hujjatdan javob olish
        </button>
      </form>
      <h2>Yangi hujjat qoralamasi</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void generate();
        }}
      >
        <label>
          Hujjat topshirig'i
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={4000}
            disabled={busy}
            placeholder="Mahsulot yetkazib berish bo'yicha tijorat taklifi tayyorla..."
          />
        </label>
        <button
          type="submit"
          disabled={busy || !prompt.trim() || !api.generateAIDocumentDraft}
        >
          {draft ? "Yangi qoralama yaratish" : "Qoralama yaratish"}
        </button>
        {draft && (
          <p>Yangi qoralama yaratish pastdagi tahrirlangan matnni almashtiradi.</p>
        )}
      </form>
      {draft && (
        <div>
          <p>
            {draft.source === "local"
              ? "AI javobi olinmadi. Oddiy shablon tayyorlandi."
              : "AI qoralamasi tayyor."}{" "}
            Saqlashdan oldin matn va rekvizitlarni tekshiring.
          </p>
          <label>
            Hujjat sarlavhasi
            <input
              value={draft.title}
              maxLength={200}
              disabled={busy || saved}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
          </label>
          <label>
            Qoralama matni
            <textarea
              className="ai1656__draft"
              value={draft.body}
              disabled={busy || saved}
              onChange={(event) => setDraft({ ...draft, body: event.target.value })}
            />
          </label>
          <button
            type="button"
            disabled={busy || saved || !draft.body.trim() || !api.createDocument}
            onClick={() => void save()}
          >
            Tekshirdim — Hujjatlarga saqlash
          </button>
          {saved && (
            <p role="status">
              Hujjat saqlandi. Uni kabinetdagi Hujjatlar bo'limidan ochishingiz mumkin.
            </p>
          )}
        </div>
      )}
      {busy && <p role="status">Tayyorlanmoqda...</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
