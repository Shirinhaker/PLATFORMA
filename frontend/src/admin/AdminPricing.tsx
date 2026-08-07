import { useCallback, useEffect, useState } from "react";

import type {
  AdminApiClient,
  AdminMethodRow,
  AdminPriceRow,
} from "./admin-client";


export type AdminPricingApi = Pick<
  AdminApiClient,
  "prices" | "updatePrice" | "methods" | "createMethod" | "updateMethod"
>;

type Props = { api: AdminPricingApi };

type MethodDraft = {
  id: number | null;
  method_type: string;
  name: string;
  recipient_name: string;
  instructions: string;
  details: Record<string, unknown>;
  card_number: string;
  sort_order: number;
  active: boolean;
};

const EMPTY_METHOD: MethodDraft = {
  id: null,
  method_type: "manual_card",
  name: "",
  recipient_name: "",
  instructions: "",
  details: {},
  card_number: "",
  sort_order: 0,
  active: true,
};

const SERVICE_TEXT: Record<string, string> = {
  subscription: "Obuna",
  advertisement: "Reklama",
  listing: "E’lon",
};

const PLAN_TEXT: Record<string, string> = {
  plus: "Plus",
  pro: "Pro",
};

/** `subscription_plus_1m` kabi kodni o'zbekcha nomga aylantiradi. */
export function priceLabel(price: AdminPriceRow) {
  const config = price.config ?? {};
  const plan = String(config.plan_code ?? "");
  const months = Number(config.duration_months ?? 0);
  if (price.service_type === "subscription" && plan) {
    const name = PLAN_TEXT[plan] ?? plan;
    return months ? `${name} obuna · ${months} oy` : `${name} obuna`;
  }
  const named: Record<string, string> = {
    advertisement_district_day: "Reklama · tumanda · bir kun",
    advertisement_district_hour: "Reklama · tumanda · bir soat",
    listing_publish: "E’lon joylash",
  };
  return named[price.price_code] ?? price.price_code;
}

function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

/** v1656da rekvizitlar `details` JSON'ida. Karta raqami eng ko'p
 *  ishlatiladigan maydon bo'lgani uchun unga alohida katak berilgan;
 *  boshqa kalitlar tegilmay saqlanadi. */
function cardNumberOf(details: Record<string, unknown>) {
  const value = details.card_number ?? details.card ?? "";
  return typeof value === "string" ? value : String(value ?? "");
}

function withCardNumber(
  details: Record<string, unknown>,
  cardNumber: string,
) {
  const next = { ...details };
  delete next.card;
  if (cardNumber.trim()) {
    next.card_number = cardNumber.trim();
  } else {
    delete next.card_number;
  }
  return next;
}

function toDraft(method: AdminMethodRow): MethodDraft {
  return {
    id: method.id,
    method_type: method.method_type,
    name: method.name,
    recipient_name: method.recipient_name,
    instructions: method.instructions,
    details: method.details ?? {},
    card_number: cardNumberOf(method.details ?? {}),
    sort_order: method.sort_order,
    active: method.active,
  };
}


export function AdminPricing({ api }: Props) {
  const [prices, setPrices] = useState<AdminPriceRow[]>([]);
  const [methods, setMethods] = useState<AdminMethodRow[]>([]);
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [method, setMethod] = useState<MethodDraft | null>(null);
  const [loading, setLoading] = useState(true);
  // Faqat bosilgan qator kutish holatiga o'tadi — barcha tugmalar emas.
  const [pendingPrice, setPendingPrice] = useState<number | null>(null);
  const [pendingMethod, setPendingMethod] = useState<number | "new" | null>(
    null,
  );
  const [note, setNote] = useState("");
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextPrices, nextMethods] = await Promise.all([
        api.prices(),
        api.methods(),
      ]);
      setPrices(nextPrices);
      setMethods(nextMethods);
      setFailed(false);
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  function report(text: string) {
    setFailed(false);
    setNote(text);
  }

  async function savePrice(price: AdminPriceRow) {
    const raw = draft[price.id] ?? String(price.amount_uzs);
    const amount = Number(raw.replace(/[^0-9]/g, ""));
    if (!Number.isFinite(amount) || amount <= 0) {
      setFailed(true);
      setNote("Narx noldan katta bo‘lishi kerak.");
      return;
    }
    setPendingPrice(price.id);
    try {
      const saved = await api.updatePrice(price.id, {
        amount_uzs: amount,
        active: price.active,
      });
      setPrices((rows) => rows.map((r) => (r.id === saved.id ? saved : r)));
      report("Narx saqlandi ✅");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setPendingPrice(null);
    }
  }

  async function togglePrice(price: AdminPriceRow) {
    setPendingPrice(price.id);
    try {
      const saved = await api.updatePrice(price.id, {
        amount_uzs: price.amount_uzs,
        active: !price.active,
      });
      setPrices((rows) => rows.map((r) => (r.id === saved.id ? saved : r)));
      report(saved.active ? "Tarif yoqildi ✅" : "Tarif o‘chirildi");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setPendingPrice(null);
    }
  }

  async function saveMethod() {
    if (!method) return;
    if (!method.name.trim()) {
      setFailed(true);
      setNote("Usul nomini kiriting.");
      return;
    }
    const body = {
      method_type: method.method_type.trim() || "manual_card",
      name: method.name.trim(),
      recipient_name: method.recipient_name.trim(),
      instructions: method.instructions.trim(),
      details: withCardNumber(method.details, method.card_number),
      sort_order: method.sort_order,
      active: method.active,
    };
    setPendingMethod(method.id ?? "new");
    try {
      if (method.id === null) {
        const saved = await api.createMethod(body);
        setMethods((rows) => [...rows, saved]);
        report("To‘lov usuli qo‘shildi ✅");
      } else {
        const saved = await api.updateMethod(method.id, body);
        setMethods((rows) => rows.map((r) => (r.id === saved.id ? saved : r)));
        report("To‘lov usuli saqlandi ✅");
      }
      setMethod(null);
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setPendingMethod(null);
    }
  }

  async function toggleMethod(row: AdminMethodRow) {
    setPendingMethod(row.id);
    try {
      const { id: _id, ...body } = row;
      const saved = await api.updateMethod(row.id, {
        ...body,
        active: !row.active,
      });
      setMethods((rows) => rows.map((r) => (r.id === saved.id ? saved : r)));
      report(saved.active ? "Usul yoqildi ✅" : "Usul o‘chirildi");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setPendingMethod(null);
    }
  }

  return (
    <section className="page active">
      <div className="page-head">
        <div>
          <div className="eyebrow">SOZLAMALAR</div>
          <h1>Narxlar va to‘lov usullari</h1>
        </div>
      </div>

      {note ? (
        <div className={`message${failed ? " error" : ""}`} role="status">
          {note}
        </div>
      ) : null}

      <div className="split-grid">
        <div className="panel">
          <div className="panel-head"><h2>Platforma narxlari</h2></div>
          <div className="settings-list">
            {loading ? <div>Yuklanmoqda…</div> : prices.map((price) => (
              <div className="settings-row" key={price.id}>
                <div>
                  <b>{priceLabel(price)}</b>
                  <div className="muted">
                    {SERVICE_TEXT[price.service_type] ?? price.service_type}
                    {price.active ? "" : " · o‘chirilgan"}
                  </div>
                </div>
                <label className="sr-only" htmlFor={`price-${price.id}`}>
                  {`${priceLabel(price)} narxi`}
                </label>
                <input
                  id={`price-${price.id}`}
                  inputMode="numeric"
                  value={draft[price.id] ?? String(price.amount_uzs)}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    [price.id]: event.target.value,
                  }))}
                />
                <button
                  type="button"
                  className="compact"
                  disabled={pendingPrice === price.id}
                  onClick={() => void savePrice(price)}
                >
                  Saqlash
                </button>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={pendingPrice === price.id}
                  onClick={() => void togglePrice(price)}
                >
                  {price.active ? "O‘chirish" : "Yoqish"}
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>To‘lov rekvizitlari</h2>
            <button
              type="button"
              className="secondary compact"
              onClick={() => setMethod({ ...EMPTY_METHOD })}
            >
              Yangi usul
            </button>
          </div>
          <div className="settings-list">
            {loading ? <div>Yuklanmoqda…</div> : methods.map((row) => (
              <div className="settings-row" key={row.id}>
                <div>
                  <b>{row.name}</b>
                  <div className="muted">
                    {row.recipient_name || cardNumberOf(row.details ?? {})
                      || row.method_type}
                  </div>
                </div>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={pendingMethod === row.id}
                  onClick={() => setMethod(toDraft(row))}
                >
                  Tahrirlash
                </button>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={pendingMethod === row.id}
                  onClick={() => void toggleMethod(row)}
                >
                  {row.active ? "O‘chirish" : "Yoqish"}
                </button>
              </div>
            ))}

            {method ? (
              <div
                className="settings-form"
                role="group"
                aria-label="To‘lov usuli formasi"
              >
                <h3>
                  {method.id === null
                    ? "Yangi to‘lov usuli"
                    : "To‘lov usulini tahrirlash"}
                </h3>
                <label htmlFor="methodName">Usul nomi</label>
                <input
                  id="methodName"
                  value={method.name}
                  onChange={(event) => setMethod({
                    ...method, name: event.target.value,
                  })}
                />
                <label htmlFor="methodRecipient">Qabul qiluvchi</label>
                <input
                  id="methodRecipient"
                  value={method.recipient_name}
                  onChange={(event) => setMethod({
                    ...method, recipient_name: event.target.value,
                  })}
                />
                <label htmlFor="methodCard">Karta raqami</label>
                <input
                  id="methodCard"
                  inputMode="numeric"
                  value={method.card_number}
                  onChange={(event) => setMethod({
                    ...method, card_number: event.target.value,
                  })}
                />
                <label htmlFor="methodInstructions">Ko‘rsatma</label>
                <input
                  id="methodInstructions"
                  value={method.instructions}
                  onChange={(event) => setMethod({
                    ...method, instructions: event.target.value,
                  })}
                />
                <div className="idesc">
                  Bular mijozga to‘lov oynasida ko‘rinadi.
                </div>
                <div className="decision-row">
                  <button
                    type="button"
                    disabled={pendingMethod !== null}
                    onClick={() => void saveMethod()}
                  >
                    Saqlash
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setMethod(null)}
                  >
                    Bekor qilish
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
