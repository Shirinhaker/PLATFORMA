import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { recordId } from "./BusinessOnlineViews";
import {
  DiningBookingForm,
  DiningConfirm,
  DiningModal,
  DiningPlaceForm,
  type DiningModalState as Modal,
} from "./BusinessDiningDialogs";
import {
  DiningOrderView,
  movePlace,
  numberValue,
  placeSubtitle,
  type DiningAction,
  type DragState,
  type Position,
} from "./BusinessDiningOrderView";
import "./BusinessDiningView.css";

type Props = {
  places: BusinessOnlineRecord[];
  menuItems: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  busy: boolean;
  createPlace: (record: BusinessOnlineRecord) => Promise<boolean>;
  patchPlace: (id: number | string, patch: BusinessOnlineRecord) => Promise<boolean>;
  removePlace: (id: number | string) => Promise<boolean>;
  action: DiningAction;
  refresh: (...resources: BusinessOnlineResource[]) => Promise<void>;
  onBackHandlerChange: (handler: (() => void) | null) => void;
};

export function BusinessDiningView({
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

  const selectedMenuPlace =
    places.find((place, index) => String(recordId(place, index)) === String(menuId)) ??
    null;

  function showMessage(value: string) {
    setFeedback(value);
  }

  function closeOrder() {
    setOrderPlace(null);
    setPositions({});
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
          <div className="app-toast on" role="alert">
            {feedback}
          </div>
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
        <div className="app-toast on" role="alert">
          {feedback}
        </div>
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
            ]
              .filter(Boolean)
              .join(" ");
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
            🛒{" "}
            {selectedMenuPlace.active_kind === "order"
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
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 10,
              margin: "15px 0",
            }}
          >
            <button
              className="btn btn-soft"
              type="button"
              style={{ height: 74, fontSize: 17 }}
              onClick={() =>
                setModal({
                  kind: "form",
                  placeKind: "table",
                  place: null,
                })
              }
            >
              🪑 Stol
            </button>
            <button
              className="btn btn-soft"
              type="button"
              style={{ height: 74, fontSize: 17 }}
              onClick={() =>
                setModal({
                  kind: "form",
                  placeKind: "room",
                  place: null,
                })
              }
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
