import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { DiningOrder } from "../api/types";
import "./BusinessKitchenV1656.css";


export type BusinessKitchenApi = Pick<
  ApiClient,
  "getDiningOrders" | "setDiningKitchenStatus"
>;

const KITCHEN_METHODS: ReadonlyArray<keyof BusinessKitchenApi> = [
  "getDiningOrders",
  "setDiningKitchenStatus",
];

export function supportsDiningKitchenApi(
  api: object,
): api is BusinessKitchenApi {
  return KITCHEN_METHODS.every((method) => (
    typeof (api as Partial<BusinessKitchenApi>)[method] === "function"
  ));
}

type Tab = "active" | "problem" | "done";

type Props = {
  api: BusinessKitchenApi;
  /** Xodim vakolatlari; rahbar uchun `null`. */
  permissions: readonly string[] | null;
  onBackHandlerChange: (handler: (() => void) | null) => void;
};


function money(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ");
}

// v1656 `notifyTime`: bugungi vaqt soat:daqiqa, aks holda kun.oy.
function orderTime(seconds: number) {
  if (!seconds) return "";
  const at = new Date(seconds * 1000);
  const now = new Date();
  const sameDay = at.getFullYear() === now.getFullYear()
    && at.getMonth() === now.getMonth()
    && at.getDate() === now.getDate();
  const pad = (value: number) => String(value).padStart(2, "0");
  return sameDay
    ? `${pad(at.getHours())}:${pad(at.getMinutes())}`
    : `${pad(at.getDate())}.${pad(at.getMonth() + 1)}`;
}

function kitchenText(order: DiningOrder) {
  if (order.kitchen_status === "done") return "Tayyor";
  return order.kitchen_status === "preparing" ? "Tayyorlanmoqda" : "Yangi";
}

function paymentText(order: DiningOrder) {
  return order.payment_status === "confirmed"
    ? "To‘lov tasdiqlandi"
    : "Hisob ochiq";
}


export function BusinessKitchenV1656({
  api,
  permissions,
  onBackHandlerChange,
}: Props) {
  const [orders, setOrders] = useState<DiningOrder[]>([]);
  const [tab, setTab] = useState<Tab | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  const canMarkReady = permissions === null || permissions.includes("kitchen");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.getDiningOrders();
      setOrders(rows.filter((row) => row.kind === "order"));
      setFailed(false);
      setMessage("");
    } catch (reason) {
      setFailed(true);
      setMessage(
        reason instanceof Error ? reason.message : "Ichki buyurtmalar yuklanmadi.",
      );
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    onBackHandlerChange(null);
  }, [onBackHandlerChange]);

  useEffect(() => {
    if (!message || failed) return;
    const timeout = window.setTimeout(() => setMessage(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [message, failed]);

  const problem = orders.filter((order) => order.problem_open);
  const active = orders.filter(
    (order) => order.status === "active" && !order.problem_open,
  );
  const done = orders.filter(
    (order) => order.status === "done" && !order.problem_open,
  );

  // v1656: bo'lim tanlanmagan bo'lsa, bo'sh bo'lmaganiga o'tadi.
  const current: Tab = tab ?? (
    active.length ? "active" : problem.length ? "problem" : "active"
  );
  const shown = current === "done" ? done : current === "problem" ? problem : active;

  async function markReady(order: DiningOrder) {
    setBusyId(order.id);
    try {
      const saved = await api.setDiningKitchenStatus(order.id, "done");
      setOrders((rows) => rows.map(
        (row) => (row.id === saved.id ? saved : row),
      ));
      setFailed(false);
      setMessage("Taom tayyor deb belgilandi ✅");
    } catch (reason) {
      setFailed(true);
      setMessage(reason instanceof Error ? reason.message : "Saqlanmadi.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return (
      <div className="biz-kitchen">
        <div className="idesc">Ichki buyurtmalar yuklanmoqda...</div>
      </div>
    );
  }

  return (
    <div className="biz-kitchen">
      <div className="biz-kitchen-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={current === "active"}
          className={`seg-b${current === "active" ? " on" : ""}`}
          onClick={() => setTab("active")}
        >
          {`Buyurtmalar (${active.length})`}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={current === "problem"}
          className={`seg-b${current === "problem" ? " on" : ""}`}
          onClick={() => setTab("problem")}
        >
          {`Muammoli (${problem.length})`}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={current === "done"}
          className={`seg-b${current === "done" ? " on" : ""}`}
          onClick={() => setTab("done")}
        >
          {`Yakunlangan (${done.length})`}
        </button>
      </div>

      {message ? (
        <div
          className={`biz-kitchen-message on${failed ? " error" : ""}`}
          role="status"
        >
          {message}
        </div>
      ) : null}

      {shown.length === 0 ? (
        <div className="empty biz-kitchen-empty">
          <h3>Buyurtma yo‘q</h3>
        </div>
      ) : (
        shown.map((order) => (
          <div className="panel-card biz-kitchen-card" key={order.id}>
            <div className="biz-kitchen-head">
              <div>
                <b>
                  {`${order.place_kind === "room" ? "🚪" : "🪑"} ${order.place_name}`}
                </b>
                <div className="idesc">
                  {`Ofitsiant: ${order.waiter_name || "Rahbar"}`}
                </div>
              </div>
              <span className="idesc">{orderTime(order.created_at)}</span>
            </div>

            {order.items.map((item) => (
              <div className="idesc biz-kitchen-item" key={item.id}>
                {`${item.name} · ${item.qty} ${item.unit || "dona"}`}
              </div>
            ))}

            <div className="biz-kitchen-foot">
              <div>
                <span className="order-status-pill">
                  {`👨‍🍳 ${kitchenText(order)}`}
                </span>
                <div className="idesc biz-kitchen-pay">
                  {`💳 ${paymentText(order)}`}
                </div>
              </div>
              <b>{`${money(order.total)} so‘m`}</b>
            </div>

            {canMarkReady
              && order.status === "active"
              && order.kitchen_status !== "done" ? (
                <button
                  type="button"
                  className="mini-btn biz-kitchen-ready"
                  disabled={busyId === order.id}
                  onClick={() => void markReady(order)}
                >
                  ✅ Tayyor bo‘ldi
                </button>
              ) : null}
          </div>
        ))
      )}
    </div>
  );
}
