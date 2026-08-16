// `BusinessOnlineViews.tsx` dan ajratildi.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { money } from "../business-profile-config";

export type OrderFilter = "new" | "active" | "terminal";

export type SharedActions = {
  busy: boolean;
  form: string | null;
  draft: BusinessOnlineRecord;
  setForm: (value: string | null) => void;
  setDraft: (value: BusinessOnlineRecord) => void;
  create: (
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ) => Promise<void>;
  patch: (
    resource: BusinessOnlineResource,
    id: number | string,
    patch: BusinessOnlineRecord,
  ) => Promise<void>;
  remove: (resource: BusinessOnlineResource, id: number | string) => Promise<void>;
  action: (
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ) => Promise<void>;
};

export const TERMINAL = new Set([
  "done",
  "delivered",
  "pickup_waiting_customer",
  "rejected",
  "cancelled",
  "canceled",
]);

export const SERVICE_TYPES = new Set(["booking", "service", "queue", "medical"]);

export const ITEM_FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["all", "Barchasi"],
  ["product", "Mahsulotlar"],
  ["service", "Xizmatlar"],
];

export function recordText(row: BusinessOnlineRecord, ...keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== "") {
      return String(value);
    }
  }
  return "";
}

export function recordNumber(row: BusinessOnlineRecord, ...keys: string[]): number {
  for (const key of keys) {
    const value = Number(row[key] ?? 0);
    if (Number.isFinite(value) && value !== 0) return value;
  }
  return 0;
}

export function recordId(row: BusinessOnlineRecord, index = 0): number | string {
  const value = row.id;
  return typeof value === "number" || typeof value === "string" ? value : index + 1;
}

export function isServiceOrder(row: BusinessOnlineRecord): boolean {
  const category = recordText(row, "order_category");
  if (category) return category === "service";
  return SERVICE_TYPES.has(recordText(row, "order_type", "kind"));
}

export function statusLabel(value: unknown): string {
  const status = String(value ?? "");
  const labels: Record<string, string> = {
    new: "Yangi",
    accepted: "Qabul qilindi",
    pending: "Kutilmoqda",
    pending_payment: "To‘lov kutilmoqda",
    payment_waiting: "To‘lov kutilmoqda",
    payment_confirmed: "To‘lov tasdiqlandi",
    preparing: "Tayyorlanmoqda",
    ready: "Tayyor",
    in_delivery: "Yetkazilmoqda",
    delivered: "Yetkazildi",
    done: "Yakunlandi",
    active: "Faol",
    paused: "To‘xtatilgan",
    archived: "Arxivda",
    approved: "Tasdiqlangan",
    rejected: "Rad etilgan",
    draft: "Qoralama",
  };
  return (labels[status] ?? status) || "Holat ko‘rsatilmagan";
}

export function subscriptionPlanName(value: unknown): string {
  const code = String(value ?? "").toLocaleLowerCase("uz");
  return code === "pro" ? "Pro" : code === "plus" ? "Plus" : "Bepul";
}

export function subscriptionDate(value: unknown): string {
  const seconds = Number(value ?? 0);
  if (!seconds) return "—";
  return new Date(seconds * 1000).toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export function paymentDate(value: unknown): string {
  const timestamp = Number(value ?? 0);
  return timestamp ? new Date(timestamp * 1000).toLocaleString("uz-UZ") : "";
}

export function notifyTime(value: unknown): string {
  const timestamp = Number(value ?? 0);
  if (!timestamp) return "";
  const date = new Date(timestamp * 1000);
  return `${date.toLocaleDateString("uz-UZ")} · ${date.toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export function orderCreatedText(value: unknown): string {
  const timestamp = Number(value ?? 0);
  if (!timestamp) return "—";
  const date = new Date(timestamp * 1000);
  return `${date.toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })} · ${date.toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export function v1656Money(value: number): string {
  return `${new Intl.NumberFormat("uz-UZ").format(Number(value || 0))} so'm`;
}

export function SectionTitle({ title, note }: { title: string; note: string }) {
  return (
    <div className="business-online__section-title">
      <h2>{title}</h2>
      <span>{note}</span>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="business-online__empty">{children}</div>;
}

export function InlineForm({
  title,
  fields,
  draft,
  setDraft,
  busy,
  onCancel,
  onSave,
}: {
  title: string;
  fields: string[];
  draft: BusinessOnlineRecord;
  setDraft: (value: BusinessOnlineRecord) => void;
  busy: boolean;
  onCancel: () => void;
  onSave: () => Promise<void>;
}) {
  const labels: Record<string, string> = {
    name: "Nomi",
    title: "Sarlavha",
    kind: "Turi",
    group_id: "Guruh ID",
    price: "Narxi",
    description: "Tavsif",
    caption: "Qisqa matn",
    placement: "Joylashuvi",
    region: "Viloyat",
    district: "Tuman",
    category: "Toifa",
    media_type: "Media turi",
    media_url: "Media manzili",
  };
  return (
    <div className="business-online__form">
      <h2>{title}</h2>
      {fields.map((field) => (
        <label key={field}>
          {labels[field] ?? field}
          <input
            value={String(draft[field] ?? "")}
            onChange={(event) =>
              setDraft({
                ...draft,
                [field]: event.currentTarget.value,
              })
            }
          />
        </label>
      ))}
      <div>
        <button type="button" onClick={onCancel}>
          Bekor qilish
        </button>
        <button type="button" disabled={busy} onClick={() => void onSave()}>
          Saqlash
        </button>
      </div>
    </div>
  );
}
