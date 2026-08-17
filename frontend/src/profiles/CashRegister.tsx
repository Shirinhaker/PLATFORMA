import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  CashCatalogItem,
  CashPayType,
  CashReceipt,
  CashReceiptCreate,
  CashRegister,
  Debtor,
} from "../api/types";
import { money } from "./business-profile-config";
import {
  CashRegisterCreateView,
  ReceiptCard,
  type DraftLine,
} from "./CashRegisterViews";
import { DebtorPicker } from "./DebtorPicker";
import "./CashRegister.css";

export type CashRegisterApi = Pick<
  ApiClient,
  | "getCashRegister"
  | "getCashCatalog"
  | "createCashReceipt"
  | "deleteCashReceipt"
  | "updateCashOrderPayment"
  | "getDebtors"
  | "createDebtor"
>;

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

export function CashRegisterScreen({
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
  const [debtors, setDebtors] = useState<Debtor[]>([]);
  const [debtorId, setDebtorId] = useState(0);
  const [debtorPicker, setDebtorPicker] = useState<"sale" | "payment" | null>(null);
  const [paymentReceipt, setPaymentReceipt] = useState<CashReceipt | null>(null);
  const [note, setNote] = useState("");
  const [saleDate, setSaleDate] = useState(today());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    async (selectedDay: string) => {
      setLoading(true);
      setError("");
      try {
        setRegister(await api.getCashRegister(selectedDay));
      } catch (reason) {
        setError(errorMessage(reason));
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .getCashRegister(day)
      .then((value) => {
        if (active) setRegister(value);
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
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
      const [items, debtorRows] = await Promise.all([
        api.getCashCatalog(),
        api.getDebtors(),
      ]);
      setCatalog(items);
      setDebtors(debtorRows);
      setDebtorId(debtorRows[0]?.id ?? 0);
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
        return current.map((line) =>
          line.key === found.key ? { ...line, qty: line.qty + 1 } : line,
        );
      }
      return [
        ...current,
        {
          key: `catalog-${item.id}`,
          catalog_item_id: item.id,
          name: item.name,
          qty: 1,
          price: item.price,
        },
      ];
    });
  }

  function addCustomItem() {
    setDraft((current) => [
      ...current,
      {
        key: `custom-${Date.now()}-${current.length}`,
        catalog_item_id: null,
        name: "",
        qty: 1,
        price: 0,
      },
    ]);
  }

  function updateLine(key: string, patch: Partial<DraftLine>) {
    setDraft((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  async function save() {
    if (!draft.length) {
      setError("Chek bo‘sh — mahsulot tanlang.");
      return;
    }
    const invalid = draft.find(
      (line) => !line.name.trim() || line.qty <= 0 || line.price <= 0,
    );
    if (invalid) {
      setError(
        !invalid.name.trim()
          ? "Mahsulot nomi kiritilmadi."
          : `Narx yoki miqdor noto‘g‘ri: ${invalid.name}`,
      );
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
      debtor_id: payType === "qarz" ? debtorId : null,
      note: note.trim(),
      sale_date: saleDate || null,
    };
    if (payType === "qarz" && debtorId <= 0) {
      setError("Qarzdorni tanlang.");
      return;
    }
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
    if (
      !window.confirm(
        `${label} butun o‘chirilsinmi? Ombor va qarz daftari qaytariladi.`,
      )
    )
      return;
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
    if (value === "qarz") {
      setPaymentReceipt(receipt);
      setDebtorPicker("payment");
      return;
    }
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

  async function selectDebtor(selectedDebtorId: number) {
    if (debtorPicker === "sale") {
      const rows = await api.getDebtors();
      setDebtors(rows);
      setDebtorId(selectedDebtorId);
      setDebtorPicker(null);
      return;
    }
    if (debtorPicker === "payment" && paymentReceipt) {
      setBusy(true);
      setError("");
      try {
        await api.updateCashOrderPayment(paymentReceipt.id, "qarz", selectedDebtorId);
        setDebtorPicker(null);
        setPaymentReceipt(null);
        await load(day);
      } catch (reason) {
        setError(errorMessage(reason));
      } finally {
        setBusy(false);
      }
    }
  }

  if (screen === "create") {
    return (
      <CashRegisterCreateView
        api={api}
        draft={draft}
        setDraft={setDraft}
        search={search}
        setSearch={setSearch}
        visibleCatalog={visibleCatalog}
        addCatalogItem={addCatalogItem}
        addCustomItem={addCustomItem}
        updateLine={updateLine}
        payType={payType}
        setPayType={setPayType}
        debtorId={debtorId}
        setDebtorId={setDebtorId}
        debtors={debtors}
        setDebtorPicker={setDebtorPicker}
        saleDate={saleDate}
        setSaleDate={setSaleDate}
        note={note}
        setNote={setNote}
        maxDate={today()}
        busy={busy}
        save={save}
        error={error}
        debtorPicker={debtorPicker}
        setPaymentReceipt={setPaymentReceipt}
        selectDebtor={selectDebtor}
        onBack={() => setScreen("list")}
      />
    );
  }

  const selectedDay = register.day || today();
  return (
    <main className="cash-v1656">
      <header className="cash-v1656__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>Kassa</h1>
          <p>Savdo daftari va kunlik tushum</p>
        </div>
        <button
          type="button"
          className="cash-v1656__add"
          disabled={busy}
          onClick={openCreate}
        >
          + Savdo yozish
        </button>
      </header>
      {error ? (
        <p className="cash-v1656__error" role="alert">
          {error}
        </p>
      ) : null}
      <section className="cash-v1656__summary">
        <div className="cash-v1656__days">
          <button type="button" onClick={() => setDay(shiftDay(selectedDay, -1))}>
            ‹
          </button>
          <b>{day ? `${selectedDay} tushumi` : "Bugungi tushum"}</b>
          <button type="button" onClick={() => setDay(shiftDay(selectedDay, 1))}>
            ›
          </button>
          <button type="button" onClick={() => setDay("")}>
            Bugun
          </button>
        </div>
        <strong>{money(register.totals.cash_in)}</strong>
        <p>
          Haqiqiy tushum · Naqd: <b>{money(register.totals.naqd)}</b> · Karta:{" "}
          <b>{money(register.totals.karta)}</b>
          {` · Qarz to‘lovi: ${money(register.totals.qarzpay)}`}
          <br />
          Jami savdo: <b>{money(register.totals.all)}</b> · Qarzga:{" "}
          <b>{money(register.totals.qarz)}</b>
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
      {debtorPicker ? (
        <DebtorPicker
          api={api}
          title="Buyurtmani qarzga yozish"
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
