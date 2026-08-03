import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  CashCatalogItem,
  CashPayType,
  CashReceipt,
  CashReceiptCreate,
  CashRegister,
} from "../api/types";
import { money } from "./business-profile-config";
import "./CashRegisterV1656.css";


export type CashRegisterApi = Pick<
  ApiClient,
  | "getCashRegister"
  | "getCashCatalog"
  | "createCashReceipt"
  | "deleteCashReceipt"
  | "updateCashOrderPayment"
>;

type DraftLine = {
  key: string;
  catalog_item_id: number | null;
  name: string;
  qty: number;
  price: number;
};

const EMPTY_TOTALS = {
  all: 0,
  cash_in: 0,
  naqd: 0,
  karta: 0,
  qarz: 0,
  qarzpay: 0,
  order: 0,
};

function today() {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

function shiftDay(value: string, delta: number) {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) {
    return today();
  }
  const [year = 1970, month = 1, day = 1] = parts;
  const shifted = new Date(Date.UTC(year, month - 1, day + delta));
  return shifted.toISOString().slice(0, 10);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function quantity(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ", { maximumFractionDigits: 3 });
}

function receiptTitle(receipt: CashReceipt) {
  if (receipt.source === "order") return `Buyurtma #${receipt.order_id ?? receipt.id}`;
  if (receipt.source === "dining") return `🍽️ Ichki buyurtma #${receipt.order_id ?? receipt.id}`;
  if (receipt.source === "debt_payment") return `💵 ${receipt.lines[0]?.item_name ?? "Qarz to‘lovi"}`;
  if (receipt.receipt_no) return `🧾 Chek #${receipt.receipt_no}`;
  return "Savdo";
}

function ReceiptCard({
  receipt,
  busy,
  onDelete,
  onPayment,
}: {
  receipt: CashReceipt;
  busy: boolean;
  onDelete: (receipt: CashReceipt) => void;
  onPayment: (receipt: CashReceipt, payType: CashPayType) => void;
}) {
  const time = new Intl.DateTimeFormat("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Tashkent",
  }).format(new Date(receipt.created_at));
  return (
    <article className="cash-v1656__receipt">
      <header>
        <strong>{receiptTitle(receipt)}</strong>
        <b>{money(receipt.total)}</b>
      </header>
      {receipt.source !== "debt_payment" ? (
        <ul>
          {receipt.lines.map((line) => (
            <li key={line.id}>
              {line.item_name} × {quantity(line.qty)}
              {line.unit && line.unit !== "dona" ? ` ${line.unit}` : ""}
              <span>{money(line.total)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <footer>
        <span>
          {time} · <b>{receipt.pay_text}</b>
          {receipt.debtor_name ? ` · 📒 ${receipt.debtor_name}` : ""}
          {` · ${receipt.source === "order" ? "Tashqi buyurtmadan" : `Qo‘lda · ${receipt.who}`}`}
        </span>
        {receipt.can_change_payment ? (
          <span className="cash-v1656__payment-actions">
            <button
              type="button"
              disabled={busy || receipt.pay_type === "naqd"}
              onClick={() => onPayment(receipt, "naqd")}
            >Naqd</button>
            <button
              type="button"
              disabled={busy || receipt.pay_type === "karta"}
              onClick={() => onPayment(receipt, "karta")}
            >Karta</button>
          </span>
        ) : null}
        {receipt.can_delete ? (
          <button type="button" disabled={busy} onClick={() => onDelete(receipt)}>
            O‘chirish
          </button>
        ) : null}
      </footer>
    </article>
  );
}

export function CashRegisterV1656({
  api,
  onBack,
}: {
  api: CashRegisterApi;
  onBack: () => void;
}) {
  const [register, setRegister] = useState<CashRegister>({
    day: today(),
    totals: EMPTY_TOTALS,
    receipts: [],
  });
  const [day, setDay] = useState("");
  const [screen, setScreen] = useState<"list" | "create">("list");
  const [catalog, setCatalog] = useState<CashCatalogItem[]>([]);
  const [draft, setDraft] = useState<DraftLine[]>([]);
  const [search, setSearch] = useState("");
  const [payType, setPayType] = useState<CashPayType>("naqd");
  const [note, setNote] = useState("");
  const [saleDate, setSaleDate] = useState(today());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (selectedDay: string) => {
    setLoading(true);
    setError("");
    try {
      setRegister(await api.getCashRegister(selectedDay));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.getCashRegister(day)
      .then((value) => { if (active) setRegister(value); })
      .catch((reason) => { if (active) setError(errorMessage(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, day]);

  const visibleCatalog = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("uz");
    return query
      ? catalog.filter((item) => item.name.toLocaleLowerCase("uz").includes(query))
      : catalog;
  }, [catalog, search]);

  async function openCreate() {
    setBusy(true);
    setError("");
    try {
      const items = await api.getCashCatalog();
      setCatalog(items);
      setDraft([]);
      setSearch("");
      setPayType("naqd");
      setNote("");
      setSaleDate(today());
      setScreen("create");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function addCatalogItem(item: CashCatalogItem) {
    setDraft((current) => {
      const found = current.find((line) => line.catalog_item_id === item.id);
      if (found) {
        return current.map((line) => line.key === found.key
          ? { ...line, qty: line.qty + 1 }
          : line);
      }
      return [...current, {
        key: `catalog-${item.id}`,
        catalog_item_id: item.id,
        name: item.name,
        qty: 1,
        price: item.price,
      }];
    });
  }

  function addCustomItem() {
    setDraft((current) => [...current, {
      key: `custom-${Date.now()}-${current.length}`,
      catalog_item_id: null,
      name: "",
      qty: 1,
      price: 0,
    }]);
  }

  function updateLine(key: string, patch: Partial<DraftLine>) {
    setDraft((current) => current.map((line) => (
      line.key === key ? { ...line, ...patch } : line
    )));
  }

  async function save() {
    if (!draft.length) {
      setError("Chek bo‘sh — mahsulot tanlang.");
      return;
    }
    const invalid = draft.find((line) => !line.name.trim() || line.qty <= 0 || line.price <= 0);
    if (invalid) {
      setError(!invalid.name.trim()
        ? "Mahsulot nomi kiritilmadi."
        : `Narx yoki miqdor noto‘g‘ri: ${invalid.name}`);
      return;
    }
    const byId = new Map(catalog.map((item) => [item.id, item]));
    const lacking = draft.filter((line) => {
      const item = line.catalog_item_id ? byId.get(line.catalog_item_id) : undefined;
      return Boolean(item?.track_stock && line.qty > item.stock_qty);
    });
    if (lacking.length) {
      setError(`Omborda yetarli emas: ${lacking.map((line) => line.name).join(", ")}.`);
      return;
    }
    const body: CashReceiptCreate = {
      items: draft.map((line) => ({
        catalog_item_id: line.catalog_item_id,
        name: line.catalog_item_id ? "" : line.name.trim(),
        qty: line.qty,
        price: line.price,
      })),
      pay_type: payType,
      note: note.trim(),
      sale_date: saleDate || null,
    };
    setBusy(true);
    setError("");
    try {
      await api.createCashReceipt(body);
      setScreen("list");
      const targetDay = saleDate === today() ? "" : saleDate;
      if (targetDay === day) await load(targetDay);
      else setDay(targetDay);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function deleteReceipt(receipt: CashReceipt) {
    const label = receipt.receipt_no ? `Chek #${receipt.receipt_no}` : "Bu savdo";
    if (!window.confirm(`${label} butun o‘chirilsinmi? Ombor qaytariladi.`)) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteCashReceipt(receipt.id);
      await load(day);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function updatePayment(receipt: CashReceipt, value: CashPayType) {
    setBusy(true);
    setError("");
    try {
      await api.updateCashOrderPayment(receipt.id, value);
      await load(day);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (screen === "create") {
    const grand = draft.reduce((total, line) => total + line.qty * line.price, 0);
    return (
      <main className="cash-v1656">
        <header className="cash-v1656__heading">
          <button type="button" onClick={() => setScreen("list")}>← Kassa</button>
          <div><h1>Savdo yozish</h1><p>Bitta chekda bir nechta mahsulot</p></div>
        </header>
        {error ? <p className="cash-v1656__error" role="alert">{error}</p> : null}
        <section className="cash-v1656__form-card">
          <label>Mahsulot qidirish
            <input value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
          <div className="cash-v1656__catalog">
            {visibleCatalog.map((item) => (
              <button type="button" key={item.id} onClick={() => addCatalogItem(item)}>
                <span><b>{item.name}</b><small>{item.track_stock
                  ? `Omborda: ${quantity(item.stock_qty)} ${item.unit}`
                  : item.unit}</small></span>
                <strong>{money(item.price)}</strong>
                <em>+</em>
              </button>
            ))}
          </div>
          <button type="button" className="cash-v1656__custom" onClick={addCustomItem}>
            + Boshqa mahsulot
          </button>
        </section>
        <section className="cash-v1656__form-card">
          <h2>Chek ({draft.length})</h2>
          {!draft.length ? <p>Chek bo‘sh — mahsulot tanlang.</p> : (
            <div className="cash-v1656__draft-lines">
              {draft.map((line) => (
                <article key={line.key}>
                  <input
                    aria-label="Mahsulot nomi"
                    value={line.name}
                    disabled={line.catalog_item_id !== null}
                    onChange={(event) => updateLine(line.key, { name: event.target.value })}
                  />
                  <label>Miqdor<input
                    type="number" min="0.001" step="0.001" value={line.qty}
                    onChange={(event) => updateLine(line.key, { qty: Number(event.target.value) })}
                  /></label>
                  <label>Narx<input
                    type="number" min="1" step="1" value={line.price}
                    onChange={(event) => updateLine(line.key, { price: Number(event.target.value) })}
                  /></label>
                  <b>{money(line.qty * line.price)}</b>
                  <button type="button" aria-label={`${line.name || "Mahsulot"}ni o‘chirish`}
                    onClick={() => setDraft((current) => current.filter((row) => row.key !== line.key))}>×</button>
                </article>
              ))}
            </div>
          )}
          <div className="cash-v1656__fields">
            <label>To‘lov turi<select value={payType}
              onChange={(event) => setPayType(event.target.value as CashPayType)}>
              <option value="naqd">Naqd</option>
              <option value="karta">Karta</option>
              <option value="qarz" disabled>Qarz — keyingi migratsiyada</option>
            </select></label>
            <label>Sana<input type="date" max={today()} value={saleDate}
              onChange={(event) => setSaleDate(event.target.value)} /></label>
            <label className="cash-v1656__wide">Izoh<textarea maxLength={200} value={note}
              onChange={(event) => setNote(event.target.value)} /></label>
          </div>
          <div className="cash-v1656__save">
            <strong>Jami: {money(grand)}</strong>
            <button type="button" disabled={busy} onClick={save}>Savdoni saqlash</button>
          </div>
        </section>
      </main>
    );
  }

  const selectedDay = register.day || today();
  return (
    <main className="cash-v1656">
      <header className="cash-v1656__heading">
        <button type="button" onClick={onBack}>← Kabinetga qaytish</button>
        <div><h1>Kassa</h1><p>Savdo daftari va kunlik tushum</p></div>
        <button type="button" className="cash-v1656__add" disabled={busy} onClick={openCreate}>
          + Savdo yozish
        </button>
      </header>
      {error ? <p className="cash-v1656__error" role="alert">{error}</p> : null}
      <section className="cash-v1656__summary">
        <div className="cash-v1656__days">
          <button type="button" onClick={() => setDay(shiftDay(selectedDay, -1))}>‹</button>
          <b>{day ? `${selectedDay} tushumi` : "Bugungi tushum"}</b>
          <button type="button" onClick={() => setDay(shiftDay(selectedDay, 1))}>›</button>
          <button type="button" onClick={() => setDay("")}>Bugun</button>
        </div>
        <strong>{money(register.totals.cash_in)}</strong>
        <p>
          Haqiqiy tushum · Naqd: <b>{money(register.totals.naqd)}</b> · Karta: <b>{money(register.totals.karta)}</b>
          {` · Qarz to‘lovi: ${money(register.totals.qarzpay)}`}
          <br />Jami savdo: <b>{money(register.totals.all)}</b> · Qarzga: <b>{money(register.totals.qarz)}</b>
          {` · To‘lov turi belgilanmagan: ${money(register.totals.order)}`}
        </p>
      </section>
      {loading ? <div className="cash-v1656__empty">Yuklanmoqda…</div> : null}
      {!loading && !register.receipts.length ? (
        <div className="cash-v1656__empty">Bu kunda savdo yo‘q.</div>
      ) : null}
      {!loading ? (
        <section className="cash-v1656__receipts">
          {register.receipts.map((receipt) => (
            <ReceiptCard
              key={receipt.id}
              receipt={receipt}
              busy={busy}
              onDelete={deleteReceipt}
              onPayment={updatePayment}
            />
          ))}
        </section>
      ) : null}
    </main>
  );
}
