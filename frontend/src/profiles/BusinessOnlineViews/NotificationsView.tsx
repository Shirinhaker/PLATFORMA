// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";
import { notifyTime, recordId, recordText } from "./shared";

export function NotificationsView({
  rows,
  filters = [],
  pushPreference,
  busy,
  markAll,
  markOne,
  createFilter,
  removeFilter,
  savePushPreference,
  onOpenOrder,
}: {
  rows: BusinessOnlineRecord[];
  filters?: BusinessOnlineRecord[];
  pushPreference?: BusinessOnlineRecord;
  busy: boolean;
  markAll: () => Promise<void>;
  markOne: (id: number | string) => Promise<void>;
  createFilter?: (record: BusinessOnlineRecord) => Promise<void>;
  removeFilter?: (id: number | string) => Promise<void>;
  savePushPreference?: (enabled: boolean) => Promise<void>;
  onOpenOrder?: (orderId: number) => void | Promise<void>;
}) {
  const serverPushEnabled = pushPreference
    ? Boolean(pushPreference.enabled) && Boolean(pushPreference.orders_enabled)
    : true;
  const [pushEnabled, setPushEnabled] = useState(serverPushEnabled);
  const [formOpen, setFormOpen] = useState(false);
  const [filterDraft, setFilterDraft] = useState<BusinessOnlineRecord>({ cat: "uy" });
  const [deleteFilter, setDeleteFilter] = useState<number | string | null>(null);
  const categories: Record<string, [string, string]> = {
    uy: ["🏠", "Uy-joy"],
    ish: ["💼", "Ish o'rinlari"],
    moshina: ["🚙", "Moshinalar"],
    hayvon: ["🐾", "Hayvonlar"],
    texnika: ["📱", "Texnika"],
    boshqa: ["📦", "Boshqalar"],
  };

  useEffect(() => {
    setPushEnabled(serverPushEnabled);
  }, [serverPushEnabled]);

  if (formOpen) {
    return (
      <section className="form-wrap notify-filter-form">
        <div className="lead">Yangi filtr</div>
        <div className="lead-sub">
          Faqat sizga kerakli e'lonlar haqida xabar olasiz.
        </div>
        <label className="field">
          Tur (majburiy)
          <select
            className="input"
            value={recordText(filterDraft, "cat") || "uy"}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, cat: event.currentTarget.value })
            }
          >
            {Object.entries(categories).map(([key, [icon, label]]) => (
              <option value={key} key={key}>
                {icon} {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Viloyat — ixtiyoriy
          <input
            className="input"
            value={recordText(filterDraft, "region")}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, region: event.currentTarget.value })
            }
          />
        </label>
        <label className="field">
          Tuman — ixtiyoriy
          <input
            className="input"
            value={recordText(filterDraft, "district")}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, district: event.currentTarget.value })
            }
          />
        </label>
        <div className="field">
          <label>Narx oralig'i — ixtiyoriy</label>
          <div className="notify-filter-prices">
            <input
              className="input"
              inputMode="numeric"
              aria-label="Narx dan"
              placeholder="dan (masalan 1000)"
              value={recordText(filterDraft, "price_min")}
              onChange={(event) =>
                setFilterDraft({ ...filterDraft, price_min: event.currentTarget.value })
              }
            />
            <input
              className="input"
              inputMode="numeric"
              aria-label="Narx gacha"
              placeholder="gacha (masalan 5000)"
              value={recordText(filterDraft, "price_max")}
              onChange={(event) =>
                setFilterDraft({ ...filterDraft, price_max: event.currentTarget.value })
              }
            />
          </div>
          <div className="idesc">
            Raqamlarda kiriting (dollar yoki so'm — e'lon narxiga qarab)
          </div>
        </div>
        <label className="field">
          Kalit so'z — ixtiyoriy
          <input
            className="input"
            placeholder="masalan: mushuk, Nexia, dasturchi"
            value={recordText(filterDraft, "keyword")}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, keyword: event.currentTarget.value })
            }
          />
        </label>
        <button
          type="button"
          className="btn btn-primary btn-block"
          disabled={busy}
          onClick={async () => {
            await createFilter?.({
              cat: recordText(filterDraft, "cat") || "uy",
              region: recordText(filterDraft, "region").trim(),
              district: recordText(filterDraft, "district").trim(),
              price_min: Number(filterDraft.price_min ?? 0) || 0,
              price_max: Number(filterDraft.price_max ?? 0) || 0,
              keyword: recordText(filterDraft, "keyword").trim(),
            });
            setFormOpen(false);
            setFilterDraft({ cat: "uy" });
          }}
        >
          Saqlash
        </button>
        <button
          type="button"
          className="btn btn-soft btn-block"
          onClick={() => setFormOpen(false)}
        >
          Bekor qilish
        </button>
      </section>
    );
  }

  return (
    <section className="form-wrap notify-v1656">
      <div className="lead">Bildirishnomalarim</div>
      <div className="lead-sub">
        Buyurtma jarayonidagi muhim xabarlar shu yerda saqlanadi.
      </div>
      <div className="set-row notify-push-row">
        <span>📲 Push notification</span>
        <label>
          <input
            type="checkbox"
            checked={pushEnabled}
            disabled={busy}
            onChange={(event) => {
              const enabled = event.currentTarget.checked;
              setPushEnabled(enabled);
              void savePushPreference?.(enabled);
            }}
          />{" "}
          Yoqilgan
        </label>
      </div>
      <div className="elon-hint">Mobil ilova qurilmasi ulanmagan.</div>
      <div className="notify-v1656-head">
        <b>Buyurtma bildirishnomalari</b>
        <button
          type="button"
          className="mini-btn"
          disabled={busy}
          onClick={() => void markAll()}
        >
          Barchasini o'qish
        </button>
      </div>
      <div className="order-notify-list">
        {rows.length ? (
          rows.map((row, index) => {
            const read = Boolean(Number(row.is_read ?? 0));
            return (
              <button
                type="button"
                className="menu-card"
                style={!read ? { borderColor: "var(--koprik-primary)" } : undefined}
                key={String(recordId(row, index))}
                disabled={busy}
                onClick={async () => {
                  await markOne(recordId(row, index));
                  const orderId = Number(row.order_id ?? 0);
                  if (orderId) await onOpenOrder?.(orderId);
                }}
              >
                <span className="menu-ic">{read ? "🔔" : "🟢"}</span>
                <span className="menu-main">
                  <b>{recordText(row, "title", "name") || "Bildirishnoma"}</b>
                  <span>{recordText(row, "body", "message", "text")}</span>
                  <small>{notifyTime(row.created_at)}</small>
                </span>
                <span className="chev">›</span>
              </button>
            );
          })
        ) : (
          <div className="empty notify-empty">
            <h3>Hozircha xabar yo'q</h3>
            <p>Buyurtma yangiliklari shu yerda chiqadi.</p>
          </div>
        )}
      </div>
      <div className="notify-divider" />
      <div className="lead notify-filter-title">E'lon filtrlari</div>
      <div className="lead-sub">
        Mos e'lon joylanganda Telegramingizga xabar keladi.
      </div>
      <button
        type="button"
        className="btn btn-primary btn-block"
        onClick={() => setFormOpen(true)}
      >
        ➕ Yangi filtr qo'shish
      </button>
      {filters.length ? (
        <div className="notify-filter-list">
          {filters.map((filter, index) => {
            const id = recordId(filter, index);
            const [icon, label] = categories[recordText(filter, "cat")] ?? [
              "📦",
              recordText(filter, "cat"),
            ];
            const parts = [];
            if (recordText(filter, "district"))
              parts.push(recordText(filter, "district"));
            else if (recordText(filter, "region"))
              parts.push(recordText(filter, "region"));
            if (Number(filter.price_min ?? 0) || Number(filter.price_max ?? 0)) {
              parts.push(`${filter.price_min || "0"}–${filter.price_max || "∞"}`);
            }
            if (recordText(filter, "keyword"))
              parts.push(`«${recordText(filter, "keyword")}»`);
            return (
              <div className="menu-card" key={String(id)}>
                <div className="menu-ic">{icon}</div>
                <div className="menu-main">
                  <h4>{label}</h4>
                  <p>{parts.join(" · ") || "Barcha e'lonlar"}</p>
                </div>
                <button
                  type="button"
                  className="panel-x"
                  aria-label="Filtrni o'chirish"
                  onClick={() => setDeleteFilter(id)}
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="empty notify-filter-empty">
          <h3>Filtr yo'q</h3>
          <p>«Yangi filtr» orqali qiziqishlaringizni belgilang.</p>
        </div>
      )}
      {deleteFilter !== null && (
        <>
          <button
            type="button"
            className="app-modal-back on"
            aria-label="Bekor qilish"
            onClick={() => setDeleteFilter(null)}
          />
          <div className="app-confirm on" role="dialog" aria-modal="true">
            <p className="acf-text">Bu filtrni o'chirasizmi?</p>
            <div className="acf-btns">
              <button
                type="button"
                className="acf-cancel"
                onClick={() => setDeleteFilter(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="acf-ok danger"
                disabled={busy}
                onClick={async () => {
                  await removeFilter?.(deleteFilter);
                  setDeleteFilter(null);
                }}
              >
                O'chirish
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
