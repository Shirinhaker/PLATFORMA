import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  DebtTransactionCreate,
  Debtor,
  DebtorDetail,
} from "../api/types";
import { money } from "./business-profile-config";
import "./DebtLedgerV1656.css";


export type DebtLedgerApi = Pick<
  ApiClient,
  "getDebtors" | "createDebtor" | "getDebtor" | "addDebtTransaction"
>;

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2)
    .map((part) => part.charAt(0)).join("").toLocaleUpperCase("uz");
}

export function DebtLedgerV1656({
  api,
  onBack,
}: {
  api: DebtLedgerApi;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<Debtor[]>([]);
  const [detail, setDetail] = useState<DebtorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<"debtor" | "debt" | "payment" | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api.getDebtors());
    } catch (reason) {
      setError(message(reason));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getDebtors()
      .then((value) => { if (active) setRows(value); })
      .catch((reason) => { if (active) setError(message(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api]);

  const summary = useMemo(() => ({
    total: rows.reduce((sum, row) => sum + Math.max(0, row.balance), 0),
    withDebt: rows.filter((row) => row.balance > 0).length,
  }), [rows]);

  async function openDebtor(debtorId: number) {
    setBusy(true);
    setError("");
    try {
      setDetail(await api.getDebtor(debtorId));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  function openForm(value: "debtor" | "debt" | "payment") {
    setName("");
    setPhone("");
    setAmount("");
    setNote("");
    setError("");
    setForm(value);
  }

  async function saveDebtor() {
    if (!name.trim()) {
      setError("Ism kiritilishi shart.");
      return;
    }
    const initialDebt = Number(amount.replace(/\s/g, "")) || 0;
    setBusy(true);
    setError("");
    try {
      await api.createDebtor({
        name: name.trim(),
        phone: phone.trim(),
        note: "",
        due: "",
        initial_debt: initialDebt,
      });
      setForm(null);
      await load();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveTransaction() {
    if (!detail || (form !== "debt" && form !== "payment")) return;
    const value = Number(amount.replace(/\s/g, "")) || 0;
    if (value <= 0) {
      setError("Summa noto‘g‘ri.");
      return;
    }
    const body: DebtTransactionCreate = {
      type: form,
      amount: value,
      note: note.trim(),
    };
    setBusy(true);
    setError("");
    try {
      await api.addDebtTransaction(detail.id, body);
      setForm(null);
      await openDebtor(detail.id);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  if (detail) {
    return (
      <main className="debt-v1656">
        <header className="debt-v1656__heading">
          <button type="button" onClick={() => { setDetail(null); void load(); }}>← Qarz daftari</button>
          <div><h1>{detail.name}</h1><p>{detail.phone}</p></div>
        </header>
        {error ? <p className="debt-v1656__error" role="alert">{error}</p> : null}
        <section className="debt-v1656__summary">
          <small>Joriy qarz</small>
          <strong>{money(detail.balance)}</strong>
          <p>{detail.name}{detail.phone ? ` · ${detail.phone}` : ""}</p>
          <div>
            <button type="button" disabled={busy} onClick={() => openForm("payment")}>− To‘lov</button>
            <button type="button" disabled={busy} onClick={() => openForm("debt")}>+ Qarz</button>
          </div>
        </section>
        <div className="debt-v1656__section-title">
          <h2>Amaliyotlar tarixi</h2><span>{detail.tx.length} ta</span>
        </div>
        <section className="debt-v1656__transactions">
          {detail.tx.slice().reverse().map((row) => (
            <article key={row.id}>
              <div><b>{row.type === "debt" ? "Qarz" : "To‘lov"}</b>
                <small>{row.date}{row.note ? ` · ${row.note}` : ""}</small></div>
              <strong className={row.type === "debt" ? "debit" : "credit"}>
                {row.type === "debt" ? "+" : "−"}{money(row.amount).replace(" so'm", "")}
              </strong>
            </article>
          ))}
          {!detail.tx.length ? <p>Hozircha amaliyot yo‘q.</p> : null}
        </section>
        {form === "debt" || form === "payment" ? (
          <TransactionModal
            type={form}
            amount={amount}
            note={note}
            busy={busy}
            error={error}
            setAmount={setAmount}
            setNote={setNote}
            onCancel={() => setForm(null)}
            onSave={saveTransaction}
          />
        ) : null}
      </main>
    );
  }

  return (
    <main className="debt-v1656">
      <header className="debt-v1656__heading">
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div><h1>Qarz daftari</h1><p>Mijozlar qarzlarini yuritish</p></div>
      </header>
      {error ? <p className="debt-v1656__error" role="alert">{error}</p> : null}
      <section className="debt-v1656__summary">
        <small>Umumiy qarz</small>
        <strong>{money(summary.total)}</strong>
        <p><b>{rows.length}</b> ta qarzdor · <b>{summary.withDebt}</b> tasida qarz bor</p>
      </section>
      {loading ? <p className="debt-v1656__empty">Yuklanmoqda…</p> : null}
      {!loading && !rows.length ? (
        <div className="debt-v1656__empty"><h3>Hozircha qarzdor yo‘q</h3><p>Pastdagi tugma orqali qo‘shing.</p></div>
      ) : null}
      <section className="debt-v1656__list">
        {rows.map((debtor) => (
          <button type="button" key={debtor.id} disabled={busy} onClick={() => openDebtor(debtor.id)}>
            <span className="debt-v1656__avatar">{initials(debtor.name) || "?"}</span>
            <span><b>{debtor.name}</b><small>{debtor.phone}</small></span>
            {debtor.balance > 0
              ? <strong>{money(debtor.balance)}</strong>
              : <em>Qarzi yo‘q</em>}
          </button>
        ))}
      </section>
      <button type="button" className="debt-v1656__add" disabled={busy} onClick={() => openForm("debtor")}>
        + Yangi qarzdor
      </button>
      {form === "debtor" ? (
        <div className="debt-v1656__modal-back" role="presentation">
          <section className="debt-v1656__modal" role="dialog" aria-modal="true" aria-label="Yangi qarzdor">
            <h2>Yangi qarzdor</h2>
            {error ? <p className="debt-v1656__error" role="alert">{error}</p> : null}
            <div className="debt-v1656__modal-fields">
              <label>Qarzdor ismi<input value={name} maxLength={160} onChange={(event) => setName(event.target.value)} /></label>
              <label>Telefon (ixtiyoriy)<input value={phone} maxLength={40} onChange={(event) => setPhone(event.target.value)} /></label>
              <label>Boshlang‘ich qarz (faqat raqam, ixtiyoriy)<input inputMode="numeric" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
            </div>
            <div className="debt-v1656__modal-actions">
              <button type="button" disabled={busy} onClick={() => setForm(null)}>Bekor qilish</button>
              <button type="button" disabled={busy} onClick={saveDebtor}>Qo‘shish</button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function TransactionModal({
  type,
  amount,
  note,
  busy,
  error,
  setAmount,
  setNote,
  onCancel,
  onSave,
}: {
  type: "debt" | "payment";
  amount: string;
  note: string;
  busy: boolean;
  error: string;
  setAmount: (value: string) => void;
  setNote: (value: string) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  const label = type === "debt" ? "Qarz summasi" : "To‘lov summasi";
  return (
    <div className="debt-v1656__modal-back" role="presentation">
      <section className="debt-v1656__modal" role="dialog" aria-modal="true" aria-label={label}>
        <h2>{label}</h2>
        {error ? <p className="debt-v1656__error" role="alert">{error}</p> : null}
        <div className="debt-v1656__modal-fields">
          <label>{label} (faqat raqam)<input autoFocus inputMode="numeric" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
          <label>Izoh (ixtiyoriy)<input value={note} maxLength={200} onChange={(event) => setNote(event.target.value)} /></label>
        </div>
        <div className="debt-v1656__modal-actions">
          <button type="button" disabled={busy} onClick={onCancel}>Bekor qilish</button>
          <button type="button" disabled={busy} onClick={onSave}>Saqlash</button>
        </div>
      </section>
    </div>
  );
}
