import { useEffect, useState } from "react";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import { QUEUE_DIRECTIONS } from "./business-profile-config";
import { recordId, recordText } from "./BusinessOnlineViews";


const UNITS = [
  "dona",
  "kg",
  "g",
  "litr",
  "ml",
  "metr",
  "sm",
  "m²",
  "to'plam",
  "quti",
  "juft",
  "porsiya",
  "soat",
  "kun",
  "marta",
];

export function cleanItemDraft(
  row: BusinessOnlineRecord,
): BusinessOnlineRecord {
  return Object.fromEntries(Object.entries(row).filter(([key]) => (
    !["id", "created_at", "updated_at"].includes(key)
    && !key.endsWith("_url")
  )));
}

function rowKind(row: BusinessOnlineRecord): "product" | "service" {
  return recordText(row, "kind", "item_type", "type") === "service"
    ? "service"
    : "product";
}

export function GroupForm({
  draft,
  setDraft,
  busy,
  editing,
  onCancel,
  onSave,
}: {
  draft: BusinessOnlineRecord;
  setDraft: (value: BusinessOnlineRecord) => void;
  busy: boolean;
  editing: boolean;
  onCancel: () => void;
  onSave: () => Promise<void>;
}) {
  return (
    <>
      <button
        type="button"
        className="sheet-backdrop on"
        aria-label="Guruh formasini yopish"
        onClick={onCancel}
      />
      <section className="order-sheet on" role="dialog" aria-modal="true">
        <button type="button" className="order-close" aria-label="Yopish" onClick={onCancel}>×</button>
        <div className="order-grip" />
        <div className="lead">{editing ? "Guruh nomini o'zgartirish" : "Yangi guruh"}</div>
        <label className="field">
          Guruh nomi
          <input
            className="input"
            aria-label="Guruh nomi"
            placeholder="Masalan: Ho'l mevalar"
            value={String(draft.name ?? "")}
            onChange={(event) => setDraft({
              ...draft,
              name: event.currentTarget.value,
            })}
          />
        </label>
        {!editing && (
          <div className="field">
            <label>Tur</label>
            <div className="item-kind-row" role="group" aria-label="Guruh turi">
              <button
                type="button"
                className={rowKind(draft) === "product" ? "sort-chip on" : "sort-chip"}
                onClick={() => setDraft({ ...draft, kind: "product" })}
              >
                Mahsulot
              </button>
              <button
                type="button"
                className={rowKind(draft) === "service" ? "sort-chip on" : "sort-chip"}
                onClick={() => setDraft({ ...draft, kind: "service" })}
              >
                Xizmat
              </button>
            </div>
          </div>
        )}
        <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void onSave()}>
          Saqlash
        </button>
        <button type="button" className="btn btn-soft btn-block" onClick={onCancel}>Bekor qilish</button>
      </section>
    </>
  );
}

export function ItemForm({
  draft,
  groups,
  direction,
  setDraft,
  busy,
  editing,
  onCancel,
  onSave,
  uploadImage,
}: {
  draft: BusinessOnlineRecord;
  groups: BusinessOnlineRecord[];
  direction: string;
  setDraft: (value: BusinessOnlineRecord) => void;
  busy: boolean;
  editing: boolean;
  onCancel: () => void;
  onSave: () => Promise<void>;
  uploadImage?: (file: File) => Promise<string>;
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [localPreview, setLocalPreview] = useState("");
  const selectedGroup = groups.find((group, index) => (
    String(recordId(group, index)) === String(draft.group_id ?? "")
  ));
  const kind = selectedGroup ? rowKind(selectedGroup) : rowKind(draft);
  const trackStock = Boolean(Number(draft.track_stock ?? 0));
  const dining = direction === "Umumiy ovqatlanish";
  const note = String(draft.note ?? draft.description ?? "");
  const queueVisible = kind === "service" && QUEUE_DIRECTIONS.some(
    (value) => value === direction,
  );
  const imagePreview = localPreview || recordText(
    draft,
    "image_url",
    "photo_file",
    "photo_url",
  );

  useEffect(() => () => {
    if (localPreview.startsWith("blob:")) URL.revokeObjectURL(localPreview);
  }, [localPreview]);

  async function selectImage(file: File | undefined) {
    if (!file) return;
    if (!uploadImage) {
      setUploadError("Rasm yuklash xizmati hozir mavjud emas.");
      return;
    }
    if (![
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/gif",
    ].includes(file.type)) {
      setUploadError("JPG, PNG, WEBP yoki GIF rasm tanlang.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setUploadError("Rasm hajmi 8 MB dan oshmasin.");
      return;
    }
    setUploadError("");
    setUploading(true);
    try {
      const objectKey = await uploadImage(file);
      const preview = URL.createObjectURL(file);
      setLocalPreview(preview);
      setDraft({
        ...draft,
        image_object_key: objectKey,
        image_url: preview,
      });
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Rasmni yuklab bo‘lmadi.",
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="item-form-card form-wrap">
      <h2>
        {editing
          ? "Tovarni tahrirlash"
          : "Yangi tovar"}
      </h2>
      <div className="field">
        <label>Rasm — ixtiyoriy</label>
        {imagePreview ? (
          <img
            className="item-photo-preview"
            src={imagePreview}
            alt="Tanlangan mahsulot rasmi"
          />
        ) : null}
        <label className={`item-photo-add${uploading ? " is-loading" : ""}`}>
          <input
            aria-label="Mahsulot rasmi"
            className="item-photo-input"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            disabled={busy || uploading}
            onChange={(event) => {
              void selectImage(event.currentTarget.files?.[0]);
              event.currentTarget.value = "";
            }}
          />
          <span className="ic">📷</span>
          <span>
            {uploading
              ? "Yuklanmoqda…"
              : imagePreview
                ? "Rasmni almashtirish"
                : "Rasm qo'shish"}
          </span>
        </label>
        {uploadError ? (
          <span className="item-photo-error" role="alert">{uploadError}</span>
        ) : null}
      </div>
      <label className="field">
        Nomi
        <input
          className="input"
          aria-label="Nomi"
          value={String(draft.name ?? "")}
          placeholder="Masalan: Non"
          onChange={(event) => setDraft({
            ...draft,
            name: event.currentTarget.value,
          })}
        />
      </label>
      <label className="field">
        Narxi
        <input
          className="input"
          aria-label="Narxi"
          value={String(draft.price ?? "")}
          placeholder="Masalan: 2 000 so'm"
          onChange={(event) => setDraft({
            ...draft,
            price: event.currentTarget.value,
          })}
        />
      </label>
      {kind === "product" && (
        <>
          <label className="field">
            O'lchov birligi
            <select
              className="input"
              value={String(draft.unit ?? "dona")}
              onChange={(event) => setDraft({
                ...draft,
                unit: event.currentTarget.value,
              })}
            >
              {UNITS.map((unit) => (
                <option key={unit} value={unit}>{unit}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Omborda hisoblash
            <select
              className="input"
              value={trackStock ? "1" : "0"}
              onChange={(event) => setDraft({
                ...draft,
                track_stock: Number(event.currentTarget.value),
              })}
            >
              <option value="0">Yo'q</option>
              <option value="1">Ha — qoldiq yuritiladi</option>
            </select>
          </label>
          {trackStock && dining && (
            <label className="field">
              Ombor turi
              <select
                className="input"
                aria-label="Ombor turi"
                value={String(draft.stock_type ?? "ready_food")}
                onChange={(event) => setDraft({
                  ...draft,
                  stock_type: event.currentTarget.value,
                })}
              >
                <option value="ready_food">Tayyor taom</option>
                <option value="raw_material">Xomashyo</option>
              </select>
            </label>
          )}
          {trackStock && !editing && (
            <label className="field">
              Boshlang‘ich qoldiq
              <input
                className="input"
                aria-label="Boshlang‘ich qoldiq"
                inputMode="decimal"
                value={String(draft.stock_qty ?? "")}
                placeholder="0"
                onChange={(event) => setDraft({
                  ...draft,
                  stock_qty: event.currentTarget.value,
                })}
              />
            </label>
          )}
          {trackStock && (
            <label className="field">
              Minimal qoldiq
              <input
                className="input"
                aria-label="Minimal qoldiq"
                inputMode="decimal"
                value={String(draft.min_qty ?? "")}
                placeholder="0"
                onChange={(event) => setDraft({
                  ...draft,
                  min_qty: event.currentTarget.value,
                })}
              />
            </label>
          )}
        </>
      )}
      <label className="field">
        Izoh — ixtiyoriy
        <input
          className="input"
          value={note}
          placeholder="Izoh"
          onChange={(event) => setDraft({
            ...draft,
            note: event.currentTarget.value,
            description: event.currentTarget.value,
          })}
        />
      </label>
      <label className="field">
        Guruh
        <select
          className="input"
          value={String(draft.group_id ?? "")}
          onChange={(event) => {
            const groupId = event.currentTarget.value;
            const group = groups.find((candidate, index) => (
              String(recordId(candidate, index)) === groupId
            ));
            const nextKind = group ? rowKind(group) : rowKind(draft);
            setDraft({
              ...draft,
              group_id: groupId || null,
              kind: nextKind,
              queue_enabled: nextKind === "service"
                ? draft.queue_enabled ?? 0
                : 0,
            });
          }}
        >
          <option value="">Guruhsiz</option>
          {groups.map((group, index) => {
            const id = recordId(group, index);
            return (
              <option key={String(id)} value={String(id)}>
                {recordText(group, "name", "title") || "Guruh"}
                {" — "}
                {rowKind(group) === "service" ? "Xizmat" : "Mahsulot"}
              </option>
            );
          })}
        </select>
      </label>
      <div className="field">
        {selectedGroup ? (
          <div className="item-auto-kind">
            Tur avtomatik: {kind === "service" ? "Xizmat" : "Mahsulot"} ({String(selectedGroup.name ?? "")} guruhi bo'yicha)
          </div>
        ) : (
          <>
            <label>Turi</label>
            <div className="item-kind-row" role="group" aria-label="Tovar turi">
          <button
            type="button"
            className={kind === "product" ? "sort-chip on" : "sort-chip"}
            onClick={() => setDraft({
              ...draft,
              kind: "product",
              queue_enabled: 0,
            })}
          >
            Mahsulot
          </button>
          <button
            type="button"
            className={kind === "service" ? "sort-chip on" : "sort-chip"}
            onClick={() => setDraft({ ...draft, kind: "service" })}
          >
            Xizmat
          </button>
            </div>
          </>
        )}
      </div>
      {queueVisible && (
        <div className="field" id="itQueueWrap">
          <label htmlFor="itQueueEnabled">Navbat tizimi</label>
          <select
            className="input"
            id="itQueueEnabled"
            value={Number(draft.queue_enabled ?? 0) ? "1" : "0"}
            onChange={(event) => setDraft({
              ...draft,
              queue_enabled: Number(event.currentTarget.value),
            })}
          >
            <option value="0">O‘chirilgan</option>
            <option value="1">Yoqilgan</option>
          </select>
          <div className="idesc">
            Xizmat kartasida onlayn va oflayn yagona navbatni ishlatadi.
          </div>
        </div>
      )}
      <div className="item-form-actions">
        <button
          type="button"
          className="btn btn-primary btn-block"
          disabled={busy || uploading}
          onClick={() => void onSave()}
        >
          Saqlash
        </button>
        <button type="button" className="btn btn-soft btn-block" onClick={onCancel}>Bekor qilish</button>
      </div>
    </section>
  );
}
