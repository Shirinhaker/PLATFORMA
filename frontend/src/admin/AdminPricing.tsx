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

const EMPTY_METHOD = {
  method_type: "manual_card",
  name: "",
  recipient_name: "",
  instructions: "",
  details: {},
  sort_order: 0,
  active: true,
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function AdminPricing({ api }: Props) {
  const [prices, setPrices] = useState<AdminPriceRow[]>([]);
  const [methods, setMethods] = useState<AdminMethodRow[]>([]);
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [newMethod, setNewMethod] = useState<typeof EMPTY_METHOD | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
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

  async function savePrice(price: AdminPriceRow) {
    const raw = draft[price.id] ?? String(price.amount_uzs);
    const amount = Number(raw.replace(/[^0-9]/g, ""));
    if (!Number.isFinite(amount) || amount < 0) {
      setFailed(true);
      setNote("Narx noto‘g‘ri.");
      return;
    }
    setBusy(true);
    try {
      const saved = await api.updatePrice(price.id, {
        amount_uzs: amount,
        active: price.active,
      });
      setPrices((rows) => rows.map(
        (row) => (row.id === saved.id ? saved : row),
      ));
      setFailed(false);
      setNote("Narx saqlandi ✅");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function togglePrice(price: AdminPriceRow) {
    setBusy(true);
    try {
      const saved = await api.updatePrice(price.id, {
        amount_uzs: price.amount_uzs,
        active: !price.active,
      });
      setPrices((rows) => rows.map(
        (row) => (row.id === saved.id ? saved : row),
      ));
      setFailed(false);
      setNote(saved.active ? "Tarif yoqildi ✅" : "Tarif o‘chirildi");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function saveMethod() {
    if (!newMethod) return;
    if (!newMethod.name.trim()) {
      setFailed(true);
      setNote("Usul nomini kiriting.");
      return;
    }
    setBusy(true);
    try {
      const saved = await api.createMethod(newMethod);
      setMethods((rows) => [...rows, saved]);
      setNewMethod(null);
      setFailed(false);
      setNote("To‘lov usuli qo‘shildi ✅");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function toggleMethod(method: AdminMethodRow) {
    setBusy(true);
    try {
      const { id: _id, ...body } = method;
      const saved = await api.updateMethod(method.id, {
        ...body,
        active: !method.active,
      });
      setMethods((rows) => rows.map(
        (row) => (row.id === saved.id ? saved : row),
      ));
      setFailed(false);
      setNote(saved.active ? "Usul yoqildi ✅" : "Usul o‘chirildi");
    } catch (error) {
      setFailed(true);
      setNote(message(error));
    } finally {
      setBusy(false);
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
                  <b>{price.price_code}</b>
                  <div className="muted">{price.service_type}</div>
                </div>
                <label className="sr-only" htmlFor={`price-${price.id}`}>
                  {`${price.price_code} narxi`}
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
                  disabled={busy}
                  onClick={() => void savePrice(price)}
                >
                  Saqlash
                </button>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={busy}
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
              onClick={() => setNewMethod({ ...EMPTY_METHOD })}
            >
              Yangi usul
            </button>
          </div>
          <div className="settings-list">
            {loading ? <div>Yuklanmoqda…</div> : methods.map((method) => (
              <div className="settings-row" key={method.id}>
                <div>
                  <b>{method.name}</b>
                  <div className="muted">
                    {method.recipient_name || method.method_type}
                  </div>
                </div>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={busy}
                  onClick={() => void toggleMethod(method)}
                >
                  {method.active ? "O‘chirish" : "Yoqish"}
                </button>
              </div>
            ))}

            {newMethod ? (
              <div className="settings-form">
                <label htmlFor="methodName">Usul nomi</label>
                <input
                  id="methodName"
                  value={newMethod.name}
                  onChange={(event) => setNewMethod({
                    ...newMethod, name: event.target.value,
                  })}
                />
                <label htmlFor="methodRecipient">Qabul qiluvchi</label>
                <input
                  id="methodRecipient"
                  value={newMethod.recipient_name}
                  onChange={(event) => setNewMethod({
                    ...newMethod, recipient_name: event.target.value,
                  })}
                />
                <label htmlFor="methodInstructions">Ko‘rsatma</label>
                <input
                  id="methodInstructions"
                  value={newMethod.instructions}
                  onChange={(event) => setNewMethod({
                    ...newMethod, instructions: event.target.value,
                  })}
                />
                <div className="decision-row">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void saveMethod()}
                  >
                    Saqlash
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setNewMethod(null)}
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
