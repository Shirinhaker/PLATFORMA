import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  NotificationFilterCategory,
  NotificationFilterRead,
  NotificationFilterWrite,
  NotificationPreference,
  NotificationRead,
  PushStatusRead,
} from "../api/types";
import { UZBEKISTAN_REGIONS } from "../legacy/public/location-data";
import "./Notifications.css";

export type NotificationsApi = Pick<
  ApiClient,
  | "getNotifications"
  | "getActionNotifications"
  | "markNotificationRead"
  | "markAllNotificationsRead"
  | "getNotificationPreference"
  | "saveNotificationPreference"
  | "getNotificationFilters"
  | "createNotificationFilter"
  | "deleteNotificationFilter"
  | "getPushStatus"
>;

type Props = {
  api: NotificationsApi;
  onBack: () => void;
  onOpenNotification?: (notification: NotificationRead) => void | Promise<void>;
  onUnreadChange?: (count: number) => void;
};

type Draft = NotificationFilterWrite;

const CATEGORIES: ReadonlyArray<readonly [NotificationFilterCategory, string, string]> =
  [
    ["uy", "🏠", "Uy-joy"],
    ["ish", "💼", "Ish"],
    ["moshina", "🚙", "Moshinalar"],
    ["hayvon", "🐾", "Hayvonlar"],
    ["texnika", "📱", "Texnika"],
    ["boshqa", "📦", "Boshqalar"],
  ];
const CATEGORY_MAP = new Map(
  CATEGORIES.map(([key, icon, label]) => [key, { icon, label }] as const),
);
const EMPTY_DRAFT: Draft = {
  cat: "uy",
  region: "",
  district: "",
  price_min: 0,
  price_max: 0,
  keyword: "",
};
const EMPTY_PUSH: PushStatusRead = {
  provider: "firebase",
  configured: false,
  active_devices: 0,
  pending: 0,
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function notifyTime(timestamp: number): string {
  if (!timestamp) return "";
  const date = new Date(timestamp * 1000);
  return `${date.toLocaleDateString("uz-UZ")} · ${date.toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function pushStatusText(status: PushStatusRead): string {
  if (!status.active_devices) return "Mobil ilova qurilmasi ulanmagan.";
  const state = status.configured ? "Push xizmati faol" : "Firebase kaliti kutilmoqda";
  return `${state} · ${status.active_devices} ta qurilma`;
}

function filterCaption(filter: NotificationFilterRead): string {
  const parts: string[] = [];
  if (filter.district) parts.push(filter.district);
  else if (filter.region) parts.push(filter.region);
  if (filter.price_min || filter.price_max) {
    parts.push(`${filter.price_min || "0"}–${filter.price_max || "∞"}`);
  }
  if (filter.keyword) parts.push(`«${filter.keyword}»`);
  return parts.join(" · ") || "Barcha e’lonlar";
}

export function Notifications({
  api,
  onBack,
  onOpenNotification,
  onUnreadChange,
}: Props) {
  const [items, setItems] = useState<NotificationRead[]>([]);
  const [filters, setFilters] = useState<NotificationFilterRead[]>([]);
  const [preference, setPreference] = useState<NotificationPreference>({
    enabled: true,
    orders_enabled: true,
  });
  const [pushStatus, setPushStatus] = useState<PushStatusRead>(EMPTY_PUSH);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteFilter, setDeleteFilter] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const districts = useMemo(
    () =>
      UZBEKISTAN_REGIONS.find((region) => region.name === draft.region)?.districts ??
      [],
    [draft.region],
  );

  const load = useCallback(async () => {
    setError("");
    try {
      const [notifications, nextPreference, nextFilters, nextPushStatus] =
        await Promise.all([
          api.getNotifications(),
          api.getNotificationPreference(),
          api.getNotificationFilters(),
          api.getPushStatus().catch(() => EMPTY_PUSH),
        ]);
      setItems(notifications.items);
      setPreference(nextPreference);
      setFilters(nextFilters);
      setPushStatus(nextPushStatus);
      onUnreadChange?.(notifications.unread);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [api, onUnreadChange]);

  useEffect(() => {
    void load();
  }, [load]);

  async function markOne(notification: NotificationRead) {
    if (!notification.is_read) {
      await api.markNotificationRead(notification.id);
      setItems((current) =>
        current.map((row) =>
          row.id === notification.id ? { ...row, is_read: true } : row,
        ),
      );
      const unread = items.filter(
        (row) => !row.is_read && row.id !== notification.id,
      ).length;
      onUnreadChange?.(unread);
    }
    await onOpenNotification?.(notification);
  }

  async function markAll() {
    setBusy(true);
    setError("");
    try {
      await api.markAllNotificationsRead();
      setItems((current) => current.map((row) => ({ ...row, is_read: true })));
      onUnreadChange?.(0);
      setNotice("Barcha bildirishnomalar o‘qildi ✅");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function togglePush(enabled: boolean) {
    const previous = preference;
    const next = { enabled, orders_enabled: enabled };
    setPreference(next);
    setError("");
    try {
      setPreference(await api.saveNotificationPreference(next));
      setNotice(
        enabled ? "Push notification yoqildi ✅" : "Push notification o‘chirildi",
      );
    } catch (reason) {
      setPreference(previous);
      setError(errorMessage(reason));
    }
  }

  async function saveFilter() {
    setBusy(true);
    setError("");
    try {
      const created = await api.createNotificationFilter(draft);
      setFilters((current) => [created, ...current]);
      setDraft(EMPTY_DRAFT);
      setFormOpen(false);
      setNotice("Filtr saqlandi ✅");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeFilter(filterId: number) {
    setBusy(true);
    setError("");
    try {
      await api.deleteNotificationFilter(filterId);
      setFilters((current) => current.filter((row) => row.id !== filterId));
      setDeleteFilter(null);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (formOpen) {
    return (
      <main className="notifications-v1656 notifications-v1656--form">
        <header className="notifications-v1656__header">
          <div>
            <span>Bildirishnomalarim</span>
            <h1>Yangi filtr</h1>
          </div>
          <button type="button" onClick={() => setFormOpen(false)}>
            Orqaga
          </button>
        </header>
        <p>Faqat sizga kerakli e’lonlar haqida xabar olasiz.</p>
        <label>
          Tur (majburiy)
          <select
            value={draft.cat}
            onChange={(event) => {
              const cat = event.currentTarget.value as NotificationFilterCategory;
              setDraft((current) => ({ ...current, cat }));
            }}
          >
            {CATEGORIES.map(([key, icon, label]) => (
              <option value={key} key={key}>
                {icon} {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Viloyat — ixtiyoriy
          <select
            value={draft.region}
            onChange={(event) => {
              const region = event.currentTarget.value;
              setDraft((current) => ({ ...current, region, district: "" }));
            }}
          >
            <option value="">Istalgan viloyat</option>
            {UZBEKISTAN_REGIONS.map((region) => (
              <option value={region.name} key={region.name}>
                {region.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tuman — ixtiyoriy
          <select
            value={draft.district}
            disabled={!draft.region}
            onChange={(event) => {
              const district = event.currentTarget.value;
              setDraft((current) => ({ ...current, district }));
            }}
          >
            <option value="">Istalgan tuman</option>
            {districts.map((district) => (
              <option value={district} key={district}>
                {district}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>Narx oralig‘i — ixtiyoriy</legend>
          <div className="notifications-v1656__price-grid">
            <input
              aria-label="Narx dan"
              inputMode="numeric"
              placeholder="dan (masalan 1000)"
              value={draft.price_min || ""}
              onChange={(event) => {
                const priceMin = Number(event.currentTarget.value) || 0;
                setDraft((current) => ({ ...current, price_min: priceMin }));
              }}
            />
            <input
              aria-label="Narx gacha"
              inputMode="numeric"
              placeholder="gacha (masalan 5000)"
              value={draft.price_max || ""}
              onChange={(event) => {
                const priceMax = Number(event.currentTarget.value) || 0;
                setDraft((current) => ({ ...current, price_max: priceMax }));
              }}
            />
          </div>
        </fieldset>
        <label>
          Kalit so‘z — ixtiyoriy
          <input
            placeholder="masalan: mushuk, Nexia, dasturchi"
            value={draft.keyword}
            onChange={(event) => {
              const keyword = event.currentTarget.value;
              setDraft((current) => ({ ...current, keyword }));
            }}
          />
        </label>
        {error ? (
          <p role="alert" className="notifications-v1656__error">
            {error}
          </p>
        ) : null}
        <button
          type="button"
          className="notifications-v1656__primary"
          disabled={busy}
          onClick={() => void saveFilter()}
        >
          Saqlash
        </button>
        <button
          type="button"
          className="notifications-v1656__secondary"
          onClick={() => setFormOpen(false)}
        >
          Bekor qilish
        </button>
      </main>
    );
  }

  return (
    <main className="notifications-v1656">
      <header className="notifications-v1656__header">
        <div>
          <span>Koprik</span>
          <h1>Bildirishnomalarim</h1>
        </div>
        <button type="button" onClick={onBack}>
          Kabinetga qaytish
        </button>
      </header>
      <p>Buyurtma jarayonidagi muhim xabarlar shu yerda saqlanadi.</p>
      <div className="notifications-v1656__push-row">
        <span>📲 Push notification</span>
        <label>
          <input
            type="checkbox"
            checked={preference.enabled && preference.orders_enabled}
            onChange={(event) => void togglePush(event.currentTarget.checked)}
          />{" "}
          Yoqilgan
        </label>
      </div>
      <div className="notifications-v1656__hint">{pushStatusText(pushStatus)}</div>
      {error ? (
        <p role="alert" className="notifications-v1656__error">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="notifications-v1656__notice">
          {notice}
        </p>
      ) : null}
      <div className="notifications-v1656__section-head">
        <b>Buyurtma bildirishnomalari</b>
        <button
          type="button"
          disabled={busy || !items.length}
          onClick={() => void markAll()}
        >
          Barchasini o‘qish
        </button>
      </div>
      <div className="notifications-v1656__list" aria-busy={loading}>
        {items.length ? (
          items.map((notification) => (
            <button
              type="button"
              className={`notifications-v1656__card${notification.is_read ? " is-read" : ""}`}
              key={notification.id}
              onClick={() => void markOne(notification)}
            >
              <span className="notifications-v1656__icon">
                {notification.is_read ? "🔔" : "🟢"}
              </span>
              <span className="notifications-v1656__copy">
                <strong>{notification.title || "Bildirishnoma"}</strong>
                <span>{notification.body}</span>
                <small>{notifyTime(notification.created_at)}</small>
              </span>
              <span>›</span>
            </button>
          ))
        ) : (
          <div className="notifications-v1656__empty">
            <h2>{loading ? "Yuklanmoqda..." : "Hozircha xabar yo‘q"}</h2>
            {!loading ? <p>Buyurtma yangiliklari shu yerda chiqadi.</p> : null}
          </div>
        )}
      </div>
      <div className="notifications-v1656__divider" />
      <h2>E’lon filtrlari</h2>
      <p>Mos e’lon joylanganda Telegramingizga xabar keladi.</p>
      <button
        type="button"
        className="notifications-v1656__primary"
        onClick={() => setFormOpen(true)}
      >
        ➕ Yangi filtr qo‘shish
      </button>
      <div className="notifications-v1656__filters">
        {filters.length ? (
          filters.map((filter) => {
            const category = CATEGORY_MAP.get(filter.cat) ?? {
              icon: "📦",
              label: filter.cat,
            };
            return (
              <div className="notifications-v1656__card" key={filter.id}>
                <span className="notifications-v1656__icon">{category.icon}</span>
                <span className="notifications-v1656__copy">
                  <strong>{category.label}</strong>
                  <span>{filterCaption(filter)}</span>
                </span>
                <button
                  type="button"
                  aria-label="Filtrni o‘chirish"
                  onClick={() => setDeleteFilter(filter.id)}
                >
                  ✕
                </button>
              </div>
            );
          })
        ) : (
          <div className="notifications-v1656__empty">
            <h2>Filtr yo‘q</h2>
            <p>«Yangi filtr» orqali qiziqishlaringizni belgilang.</p>
          </div>
        )}
      </div>
      {deleteFilter !== null ? (
        <div className="notifications-v1656__modal" role="dialog" aria-modal="true">
          <div>
            <p>Bu filtrni o‘chirasizmi?</p>
            <button type="button" onClick={() => setDeleteFilter(null)}>
              Bekor qilish
            </button>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={() => void removeFilter(deleteFilter)}
            >
              O‘chirish
            </button>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export function ActionNotifications({
  api,
  onOpenNotification,
}: {
  api: Pick<NotificationsApi, "getActionNotifications" | "markNotificationRead">;
  onOpenNotification?: (notification: NotificationRead) => void | Promise<void>;
}) {
  const [current, setCurrent] = useState<NotificationRead | null>(null);
  const dismissed = useRef(new Set<number>());

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const result = await api.getActionNotifications();
        if (!active) return;
        const next =
          result.items.find((item) => !dismissed.current.has(item.id)) ?? null;
        setCurrent(next);
        if (next && next.id !== current?.id) {
          try {
            navigator.vibrate?.(120);
          } catch {
            /* Qurilma vibratsiyani qo‘llamasligi mumkin. */
          }
        }
      } catch {
        if (active) setCurrent(null);
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, current?.id]);

  if (!current) return null;
  return (
    <div className="action-notification-v1656" role="status" aria-live="polite">
      <button
        type="button"
        className="action-notification-v1656__open"
        onClick={async () => {
          await api.markNotificationRead(current.id);
          setCurrent(null);
          await onOpenNotification?.(current);
        }}
      >
        <strong>🔔 {current.title}</strong>
        <span>{current.body || "Amalni bajarish uchun bosing."}</span>
      </button>
      <button
        type="button"
        className="action-notification-v1656__close"
        aria-label="Yopish"
        onClick={() => {
          dismissed.current.add(current.id);
          setCurrent(null);
        }}
      >
        ×
      </button>
    </div>
  );
}
