import { useEffect, useRef } from "react";

import type { BusinessProfile } from "../api/types";
import type { PicklocPoint } from "./BusinessLocationPickerView";

export type Hours = { from: string; to: string };
export type Point = PicklocPoint;

type QrCtor = new (
  element: HTMLElement,
  options: {
    text: string;
    width: number;
    height: number;
    colorDark: string;
    colorLight: string;
  },
) => unknown;

export const IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
export const PATCH_FIELDS = [
  "name",
  "phone",
  "description",
  "public_username",
  "direction",
  "activity_type",
  "address",
  "latitude",
  "longitude",
  "pay_card",
  "pay_holder",
  "map_visible",
] as const;

export function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "So‘rov bajarilmadi.";
}

export function finite(value: number | null | undefined, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function parseHours(value: Record<string, unknown>): Hours {
  const from = String(value.from ?? value.start ?? value.open ?? "").slice(0, 5);
  const to = String(value.to ?? value.end ?? value.close ?? "").slice(0, 5);
  if (/^\d{2}:\d{2}$/.test(from) && /^\d{2}:\d{2}$/.test(to)) {
    return { from, to };
  }
  const raw = String(value.raw ?? value.text ?? "");
  const match = raw.match(/(\d{2}:\d{2})\D+(\d{2}:\d{2})/);
  return { from: match?.[1] ?? "", to: match?.[2] ?? "" };
}

export function workHours(existing: Record<string, unknown>, hours: Hours) {
  if (!hours.from && !hours.to) return {};
  return {
    ...existing,
    from: hours.from,
    to: hours.to,
    raw: `${hours.from}–${hours.to}`,
  };
}

export function shopLink(profile: BusinessProfile) {
  const url = new URL(window.location.origin);
  url.searchParams.set("shop", profile.public_username || String(profile.account_id));
  return url.toString();
}

export function mapUrl(point: Point) {
  const bbox = [
    point.longitude - 0.0075,
    point.latitude - 0.0045,
    point.longitude + 0.0075,
    point.latitude + 0.0045,
  ].join(",");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${point.latitude},${point.longitude}`)}`;
}

export function QrCode({ value }: { value: string }) {
  const root = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = root.current;
    if (!node) return;
    node.replaceChildren();
    const QRCode = (window as unknown as { QRCode?: QrCtor }).QRCode;
    if (!QRCode) {
      node.textContent = "QR kod yuklanmadi";
      return;
    }
    new QRCode(node, {
      text: value,
      width: 148,
      height: 148,
      colorDark: "#081c17",
      colorLight: "#ffffff",
    });
  }, [value]);
  return (
    <div
      ref={root}
      className="business-profile-share__qr"
      aria-label="Do‘kon QR kodi"
    />
  );
}
