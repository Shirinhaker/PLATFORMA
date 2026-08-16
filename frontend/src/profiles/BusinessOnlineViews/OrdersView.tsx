// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import {
  OrderFilter,
  orderCreatedText,
  recordId,
  recordNumber,
  recordText,
  v1656Money,
} from "./shared";

export function OrdersView({
  rows,
  filter,
  setFilter,
  busy,
  setStatus,
  action,
}: {
  rows: BusinessOnlineRecord[];
  filter: OrderFilter;
  setFilter: (value: OrderFilter) => void;
  busy: boolean;
  setStatus: (id: number | string, status: string) => Promise<void>;
  action?: (
    id: number | string,
    name: "report_problem" | "handoff",
    payload?: BusinessOnlineRecord,
  ) => Promise<void>;
}) {
  const [problemOrder, setProblemOrder] = useState<number | string | null>(null);
  const [problemReason, setProblemReason] = useState("not_received");
  const [problemNote, setProblemNote] = useState("");
  const [handoffOrder, setHandoffOrder] = useState<number | string | null>(null);
  const activeStatuses = new Set([
    "new",
    "accepted",
    "preparing",
    "ready",
    "tayyor",
    "courier_assigned",
    "courier_arrived_store",
    "handoff_waiting_seller",
    "in_delivery",
    "courier_arrived_customer",
    "delivered_waiting_customer",
    "pickup_waiting_customer",
  ]);
  const problems = rows.filter((row) => Boolean(row.problem_open));
  const active = rows.filter(
    (row) => !row.problem_open && activeStatuses.has(recordText(row, "status")),
  );
  const done = rows.filter(
    (row) => !row.problem_open && !activeStatuses.has(recordText(row, "status")),
  );
  const current =
    filter === "active" ? "problem" : filter === "terminal" ? "done" : "active";
  const visible = current === "problem" ? problems : current === "done" ? done : active;

  function setTab(value: "active" | "problem" | "done") {
    setFilter(value === "active" ? "new" : value === "problem" ? "active" : "terminal");
  }

  function orderStatus(value: unknown) {
    const labels: Record<string, string> = {
      new: "Yangi",
      accepted: "To'lov kutilmoqda",
      preparing: "Tayyorlanmoqda",
      rejected: "Rad etildi",
      done: "Yakunlandi",
      cancelled: "Bekor qilindi",
      canceled: "Bekor qilindi",
      ready: "Tayyor",
      tayyor: "Tayyor",
      courier_assigned: "Dostavkachi biriktirildi",
      courier_arrived_store: "Dostavkachi sotuvchiga yetib keldi",
      handoff_waiting_seller: "Topshirish tasdig'i kutilmoqda",
      in_delivery: "Yo'lda",
      courier_arrived_customer: "Dostavkachi yetib keldi",
      delivered_waiting_customer: "Qabul tasdig'i kutilmoqda",
      pickup_waiting_customer: "Qabul tasdig'i kutilmoqda",
    };
    const status = String(value ?? "");
    return labels[status] ?? status ?? "—";
  }

  function orderStatusClass(value: unknown) {
    const status = String(value ?? "");
    if (["accepted", "preparing", "done", "ready", "tayyor"].includes(status)) {
      return "credit";
    }
    return ["rejected", "cancelled", "canceled"].includes(status) ? "debit" : "";
  }

  function orderType(value: unknown) {
    const type = String(value ?? "");
    return (
      (
        {
          delivery: "Yetkazib berish",
          pickup: "Olib ketish",
          booking: "Navbat/qabul",
        } as Record<string, string>
      )[type] ??
      type ??
      "—"
    );
  }

  function problemReasonText(value: unknown) {
    const reasons: Record<string, string> = {
      not_received: "Pul hisobga tushmadi",
      amount_short: "To'langan summa kam",
      receipt_mismatch: "Chek ma'lumoti mos kelmadi",
      receipt_unreadable: "Chek rasmi o'qilmaydi",
      wrong_receipt: "Noto'g'ri chek yuborilgan",
      other: "Boshqa to'lov muammosi",
    };
    const key = String(value ?? "");
    return reasons[key] ?? key;
  }

  return (
    <section>
      <div className="order-tabs-v1656">
        <button
          type="button"
          className={current === "active" ? "seg-b on" : "seg-b"}
          onClick={() => setTab("active")}
        >
          Buyurtmalar ({active.length})
          {active.some((row) => Boolean(row.is_unread)) ? " 🔔" : ""}
        </button>
        <button
          type="button"
          className={current === "problem" ? "seg-b on" : "seg-b"}
          onClick={() => setTab("problem")}
        >
          Muammoli ({problems.length})
        </button>
        <button
          type="button"
          className={current === "done" ? "seg-b on" : "seg-b"}
          onClick={() => setTab("done")}
        >
          Yakunlangan ({done.length})
          {done.some((row) => Boolean(row.is_unread)) ? " 🔔" : ""}
        </button>
      </div>
      <div className="orders-v1656-list">
        {visible.length ? (
          visible.map((row, index) => {
            const id = recordId(row, index);
            const status = recordText(row, "status");
            const classes = [
              "item",
              "order-card",
              status === "new" ? "order-new" : "",
              row.is_unread ? "order-unread" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <article className={classes} key={String(id)}>
                <div className="order-card-top">
                  <span className="order-no-pill">BUYURTMA №{id}</span>
                  <span className="idesc order-card-time">
                    🕒 {orderCreatedText(row.created_at)}
                  </span>
                </div>
                <div className="order-card-main">
                  <div>
                    <div className="iname">
                      {recordText(row, "title", "name") || "Buyurtma"}
                    </div>
                    <div className="idesc">
                      Mijoz: {recordText(row, "customer_name") || "—"}
                    </div>
                    {Boolean(row.is_unread) && (
                      <div className="order-unread-pill">
                        {recordText(row, "last_event") === "msg"
                          ? "💬 Xabar keldi"
                          : "🔔 Yangi buyurtma"}
                      </div>
                    )}
                    <div className="idesc">Turi: {orderType(row.order_type)}</div>
                    {recordText(row, "address") && (
                      <div className="idesc">📍 {recordText(row, "address")}</div>
                    )}
                    {recordText(row, "phone") && (
                      <div className="idesc">☎ {recordText(row, "phone")}</div>
                    )}
                    {recordText(row, "note") && (
                      <div className="idesc">{recordText(row, "note")}</div>
                    )}
                    {Boolean(row.problem_open) && (
                      <div
                        style={{
                          marginTop: 9,
                          padding: 9,
                          borderRadius: 10,
                          background: "#FFF7ED",
                          color: "#9A3412",
                          fontSize: 12.5,
                        }}
                      >
                        <b>⚠️ To'lov aniqlashtirilmoqda</b>
                        <div>{problemReasonText(row.problem_reason)}</div>
                        {recordText(row, "problem_note") && (
                          <div>Izoh: {recordText(row, "problem_note")}</div>
                        )}
                      </div>
                    )}
                  </div>
                  <span className={`tx-amt ${orderStatusClass(status)}`.trim()}>
                    {orderStatus(status)}
                  </span>
                </div>
                {Array.isArray(row.items) && row.items.length > 0 && (
                  <div className="order-card-items">
                    {row.items.map((item, itemIndex) => {
                      const line = item as BusinessOnlineRecord;
                      return (
                        <div
                          className="idesc order-card-line"
                          key={String(recordId(line, itemIndex))}
                        >
                          <span>
                            {recordText(line, "name", "title", "item_name") ||
                              "Mahsulot"}
                            {" × "}
                            {recordText(line, "qty", "quantity") || "1"}
                            {recordText(line, "unit") &&
                            recordText(line, "unit") !== "dona"
                              ? ` ${recordText(line, "unit")}`
                              : ""}
                          </span>
                          <b>
                            {recordNumber(line, "line_total")
                              ? v1656Money(recordNumber(line, "line_total"))
                              : recordText(line, "price") || "—"}
                          </b>
                        </div>
                      );
                    })}
                    {recordText(row, "total_text") && (
                      <div className="iprice order-card-total">
                        Jami: {recordText(row, "total_text")}
                      </div>
                    )}
                  </div>
                )}
                {status === "new" && (
                  <div className="order-card-actions">
                    <button
                      type="button"
                      className="mini-btn"
                      disabled={busy}
                      onClick={() => void setStatus(id, "accepted")}
                    >
                      Qabul qilish
                    </button>
                    <button
                      type="button"
                      className="mini-btn danger"
                      disabled={busy}
                      onClick={() => void setStatus(id, "rejected")}
                    >
                      Rad etish
                    </button>
                  </div>
                )}
                {status === "accepted" && !row.problem_open && (
                  <div className="order-card-actions">
                    {["submitted", "recheck", "disputed"].includes(
                      recordText(row, "payment_status"),
                    ) && (
                      <button
                        type="button"
                        className="mini-btn warning"
                        disabled={busy}
                        onClick={() => {
                          setProblemReason("not_received");
                          setProblemNote("");
                          setProblemOrder(id);
                        }}
                      >
                        ⚠️ To'lov muammosi
                      </button>
                    )}
                    <button
                      type="button"
                      className="mini-btn danger"
                      disabled={busy}
                      onClick={() => void setStatus(id, "cancelled")}
                    >
                      Bekor qilish
                    </button>
                  </div>
                )}
                {status === "preparing" && (
                  <button
                    type="button"
                    className="mini-btn success"
                    disabled={busy}
                    onClick={() => void setStatus(id, "tayyor")}
                  >
                    ✅ Buyurtma tayyor
                  </button>
                )}
                {status === "handoff_waiting_seller" && (
                  <button
                    type="button"
                    className="mini-btn success"
                    disabled={busy}
                    onClick={() => setHandoffOrder(id)}
                  >
                    📦 Dostavkachiga topshirdim
                  </button>
                )}
                {["ready", "tayyor"].includes(status) &&
                  recordText(row, "order_type") === "pickup" && (
                    <button
                      type="button"
                      className="mini-btn success"
                      disabled={busy}
                      onClick={() => setHandoffOrder(id)}
                    >
                      🏪 Buyurtmachiga topshirdim
                    </button>
                  )}
                <div className="idesc order-card-hint">
                  Batafsil ko‘rish va chat uchun bosing
                </div>
              </article>
            );
          })
        ) : (
          <div className="empty order-empty">
            <h3>
              {current === "done"
                ? "Yakunlangan buyurtma yo'q"
                : current === "problem"
                  ? "Muammoli buyurtma yo'q"
                  : "Faol buyurtma yo'q"}
            </h3>
          </div>
        )}
      </div>
      {problemOrder !== null && (
        <>
          <button
            type="button"
            className="sheet-backdrop on"
            aria-label="Muammo oynasini yopish"
            onClick={() => setProblemOrder(null)}
          />
          <div className="order-sheet on" role="dialog" aria-modal="true">
            <button
              type="button"
              className="order-close"
              aria-label="Yopish"
              onClick={() => setProblemOrder(null)}
            >
              ×
            </button>
            <div className="lead">To'lov bo'yicha muammo</div>
            <div className="lead-sub">
              Sababni tanlang. Muammo hal bo'lmaguncha tayyorlash, dostavka va yakunlash
              bloklanadi.
            </div>
            <label className="field">
              Muammo sababi
              <select
                className="input"
                value={problemReason}
                onChange={(event) => setProblemReason(event.currentTarget.value)}
              >
                <option value="not_received">Pul hisobga tushmadi</option>
                <option value="amount_short">To'langan summa kam</option>
                <option value="receipt_mismatch">Chek ma'lumoti mos kelmadi</option>
                <option value="receipt_unreadable">Chek rasmi o'qilmaydi</option>
                <option value="wrong_receipt">Noto'g'ri chek yuborilgan</option>
                <option value="other">Boshqa muammo</option>
              </select>
            </label>
            <label className="field">
              Izoh
              <textarea
                className="textarea"
                placeholder="Muammoni qisqacha tushuntiring"
                value={problemNote}
                onChange={(event) => setProblemNote(event.currentTarget.value)}
              />
            </label>
            <button
              type="button"
              className="btn btn-primary btn-block"
              disabled={busy}
              onClick={async () => {
                await action?.(problemOrder, "report_problem", {
                  reason: problemReason,
                  note: problemNote.trim(),
                });
                setProblemOrder(null);
              }}
            >
              Muammoli buyurtmaga o'tkazish
            </button>
          </div>
        </>
      )}
      {handoffOrder !== null && (
        <>
          <button
            type="button"
            className="app-modal-back on"
            aria-label="Bekor qilish"
            onClick={() => setHandoffOrder(null)}
          />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <p className="acf-text">Buyurtma qarshi tomonga topshirildimi?</p>
            <div className="acf-btns">
              <button
                type="button"
                className="acf-cancel"
                onClick={() => setHandoffOrder(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="acf-ok"
                disabled={busy}
                onClick={async () => {
                  await action?.(handoffOrder, "handoff");
                  setHandoffOrder(null);
                }}
              >
                Ha, topshirdim
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
