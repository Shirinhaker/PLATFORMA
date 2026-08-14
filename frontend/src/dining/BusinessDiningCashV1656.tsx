import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { DiningOrder, DiningPayType } from "../api/types";
import { DebtorPickerV1656 } from "../profiles/DebtorPickerV1656";
import "./BusinessDiningCashV1656.css";


export type BusinessDiningCashApi = Pick<
  ApiClient,
  | "getDiningOrders"
  | "confirmDiningPayment"
  | "updateDiningCashierItems"
  | "finalizeDiningOrder"
  | "cancelDiningOrder"
  | "openDiningProblem"
  | "resolveDiningProblem"
  | "getDebtors"
  | "createDebtor"
>;

const CASH_METHODS: ReadonlyArray<keyof BusinessDiningCashApi> = [
  "getDiningOrders",
  "confirmDiningPayment",
  "updateDiningCashierItems",
  "finalizeDiningOrder",
  "cancelDiningOrder",
  "openDiningProblem",
  "resolveDiningProblem",
  "getDebtors",
  "createDebtor",
];

export function supportsDiningCashApi(
  api: object,
): api is BusinessDiningCashApi {
  return CASH_METHODS.every((method) => (
    typeof (api as Partial<BusinessDiningCashApi>)[method] === "function"
  ));
}

// v1656 `openDiningProblem` dagi ro'yxat.
const PROBLEM_REASONS = [
  "To‘lov yetishmaydi",
  "Noto‘g‘ri hisob",
  "Mijoz e’tirozi",
  "Boshqa",
] as const;

type Tab = "open" | "problem" | "done";

type Modal =
  | { kind: "edit"; order: DiningOrder }
  | { kind: "problem"; order: DiningOrder }
  | { kind: "cancel"; order: DiningOrder }
  | { kind: "debt"; order: DiningOrder }
  | { kind: "pay"; order: DiningOrder; payType: DiningPayType }
  | { kind: "resolve"; order: DiningOrder }
  | { kind: "finalize"; order: DiningOrder };

type Props = {
  api: BusinessDiningCashApi;
  onChanged?: () => void;
};


function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function qtyText(value: number) {
  return Number.isInteger(value) ? String(value) : String(value);
}

function reason(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function BusinessDiningCashV1656({ api, onChanged }: Props) {
  const [orders, setOrders] = useState<DiningOrder[]>([]);
  const [tab, setTab] = useState<Tab>("open");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<Modal | null>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.getDiningOrders();
      setOrders(rows.filter((row) => row.kind === "order"));
    } catch (error) {
      setFailed(true);
      setMessage(reason(error));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!message || failed) return;
    const timeout = window.setTimeout(() => setMessage(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [message, failed]);

  function report(text: string) {
    setFailed(false);
    setMessage(text);
    onChanged?.();
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
      setModal(null);
      await load();
    } catch (error) {
      setFailed(true);
      setMessage(reason(error));
    } finally {
      setBusy(false);
    }
  }

  const open = orders.filter(
    (order) => order.status === "active"
      && order.payment_status !== "confirmed"
      && !order.problem_open,
  );
  const problems = orders.filter(
    (order) => order.problem_open && order.status === "active",
  );
  const finalize = orders.filter(
    (order) => order.status === "active"
      && order.payment_status === "confirmed"
      && !order.problem_open,
  );

  if (loading) {
    return (
      <div className="dining-cash">
        <div className="idesc">Ichki hisoblar yuklanmoqda...</div>
      </div>
    );
  }

  return (
    <div className="dining-cash">
      <div className="dining-cash-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "open"}
          className={`seg-b${tab === "open" ? " on" : ""}`}
          onClick={() => setTab("open")}
        >
          Ochiq
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "problem"}
          className={`seg-b${tab === "problem" ? " on" : ""}`}
          onClick={() => setTab("problem")}
        >
          Muammoli
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "done"}
          className={`seg-b${tab === "done" ? " on" : ""}`}
          onClick={() => setTab("done")}
        >
          Yakunlangan
        </button>
      </div>

      {message ? (
        <div
          className={`dining-cash-message on${failed ? " error" : ""}`}
          role="status"
        >
          {message}
        </div>
      ) : null}

      {tab === "open" ? (
        <OpenPanel
          orders={open}
          busy={busy}
          onEdit={(order) => setModal({ kind: "edit", order })}
          onPay={(order, payType) => setModal({ kind: "pay", order, payType })}
          onDebt={(order) => setModal({ kind: "debt", order })}
          onProblem={(order) => setModal({ kind: "problem", order })}
          onCancel={(order) => setModal({ kind: "cancel", order })}
        />
      ) : null}

      {tab === "problem" ? (
        <ProblemPanel
          orders={problems}
          busy={busy}
          onResolve={(order) => setModal({ kind: "resolve", order })}
        />
      ) : null}

      {tab === "done" ? (
        <FinalizePanel
          orders={finalize}
          busy={busy}
          onFinalize={(order) => setModal({ kind: "finalize", order })}
        />
      ) : null}

      {modal?.kind === "edit" ? (
        <EditBillModal
          order={modal.order}
          busy={busy}
          onClose={() => setModal(null)}
          onSave={(items) => void run(async () => {
            await api.updateDiningCashierItems(modal.order.id, items);
            report("Hisob yangilandi ✅");
          })}
        />
      ) : null}

      {modal?.kind === "problem" ? (
        <ProblemModal
          busy={busy}
          onClose={() => setModal(null)}
          onSave={(body) => void run(async () => {
            await api.openDiningProblem(modal.order.id, body);
            setTab("problem");
            report("Hisob Muammoli bo‘limiga o‘tkazildi");
          })}
        />
      ) : null}

      {modal?.kind === "cancel" ? (
        <CancelModal
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={(text) => void run(async () => {
            await api.cancelDiningOrder(modal.order.id, text);
            report("Ichki buyurtma bekor qilindi, stol bo‘shadi ✅");
          })}
        />
      ) : null}

      {modal?.kind === "debt" ? (
        <DebtorPickerV1656
          api={api}
          title="Ichki hisobni qarzga yozish"
          onCancel={() => setModal(null)}
          onSelect={(debtorId) => void run(async () => {
            await api.confirmDiningPayment(modal.order.id, {
              pay_type: "qarz",
              debtor_id: debtorId,
            });
            report("Ichki hisob qarz daftariga yozildi ✅");
          })}
        />
      ) : null}

      {modal?.kind === "pay" ? (
        <ConfirmModal
          text="To‘lov qabul qilinganini tasdiqlaysizmi?"
          okText="Tasdiqlash"
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={() => void run(async () => {
            await api.confirmDiningPayment(modal.order.id, {
              pay_type: modal.payType,
            });
            report("To‘lov tasdiqlandi ✅");
          })}
        />
      ) : null}

      {modal?.kind === "resolve" ? (
        <ConfirmModal
          text="Muammo hal qilinganini tasdiqlaysizmi?"
          okText="Hal qilindi"
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={() => void run(async () => {
            await api.resolveDiningProblem(modal.order.id);
            setTab("open");
            report("Hisob Ochiq bo‘limiga qaytdi ✅");
          })}
        />
      ) : null}

      {modal?.kind === "finalize" ? (
        <ConfirmModal
          text="Hisob yakunlansin va stol bo‘shatilsinmi?"
          okText="Yakunlash"
          busy={busy}
          onClose={() => setModal(null)}
          onConfirm={() => void run(async () => {
            await api.finalizeDiningOrder(modal.order.id);
            report("Hisob yakunlandi, stol bo‘shadi ✅");
          })}
        />
      ) : null}
    </div>
  );
}


function OpenPanel({
  orders,
  busy,
  onEdit,
  onPay,
  onDebt,
  onProblem,
  onCancel,
}: {
  orders: DiningOrder[];
  busy: boolean;
  onEdit(order: DiningOrder): void;
  onPay(order: DiningOrder, payType: DiningPayType): void;
  onDebt(order: DiningOrder): void;
  onProblem(order: DiningOrder): void;
  onCancel(order: DiningOrder): void;
}) {
  if (!orders.length) {
    return (
      <div className="empty dining-cash-empty">
        <h3>Ochiq ichki hisob yo‘q</h3>
      </div>
    );
  }
  return (
    <div className="item dining-cash-group">
      <b>{`🍽️ Ochiq ichki hisoblar (${orders.length})`}</b>
      {orders.map((order) => (
        <details className="dining-cash-row" key={order.id}>
          <summary>
            <div>
              <b>{`▸ ${order.place_name}`}</b>
              <div className="idesc">
                {`Ofitsiant: ${order.waiter_name || "Rahbar"}`}
              </div>
            </div>
            <b className="dining-cash-total">{`${money(order.total)} so‘m`}</b>
          </summary>
          <div className="dining-cash-body">
            {order.items.map((item) => (
              <div className="idesc" key={item.id}>
                {`• ${item.name} × ${qtyText(item.qty)} ${item.unit} — ${money(item.total)}`}
              </div>
            ))}
            <button
              type="button"
              className="mini-btn dining-cash-wide"
              disabled={busy}
              onClick={() => onEdit(order)}
            >
              Tarkibni tahrirlash
            </button>
            <div className="dining-cash-pair">
              <button
                type="button"
                className="mini-btn"
                disabled={busy}
                onClick={() => onPay(order, "naqd")}
              >
                Naqd tasdiqlash
              </button>
              <button
                type="button"
                className="mini-btn"
                disabled={busy}
                onClick={() => onPay(order, "karta")}
              >
                Karta tasdiqlash
              </button>
            </div>
            <button
              type="button"
              className="mini-btn dining-cash-wide dining-cash-debt"
              disabled={busy}
              onClick={() => onDebt(order)}
            >
              📒 Qarzga rasmiylashtirish
            </button>
            <button
              type="button"
              className="mini-btn dining-cash-wide dining-cash-problem"
              disabled={busy}
              onClick={() => onProblem(order)}
            >
              ⚠️ Muammoli deb belgilash
            </button>
            <button
              type="button"
              className="mini-btn dining-cash-wide dining-cash-cancel"
              disabled={busy}
              onClick={() => onCancel(order)}
            >
              ✕ Ichki buyurtmani bekor qilish
            </button>
          </div>
        </details>
      ))}
    </div>
  );
}


function ProblemPanel({
  orders,
  busy,
  onResolve,
}: {
  orders: DiningOrder[];
  busy: boolean;
  onResolve(order: DiningOrder): void;
}) {
  if (!orders.length) {
    return (
      <div className="empty dining-cash-empty">
        <h3>Muammoli hisob yo‘q</h3>
      </div>
    );
  }
  return (
    <>
      {orders.map((order) => (
        <div className="item dining-cash-problem-card" key={order.id}>
          <div className="dining-cash-problem-head">
            <div>
              <b>{`⚠️ ${order.place_name}`}</b>
              <div className="idesc">
                {`Ichki · ${order.problem_reason || "Boshqa"}${
                  order.problem_note ? ` · ${order.problem_note}` : ""
                }`}
              </div>
            </div>
            <b>{`${money(order.total)} so‘m`}</b>
          </div>
          <button
            type="button"
            className="mini-btn dining-cash-wide dining-cash-resolve"
            disabled={busy}
            onClick={() => onResolve(order)}
          >
            Muammo hal qilindi
          </button>
        </div>
      ))}
    </>
  );
}


function FinalizePanel({
  orders,
  busy,
  onFinalize,
}: {
  orders: DiningOrder[];
  busy: boolean;
  onFinalize(order: DiningOrder): void;
}) {
  if (!orders.length) {
    return (
      <div className="empty dining-cash-empty">
        <h3>Yakunlash kutilayotgan hisob yo‘q</h3>
      </div>
    );
  }
  return (
    <div className="item dining-cash-group">
      <b>{`✅ Yakunlash kutilmoqda (${orders.length})`}</b>
      {orders.map((order) => {
        const ready = order.kitchen_status === "done";
        return (
          <details className="dining-cash-row" key={order.id}>
            <summary>
              <div>
                <b>{`▸ ${order.place_name}`}</b>
                <div className="idesc">
                  {ready
                    ? "Taom tayyor · to‘lov tasdiqlangan"
                    : "⏳ Oshpaz tayyorlashi kutilmoqda"}
                </div>
              </div>
              <b className="dining-cash-total">{`${money(order.total)} so‘m`}</b>
            </summary>
            <div className="dining-cash-body">
              {ready ? (
                <button
                  type="button"
                  className="mini-btn dining-cash-wide dining-cash-resolve"
                  disabled={busy}
                  onClick={() => onFinalize(order)}
                >
                  ✅ Hisobni yakunlash va stolni bo‘shatish
                </button>
              ) : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}


function EditBillModal({
  order,
  busy,
  onClose,
  onSave,
}: {
  order: DiningOrder;
  busy: boolean;
  onClose(): void;
  onSave(items: { line_id: number; qty: number }[]): void;
}) {
  const [quantities, setQuantities] = useState<Record<number, number>>(
    () => Object.fromEntries(order.items.map((item) => [item.id, item.qty])),
  );

  function step(lineId: number, delta: number) {
    setQuantities((current) => ({
      ...current,
      [lineId]: Math.max(0, (current[lineId] ?? 0) + delta),
    }));
  }

  return (
    <Sheet title="Kassir — hisobni tahrirlash" onClose={onClose}>
      <div className="dining-cash-lines">
        {order.items.map((item) => (
          <div className="dorder-row" key={item.id}>
            <div>
              <b>{item.name}</b>
              <div className="idesc">{`${money(item.price)} so‘m`}</div>
            </div>
            <div className="dorder-step">
              <button
                type="button"
                aria-label={`${item.name} kamaytirish`}
                onClick={() => step(item.id, -1)}
              >
                −
              </button>
              <b>{qtyText(quantities[item.id] ?? 0)}</b>
              <button
                type="button"
                aria-label={`${item.name} ko‘paytirish`}
                onClick={() => step(item.id, 1)}
              >
                +
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="idesc">0 ga tushirilgan taom hisobdan o‘chadi.</div>
      <div className="acf-btns">
        <button type="button" className="acf-cancel" onClick={onClose}>
          Bekor qilish
        </button>
        <button
          type="button"
          className="acf-ok"
          disabled={busy}
          onClick={() => onSave(
            order.items.map((item) => ({
              line_id: item.id,
              qty: quantities[item.id] ?? 0,
            })),
          )}
        >
          Saqlash
        </button>
      </div>
    </Sheet>
  );
}


function ProblemModal({
  busy,
  onClose,
  onSave,
}: {
  busy: boolean;
  onClose(): void;
  onSave(body: { reason: string; note: string }): void;
}) {
  const [chosen, setChosen] = useState<string>(PROBLEM_REASONS[0]);
  const [note, setNote] = useState("");

  return (
    <Sheet title="Muammoli hisob" onClose={onClose}>
      <div className="field">
        <label htmlFor="dining-problem-reason">Sabab</label>
        <select
          className="select"
          id="dining-problem-reason"
          value={chosen}
          onChange={(event) => setChosen(event.target.value)}
        >
          {PROBLEM_REASONS.map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="dining-problem-note">Izoh</label>
        <textarea
          className="textarea"
          id="dining-problem-note"
          placeholder="Muammoni qisqacha yozing"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
      <div className="acf-btns">
        <button type="button" className="acf-cancel" onClick={onClose}>
          Bekor qilish
        </button>
        <button
          type="button"
          className="acf-ok"
          disabled={busy}
          onClick={() => onSave({ reason: chosen, note: note.trim() })}
        >
          Saqlash
        </button>
      </div>
    </Sheet>
  );
}


function CancelModal({
  busy,
  onClose,
  onConfirm,
}: {
  busy: boolean;
  onClose(): void;
  onConfirm(reason: string): void;
}) {
  const [text, setText] = useState("");
  const [warned, setWarned] = useState(false);

  return (
    <Sheet title="Ichki buyurtmani bekor qilish" onClose={onClose}>
      <div className="field">
        <label htmlFor="dining-cancel-reason">Bekor qilish sababi</label>
        <input
          className="input"
          id="dining-cancel-reason"
          placeholder="Masalan: mijoz buyurtmadan voz kechdi"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setWarned(false);
          }}
        />
      </div>
      {warned ? (
        <div className="idesc dining-cash-warning" role="status">
          Bekor qilish sababini kiriting.
        </div>
      ) : null}
      <div className="idesc">Buyurtma bekor qilinsin va stol bo‘shatilsinmi?</div>
      <div className="acf-btns">
        <button type="button" className="acf-cancel" onClick={onClose}>
          Bekor qilish
        </button>
        <button
          type="button"
          className="acf-ok danger"
          disabled={busy}
          onClick={() => {
            if (!text.trim()) {
              setWarned(true);
              return;
            }
            onConfirm(text.trim());
          }}
        >
          Ha, bekor qilish
        </button>
      </div>
    </Sheet>
  );
}


function ConfirmModal({
  text,
  okText,
  busy,
  onClose,
  onConfirm,
}: {
  text: string;
  okText: string;
  busy: boolean;
  onClose(): void;
  onConfirm(): void;
}) {
  return (
    <Sheet title={text} onClose={onClose}>
      <div className="acf-btns">
        <button type="button" className="acf-cancel" onClick={onClose}>
          Bekor qilish
        </button>
        <button
          type="button"
          className="acf-ok"
          disabled={busy}
          onClick={onConfirm}
        >
          {okText}
        </button>
      </div>
    </Sheet>
  );
}


function Sheet({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose(): void;
  children: React.ReactNode;
}) {
  return (
    <>
      <div className="app-modal-back on" onClick={onClose} />
      <div className="app-confirm on" role="dialog" aria-modal="true">
        <div className="acf-title">{title}</div>
        {children}
      </div>
    </>
  );
}
