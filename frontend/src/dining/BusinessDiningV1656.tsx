import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import type { DiningOrder, DiningPlace, DiningPlaceKind } from "../api/types";
import { BusinessDiningV1656View } from "../profiles/BusinessDiningV1656View";


export type BusinessDiningApi = Pick<
  ApiClient,
  | "getDiningPlaces"
  | "getDiningOrders"
  | "createDiningPlace"
  | "updateDiningPlace"
  | "deleteDiningPlace"
  | "clearDiningPlace"
  | "bookDiningPlace"
  | "createDiningOrder"
  | "addDiningOrderItems"
>;

const DINING_METHODS: ReadonlyArray<keyof BusinessDiningApi> = [
  "getDiningPlaces",
  "getDiningOrders",
  "createDiningPlace",
  "updateDiningPlace",
  "deleteDiningPlace",
  "clearDiningPlace",
  "bookDiningPlace",
  "createDiningOrder",
  "addDiningOrderItems",
];

export function supportsDiningApi(api: object): api is BusinessDiningApi {
  return DINING_METHODS.every((method) => (
    typeof (api as Partial<BusinessDiningApi>)[method] === "function"
  ));
}

type Props = {
  api: BusinessDiningApi;
  /** Menyu katalogdan keladi — u alohida domen, o'zgarmaydi. */
  menuItems: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  onBackHandlerChange: (handler: (() => void) | null) => void;
};


function text(value: unknown, fallback = "") {
  return typeof value === "string" && value ? value : fallback;
}

function number(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function placeKind(value: unknown): DiningPlaceKind {
  return value === "room" ? "room" : "table";
}

/** Stolga tegishli faol yozuv — v1656 `sync_dining_place_activity`. */
function activityOf(place: DiningPlace, orders: DiningOrder[]) {
  const active = orders.filter(
    (order) => order.place_id === place.id && order.status === "active",
  );
  const order = active.find((row) => row.kind === "order");
  if (order) {
    return {
      active_kind: "order",
      active_id: order.id,
      total: order.total,
      booking_time: "",
      customer_name: order.customer_name,
    };
  }
  const booking = active.find((row) => row.kind === "booking");
  if (booking) {
    return {
      active_kind: "booking",
      active_id: booking.id,
      total: 0,
      booking_time: booking.booking_time,
      customer_name: booking.customer_name,
    };
  }
  return {
    active_kind: "",
    active_id: 0,
    total: 0,
    booking_time: "",
    customer_name: "",
  };
}

function placeRecord(
  place: DiningPlace,
  orders: DiningOrder[],
): BusinessOnlineRecord {
  return {
    id: place.id,
    kind: place.kind,
    name: place.name,
    seats: place.seats,
    x: place.x,
    y: place.y,
    // Eski ekran `locked` ni son sifatida o'qiydi.
    locked: place.locked ? 1 : 0,
    ...activityOf(place, orders),
  } as BusinessOnlineRecord;
}

function orderRecord(order: DiningOrder): BusinessOnlineRecord {
  return {
    id: order.id,
    place_id: order.place_id,
    kind: order.kind,
    customer_name: order.customer_name,
    note: order.note,
    total: order.total,
    kitchen_status: order.kitchen_status,
    payment_status: order.payment_status,
    status: order.status,
    items: order.items.map((item) => ({
      id: item.id,
      item_id: item.item_id,
      name: item.name,
      qty: item.qty,
      unit: item.unit,
      price: item.price,
      total: item.total,
    })),
  } as unknown as BusinessOnlineRecord;
}

/** Ekran yuboradigan yozuvni `DiningPlaceWrite` ga aylantiradi. */
function placeWrite(record: BusinessOnlineRecord) {
  return {
    kind: placeKind(record.kind),
    name: text(record.name, "Stol"),
    seats: Math.max(0, Math.trunc(number(record.seats))),
    x: number(record.x, 4),
    y: number(record.y, 4),
    locked: number(record.locked, 1) !== 0,
  };
}

function itemInputs(payload: BusinessOnlineRecord | undefined) {
  const raw = (payload as { items?: unknown } | undefined)?.items;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((entry) => {
    const value = entry as { item_id?: unknown; qty?: unknown };
    const itemId = Number(value.item_id);
    const qty = Number(value.qty);
    if (!Number.isFinite(itemId) || itemId <= 0) return [];
    if (!Number.isFinite(qty) || qty <= 0) return [];
    return [{ item_id: itemId, qty }];
  });
}


export function BusinessDiningV1656({
  api,
  menuItems,
  groups,
  onBackHandlerChange,
}: Props) {
  const [places, setPlaces] = useState<DiningPlace[]>([]);
  const [orders, setOrders] = useState<DiningOrder[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextPlaces, nextOrders] = await Promise.all([
        api.getDiningPlaces(),
        api.getDiningOrders(),
      ]);
      setPlaces(nextPlaces);
      setOrders(nextOrders);
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Zal rejasi yuklanmadi.",
      );
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!error) return;
    const timeout = window.setTimeout(() => setError(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [error]);

  async function guard<T>(action: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setError("");
    try {
      return await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "So‘rov bajarilmadi.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function createPlace(record: BusinessOnlineRecord) {
    const saved = await guard(() => api.createDiningPlace(placeWrite(record)));
    if (saved) setPlaces((rows) => [...rows, saved]);
    return saved !== null;
  }

  async function patchPlace(
    id: number | string,
    patch: BusinessOnlineRecord,
  ) {
    const current = places.find((place) => String(place.id) === String(id));
    if (!current) return false;
    // Ekran faqat o'zgargan maydonlarni yuboradi (surishda x/y).
    const merged = placeWrite({
      kind: patch.kind ?? current.kind,
      name: patch.name ?? current.name,
      seats: patch.seats ?? current.seats,
      x: patch.x ?? current.x,
      y: patch.y ?? current.y,
      locked: patch.locked ?? (current.locked ? 1 : 0),
    } as BusinessOnlineRecord);
    const saved = await guard(
      () => api.updateDiningPlace(Number(id), merged),
    );
    if (saved) {
      setPlaces((rows) => rows.map(
        (place) => (place.id === saved.id ? saved : place),
      ));
    }
    return saved !== null;
  }

  async function removePlace(id: number | string) {
    const done = await guard(async () => {
      await api.deleteDiningPlace(Number(id));
      return true;
    });
    if (done) {
      setPlaces((rows) => rows.filter(
        (place) => String(place.id) !== String(id),
      ));
    }
    return done !== null;
  }

  async function action(
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ): Promise<BusinessOnlineRecord | null> {
    if (id === undefined) return null;

    if (resource === "dining_places" && name === "book") {
      const saved = await guard(() => api.bookDiningPlace(Number(id), {
        customer_name: text(payload?.customer_name),
        booking_date: text(payload?.booking_date),
        booking_time: text(payload?.booking_time),
        phone: text(payload?.phone),
        guests: Math.max(1, Math.trunc(number(payload?.guests, 1))),
        note: text(payload?.note),
      }));
      if (!saved) return null;
      await load();
      return orderRecord(saved);
    }

    if (resource === "dining_places" && name === "create_order") {
      const saved = await guard(() => api.createDiningOrder(Number(id), {
        items: itemInputs(payload),
        customer_name: text(payload?.customer_name),
        note: text(payload?.note),
      }));
      if (!saved) return null;
      await load();
      return orderRecord(saved);
    }

    if (resource === "dining_places" && name === "clear") {
      const done = await guard(async () => {
        await api.clearDiningPlace(Number(id));
        return true;
      });
      if (!done) return null;
      await load();
      return {} as BusinessOnlineRecord;
    }

    if (resource === "dining_orders" && name === "add_items") {
      const saved = await guard(
        () => api.addDiningOrderItems(Number(id), itemInputs(payload)),
      );
      if (!saved) return null;
      await load();
      return orderRecord(saved);
    }

    return null;
  }

  const placeRecords = places.map((place) => placeRecord(place, orders));

  return (
    <>
      {error ? (
        <div className="dining-load-error" role="status">{error}</div>
      ) : null}
      <BusinessDiningV1656View
        places={placeRecords}
        menuItems={menuItems}
        groups={groups}
        busy={busy}
        createPlace={createPlace}
        patchPlace={patchPlace}
        removePlace={removePlace}
        action={action}
        refresh={async () => { await load(); }}
        onBackHandlerChange={onBackHandlerChange}
      />
    </>
  );
}
