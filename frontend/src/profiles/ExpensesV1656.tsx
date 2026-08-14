import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ExpenseCategories, ExpenseDay } from "../api/types";
import "./ExpensesV1656.css";


export type ExpensesApi = Pick<
  ApiClient,
  | "getExpenses"
  | "getExpenseCategories"
  | "createExpenseCategory"
  | "createExpense"
  | "deleteExpense"
>;

const EMPTY_DAY: ExpenseDay = {
  day: "",
  expenses: [],
  total: 0,
  by_category: {},
};

function today() {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

function shiftDay(value: string, delta: number) {
  const [year = 1970, month = 1, day = 1] = value.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + delta));
  return shifted.toISOString().slice(0, 10);
}

function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function timeLabel(value: string) {
  return new Intl.DateTimeFormat("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Tashkent",
  }).format(new Date(value));
}

export function ExpensesV1656({
  api,
  onBack,
}: {
  api: ExpensesApi;
  onBack: () => void;
}) {
  const [day, setDay] = useState("");
  const [data, setData] = useState<ExpenseDay>(EMPTY_DAY);
  const [categories, setCategories] = useState<ExpenseCategories>({
    categories: [],
    defaults: [],
  });
  const [formOpen, setFormOpen] = useState(false);
  const [category, setCategory] = useState("Boshqa");
  const [newCategory, setNewCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.getExpenses(day)
      .then((value) => { if (active) setData(value); })
      .catch((reason) => { if (active) setError(message(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, day]);

  async function reload() {
    setData(await api.getExpenses(day));
  }

  function moveDay(delta: number) {
    const next = shiftDay(day || today(), delta);
    setDay(next === today() ? "" : next);
  }

  async function openForm() {
    setBusy(true);
    setError("");
    try {
      const value = await api.getExpenseCategories();
      setCategories(value);
      setCategory(value.categories[0] ?? "Boshqa");
      setNewCategory("");
      setAmount("");
      setNote("");
      setFormOpen(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    const selected = category === "__new__" ? newCategory.trim() : category;
    if (!selected) {
      setError("Kategoriya nomini yozing.");
      return;
    }
    const numericAmount = Number(amount.replace(/[^0-9]/g, "")) || 0;
    if (numericAmount <= 0) {
      setError("Summa kiritilmadi.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (category === "__new__") {
        await api.createExpenseCategory({ name: selected });
      }
      await api.createExpense({
        category: selected,
        amount: numericAmount,
        note: note.trim(),
      });
      setFormOpen(false);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove(expenseId: number) {
    if (!window.confirm("Bu xarajat o‘chirilsinmi?")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteExpense(expenseId);
      await reload();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="expenses-v1656">
      <header className="expenses-v1656__heading">
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div><h1>Xarajatlar</h1><p>Kunlik xarajatlar hisobi</p></div>
      </header>
      {error ? <p className="expenses-v1656__error" role="alert">{error}</p> : null}
      <section className="expenses-v1656__summary">
        <small>{day ? `${data.day} xarajati` : "Bugungi xarajat"}</small>
        <strong>{money(data.total)} so'm</strong>
        <p>{Object.entries(data.by_category).map(([name, value]) => (
          <span key={name}>{name}: <b>{money(value)}</b></span>
        ))}</p>
      </section>
      <button
        type="button"
        className="expenses-v1656__add"
        disabled={busy}
        onClick={() => void openForm()}
      >+ Xarajat yozish</button>
      <nav className="expenses-v1656__days" aria-label="Xarajat sanasi">
        <button type="button" onClick={() => moveDay(-1)}>← Oldingi</button>
        <button type="button" onClick={() => setDay("")}>Bugun</button>
        <button type="button" onClick={() => moveDay(1)}>Keyingi →</button>
      </nav>
      {loading ? <p className="expenses-v1656__empty">Yuklanmoqda…</p> : null}
      {!loading && !data.expenses.length ? (
        <p className="expenses-v1656__empty">Bu kunda xarajat yo‘q.</p>
      ) : null}
      <section className="expenses-v1656__list">
        {data.expenses.map((expense) => {
          const fromStock = expense.source === "stock";
          return (
            <article key={expense.id}>
              <div className="expenses-v1656__row">
                <b>{expense.category}{expense.note ? ` — ${expense.note}` : ""}</b>
                <strong>−{money(expense.amount)}</strong>
              </div>
              <div className="expenses-v1656__meta">
                <span>{timeLabel(expense.created_at)}{fromStock
                  ? " · Ombor kirimi"
                  : expense.who ? ` · ${expense.who}` : ""}</span>
                {fromStock ? <em>avtomatik</em> : (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void remove(expense.id)}
                  >O‘chirish</button>
                )}
              </div>
            </article>
          );
        })}
      </section>
      {formOpen ? (
        <div className="expenses-v1656__modal-back" role="presentation">
          <section
            className="expenses-v1656__modal"
            role="dialog"
            aria-modal="true"
            aria-label="Xarajat yozish"
          >
            <h2>Xarajat yozish</h2>
            {error ? <p className="expenses-v1656__error" role="alert">{error}</p> : null}
            <label>Kategoriya
              <select value={category} onChange={(event) => setCategory(event.target.value)}>
                {categories.categories.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
                <option value="__new__">+ Yangi kategoriya...</option>
              </select>
            </label>
            {category === "__new__" ? (
              <label>Yangi kategoriya nomi
                <input value={newCategory} maxLength={40} onChange={(event) => setNewCategory(event.target.value)} />
              </label>
            ) : null}
            <label>Summa (so‘m)
              <input inputMode="numeric" value={amount} onChange={(event) => setAmount(event.target.value)} />
            </label>
            <label>Izoh (ixtiyoriy)
              <input value={note} maxLength={200} onChange={(event) => setNote(event.target.value)} />
            </label>
            <div className="expenses-v1656__modal-actions">
              <button type="button" disabled={busy} onClick={() => setFormOpen(false)}>Bekor qilish</button>
              <button type="button" disabled={busy} onClick={() => void save()}>Saqlash</button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
