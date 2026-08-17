import {
  useMemo,
  useState,
  type Dispatch,
  type MutableRefObject,
  type PointerEvent as ReactPointerEvent,
  type SetStateAction,
} from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { recordId } from "./BusinessOnlineViews";

export type DiningAction = (
  resource: BusinessOnlineResource,
  name: string,
  id?: number | string,
  payload?: BusinessOnlineRecord,
) => Promise<BusinessOnlineRecord | null>;

export type Position = { x: number; y: number };
export type DragState = {
  id: number | string;
  dx: number;
  dy: number;
} | null;

export function DiningOrderView({
  place,
  rows,
  groups,
  busy,
  action,
  refresh,
  close,
  showMessage,
}: {
  place: BusinessOnlineRecord;
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  busy: boolean;
  action: DiningAction;
  refresh: (...resources: BusinessOnlineResource[]) => Promise<void>;
  close: () => void;
  showMessage: (value: string) => void;
}) {
  const orderId = place.active_kind === "order" ? numberValue(place.active_id) : 0;
  const [query, setQuery] = useState("");
  const [cart, setCart] = useState<Record<string, number>>({});
  const [customerName, setCustomerName] = useState("");
  const [note, setNote] = useState("");
  const groupNames = useMemo(
    () =>
      new Map(
        groups.map((group, index) => [
          String(recordId(group, index)),
          String(group.name ?? ""),
        ]),
      ),
    [groups],
  );
  const menuRows = useMemo<BusinessOnlineRecord[]>(
    () =>
      rows
        .filter((row) => String(row.stock_type ?? "ready_food") === "ready_food")
        .map((row): BusinessOnlineRecord => {
          const groupName =
            row.group_name ??
            groupNames.get(String(row.group_id ?? row.item_group_id ?? ""));
          return {
            ...row,
            group_name: groupName === undefined ? "" : String(groupName),
          };
        }),
    [groupNames, rows],
  );
  const visible = useMemo(() => {
    const clean = normalizeSearch(query);
    if (!clean) return menuRows;
    return menuRows.filter((item) =>
      normalizeSearch(
        [item.name, item.group_name, item.group_kind, item.kind, item.note].join(" "),
      ).includes(clean),
    );
  }, [menuRows, query]);
  const total = menuRows.reduce(
    (sum, item, index) =>
      sum + (cart[String(recordId(item, index))] ?? 0) * parsePriceAmount(item.price),
    0,
  );

  async function save() {
    showMessage("");
    const items = menuRows.flatMap((item, index) => {
      const itemId = recordId(item, index);
      const quantity = cart[String(itemId)] ?? 0;
      return quantity > 0 ? [{ item_id: Number(itemId), qty: quantity }] : [];
    });
    if (!items.length) {
      showMessage("Kamida bitta mahsulot tanlang.");
      return;
    }
    let saved: BusinessOnlineRecord | null;
    if (orderId) {
      saved = await action("dining_orders", "add_items", orderId, {
        items,
        note: note.trim(),
      });
    } else {
      saved = await action("dining_places", "create_order", recordId(place), {
        items,
        customer_name: customerName.trim(),
        note: note.trim(),
      });
    }
    if (!saved) return;
    const confirmed = orderId
      ? String(saved.id) === String(orderId)
      : numberValue(saved.active_id) > 0;
    if (!confirmed) {
      showMessage("Buyurtma ro‘yxatda tasdiqlanmadi.");
      return;
    }
    await refresh("dining_places", "dining_orders");
    showMessage(
      orderId
        ? "Taomlar shu stol zakaziga qo‘shildi ✅"
        : "Zakaz saqlandi, ichki buyurtma va kassaga yuborildi ✅",
    );
    close();
  }

  return (
    <div className="form-wrap">
      <div className="panel-card" style={{ marginBottom: 10 }}>
        <b>
          {String(place.name ?? "")}
          {orderId ? " — zakazga qo‘shish" : " — yangi zakaz"}
        </b>
        <div className="idesc">Mahsulotlarni + va − orqali tanlang.</div>
      </div>
      <div className="item-search" style={{ marginBottom: 10 }}>
        <span className="ic">🔍</span>
        <input
          type="search"
          value={query}
          placeholder="Mahsulot yoki guruhni qidirish..."
          autoComplete="off"
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <div>
        {!menuRows.length ? (
          <div className="empty">
            <h3>Mahsulot yo'q</h3>
            <p>Avval Mahsulot va xizmatlar bo'limida mahsulot qo'shing.</p>
          </div>
        ) : !visible.length ? (
          <div className="empty" style={{ padding: "35px 16px" }}>
            <h3>Topilmadi</h3>
            <p>Boshqa nom bilan qidirib ko'ring.</p>
          </div>
        ) : (
          visible.map((item, index) => {
            const id = recordId(item, index);
            const quantity = cart[String(id)] ?? 0;
            return (
              <div className="dorder-row" key={String(id)}>
                <div>
                  <b>{String(item.name ?? "")}</b>
                  {Boolean(item.group_name) && (
                    <div className="idesc">{String(item.group_name)}</div>
                  )}
                  <div className="idesc">
                    {legacyMoneyWithSuffix(parsePriceAmount(item.price))}
                    {" · "}
                    {String(item.unit ?? "dona")}
                  </div>
                </div>
                <div className="dorder-step">
                  <button
                    type="button"
                    onClick={() =>
                      setCart((current) => ({
                        ...current,
                        [String(id)]: Math.max(0, quantity - 1),
                      }))
                    }
                  >
                    −
                  </button>
                  <b>{quantity}</b>
                  <button
                    type="button"
                    onClick={() =>
                      setCart((current) => ({
                        ...current,
                        [String(id)]: quantity + 1,
                      }))
                    }
                  >
                    +
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
      <div className="dorder-total">
        <div
          className="panel-card"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 8,
          }}
        >
          <b>Jami</b>
          <b>{legacyMoneyWithSuffix(total)}</b>
        </div>
        {!orderId && (
          <input
            className="input"
            style={{ marginBottom: 8 }}
            value={customerName}
            placeholder="Mijoz ismi — ixtiyoriy"
            onChange={(event) => setCustomerName(event.target.value)}
          />
        )}
        <input
          className="input"
          style={{ marginBottom: 8 }}
          value={note}
          placeholder={orderId ? "Qo‘shimcha izoh — ixtiyoriy" : "Izoh — ixtiyoriy"}
          onChange={(event) => setNote(event.target.value)}
        />
        <button
          className="btn btn-primary btn-block"
          type="button"
          disabled={busy}
          onClick={() => void save()}
        >
          {orderId ? "Zakazga qo‘shish" : "Zakazni saqlash"}
        </button>
      </div>
    </div>
  );
}

export function movePlace(
  event: ReactPointerEvent<HTMLDivElement>,
  id: number | string,
  setPositions: Dispatch<SetStateAction<Record<string, Position>>>,
  drag: MutableRefObject<DragState>,
) {
  if (!drag.current || String(drag.current.id) !== String(id)) return;
  const plan = event.currentTarget.parentElement;
  if (!plan) return;
  const bounds = plan.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const left = Math.max(
    0,
    Math.min(
      bounds.width - event.currentTarget.offsetWidth,
      event.clientX - bounds.left - drag.current.dx,
    ),
  );
  const top = Math.max(
    0,
    Math.min(
      bounds.height - event.currentTarget.offsetHeight,
      event.clientY - bounds.top - drag.current.dy,
    ),
  );
  setPositions((current) => ({
    ...current,
    [String(id)]: {
      x: (left / bounds.width) * 100,
      y: (top / bounds.height) * 100,
    },
  }));
}

export function placeSubtitle(place: BusinessOnlineRecord): string {
  if (place.active_kind === "order") {
    return `Zakaz · ${legacyMoneyText(numberValue(place.total))}`;
  }
  if (place.active_kind === "booking") {
    return `Bron · ${String(place.booking_time ?? "")} ${String(
      place.customer_name ?? "",
    )}`;
  }
  if (place.kind === "table" && numberValue(place.seats)) {
    return `${numberValue(place.seats)} joy`;
  }
  return "Bo'sh";
}

function legacyMoneyText(value: number): string {
  const amount = Math.trunc(value || 0);
  if (!amount) return "";
  return `${String(amount).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} so'm`;
}

function legacyMoneyWithSuffix(value: number): string {
  return `${legacyMoneyText(value)} so'm`;
}

function parsePriceAmount(value: unknown): number {
  const digits = String(value ?? "").replace(/[^0-9]/g, "");
  return digits ? Number.parseInt(digits, 10) || 0 : 0;
}

export function numberValue(value: unknown): number {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
}

function normalizeSearch(value: string): string {
  return value
    .toLocaleLowerCase("uz")
    .replace(/[ʻʼ‘’`]/g, "'")
    .trim();
}
