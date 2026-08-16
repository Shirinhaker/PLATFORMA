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

export function ListingForm({
  draft,
  setDraft,
  busy,
  error,
  save,
  cancel,
}: {
  draft: BusinessOnlineRecord;
  setDraft: (row: BusinessOnlineRecord) => void;
  busy: boolean;
  error: string;
  save: () => Promise<void>;
  cancel: () => void;
}) {
  const mediaInput = useRef<HTMLInputElement | null>(null);
  const [locationOpen, setLocationOpen] = useState(false);
  const categories = [
    { key: "uy", name: "Uy-joy" },
    { key: "ish", name: "Ish o'rinlari" },
    { key: "moshina", name: "Moshinalar" },
    { key: "hayvon", name: "Hayvonlar" },
    { key: "texnika", name: "Texnika" },
    { key: "boshqa", name: "Boshqalar" },
  ];
  if (locationOpen) {
    const homeLocation = readHomeLocation();
    const latitude = recordText(draft, "lat");
    const longitude = recordText(draft, "lng");
    return (
      <BusinessLocationPickerView
        prefix="be"
        value={latitude && longitude ? normalizeLatLng(latitude, longitude) : null}
        fallback={normalizeLatLng(homeLocation?.latitude, homeLocation?.longitude)}
        onCancel={() => setLocationOpen(false)}
        onConfirm={(point) => {
          setDraft({
            ...draft,
            lat: point.latitude,
            lng: point.longitude,
          });
          setLocationOpen(false);
        }}
      />
    );
  }
  return (
    <div className="form-wrap listing-form-v1656">
      <div className="field">
        <label>Toifa</label>
        <div className="sort-row">
          {categories.map((category) => (
            <button
              type="button"
              className={
                recordText(draft, "cat", "category") === category.key
                  ? "sort-chip on"
                  : "sort-chip"
              }
              key={category.key}
              onClick={() => setDraft({ ...draft, cat: category.key })}
            >
              {category.name}
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        Sarlavha
        <input
          className="input"
          aria-label="Sarlavha"
          placeholder="Masalan: 3 xonali kvartira"
          value={recordText(draft, "title")}
          onChange={(event) => setDraft({ ...draft, title: event.currentTarget.value })}
        />
      </label>
      <label className="field">
        Narx
        <input
          className="input"
          aria-label="Narx"
          placeholder="Narx yoki «kelishilgan»"
          value={recordText(draft, "price")}
          onChange={(event) => setDraft({ ...draft, price: event.currentTarget.value })}
        />
      </label>
      <label className="field">
        Tavsif
        <textarea
          className="textarea"
          aria-label="Tavsif"
          placeholder="E'lon haqida batafsil"
          value={recordText(draft, "description", "descr")}
          onChange={(event) =>
            setDraft({ ...draft, description: event.currentTarget.value })
          }
        />
      </label>
      <div className="field">
        <label>Rasm va video</label>
        <input
          ref={mediaInput}
          type="file"
          hidden
          multiple
          accept="image/*,video/*"
          aria-label="E'lon media fayllari"
          onChange={(event) => {
            const files = [...(event.currentTarget.files ?? [])];
            setDraft({
              ...draft,
              media: files.map((file) => ({
                name: file.name,
                type: file.type,
                size: file.size,
              })),
            });
          }}
        />
        <button
          type="button"
          className="upload"
          onClick={() => mediaInput.current?.click()}
        >
          📷 Galereya yoki papkadan tanlash
        </button>
        {Array.isArray(draft.media) && draft.media.length > 0 && (
          <div className="idesc">{draft.media.length} ta fayl tanlandi</div>
        )}
      </div>
      <div className="field">
        <label>Joylashuv</label>
        <button type="button" className="upload" onClick={() => setLocationOpen(true)}>
          📍 Xaritada joy belgilash
        </button>
        <div className="idesc">
          {Number.isFinite(Number(draft.lat)) && Number.isFinite(Number(draft.lng))
            ? `📍 ${draft.lat}, ${draft.lng}`
            : "Joy hali belgilanmagan"}
        </div>
        <input
          className="input"
          placeholder="Manzil nomi (ixtiyoriy)"
          value={recordText(draft, "address")}
          onChange={(event) =>
            setDraft({ ...draft, address: event.currentTarget.value })
          }
        />
      </div>
      <div className="field">
        <label>Kimlarga ko'rinadi?</label>
        <button
          type="button"
          className={
            recordText(draft, "visibility") !== "own" ? "vis-card on" : "vis-card"
          }
          onClick={() => setDraft({ ...draft, visibility: "all" })}
        >
          <span className="v-ic">🌍</span>
          <span>
            <b>Butun platformaga</b>
            <small>Bosh sahifa, xarita va qidiruvda hammaga ko'rinadi.</small>
          </span>
        </button>
        <button
          type="button"
          className={
            recordText(draft, "visibility") === "own" ? "vis-card on" : "vis-card"
          }
          onClick={() => setDraft({ ...draft, visibility: "own" })}
        >
          <span className="v-ic">🏪</span>
          <span>
            <b>Faqat sahifam mehmonlariga</b>
            <small>Faqat sahifangizga kirganlar ko'radi.</small>
          </span>
        </button>
      </div>
      {error && (
        <div className="app-toast on" role="alert">
          {error}
        </div>
      )}
      <button
        type="button"
        className="btn btn-primary btn-block"
        disabled={busy}
        onClick={() => void save()}
      >
        Joylash
      </button>
      <button type="button" className="btn btn-soft btn-block" onClick={cancel}>
        Bekor qilish
      </button>
    </div>
  );
}
