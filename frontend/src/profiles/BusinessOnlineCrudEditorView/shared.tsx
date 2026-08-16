// `BusinessOnlineCrudEditorView.tsx` dan ajratildi.
import { useEffect, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import { UZBEKISTAN_REGIONS } from "../../legacy/public/location-data";
import { readHomeLocation } from "../../legacy/public/location-storage";
import {
  BusinessLocationPickerView,
  normalizeLatLng,
} from "../BusinessLocationPickerView";
import {
  recordId,
  recordNumber,
  recordText,
  type SharedActions,
} from "../BusinessOnlineViews";

export function v1656Money(value: number): string {
  return `${new Intl.NumberFormat("uz-UZ").format(Number(value || 0))} so'm`;
}

export function storyRemaining(value: unknown): string {
  const seconds = Math.max(0, Number(value ?? 0) - Math.floor(Date.now() / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0
    ? `${hours} soat ${minutes} daqiqa qoldi`
    : `${minutes} daqiqa qoldi`;
}

export function localDateInputValue(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function cleanDraft(row: BusinessOnlineRecord): BusinessOnlineRecord {
  return Object.fromEntries(
    Object.entries(row).filter(
      ([key]) =>
        !["id", "created_at", "updated_at"].includes(key) && !key.endsWith("_url"),
    ),
  );
}

export function formId(resource: BusinessOnlineResource, mode: "new" | "edit") {
  return `${resource}:${mode}`;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="business-online__empty">{children}</div>;
}

export function PromotionTabs({
  active,
  onChange,
}: {
  active: "ads" | "listings";
  onChange?: (view: "advertisements" | "listings") => void;
}) {
  return (
    <div className="ad-tabs">
      <button
        type="button"
        className={active === "ads" ? "ad-tab on" : "ad-tab"}
        onClick={() => onChange?.("advertisements")}
      >
        Reklamalarim
      </button>
      <button
        type="button"
        className={active === "listings" ? "ad-tab on" : "ad-tab"}
        onClick={() => onChange?.("listings")}
      >
        E'lonlarim
      </button>
    </div>
  );
}
