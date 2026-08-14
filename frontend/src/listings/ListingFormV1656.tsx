import { useEffect, useRef, useState, type ChangeEvent } from "react";

import type { ApiClient } from "../api/client";
import type {
  ListingCategory,
  ListingCreate,
  ListingMediaAttachment,
} from "../api/types";
import {
  BusinessLocationPickerV1656View,
  type PicklocPoint,
} from "../profiles/BusinessLocationPickerV1656View";
import { readHomeLocation } from "../legacy/public/location-storage";
import { ListingMediaViewerV1656 } from "./ListingMediaViewerV1656";


type FormApi = Pick<ApiClient, "createUploadGrant" | "uploadGrantedFile">;
type Props = {
  actor: "user" | "business";
  api: FormApi;
  busy: boolean;
  onSave(body: ListingCreate): Promise<void>;
};

const CATEGORIES: ReadonlyArray<{ key: ListingCategory; name: string }> = [
  { key: "uy", name: "Uy-joy" },
  { key: "ish", name: "Ish o'rinlari" },
  { key: "moshina", name: "Moshinalar" },
  { key: "hayvon", name: "Hayvonlar" },
  { key: "texnika", name: "Texnika" },
  { key: "boshqa", name: "Boshqalar" },
];

type DraftMedia = ListingMediaAttachment & { previewUrl: string };


export function ListingFormV1656({ actor, api, busy, onSave }: Props) {
  const [cat, setCat] = useState<ListingCategory>("uy");
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [descr, setDescr] = useState("");
  const [address, setAddress] = useState("");
  const [point, setPoint] = useState<PicklocPoint | null>(null);
  const [visibility, setVisibility] = useState<"all" | "own">("all");
  const [media, setMedia] = useState<DraftMedia[]>([]);
  const [openedMedia, setOpenedMedia] = useState<DraftMedia | null>(null);
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState("");
  const [picker, setPicker] = useState(false);
  const homeLocation = readHomeLocation();
  const previewUrls = useRef(new Set<string>());

  useEffect(() => () => {
    previewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrls.current.clear();
  }, []);

  if (picker) {
    return (
      <BusinessLocationPickerV1656View
        fallback={homeLocation ? {
          latitude: homeLocation.latitude ?? 41.311,
          longitude: homeLocation.longitude ?? 69.28,
        } : null}
        prefix={actor === "business" ? "be" : "ue"}
        value={point}
        onCancel={() => setPicker(false)}
        onConfirm={(value) => {
          setPoint(value);
          setPicker(false);
        }}
      />
    );
  }

  async function uploadFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = [...(event.currentTarget.files ?? [])];
    event.currentTarget.value = "";
    const room = 10 - media.length;
    if (room <= 0) {
      setError("Bitta e'longa ko'pi bilan 10 ta rasm yoki video qo'shiladi.");
      return;
    }
    const files = selected.slice(0, room);
    setUploading(files.length);
    setError("");
    try {
      for (const file of files) {
        const type = file.type.startsWith("video/") ? "video" : "photo";
        const grant = await api.createUploadGrant({
          purpose: type === "video" ? "listing_video" : "listing_photo",
          filename: file.name,
          content_type: file.type,
          size_bytes: file.size,
        });
        await api.uploadGrantedFile(grant, file);
        const previewUrl = typeof URL.createObjectURL === "function"
          ? URL.createObjectURL(file)
          : "";
        if (previewUrl) previewUrls.current.add(previewUrl);
        setMedia((current) => [
          ...current,
          { type, object_key: grant.object_key, previewUrl },
        ]);
        setUploading((current) => Math.max(0, current - 1));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Media yuklanmadi.");
    } finally {
      setUploading(0);
    }
  }

  async function submit() {
    if (!title.trim()) {
      setError("Sarlavha kiritilishi shart.");
      return;
    }
    if (!point) {
      setError("Iltimos, e'lon joyini xaritada belgilang (📍 Xaritada joy belgilash).");
      return;
    }
    setError("");
    await onSave({
      cat,
      title: title.trim(),
      price: price.trim(),
      descr: descr.trim(),
      address: address.trim(),
      lat: point.latitude,
      lng: point.longitude,
      visibility,
      media: media.map(({ type, object_key }) => ({ type, object_key })),
    });
  }

  function removeMedia(index: number) {
    setMedia((current) => {
      const removed = current[index];
      if (removed?.previewUrl) {
        URL.revokeObjectURL(removed.previewUrl);
        previewUrls.current.delete(removed.previewUrl);
      }
      return current.filter((_, itemIndex) => itemIndex !== index);
    });
  }

  return (
    <div className="form-wrap listing-form-v1656">
      <div className="field">
        <label>Toifa</label>
        <div className="sort-row">
          {CATEGORIES.map((item) => (
            <button
              className={`sort-chip${cat === item.key ? " on" : ""}`}
              key={item.key}
              type="button"
              onClick={() => setCat(item.key)}
            >
              {item.name}
            </button>
          ))}
        </div>
      </div>
      <label className="field">Sarlavha
        <input
          className="input"
          placeholder={actor === "business" ? "Masalan: 3 xonali kvartira" : "Masalan: Nexia 3 sotiladi"}
          value={title}
          onChange={(event) => setTitle(event.currentTarget.value)}
        />
      </label>
      <label className="field">Narx
        <input
          className="input"
          placeholder="Narx yoki «kelishilgan»"
          value={price}
          onChange={(event) => setPrice(event.currentTarget.value)}
        />
      </label>
      <label className="field">Tavsif
        <textarea
          className="textarea"
          placeholder="E'lon haqida batafsil"
          value={descr}
          onChange={(event) => setDescr(event.currentTarget.value)}
        />
      </label>
      <div className="field">
        <label>Rasm va video</label>
        <label className="upload">
          📷 Galereya yoki papkadan tanlash
          <input
            accept="image/*,video/*"
            aria-label="E'lon media fayllari"
            hidden
            multiple
            type="file"
            onChange={(event) => void uploadFiles(event)}
          />
        </label>
        {media.length ? (
          <div className="listing-upload-list">
            {media.map((item, index) => (
              <div className="listing-upload-item" key={`${item.object_key}:${index}`}>
                <button
                  aria-label={item.type === "video" ? "Videoni katta ko‘rish" : "Rasmni katta ko‘rish"}
                  className="listing-upload-open"
                  type="button"
                  onClick={() => setOpenedMedia(item)}
                >
                  {item.type === "video" ? (
                    <video className="listing-upload-visual" muted playsInline preload="metadata" src={item.previewUrl || undefined} />
                  ) : (
                    <img alt="E'lon rasmi" className="listing-upload-visual" src={item.previewUrl || undefined} />
                  )}
                  {item.type === "video" ? <span className="listing-media-play">▶</span> : null}
                  <span className="listing-upload-status">
                    {item.type === "video" ? "VIDEO" : "RASM"}
                  </span>
                </button>
                <button
                  aria-label="Mediani olib tashlash"
                  className="listing-upload-remove"
                  type="button"
                  onClick={() => removeMedia(index)}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div className="field">
        <label>Joylashuv</label>
        <button className="upload" type="button" onClick={() => setPicker(true)}>
          📍 Xaritada joy belgilash
        </button>
        <div className="idesc">{point ? "✅ Joy belgilandi" : "Joy hali belgilanmagan"}</div>
        <input
          className="input"
          placeholder="Manzil nomi (ixtiyoriy)"
          value={address}
          onChange={(event) => setAddress(event.currentTarget.value)}
        />
      </div>
      {actor === "business" ? (
        <div className="field">
          <label>Kimlarga ko&apos;rinadi?</label>
          <button
            className={`vis-card${visibility === "all" ? " on" : ""}`}
            type="button"
            onClick={() => setVisibility("all")}
          >
            <span className="v-ic">🌍</span>
            <div><h5>Butun platformaga</h5><p>Bosh sahifa, xarita va qidiruvda hammaga ko&apos;rinadi.</p></div>
          </button>
          <button
            className={`vis-card${visibility === "own" ? " on" : ""}`}
            type="button"
            onClick={() => setVisibility("own")}
          >
            <span className="v-ic">🏪</span>
            <div><h5>Faqat sahifam mehmonlariga</h5><p>Faqat sahifangizga kirganlar ko&apos;radi.</p></div>
          </button>
        </div>
      ) : null}
      {error ? <div className="story-upload-error on" role="alert">{error}</div> : null}
      <button
        className="btn btn-primary btn-block"
        disabled={busy || uploading > 0}
        type="button"
        onClick={() => void submit()}
      >
        {uploading ? `Media yuklanmoqda… ${uploading}` : "Joylash"}
      </button>
      <ListingMediaViewerV1656
        media={openedMedia ? { type: openedMedia.type, url: openedMedia.previewUrl } : null}
        onClose={() => setOpenedMedia(null)}
      />
    </div>
  );
}
