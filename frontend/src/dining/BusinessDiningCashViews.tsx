import { useState, type ReactNode } from "react";

import type { DiningOrder, DiningPayType } from "../api/types";

// v1656 `openDiningProblem` dagi ro'yxat.
const PROBLEM_REASONS = [
  "To‘lov yetishmaydi",
  "Noto‘g‘ri hisob",
  "Mijoz e’tirozi",
  "Boshqa",
] as const;

function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

function qtyText(value: number) {
  return Number.isInteger(value) ? String(value) : String(value);
}

export function OpenPanel({
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

export function ProblemPanel({
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

export function FinalizePanel({
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

export function EditBillModal({
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
  const [quantities, setQuantities] = useState<Record<number, number>>(() =>
    Object.fromEntries(order.items.map((item) => [item.id, item.qty])),
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
          onClick={() =>
            onSave(
              order.items.map((item) => ({
                line_id: item.id,
                qty: quantities[item.id] ?? 0,
              })),
            )
          }
        >
          Saqlash
        </button>
      </div>
    </Sheet>
  );
}

export function ProblemModal({
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
            <option key={value} value={value}>
              {value}
            </option>
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

export function CancelModal({
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

export function ConfirmModal({
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
        <button type="button" className="acf-ok" disabled={busy} onClick={onConfirm}>
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
  children: ReactNode;
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
