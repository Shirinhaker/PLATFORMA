// Formatlash va payload bilan ishlash yordamchilari.

import type { PayloadSource } from "./types";

export const TERMINAL_STATUSES = new Set([
  "done",
  "delivered",
  "cancelled",
  "canceled",
  "rejected",
  "pickup_waiting_customer",
]);

export function money(value: number) {
  return `${Number(value || 0).toLocaleString("uz-UZ")} so‘m`;
}

export function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase())
        .join("")
    : "B";
}

export function activityDate(value: number) {
  return value ? new Date(value * 1000).toLocaleString("uz-UZ") : "Vaqt ko‘rsatilmagan";
}

export function isService(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const data = row as Record<string, unknown>;
  if (String(data.order_category ?? "") === "service") return true;
  return ["booking", "service", "queue", "medical"].includes(
    String(data.order_type ?? data.kind ?? ""),
  );
}

export function payloadRows(
  payload: Record<string, unknown>,
  source: PayloadSource,
): unknown[] {
  const keys = typeof source === "string" ? [source] : source;
  return keys.flatMap((key) => {
    const value = payload[key];
    return Array.isArray(value) ? value : [];
  });
}

export function hasPayload(
  payload: Record<string, unknown>,
  source?: PayloadSource,
): boolean {
  return Boolean(source && payloadRows(payload, source).length);
}
