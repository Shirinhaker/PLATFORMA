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

export function EditorForm({
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
    group_id: "Guruh",
    price: "Narxi",
    description: "Tavsif",
    caption: "Qisqa matn",
    placement: "Joylashuvi",
    region: "Viloyat",
    district: "Tuman",
    category: "Toifa",
    media_type: "Media turi",
    media_url: "Media manzili",
    start_at: "Boshlanish vaqti",
    end_at: "Tugash vaqti",
  };
  const longText = new Set(["description", "caption"]);
  return (
    <div className="business-online__form">
      <h2>{title}</h2>
      {fields.map((field) => (
        <label key={field}>
          {labels[field] ?? field}
          {longText.has(field) ? (
            <textarea
              value={String(draft[field] ?? "")}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  [field]: event.currentTarget.value,
                })
              }
            />
          ) : (
            <input
              type={field === "price" ? "number" : "text"}
              value={String(draft[field] ?? "")}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  [field]: event.currentTarget.value,
                })
              }
            />
          )}
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
