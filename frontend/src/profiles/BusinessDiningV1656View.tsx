import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { recordId } from "./BusinessOnlineViews";
import "./BusinessDiningV1656View.css";


type DiningAction = (
  resource: BusinessOnlineResource,
  name: string,
  id?: number | string,
  payload?: BusinessOnlineRecord,
) => Promise<BusinessOnlineRecord | null>;

type Props = {
  places: BusinessOnlineRecord[];
  menuItems: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  busy: boolean;
  createPlace: (record: BusinessOnlineRecord) => Promise<boolean>;
  patchPlace: (
    id: number | string,
    patch: BusinessOnlineRecord,
  ) => Promise<boolean>;
  removePlace: (id: number | string) => Promise<boolean>;
  action: DiningAction;
  refresh: (...resources: BusinessOnlineResource[]) => Promise<void>;
  onBackHandlerChange: (handler: (() => void) | null) => void;
};

type Modal =
  | { kind: "choose" }
  | {
    kind: "form";
    placeKind: "table" | "room";
    place: BusinessOnlineRecord | null;
  }
  | { kind: "booking"; place: BusinessOnlineRecord }
  | { kind: "delete"; place: BusinessOnlineRecord }
  | { kind: "clear"; place: BusinessOnlineRecord };

type Position = { x: number; y: number };
type DragState = {
  id: number | string;
  dx: number;
  dy: number;
} | null;


export function BusinessDiningV1656View({
  places,
  menuItems,
  groups,
  busy,
  createPlace,
  patchPlace,
  removePlace,
  action,
  refresh,
  onBackHandlerChange,
}: Props) {
  const [modal, setModal] = useState<Modal | null>(null);
  const [menuId, setMenuId] = useState<number | string | null>(null);
  const [movingId, setMovingId] = useState<number | string | null>(null);
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const [orderPlace, setOrderPlace] = useState<BusinessOnlineRecord | null>(null);
  const [feedback, setFeedback] = useState("");
  const drag = useRef<DragState>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = useState({ left: 8, top: 8 });

  const selectedMenuPlace = places.find(
    (place, index) => String(recordId(place, index)) === String(menuId),
  ) ?? null;

  function showMessage(value: string) {
    setFeedback(value);
  }

  function closeOrder() {
    setOrderPlace(null);
    onBackHandlerChange(null);
  }

  function openOrder(place: BusinessOnlineRecord) {
    setMenuId(null);
    setOrderPlace(place);
    setFeedback("");
    onBackHandlerChange(closeOrder);
  }

  useEffect(() => {
    if (!feedback) return;
    const timeout = window.setTimeout(() => setFeedback(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [feedback]);

  useEffect(() => {
    if (!selectedMenuPlace) return;
    const close = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node)) setMenuId(null);
    };
    document.addEventListener("pointerdown", close, true);
    return () => document.removeEventListener("pointerdown", close, true);
  }, [selectedMenuPlace]);

  useLayoutEffect(() => {
    if (!selectedMenuPlace || !menu.current) return;
    const height = menu.current.offsetHeight;
    setMenuPosition((current) => ({
      left: current.left,
      top: Math.max(8, Math.min(window.innerHeight - height - 8, current.top)),
    }));
  }, [selectedMenuPlace]);

  if (orderPlace) {
    return (
      <div className="business-dining-v1656">
        {feedback && (
          <div className="app-toast on" role="alert">{feedback}</div>
        )}
        <DiningOrderView
          place={orderPlace}
          rows={menuItems}
          groups={groups}
          busy={busy}
          action={action}
          refresh={refresh}
          close={closeOrder}
          showMessage={showMessage}
        />
      </div>
    );
  }

  return (
    <div className="business-dining-v1656">
      {feedback && (
        <div className="app-toast on" role="alert">{feedback}</div>
      )}
      <div className="dining-wrap">
        <div className="dining-toolbar">
          <button
            className="dining-add"
            type="button"
            aria-label="Stol yoki xona qo'shish"
            onClick={() => {
              setFeedback("");
              setModal({ kind: "choose" });
            }}
          >
            +
          </button>
          <div>
            <b>Zal rejasi</b>
            <div className="idesc">
              Belgini harakatlantirish uchun uch nuqtali menyuni oching.
            </div>
          </div>
        </div>
        <div className="dining-plan">
          <div
            className="dining-empty"
            style={{ display: places.length ? "none" : "flex" }}
          >
            Hozircha stol yoki xona yo'q.
            <br />
            Yuqoridagi + tugmasini bosing.
          </div>
          {places.map((place, index) => {
            const id = recordId(place, index);
            const position = positions[String(id)] ?? {
              x: numberValue(place.x),
              y: numberValue(place.y),
            };
            const activeKind = String(place.active_kind ?? "");
            const placeKind = String(place.kind ?? "table");
            const isMoving = String(movingId) === String(id);
            const canMove = isMoving || !Boolean(numberValue(place.locked));
            const classes = [
              "dining-place",
              placeKind === "room" ? "room" : "",
              activeKind,
              canMove ? "moving" : "",
            ].filter(Boolean).join(" ");
            return (
              <div
                className={classes}
                key={String(id)}
                style={{ left: `${position.x}%`, top: `${position.y}%` }}
                onPointerDown={(event) => {
                  if (!canMove || (event.target as Element).closest("button")) {
                    return;
                  }
                  const bounds = event.currentTarget.getBoundingClientRect();
                  drag.current = {
                    id,
                    dx: event.clientX - bounds.left,
                    dy: event.clientY - bounds.top,
                  };
                  event.currentTarget.setPointerCapture?.(event.pointerId);
                  event.preventDefault();
                }}
                onPointerMove={(event) => movePlace(event, id, setPositions, drag)}
                onPointerUp={() => {
                  drag.current = null;
                }}
                onPointerCancel={() => {
                  drag.current = null;
                }}
              >
                <button
                  className="dp-more"
                  type="button"
                  aria-label="Menyu"
                  onClick={(event) => {
                    event.stopPropagation();
                    const bounds = event.currentTarget.getBoundingClientRect();
                    setMenuPosition({
                      left: Math.max(
                        8,
                        Math.min(window.innerWidth - 208, bounds.right - 200),
                      ),
                      top: Math.max(
                        8,
                        Math.min(window.innerHeight - 16, bounds.bottom + 4),
                      ),
                    });
                    setMenuId(id);
                  }}
                >
                  ⋮
                </button>
                <div className="dp-icon">{placeKind === "room" ? "🚪" : "🪑"}</div>
                <div className="dp-name">{String(place.name ?? "")}</div>
                <div className="dp-sub">{placeSubtitle(place)}</div>
              </div>
            );
          })}
        </div>
      </div>

      {selectedMenuPlace && (
        <div
          className="dining-menu"
          ref={menu}
          style={{ left: menuPosition.left, top: menuPosition.top }}
        >
          <button type="button" onClick={() => openOrder(selectedMenuPlace)}>
            🛒 {selectedMenuPlace.active_kind === "order"
              ? "Zakazga taom qo‘shish"
              : "Zakaz qilish"}
          </button>
          <button
            type="button"
            onClick={() => {
              setMenuId(null);
              setModal({ kind: "booking", place: selectedMenuPlace });
            }}
          >
            📅 Bron qilish
          </button>
          {Boolean(selectedMenuPlace.active_id) && (
            <button
              type="button"
              onClick={() => {
                setMenuId(null);
                setModal({ kind: "clear", place: selectedMenuPlace });
              }}
            >
              ✅ Bo'shatish
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setMovingId(recordId(selectedMenuPlace));
              setMenuId(null);
              showMessage("Belgini bosib ushlab, kerakli joyga suring.");
            }}
          >
            ✥ Harakatlantirish
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setFeedback("");
              const id = recordId(selectedMenuPlace);
              const position = positions[String(id)] ?? {
                x: numberValue(selectedMenuPlace.x),
                y: numberValue(selectedMenuPlace.y),
              };
              const saved = await patchPlace(id, { ...position, locked: 1 });
              if (!saved) return;
              setMovingId(null);
              setMenuId(null);
              showMessage("Joylashuv qotirildi ✅");
            }}
          >
            🔒 Qotirish
          </button>
          <button
            type="button"
            onClick={() => {
              setMenuId(null);
              setModal({
                kind: "form",
                placeKind: selectedMenuPlace.kind === "room" ? "room" : "table",
                place: selectedMenuPlace,
              });
            }}
          >
            ✏️ Tahrirlash
          </button>
          <button
            type="button"
            style={{ color: "#DC2626" }}
            onClick={() => {
              setMenuId(null);
              setModal({ kind: "delete", place: selectedMenuPlace });
            }}
          >
            🗑 O'chirish
          </button>
        </div>
      )}

      {modal?.kind === "choose" && (
        <DiningModal close={() => setModal(null)}>
          <div className="acf-title">Nima qo'shamiz?</div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 10,
            margin: "15px 0",
          }}>
            <button
              className="btn btn-soft"
              type="button"
              style={{ height: 74, fontSize: 17 }}
              onClick={() => setModal({
                kind: "form",
                placeKind: "table",
                place: null,
              })}
            >
              🪑 Stol
            </button>
            <button
              className="btn btn-soft"
              type="button"
              style={{ height: 74, fontSize: 17 }}
              onClick={() => setModal({
                kind: "form",
                placeKind: "room",
                place: null,
              })}
            >
              🚪 Xona
            </button>
          </div>
          <button
            className="btn btn-outline btn-block"
            type="button"
            onClick={() => setModal(null)}
          >
            Bekor qilish
          </button>
        </DiningModal>
      )}
      {modal?.kind === "form" && (
        <DiningPlaceForm
          modal={modal}
          busy={busy}
          close={() => setModal(null)}
          save={async (record) => {
            setFeedback("");
            let saved: boolean;
            if (modal.place) {
              saved = await patchPlace(recordId(modal.place), record);
            } else {
              saved = await createPlace(record);
            }
            if (!saved) return;
            setModal(null);
            showMessage("Saqlandi ✅");
          }}
          showMessage={showMessage}
        />
      )}
      {modal?.kind === "booking" && (
        <DiningBookingForm
          place={modal.place}
          busy={busy}
          close={() => setModal(null)}
          save={async (record) => {
            setFeedback("");
            const saved = await action(
              "dining_places",
              "book",
              recordId(modal.place),
              record,
            );
            if (!saved) return;
            setModal(null);
            showMessage("Bron saqlandi ✅");
          }}
          showMessage={showMessage}
        />
      )}
      {modal?.kind === "delete" && (
        <DiningConfirm
          text={`${String(modal.place.name ?? "")} o'chirilsinmi?`}
          okText="O'chirish"
          danger
          busy={busy}
          close={() => setModal(null)}
          confirm={async () => {
            setFeedback("");
            const removed = await removePlace(recordId(modal.place));
            if (!removed) return;
            setModal(null);
            showMessage("O'chirildi");
          }}
        />
      )}
      {modal?.kind === "clear" && (
        <DiningConfirm
          text={`${String(modal.place.name ?? "")} bo'shatilsinmi? Faol zakaz va bron yakunlanadi.`}
          okText="Bo'shatish"
          busy={busy}
          close={() => setModal(null)}
          confirm={async () => {
            setFeedback("");
            const cleared = await action(
              "dining_places",
              "clear",
              recordId(modal.place),
            );
            if (!cleared) return;
            await refresh("dining_places", "dining_orders");
            setModal(null);
            showMessage("Bo'shatildi ✅");
          }}
        />
      )}
    </div>
  );
}


function DiningModal({
  children,
  close,
}: {
  children: React.ReactNode;
  close: () => void;
}) {
  return (
    <>
      <div className="app-modal-back on" onClick={close} />
      <div
        className="app-confirm on"
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </>
  );
}


function DiningPlaceForm({
  modal,
  busy,
  close,
  save,
  showMessage,
}: {
  modal: Extract<Modal, { kind: "form" }>;
  busy: boolean;
  close: () => void;
  save: (record: BusinessOnlineRecord) => Promise<void>;
  showMessage: (value: string) => void;
}) {
  const isTable = modal.placeKind === "table";
  const [name, setName] = useState(String(modal.place?.name ?? ""));
  const [seats, setSeats] = useState(
    modal.place?.seats ? String(modal.place.seats) : "",
  );
  return (
    <DiningModal close={close}>
      <div className="acf-title">
        {modal.place ? "Tahrirlash" : (isTable ? "Yangi stol" : "Yangi xona")}
      </div>
      <div style={{
        margin: "12px 2px 4px",
        fontSize: 13,
        color: "var(--koprik-soft)",
        textAlign: "left",
      }}>
        {isTable ? "Stol raqami yoki nomi" : "Xona nomi"}
      </div>
      <input
        className="input"
        maxLength={60}
        value={name}
        autoFocus
        placeholder={isTable ? "Masalan: Stol 1" : "Masalan: VIP xona"}
        onChange={(event) => setName(event.target.value)}
      />
      {isTable && (
        <>
          <div style={{
            margin: "10px 2px 4px",
            fontSize: 13,
            color: "var(--koprik-soft)",
            textAlign: "left",
          }}>
            O'rindiqlar soni
          </div>
          <input
            className="input"
            inputMode="numeric"
            value={seats}
            placeholder="4"
            onChange={(event) => setSeats(event.target.value)}
          />
        </>
      )}
      <div className="acf-btns">
        <button className="acf-cancel" type="button" onClick={close}>
          Bekor qilish
        </button>
        <button
          className="acf-ok"
          type="button"
          disabled={busy}
          onClick={() => {
            const cleanName = name.trim();
            if (!cleanName) {
              showMessage(isTable
                ? "Stol nomini kiriting."
                : "Xona nomini kiriting.");
              return;
            }
            void save({
              kind: modal.placeKind,
              name: cleanName,
              seats: isTable ? Number.parseInt(seats || "0", 10) || 0 : 0,
            });
          }}
        >
          Saqlash
        </button>
      </div>
    </DiningModal>
  );
}


function DiningBookingForm({
  place,
  busy,
  close,
  save,
  showMessage,
}: {
  place: BusinessOnlineRecord;
  busy: boolean;
  close: () => void;
  save: (record: BusinessOnlineRecord) => Promise<void>;
  showMessage: (value: string) => void;
}) {
  const today = todayYmd();
  const [customerName, setCustomerName] = useState("");
  const [phone, setPhone] = useState("");
  const [bookingDate, setBookingDate] = useState(today);
  const [bookingTime, setBookingTime] = useState("");
  const [guests, setGuests] = useState("");
  const [note, setNote] = useState("");
  return (
    <DiningModal close={close}>
      <div className="acf-title">
        📅 {String(place.name ?? "")} — bron
      </div>
      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <input
          className="input"
          value={customerName}
          placeholder="Mijoz ismi"
          onChange={(event) => setCustomerName(event.target.value)}
        />
        <input
          className="input"
          inputMode="tel"
          value={phone}
          placeholder="Telefon raqami"
          onChange={(event) => setPhone(event.target.value)}
        />
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
        }}>
          <input
            className="input"
            type="date"
            min={today}
            value={bookingDate}
            onChange={(event) => setBookingDate(event.target.value)}
          />
          <input
            className="input"
            type="time"
            value={bookingTime}
            onChange={(event) => setBookingTime(event.target.value)}
          />
        </div>
        <input
          className="input"
          inputMode="numeric"
          value={guests}
          placeholder="Mehmonlar soni"
          onChange={(event) => setGuests(event.target.value)}
        />
        <input
          className="input"
          value={note}
          placeholder="Izoh — ixtiyoriy"
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
      <div className="acf-btns">
        <button className="acf-cancel" type="button" onClick={close}>
          Bekor qilish
        </button>
        <button
          className="acf-ok"
          type="button"
          disabled={busy}
          onClick={() => {
            const customer = customerName.trim();
            if (!customer || !bookingDate || !bookingTime) {
              showMessage("Mijoz ismi, sana va vaqtni kiriting.");
              return;
            }
            void save({
              customer_name: customer,
              phone: phone.trim(),
              booking_date: bookingDate,
              booking_time: bookingTime,
              guests: Number.parseInt(guests || "1", 10) || 1,
              note: note.trim(),
            });
          }}
        >
          Bron qilish
        </button>
      </div>
    </DiningModal>
  );
}


function DiningConfirm({
  text,
  okText,
  danger = false,
  busy,
  close,
  confirm,
}: {
  text: string;
  okText: string;
  danger?: boolean;
  busy: boolean;
  close: () => void;
  confirm: () => Promise<void>;
}) {
  return (
    <DiningModal close={close}>
      <div className="acf-text">{text}</div>
      <div className="acf-btns">
        <button className="acf-cancel" type="button" onClick={close}>
          Bekor qilish
        </button>
        <button
          className={`acf-ok${danger ? " danger" : ""}`}
          type="button"
          disabled={busy}
          onClick={() => void confirm()}
        >
          {okText}
        </button>
      </div>
    </DiningModal>
  );
}


function DiningOrderView({
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
  const orderId = place.active_kind === "order"
    ? numberValue(place.active_id)
    : 0;
  const [query, setQuery] = useState("");
  const [cart, setCart] = useState<Record<string, number>>({});
  const [customerName, setCustomerName] = useState("");
  const [note, setNote] = useState("");
  const groupNames = useMemo(
    () => new Map(groups.map((group, index) => [
      String(recordId(group, index)),
      String(group.name ?? ""),
    ])),
    [groups],
  );
  const menuRows = useMemo<BusinessOnlineRecord[]>(
    () => rows.filter(
      (row) => String(row.stock_type ?? "ready_food") === "ready_food",
    ).map((row): BusinessOnlineRecord => {
      const groupName = row.group_name
        ?? groupNames.get(String(row.group_id ?? row.item_group_id ?? ""));
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
    return menuRows.filter((item) => normalizeSearch([
      item.name,
      item.group_name,
      item.group_kind,
      item.kind,
      item.note,
    ].join(" ")).includes(clean));
  }, [menuRows, query]);
  const total = menuRows.reduce(
    (sum, item, index) => sum
      + (cart[String(recordId(item, index))] ?? 0)
      * parsePriceAmount(item.price),
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
    showMessage(orderId
      ? "Taomlar shu stol zakaziga qo‘shildi ✅"
      : "Zakaz saqlandi, ichki buyurtma va kassaga yuborildi ✅");
    close();
  }

  return (
    <div className="form-wrap">
      <div className="panel-card" style={{ marginBottom: 10 }}>
        <b>{String(place.name ?? "")}{orderId
          ? " — zakazga qo‘shish"
          : " — yangi zakaz"}</b>
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
            <p>
              Avval Mahsulot va xizmatlar bo'limida mahsulot qo'shing.
            </p>
          </div>
        ) : !visible.length ? (
          <div className="empty" style={{ padding: "35px 16px" }}>
            <h3>Topilmadi</h3>
            <p>Boshqa nom bilan qidirib ko'ring.</p>
          </div>
        ) : visible.map((item, index) => {
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
                  onClick={() => setCart((current) => ({
                    ...current,
                    [String(id)]: Math.max(0, quantity - 1),
                  }))}
                >
                  −
                </button>
                <b>{quantity}</b>
                <button
                  type="button"
                  onClick={() => setCart((current) => ({
                    ...current,
                    [String(id)]: quantity + 1,
                  }))}
                >
                  +
                </button>
              </div>
            </div>
          );
        })}
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
          placeholder={orderId
            ? "Qo‘shimcha izoh — ixtiyoriy"
            : "Izoh — ixtiyoriy"}
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


function movePlace(
  event: ReactPointerEvent<HTMLDivElement>,
  id: number | string,
  setPositions: React.Dispatch<React.SetStateAction<Record<string, Position>>>,
  drag: React.MutableRefObject<DragState>,
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
      x: left / bounds.width * 100,
      y: top / bounds.height * 100,
    },
  }));
}


function placeSubtitle(place: BusinessOnlineRecord): string {
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


function numberValue(value: unknown): number {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
}


function normalizeSearch(value: string): string {
  return value
    .toLocaleLowerCase("uz")
    .replace(/[ʻʼ‘’`]/g, "'")
    .trim();
}


function todayYmd(): string {
  const today = new Date();
  return [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");
}
