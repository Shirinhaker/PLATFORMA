import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../api/client";
import type { CashCatalogItem, CashPayType, CashReceipt, Debtor } from "../api/types";
import { money } from "./business-profile-config";
import { DebtorPicker } from "./DebtorPicker";

export type DraftLine = {
  key: string;
  catalog_item_id: number | null;
  name: string;
  qty: number;
  price: number;
};

function quantity(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ", { maximumFractionDigits: 3 });
}

function receiptTitle(receipt: CashReceipt) {
  if (receipt.source === "order") return `Buyurtma #${receipt.order_id ?? receipt.id}`;
  if (receipt.source === "dining")
    return `🍽️ Ichki buyurtma #${receipt.order_id ?? receipt.id}`;
  if (receipt.source === "debt_payment")
    return `💵 ${receipt.lines[0]?.item_name ?? "Qarz to‘lovi"}`;
  if (receipt.receipt_no) return `🧾 Chek #${receipt.receipt_no}`;
  return "Savdo";
}

export function ReceiptCard({
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
            >
              Naqd
            </button>
            <button
              type="button"
              disabled={busy || receipt.pay_type === "karta"}
              onClick={() => onPayment(receipt, "karta")}
            >
              Karta
            </button>
            <button
              type="button"
              disabled={busy || receipt.pay_type === "qarz"}
              onClick={() => onPayment(receipt, "qarz")}
            >
              Qarz
            </button>
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

type DebtorApi = Pick<ApiClient, "getDebtors" | "createDebtor">;

export function CashRegisterCreateView({
  api,
  draft,
  setDraft,
  search,
  setSearch,
  visibleCatalog,
  addCatalogItem,
  addCustomItem,
  updateLine,
  payType,
  setPayType,
  debtorId,
  setDebtorId,
  debtors,
  setDebtorPicker,
  saleDate,
  setSaleDate,
  note,
  setNote,
  maxDate,
  busy,
  save,
  error,
  debtorPicker,
  setPaymentReceipt,
  selectDebtor,
  onBack,
}: {
  api: DebtorApi;
  draft: DraftLine[];
  setDraft: Dispatch<SetStateAction<DraftLine[]>>;
  search: string;
  setSearch: Dispatch<SetStateAction<string>>;
  visibleCatalog: CashCatalogItem[];
  addCatalogItem(item: CashCatalogItem): void;
  addCustomItem(): void;
  updateLine(key: string, patch: Partial<DraftLine>): void;
  payType: CashPayType;
  setPayType: Dispatch<SetStateAction<CashPayType>>;
  debtorId: number;
  setDebtorId: Dispatch<SetStateAction<number>>;
  debtors: Debtor[];
  setDebtorPicker: Dispatch<SetStateAction<"sale" | "payment" | null>>;
  saleDate: string;
  setSaleDate: Dispatch<SetStateAction<string>>;
  note: string;
  setNote: Dispatch<SetStateAction<string>>;
  maxDate: string;
  busy: boolean;
  save(): Promise<void>;
  error: string;
  debtorPicker: "sale" | "payment" | null;
  setPaymentReceipt: Dispatch<SetStateAction<CashReceipt | null>>;
  selectDebtor(selectedDebtorId: number): Promise<void>;
  onBack(): void;
}) {
  const grand = draft.reduce((total, line) => total + line.qty * line.price, 0);
  return (
    <main className="cash-v1656">
      <header className="cash-v1656__heading">
        <button type="button" onClick={onBack}>
          ← Kassa
        </button>
        <div>
          <h1>Savdo yozish</h1>
          <p>Bitta chekda bir nechta mahsulot</p>
        </div>
      </header>
      {error ? (
        <p className="cash-v1656__error" role="alert">
          {error}
        </p>
      ) : null}
      <section className="cash-v1656__form-card">
        <label>
          Mahsulot qidirish
          <input value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>
        <div className="cash-v1656__catalog">
          {visibleCatalog.map((item) => (
            <button type="button" key={item.id} onClick={() => addCatalogItem(item)}>
              <span>
                <b>{item.name}</b>
                <small>
                  {item.track_stock
                    ? `Omborda: ${quantity(item.stock_qty)} ${item.unit}`
                    : item.unit}
                </small>
              </span>
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
        {!draft.length ? (
          <p>Chek bo‘sh — mahsulot tanlang.</p>
        ) : (
          <div className="cash-v1656__draft-lines">
            {draft.map((line) => (
              <article key={line.key}>
                <input
                  aria-label="Mahsulot nomi"
                  value={line.name}
                  disabled={line.catalog_item_id !== null}
                  onChange={(event) =>
                    updateLine(line.key, { name: event.target.value })
                  }
                />
                <label>
                  Miqdor
                  <input
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={line.qty}
                    onChange={(event) =>
                      updateLine(line.key, { qty: Number(event.target.value) })
                    }
                  />
                </label>
                <label>
                  Narx
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={line.price}
                    onChange={(event) =>
                      updateLine(line.key, { price: Number(event.target.value) })
                    }
                  />
                </label>
                <b>{money(line.qty * line.price)}</b>
                <button
                  type="button"
                  aria-label={`${line.name || "Mahsulot"}ni o‘chirish`}
                  onClick={() =>
                    setDraft((current) => current.filter((row) => row.key !== line.key))
                  }
                >
                  ×
                </button>
              </article>
            ))}
          </div>
        )}
        <div className="cash-v1656__fields">
          <label>
            To‘lov turi
            <select
              value={payType}
              onChange={(event) => setPayType(event.target.value as CashPayType)}
            >
              <option value="naqd">Naqd</option>
              <option value="karta">Karta</option>
              <option value="qarz">Qarz (daftariga yoziladi)</option>
            </select>
          </label>
          {payType === "qarz" ? (
            <label>
              Qarzdor
              <div className="cash-v1656__debtor-field">
                <select
                  value={debtorId}
                  onChange={(event) => setDebtorId(Number(event.target.value))}
                >
                  <option value={0}>Qarzdorni tanlang</option>
                  {debtors.map((debtor) => (
                    <option key={debtor.id} value={debtor.id}>
                      {debtor.name} · {money(debtor.balance)}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={() => setDebtorPicker("sale")}>
                  + Yangi
                </button>
              </div>
            </label>
          ) : null}
          <label>
            Sana
            <input
              type="date"
              max={maxDate}
              value={saleDate}
              onChange={(event) => setSaleDate(event.target.value)}
            />
          </label>
          <label className="cash-v1656__wide">
            Izoh
            <textarea
              maxLength={200}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
        </div>
        <div className="cash-v1656__save">
          <strong>Jami: {money(grand)}</strong>
          <button type="button" disabled={busy} onClick={save}>
            Savdoni saqlash
          </button>
        </div>
      </section>
      {debtorPicker ? (
        <DebtorPicker
          api={api}
          title={
            debtorPicker === "payment"
              ? "Buyurtmani qarzga yozish"
              : "Qarzdorni tanlash"
          }
          onCancel={() => {
            setDebtorPicker(null);
            setPaymentReceipt(null);
          }}
          onSelect={(value) => {
            void selectDebtor(value);
          }}
        />
      ) : null}
    </main>
  );
}
