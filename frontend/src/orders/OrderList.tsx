import type { ReactNode } from "react";

import type { OrderProblemSolution, OrderRead } from "../api/types";
import {
  createdText,
  isMessageEvent,
  problemReasonText,
  qtyText,
  statusText,
  typeText,
  workHoursText,
} from "./order-cabinet-helpers";
import type { OrderConfirmation, OrdersApi, OrdersTab } from "./order-cabinet-types";

type Props = {
  api: OrdersApi;
  side: "customer" | "provider";
  category: "product" | "service";
  error: string;
  beforeList?: ReactNode;
  tab: OrdersTab;
  active: OrderRead[];
  problem: OrderRead[];
  done: OrderRead[];
  shown: OrderRead[];
  loading: boolean;
  busy: boolean;
  onBack(): void;
  onTabChange(tab: OrdersTab): void;
  onOpenDetail(order: OrderRead): Promise<void>;
  onMutate(action: () => Promise<OrderRead>): Promise<boolean>;
  onSelect(order: OrderRead): void;
  onConfirmationChange(value: OrderConfirmation): void;
  onProblemOpen(value: boolean): void;
};

export function OrderList({
  api,
  side,
  category,
  error,
  beforeList,
  tab,
  active,
  problem,
  done,
  shown,
  loading,
  busy,
  onBack,
  onTabChange,
  onOpenDetail: openDetail,
  onMutate: mutate,
  onSelect,
  onConfirmationChange,
  onProblemOpen,
}: Props) {
  return (
    <main className="orders-cabinet-v1656">
      <header className="orders-v1656-heading">
        <button type="button" className="mini-btn" onClick={onBack}>
          ‹
        </button>
        <h1>
          {side === "customer"
            ? category === "service"
              ? "Xizmat buyurtmalarim"
              : "Buyurtmalarim"
            : category === "service"
              ? "Xizmat buyurtmalari"
              : "Buyurtmalar"}
        </h1>
      </header>
      {error ? (
        <p className="app-toast on" role="alert">
          {error}
        </p>
      ) : null}
      {beforeList}
      <div className="order-tabs" role="tablist">
        <button
          type="button"
          className={`seg-b${tab === "active" ? " on" : ""}`}
          onClick={() => onTabChange("active")}
        >
          Buyurtmalar ({active.length})
          {active.some((order) => order.is_unread) ? " 🔔" : ""}
        </button>
        <button
          type="button"
          className={`seg-b${tab === "problem" ? " on" : ""}`}
          onClick={() => onTabChange("problem")}
        >
          Muammoli ({problem.length})
        </button>
        <button
          type="button"
          className={`seg-b${tab === "done" ? " on" : ""}`}
          onClick={() => onTabChange("done")}
        >
          Yakunlangan ({done.length})
          {done.some((order) => order.is_unread) ? " 🔔" : ""}
        </button>
      </div>
      {loading ? (
        <p>Buyurtmalar yuklanmoqda...</p>
      ) : shown.length ? (
        <div className="orders-v1656-list">
          {shown.map((order) => (
            <div
              role="button"
              tabIndex={0}
              className={`item order-card${order.status === "new" ? " order-new" : ""}${order.is_unread ? " order-unread" : ""}`}
              key={order.id}
              onClick={() => void openDetail(order)}
              onKeyDown={(event) => {
                if (event.currentTarget !== event.target) return;
                if (event.key === "Enter" || event.key === " ") void openDetail(order);
              }}
            >
              <div className="order-card-number">
                <span className="order-no-pill">BUYURTMA №{order.id}</span>
                <span className="idesc">🕒 {createdText(order.created_at)}</span>
              </div>
              <div className="order-card-head">
                <div>
                  <div className="iname">{order.title || "Buyurtma"}</div>
                  <div className="idesc">
                    {side === "provider" ? "Mijoz" : "Qabul qiluvchi"}:{" "}
                    {side === "provider" ? order.customer_name : order.provider_name}
                  </div>
                </div>
                <span
                  className={`tx-amt ${["rejected", "cancelled"].includes(order.status) ? "debit" : "credit"}`}
                >
                  {statusText(order.status)}
                </span>
              </div>
              {order.is_unread ? (
                <div className="order-unread-pill">
                  {isMessageEvent(order.last_event)
                    ? "💬 Xabar keldi"
                    : side === "provider"
                      ? "🔔 Yangi buyurtma"
                      : "🔔 Status yangilandi"}
                </div>
              ) : null}
              <div className="idesc">Turi: {typeText(order.order_type)}</div>
              {order.address ? <div className="idesc">📍 {order.address}</div> : null}
              {order.delivery_lat != null && order.delivery_lng != null ? (
                <div className="idesc">
                  🗺 {order.delivery_lat.toFixed(6)}, {order.delivery_lng.toFixed(6)}
                </div>
              ) : null}
              {order.desired_time ? (
                <div className="idesc">🕒 {order.desired_time}</div>
              ) : null}
              {order.phone ? <div className="idesc">☎ {order.phone}</div> : null}
              {order.note ? (
                <div className="idesc order-card-note">{order.note}</div>
              ) : null}
              {order.problem_open ? (
                <div className="order-card-problem">
                  <b>⚠️ To'lov aniqlashtirilmoqda</b>
                  <div>{problemReasonText(order.problem_reason)}</div>
                  {order.problem_note ? <div>Izoh: {order.problem_note}</div> : null}
                  {order.problem_solution === "pickup" ? (
                    <div>
                      <b>Do'kon:</b> {order.provider_address || "Manzil kiritilmagan"}
                      {order.provider_phone ? ` · ${order.provider_phone}` : ""}
                      {workHoursText(order.provider_work_hours)
                        ? ` · ${workHoursText(order.provider_work_hours)}`
                        : ""}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {order.items.length ? (
                <div className="order-card-items">
                  {order.items.map((item) => (
                    <div className="idesc" key={item.id}>
                      <span>
                        {item.name} × {qtyText(item.qty, item.unit)}
                      </span>
                      <b>
                        {item.line_total
                          ? item.line_total.toLocaleString("uz-UZ")
                          : item.price || "—"}
                      </b>
                    </div>
                  ))}
                  {order.total_text ? (
                    <div className="iprice">Jami: {order.total_text}</div>
                  ) : null}
                </div>
              ) : null}
              {order.last_chat ? (
                <div className="idesc order-card-chat">💬 {order.last_chat}</div>
              ) : order.chat_count ? (
                <div className="idesc order-card-chat">
                  💬 {order.chat_count} ta xabar
                </div>
              ) : null}
              {!order.problem_open && side === "provider" && order.status === "new" ? (
                <div className="order-card-actions">
                  <button
                    type="button"
                    className="mini-btn"
                    disabled={busy}
                    onClick={(event) => {
                      event.stopPropagation();
                      void mutate(() => api.changeOrderStatus(order.id, "accepted"));
                    }}
                  >
                    Qabul qilish
                  </button>
                  <button
                    type="button"
                    className="mini-btn danger"
                    disabled={busy}
                    onClick={(event) => {
                      event.stopPropagation();
                      void mutate(() => api.changeOrderStatus(order.id, "rejected"));
                    }}
                  >
                    Rad etish
                  </button>
                </div>
              ) : null}
              {!order.problem_open &&
              side === "provider" &&
              order.status === "accepted" ? (
                <div className="order-card-actions">
                  {["submitted", "recheck", "disputed"].includes(
                    order.payment_status,
                  ) ? (
                    <button
                      type="button"
                      className="mini-btn warning"
                      disabled={busy}
                      onClick={(event) => {
                        event.stopPropagation();
                        void openDetail(order).then(() => onProblemOpen(true));
                      }}
                    >
                      ⚠️ To'lov muammosi
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="mini-btn danger"
                    disabled={busy}
                    onClick={(event) => {
                      event.stopPropagation();
                      void mutate(() => api.changeOrderStatus(order.id, "cancelled"));
                    }}
                  >
                    Bekor qilish
                  </button>
                </div>
              ) : null}
              {!order.problem_open &&
              side === "provider" &&
              order.status === "preparing" ? (
                <div className="order-card-actions">
                  <button
                    type="button"
                    className="mini-btn ok"
                    disabled={busy}
                    onClick={(event) => {
                      event.stopPropagation();
                      void mutate(() => api.changeOrderStatus(order.id, "tayyor"));
                    }}
                  >
                    ✅ Buyurtma tayyor
                  </button>
                </div>
              ) : null}
              {!order.problem_open &&
              side === "provider" &&
              order.status === "tayyor" &&
              order.order_type === "delivery" ? (
                <div className="idesc order-card-status">Dostavkachi qidirilmoqda</div>
              ) : null}
              {!order.problem_open &&
              side === "provider" &&
              order.status === "handoff_waiting_seller" ? (
                <div className="order-card-actions">
                  <button
                    type="button"
                    className="mini-btn ok"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(order);
                      onConfirmationChange("handoff");
                    }}
                  >
                    📦 Dostavkachiga topshirdim
                  </button>
                </div>
              ) : null}
              {!order.problem_open &&
              side === "provider" &&
              order.status === "tayyor" &&
              order.order_type === "pickup" ? (
                <div className="order-card-actions">
                  <button
                    type="button"
                    className="mini-btn ok"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(order);
                      onConfirmationChange("handoff");
                    }}
                  >
                    🏪 Buyurtmachiga topshirdim
                  </button>
                </div>
              ) : null}
              {!order.problem_open &&
              side === "customer" &&
              ["new", "accepted"].includes(order.status) ? (
                <div className="order-card-actions">
                  <button
                    type="button"
                    className="mini-btn danger"
                    disabled={busy}
                    onClick={(event) => {
                      event.stopPropagation();
                      void mutate(() => api.changeOrderStatus(order.id, "cancelled"));
                    }}
                  >
                    Bekor qilish
                  </button>
                </div>
              ) : null}
              {!order.problem_open &&
              side === "customer" &&
              order.status === "preparing" ? (
                <div className="idesc order-card-status">Buyurtma tayyorlanmoqda</div>
              ) : null}
              {!order.problem_open &&
              side === "customer" &&
              order.status === "tayyor" ? (
                <div className="idesc order-card-status">
                  {order.order_type === "delivery"
                    ? "Dostavkachi qidirilmoqda"
                    : "Do'kondan olib ketishingiz mumkin"}
                </div>
              ) : null}
              {!order.problem_open &&
              side === "customer" &&
              ["delivered_waiting_customer", "pickup_waiting_customer"].includes(
                order.status,
              ) ? (
                <div className="order-card-actions">
                  <button
                    type="button"
                    className="mini-btn ok"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(order);
                      onConfirmationChange("received");
                    }}
                  >
                    ✅ Buyurtmani qabul qildim
                  </button>
                </div>
              ) : null}
              {order.problem_open && side === "customer" ? (
                <div className="order-card-actions">
                  {(
                    [
                      ["pickup", "🏪 Do'konga boraman"],
                      ["wait", "⏳ Kutaman"],
                      ["new_receipt", "🧾 Yangi chek"],
                    ] as Array<[OrderProblemSolution, string]>
                  ).map(([solution, label]) => (
                    <button
                      type="button"
                      className="mini-btn"
                      key={solution}
                      disabled={busy}
                      onClick={(event) => {
                        event.stopPropagation();
                        void mutate(() =>
                          api.chooseOrderProblemSolution(order.id, solution),
                        );
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : null}
              <div className="idesc order-detail-hint">
                Batafsil ko‘rish va chat uchun bosing
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty">
          <h3>
            {tab === "active"
              ? "Faol buyurtma yo'q"
              : tab === "problem"
                ? "Muammoli buyurtma yo'q"
                : "Yakunlangan buyurtma yo'q"}
          </h3>
        </div>
      )}
    </main>
  );
}
