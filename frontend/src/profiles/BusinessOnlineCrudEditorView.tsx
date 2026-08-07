import { useEffect, useRef, useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { UZBEKISTAN_REGIONS } from "../legacy/public/location-data";
import { readHomeLocation } from "../legacy/public/location-storage";
import {
  BusinessLocationPickerV1656View,
  normalizeLatLng,
} from "./BusinessLocationPickerV1656View";
import {
  recordId,
  recordNumber,
  recordText,
  type SharedActions,
} from "./BusinessOnlineViews";
function v1656Money(value: number): string {
  return `${new Intl.NumberFormat("uz-UZ").format(Number(value || 0))} so'm`;
}

function storyRemaining(value: unknown): string {
  const seconds = Math.max(
    0,
    Number(value ?? 0) - Math.floor(Date.now() / 1000),
  );
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0
    ? `${hours} soat ${minutes} daqiqa qoldi`
    : `${minutes} daqiqa qoldi`;
}

function localDateInputValue(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}


function cleanDraft(row: BusinessOnlineRecord): BusinessOnlineRecord {
  return Object.fromEntries(Object.entries(row).filter(([key]) => (
    !["id", "created_at", "updated_at"].includes(key)
    && !key.endsWith("_url")
  )));
}

function formId(
  resource: BusinessOnlineResource,
  mode: "new" | "edit",
) {
  return `${resource}:${mode}`;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="business-online__empty">{children}</div>;
}

function EditorForm({
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
              onChange={(event) => setDraft({
                ...draft,
                [field]: event.currentTarget.value,
              })}
            />
          ) : (
            <input
              type={field === "price" ? "number" : "text"}
              value={String(draft[field] ?? "")}
              onChange={(event) => setDraft({
                ...draft,
                [field]: event.currentTarget.value,
              })}
            />
          )}
        </label>
      ))}
      <div>
        <button type="button" onClick={onCancel}>Bekor qilish</button>
        <button type="button" disabled={busy} onClick={() => void onSave()}>
          Saqlash
        </button>
      </div>
    </div>
  );
}


export function CrudEditorView({
  resource,
  rows,
  addLabel,
  empty,
  fields,
  extraAction,
  rowAction,
  quoteAdvertisement,
  uploadImage,
  ...actions
}: SharedActions & {
  resource: BusinessOnlineResource;
  rows: BusinessOnlineRecord[];
  addLabel: string;
  empty: string;
  fields: string[];
  extraAction?: (row: BusinessOnlineRecord, index: number) => ReactNode;
  /** Har bir reklama qatori ostida chiqadigan amal (masalan to'lov). */
  rowAction?: (row: BusinessOnlineRecord, index: number) => ReactNode;
  quoteAdvertisement?: (
    request: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null | void>;
  /** Berilsa reklama rasmi R2'ga yuklanadi. */
  uploadImage?: (file: File) => Promise<string>;
}) {
  const [openForm, setOpenForm] = useState(false);
  const [draft, setDraft] = useState<BusinessOnlineRecord>({});
  const [storyState, setStoryState] = useState<"active" | "archived">("active");
  const [storyViewer, setStoryViewer] = useState<BusinessOnlineRecord | null>(null);
  const [storyFile, setStoryFile] = useState<File | null>(null);
  const [confirm, setConfirm] = useState<{
    id: number | string;
    title?: string;
    text: string;
    ok: string;
  } | null>(null);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    setOpenForm(false);
    setDraft({});
    setConfirm(null);
    setValidationError("");
    setStoryViewer(null);
    setStoryFile(null);
  }, [resource]);

  function begin(next: BusinessOnlineRecord) {
    setDraft(next);
    setValidationError("");
    setOpenForm(true);
    actions.setDraft(next);
    actions.setForm(formId(resource, "new"));
  }

  async function saveDraft() {
    const title = recordText(draft, "title", "caption").trim();
    if (resource === "advertisements") {
      if (!recordText(draft, "image_file")) {
        setValidationError("Reklama rasmini tanlang.");
        return;
      }
      if (!title) {
        setValidationError("Reklama sarlavhasini kiriting.");
        return;
      }
      if (!Array.isArray(draft.targets) || draft.targets.length === 0) {
        setValidationError("Kamida bitta hudud tanlang.");
        return;
      }
      if (!recordText(draft, "start_date")) {
        setValidationError("Boshlanish vaqtini tanlang.");
        return;
      }
      if (!draft.daily_all_day) {
        const start = recordText(draft, "daily_start");
        const end = recordText(draft, "daily_end");
        if (!start || !end) {
          setValidationError("Kunlik boshlanish va tugash vaqtini tanlang.");
          return;
        }
        if (start === end) {
          setValidationError("Kunlik boshlanish va tugash vaqti bir xil bo'lmasin.");
          return;
        }
      }
    } else if (!title) {
      setValidationError("Sarlavha kiritilishi shart.");
      return;
    }
    if (
      resource === "listings"
      && (!Number.isFinite(Number(draft.lat)) || !Number.isFinite(Number(draft.lng)))
    ) {
      setValidationError("Iltimos, e'lon joyini xaritada belgilang (📍 Xaritada joy belgilash).");
      return;
    }
    await actions.create(resource, cleanDraft(draft));
    setOpenForm(false);
    setDraft({});
    setValidationError("");
  }

  function dialog() {
    if (!confirm) return null;
    return (
      <>
        <button
          type="button"
          className="app-modal-back on"
          aria-label="Bekor qilish"
          onClick={() => setConfirm(null)}
        />
        <div className="app-confirm on" role="dialog" aria-modal="true">
          {confirm.title && <div className="acf-title">{confirm.title}</div>}
          <p className="acf-text">{confirm.text}</p>
          <div className="acf-btns">
            <button type="button" className="acf-cancel" onClick={() => setConfirm(null)}>
              Bekor qilish
            </button>
            <button
              type="button"
              className="acf-ok danger"
              disabled={actions.busy}
              onClick={() => {
                const pending = confirm;
                void actions.remove(resource, pending.id).then(() => setConfirm(null));
              }}
            >
              {confirm.ok}
            </button>
          </div>
        </div>
      </>
    );
  }

  if (resource === "stories") {
    const visible = rows.filter((row) => {
      const state = recordText(row, "state", "status");
      return storyState === "archived"
        ? ["archived", "expired"].includes(state)
        : !["archived", "expired"].includes(state);
    });
    return (
      <section className="my-stories-shell">
        <div className="my-stories-tabs ad-tabs">
          <button
            type="button"
            className={storyState === "active" ? "ad-tab on" : "ad-tab"}
            onClick={() => setStoryState("active")}
          >
            Faol
          </button>
          <button
            type="button"
            className={storyState === "archived" ? "ad-tab on" : "ad-tab"}
            onClick={() => setStoryState("archived")}
          >
            Arxiv
          </button>
        </div>
        <div className="my-stories-grid">
          {visible.length ? visible.map((row, index) => {
            const id = recordId(row, index);
            const archived = ["archived", "expired"].includes(
              recordText(row, "state", "status"),
            );
            return (
              <article className="my-story-card" data-my-story-id={id} key={String(id)}>
                <div className="my-story-thumb">
                  {recordText(row, "thumbnail_url", "media_url") ? (
                    <img
                      src={recordText(row, "thumbnail_url", "media_url")}
                      alt="Istoriya muqovasi"
                    />
                  ) : <span className="my-story-thumb-fallback">Media topilmadi</span>}
                  {recordText(row, "media_type") === "video" && (
                    <span className="my-story-video-badge">▶ Video</span>
                  )}
                </div>
                <div className="my-story-main">
                  <div className="my-story-caption">
                    {recordText(row, "caption") || "Matnsiz istoriya"}
                  </div>
                  <div className="my-story-meta">
                    {new Date(Number(row.created_at ?? 0) * 1000).toLocaleString("uz-UZ", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    <br />👁 {Number(row.view_count ?? 0)} ko‘rish
                  </div>
                  <span className={archived ? "my-story-state archived" : "my-story-state"}>
                    {archived ? "Arxiv" : `Faol · ${storyRemaining(row.expires_at)}`}
                  </span>
                  <div className="my-story-actions">
                    <button type="button" onClick={() => setStoryViewer(row)}>Ko‘rish</button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => setConfirm({
                        id,
                        title: "Istoriyani o‘chirish",
                        text: "Istoriya va uning media fayli butunlay o‘chiriladi.",
                        ok: "O‘chirish",
                      })}
                    >
                      O‘chirish
                    </button>
                  </div>
                </div>
              </article>
            );
          }) : storyState === "archived" ? (
            <div className="empty my-stories-status">
              <h3>Arxiv hozircha bo‘sh</h3>
              <p>24 soati tugagan istoriyalar shu yerda saqlanadi.</p>
            </div>
          ) : (
            <div className="empty my-stories-status">
              <h3>Hali istoriya joylamagansiz</h3>
              <p>Rasm yoki 1 daqiqagacha video joylang.</p>
              <button type="button" className="btn btn-primary" onClick={() => begin({ status: "active" })}>
                Istoriya joylash
              </button>
            </div>
          )}
        </div>
        {openForm && (
          <div className="story-layer on">
            <div className="story-sheet" role="dialog" aria-modal="true" aria-label="Istoriya joylash">
              <div className="story-sheet-head">
                <div className="story-sheet-title">Istoriya joylash</div>
                <button type="button" className="story-text-btn" onClick={() => setOpenForm(false)}>Yopish</button>
              </div>
              <input
                type="file"
                hidden
                id="reactStoryFileInput"
                aria-label="Istoriya media fayli"
                accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0] ?? null;
                  if (file && ![
                    "image/jpeg", "image/png", "image/webp",
                    "video/mp4", "video/quicktime", "video/webm",
                  ].includes(file.type)) {
                    setStoryFile(null);
                    setValidationError("Rasm yoki video tanlang.");
                    event.currentTarget.value = "";
                    return;
                  }
                  if (file?.type.startsWith("image/") && file.size > 10 * 1024 * 1024) {
                    setStoryFile(null);
                    setValidationError("Rasm hajmi 10 MB dan oshmasin.");
                    event.currentTarget.value = "";
                    return;
                  }
                  if (file?.type.startsWith("video/") && file.size > 100 * 1024 * 1024) {
                    setStoryFile(null);
                    setValidationError("Video hajmi 100 MB dan oshmasin.");
                    event.currentTarget.value = "";
                    return;
                  }
                  setStoryFile(file);
                  setValidationError("");
                }}
              />
              <div className="story-source-grid">
                <button type="button" className="story-source-btn" onClick={() => {
                  const input = document.getElementById("reactStoryFileInput");
                  input?.setAttribute("capture", "environment");
                  input?.click();
                }}>
                  Kamera orqali<small>Hozir rasm yoki video oling</small>
                </button>
                <button type="button" className="story-source-btn" onClick={() => {
                  const input = document.getElementById("reactStoryFileInput");
                  input?.removeAttribute("capture");
                  input?.click();
                }}>
                  Galereyadan<small>Telefondagi rasm yoki videoni tanlang</small>
                </button>
              </div>
              {storyFile && (
                <div className="story-compose-fields on">
                  <div className="idesc">{storyFile.name}</div>
                  <label className="field">Qisqa matn — ixtiyoriy
                    <textarea
                      className="textarea"
                      maxLength={200}
                      placeholder="Istoriya haqida qisqa yozing"
                      value={recordText(draft, "caption")}
                      onChange={(event) => setDraft({ ...draft, caption: event.currentTarget.value })}
                    />
                    <span className="idesc">{recordText(draft, "caption").length} / 200</span>
                  </label>
                </div>
              )}
              {validationError && <div className="story-upload-error on" role="alert">{validationError}</div>}
              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={actions.busy}
                onClick={async () => {
                  if (!storyFile) {
                    setValidationError("Avval rasm yoki video tanlang.");
                    return;
                  }
                  await actions.create("stories", {
                    caption: recordText(draft, "caption").trim(),
                    media_file: storyFile.name,
                    media_type: storyFile.type.startsWith("video/") ? "video" : "photo",
                    status: "active",
                  });
                  setStoryFile(null);
                  setOpenForm(false);
                }}
              >Joylash</button>
            </div>
          </div>
        )}
        {storyViewer && (
          <div className="story-viewer on">
            <div className="story-stage" role="dialog" aria-modal="true" aria-label="Istoriya">
              <div className="story-viewer-media">
                {recordText(storyViewer, "media_type") === "video" ? (
                  <video src={recordText(storyViewer, "media_url")} controls />
                ) : (
                  <img src={recordText(storyViewer, "media_url", "thumbnail_url")} alt="Istoriya" />
                )}
              </div>
              <button
                type="button"
                className="story-viewer-close"
                aria-label="Istoriyani yopish"
                onClick={() => setStoryViewer(null)}
              >×</button>
              <div className="story-viewer-caption">{recordText(storyViewer, "caption")}</div>
            </div>
          </div>
        )}
        {dialog()}
      </section>
    );
  }

  if (resource === "listings") {
    return (
      <section className="promotion-v1656">
        <PromotionTabs active="listings" />
        {!openForm ? (
          <div className="biz-listings-pane">
            <button
              type="button"
              className="btn btn-primary btn-block"
              onClick={() => begin({ cat: "uy", visibility: "all", status: "active" })}
            >
              + E'lon joylash
            </button>
            <div>
              {rows.length ? rows.map((row, index) => {
                const id = recordId(row, index);
                const icon = ({
                  uy: "🏠", ish: "💼", moshina: "🚙", hayvon: "🐾",
                  texnika: "📱", boshqa: "📦",
                } as Record<string, string>)[recordText(row, "cat", "category")] || "📦";
                const visibility = recordText(row, "visibility") === "own"
                  ? "🏪 Faqat mehmonlar"
                  : "🌍 Butun platforma";
                const status = recordText(row, "status") === "active" ? "Faol" : "O'chiq";
                const mediaCount = Array.isArray(row.media) ? row.media.length : 0;
                return (
                  <article className="elon-item" key={String(id)}>
                    <div className="li-thumb"><span>{icon}</span></div>
                    <div className="li-main">
                      <div className="li-title">{recordText(row, "title")}</div>
                      <div className="li-price">{recordText(row, "price")}</div>
                      <div className="li-meta">
                        {visibility} · {status}{mediaCount ? ` · 📎 ${mediaCount}` : ""}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="mini-ic"
                      aria-label="E'lonni o'chirish"
                      onClick={() => setConfirm({
                        id,
                        text: "Bu e'lon o'chirilsinmi?",
                        ok: "O'chirish",
                      })}
                    >
                      🗑
                    </button>
                  </article>
                );
              }) : (
                <div className="empty listing-empty">
                  <h3>Hozircha e'lon yo'q</h3><p>Yuqoridagi tugma orqali joylang.</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <ListingForm
            draft={draft}
            setDraft={setDraft}
            busy={actions.busy}
            error={validationError}
            save={saveDraft}
            cancel={() => setOpenForm(false)}
          />
        )}
        {dialog()}
      </section>
    );
  }

  if (resource === "advertisements") {
    return (
      <section className="promotion-v1656">
        <PromotionTabs active="ads" />
        {!openForm ? (
          <div className="biz-ads-pane">
            <div className="ad-info">
              Bosh sahifadagi banner reklama. Hudud, boshlanish vaqti va
              davomiyligini o'zingiz tanlaysiz.
            </div>
            <button
              type="button"
              className="btn btn-primary btn-block"
              onClick={() => begin({
                status: "payment_pending",
                daily_all_day: 1,
                daily_start: "19:00",
                daily_end: "21:00",
                duration_days: 1,
                start_date: localDateInputValue(),
                target_level: "district",
                targets: [],
              })}
            >
              + Reklama joylashtirish
            </button>
            <div>
              {rows.length ? rows.map((row, index) => {
                const id = recordId(row, index);
                const status = recordText(row, "status");
                const label = ({
                  active: "Faol", scheduled: "Rejalashtirilgan",
                  payment_pending: "To‘lov kutilmoqda", ended: "Yakunlangan",
                  cancelled: "Bekor qilingan",
                } as Record<string, string>)[status] || status;
                const targets = Array.isArray(row.targets)
                  ? row.targets.map((target) => {
                    const item = target as BusinessOnlineRecord;
                    if (item.level === "republic") return "🇺🇿 Respublika";
                    if (item.level === "region") return `Viloyat: ${recordText(item, "region")}`;
                    return `${recordText(item, "region")} · ${recordText(item, "district")}`;
                  }).join(", ")
                  : "";
                return (
                  <article className="ad-own-card" key={String(id)}>
                    <div className="ad-own-top">
                      <div className="ad-own-thumb">
                        {recordText(row, "image_file", "image_url") && (
                          <img src={recordText(row, "image_file", "image_url")} alt="" />
                        )}
                      </div>
                      <div className="ad-own-main">
                        <div className="li-title">{recordText(row, "title")}</div>
                        <div className="li-meta">{targets}</div>
                        <div className="li-meta">
                          {Number(row.duration_days ?? 1)} kun · {row.daily_all_day ? "Kun bo'yi" : "Belgilangan vaqtda"}
                        </div>
                      </div>
                      <span className={`ad-status ${status}`}>{label}</span>
                    </div>
                    <div className="ad-own-stats">
                      <b>{v1656Money(recordNumber(row, "price"))}</b>
                      <span className="li-meta">
                        👁 {Number(row.views ?? 0)} · ↗ {Number(row.clicks ?? 0)}
                      </span>
                    </div>
                    {rowAction?.(row, index)}
                    {!['cancelled', 'ended'].includes(status) && (
                      <button
                        type="button"
                        className="btn btn-outline btn-block"
                        onClick={() => setConfirm({
                          id,
                          text: "Reklama bekor qilinsinmi?",
                          ok: "Bekor qilish",
                        })}
                      >
                        Bekor qilish
                      </button>
                    )}
                  </article>
                );
              }) : (
                <div className="empty ad-empty">
                  <div className="ic">📣</div><h3>Reklama yo'q</h3>
                  <p>Bosh sahifaga hududiy reklama joylashtirishingiz mumkin.</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <AdvertisementForm
            draft={draft}
            setDraft={setDraft}
            busy={actions.busy}
            error={validationError}
            quoteAdvertisement={quoteAdvertisement}
            uploadImage={uploadImage}
            save={saveDraft}
            cancel={() => setOpenForm(false)}
          />
        )}
        {dialog()}
      </section>
    );
  }

  return (
    <section>
      <EditorForm
        title={addLabel}
        fields={fields}
        draft={draft}
        setDraft={setDraft}
        busy={actions.busy}
        onCancel={() => setOpenForm(false)}
        onSave={saveDraft}
      />
      {extraAction?.({}, 0)}
      <Empty>{empty}</Empty>
    </section>
  );
}

function PromotionTabs({ active }: { active: "ads" | "listings" }) {
  return (
    <div className="ad-tabs">
      <button type="button" className={active === "ads" ? "ad-tab on" : "ad-tab"}>
        Reklamalarim
      </button>
      <button type="button" className={active === "listings" ? "ad-tab on" : "ad-tab"}>
        E'lonlarim
      </button>
    </div>
  );
}

function ListingForm({
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
      <BusinessLocationPickerV1656View
        prefix="be"
        value={latitude && longitude
          ? normalizeLatLng(latitude, longitude)
          : null}
        fallback={normalizeLatLng(
          homeLocation?.latitude,
          homeLocation?.longitude,
        )}
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
              className={recordText(draft, "cat", "category") === category.key
                ? "sort-chip on"
                : "sort-chip"}
              key={category.key}
              onClick={() => setDraft({ ...draft, cat: category.key })}
            >
              {category.name}
            </button>
          ))}
        </div>
      </div>
      <label className="field">Sarlavha
        <input
          className="input"
          aria-label="Sarlavha"
          placeholder="Masalan: 3 xonali kvartira"
          value={recordText(draft, "title")}
          onChange={(event) => setDraft({ ...draft, title: event.currentTarget.value })}
        />
      </label>
      <label className="field">Narx
        <input
          className="input"
          aria-label="Narx"
          placeholder="Narx yoki «kelishilgan»"
          value={recordText(draft, "price")}
          onChange={(event) => setDraft({ ...draft, price: event.currentTarget.value })}
        />
      </label>
      <label className="field">Tavsif
        <textarea
          className="textarea"
          aria-label="Tavsif"
          placeholder="E'lon haqida batafsil"
          value={recordText(draft, "description", "descr")}
          onChange={(event) => setDraft({ ...draft, description: event.currentTarget.value })}
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
              media: files.map((file) => ({ name: file.name, type: file.type, size: file.size })),
            });
          }}
        />
        <button type="button" className="upload" onClick={() => mediaInput.current?.click()}>
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
          onChange={(event) => setDraft({ ...draft, address: event.currentTarget.value })}
        />
      </div>
      <div className="field">
        <label>Kimlarga ko'rinadi?</label>
        <button
          type="button"
          className={recordText(draft, "visibility") !== "own" ? "vis-card on" : "vis-card"}
          onClick={() => setDraft({ ...draft, visibility: "all" })}
        >
          <span className="v-ic">🌍</span><span><b>Butun platformaga</b><small>Bosh sahifa, xarita va qidiruvda hammaga ko'rinadi.</small></span>
        </button>
        <button
          type="button"
          className={recordText(draft, "visibility") === "own" ? "vis-card on" : "vis-card"}
          onClick={() => setDraft({ ...draft, visibility: "own" })}
        >
          <span className="v-ic">🏪</span><span><b>Faqat sahifam mehmonlariga</b><small>Faqat sahifangizga kirganlar ko'radi.</small></span>
        </button>
      </div>
      {error && <div className="app-toast on" role="alert">{error}</div>}
      <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void save()}>
        Joylash
      </button>
      <button type="button" className="btn btn-soft btn-block" onClick={cancel}>Bekor qilish</button>
    </div>
  );
}

function AdvertisementForm({
  draft,
  setDraft,
  busy,
  error,
  quoteAdvertisement,
  uploadImage,
  save,
  cancel,
}: {
  draft: BusinessOnlineRecord;
  setDraft: (row: BusinessOnlineRecord) => void;
  busy: boolean;
  error: string;
  quoteAdvertisement?: (
    request: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null | void>;
  /** Berilsa rasm R2'ga yuklanib, obyekt kaliti draftga yoziladi. */
  uploadImage?: (file: File) => Promise<string>;
  save: () => Promise<void>;
  cancel: () => void;
}) {
  const desktopInput = useRef<HTMLInputElement | null>(null);
  const mobileInput = useRef<HTMLInputElement | null>(null);
  const [fileError, setFileError] = useState("");
  const [quoteError, setQuoteError] = useState("");
  const [quote, setQuote] = useState<BusinessOnlineRecord | null>(null);
  const quoteAdvertisementRef = useRef(quoteAdvertisement);
  quoteAdvertisementRef.current = quoteAdvertisement;
  const targets = Array.isArray(draft.targets)
    ? draft.targets.filter((target): target is BusinessOnlineRecord => (
      Boolean(target && typeof target === "object")
    ))
    : [];
  const level = recordText(draft, "target_level") || "district";
  const selectedRegion = recordText(draft, "target_region")
    || UZBEKISTAN_REGIONS[0]?.name
    || "";
  const districts = UZBEKISTAN_REGIONS.find(
    (region) => region.name === selectedRegion,
  )?.districts ?? [];
  const selectedDistrict = districts.includes(recordText(draft, "target_district"))
    ? recordText(draft, "target_district")
    : districts[0] ?? "";
  const hours = Array.from({ length: 24 }, (_, hour) => (
    String(hour).padStart(2, "0") + ":00"
  ));
  const targetsKey = JSON.stringify(targets);
  const durationDays = Number(draft.duration_days ?? 1);
  const dailyAllDay = Boolean(draft.daily_all_day);
  const dailyStart = recordText(draft, "daily_start") || "00:00";
  const dailyEnd = recordText(draft, "daily_end") || "00:00";

  useEffect(() => {
    let current = true;
    if (!targets.length || !quoteAdvertisementRef.current) {
      setQuote(null);
      setQuoteError("");
      return () => { current = false; };
    }
    setQuoteError("");
    void quoteAdvertisementRef.current({
      targets,
      duration_days: durationDays,
      daily_all_day: dailyAllDay,
      daily_start: dailyStart,
      daily_end: dailyEnd,
    }).then((value) => {
      if (current && value) setQuote(value);
    }).catch((reason: unknown) => {
      if (!current) return;
      setQuote(null);
      setQuoteError(reason instanceof Error ? reason.message : "Reklama narxi hisoblanmadi.");
    });
    return () => { current = false; };
  }, [
    targetsKey,
    durationDays,
    dailyAllDay,
    dailyStart,
    dailyEnd,
  ]);

  async function selectImage(
    file: File | undefined,
    key: "image_file" | "mobile_image_file",
  ) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setFileError("Faqat JPG, PNG yoki WEBP rasm tanlang.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setFileError("Rasm hajmi 5 MB dan oshmasin.");
      return;
    }
    setFileError("");
    if (!uploadImage) {
      // Eski JSON yo'li: faqat nom saqlanadi.
      setDraft({ ...draft, [key]: file.name });
      return;
    }
    setFileError("Rasm yuklanmoqda...");
    try {
      const objectKey = await uploadImage(file);
      setFileError("");
      setDraft({ ...draft, [key]: file.name, [`${key}_key`]: objectKey });
    } catch (reason) {
      setFileError(
        reason instanceof Error ? reason.message : "Rasm yuklanmadi.",
      );
    }
  }

  function targetLabel(target: BusinessOnlineRecord) {
    if (target.level === "republic") return "🇺🇿 Respublika";
    if (target.level === "region") return `Viloyat: ${recordText(target, "region")}`;
    return `${recordText(target, "region")} · ${recordText(target, "district")}`;
  }

  return (
    <div className="form-wrap advertisement-form-v1656">
      <div className="ad-quality">
        <b>Rasm talabi:</b> kompyuter uchun 2744 × 368 px (7.46:1), telefon
        uchun 800 × 250 px (3.2:1) tavsiya etiladi. JPG, PNG yoki WEBP;
        har biri 5 MB gacha.
      </div>
      <div className="field"><label>Kompyuter uchun rasm — majburiy</label>
        <input
          ref={desktopInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp"
          aria-label="Kompyuter uchun rasm"
          onChange={(event) => void selectImage(
            event.currentTarget.files?.[0], "image_file",
          )}
        />
        <button type="button" className="upload" onClick={() => desktopInput.current?.click()}>
          {recordText(draft, "image_file") ? "Rasm tanlandi ✅" : "🖼 Galereyadan rasm tanlash"}
        </button>
      </div>
      <div className="field"><label>Telefon uchun rasm — ixtiyoriy</label>
        <input
          ref={mobileInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp"
          aria-label="Telefon uchun rasm"
          onChange={(event) => void selectImage(
            event.currentTarget.files?.[0], "mobile_image_file",
          )}
        />
        <button type="button" className="upload" onClick={() => mobileInput.current?.click()}>
          {recordText(draft, "mobile_image_file") ? "Telefon rasmi tanlandi ✅" : "📱 Telefon rasmini tanlash"}
        </button>
        <div className="idesc">Yuklanmasa, telefonda kompyuter rasmi ko‘rsatiladi.</div>
      </div>
      <label className="field">Reklama sarlavhasi
        <input
          className="input"
          value={recordText(draft, "title")}
          placeholder="Masalan: Bugun 20% chegirma"
          onChange={(event) => setDraft({ ...draft, title: event.currentTarget.value })}
        />
      </label>
      <label className="field">Qisqa matn
        <textarea
          className="textarea"
          value={recordText(draft, "caption")}
          placeholder="Reklama haqida qisqa va aniq ma'lumot"
          onChange={(event) => setDraft({ ...draft, caption: event.currentTarget.value })}
        />
      </label>
      <div className="field"><label>Qayerda ko'rinsin?</label>
        <select
          className="input full"
          aria-label="Hudud darajasi"
          value={level}
          onChange={(event) => setDraft({
            ...draft,
            target_level: event.currentTarget.value,
            target_region: selectedRegion,
            target_district: selectedDistrict,
          })}
        >
          <option value="district">Tuman kesimida</option>
          <option value="region">Viloyat kesimida</option>
          <option value="republic">Respublika bo'ylab</option>
        </select>
        {level !== "republic" && (
          <select
            className="input"
            aria-label="Reklama viloyati"
            value={selectedRegion}
            onChange={(event) => {
              const region = event.currentTarget.value;
              const district = UZBEKISTAN_REGIONS.find(
                (item) => item.name === region,
              )?.districts[0] ?? "";
              setDraft({
                ...draft,
                target_region: region,
                target_district: district,
              });
            }}
          >
            {UZBEKISTAN_REGIONS.map((region) => (
              <option value={region.name} key={region.name}>{region.name}</option>
            ))}
          </select>
        )}
        {level === "district" && (
          <select
            className="input"
            aria-label="Reklama tumani"
            value={selectedDistrict}
            onChange={(event) => setDraft({ ...draft, target_district: event.currentTarget.value })}
          >
            {districts.map((district) => (
              <option value={district} key={district}>{district}</option>
            ))}
          </select>
        )}
        <button
          type="button"
          className="mini-btn"
          onClick={() => {
            const target = {
              level,
              region: level === "republic" ? "" : selectedRegion,
              district: level === "district" ? selectedDistrict : "",
            };
            if (level !== "republic" && !target.region) return;
            if (level === "district" && !target.district) return;
            const next = level === "republic"
              ? [target]
              : [
                ...targets.filter((value) => value.level !== "republic"),
                target,
              ].filter((value, index, all) => (
                all.findIndex((candidate) => JSON.stringify(candidate) === JSON.stringify(value)) === index
              ));
            setDraft({ ...draft, targets: next });
          }}
        >+ Hududni qo'shish</button>
        <div className="ad-targets">
          {targets.map((target, index) => (
            <span className="ad-target-chip" key={`${targetLabel(target)}-${index}`}>
              {targetLabel(target)}
              <button type="button" aria-label="Hududni o'chirish" onClick={() => setDraft({
                ...draft,
                targets: targets.filter((_, targetIndex) => targetIndex !== index),
              })}>×</button>
            </span>
          ))}
        </div>
      </div>
      <label className="field">Qachondan ko'rinsin?
        <input
          className="input"
          type="date"
          value={recordText(draft, "start_date")}
          onChange={(event) => setDraft({ ...draft, start_date: event.currentTarget.value })}
        />
      </label>
      <div className="field"><label>Har kuni qaysi vaqtda ko'rinsin?</label>
        <label className="ad-all-day">
          <input
            type="checkbox"
            checked={Boolean(draft.daily_all_day)}
            onChange={(event) => setDraft({ ...draft, daily_all_day: event.currentTarget.checked ? 1 : 0 })}
          /> Kun bo'yi ko'rinsin
        </label>
        {!draft.daily_all_day && (
          <div className="ad-daily-times">
            <select className="input" aria-label="Kunlik boshlanish" value={recordText(draft, "daily_start")} onChange={(event) => setDraft({ ...draft, daily_start: event.currentTarget.value })}>
              {hours.map((hour) => <option value={hour} key={hour}>{hour}</option>)}
            </select>
            <span>—</span>
            <select className="input" aria-label="Kunlik tugash" value={recordText(draft, "daily_end")} onChange={(event) => setDraft({ ...draft, daily_end: event.currentTarget.value })}>
              {hours.map((hour) => <option value={hour} key={hour}>{hour}</option>)}
            </select>
          </div>
        )}
        <div className="idesc">
          {draft.daily_all_day
            ? "Reklama kun davomida uzluksiz ko'rinadi."
            : `Har kuni ${recordText(draft, "daily_start")} dan ${recordText(draft, "daily_end")} gacha ko'rinadi.`}
        </div>
      </div>
      <label className="field">Qancha vaqt?
        <select className="input" value={Number(draft.duration_days ?? 1)} onChange={(event) => setDraft({ ...draft, duration_days: Number(event.currentTarget.value) })}>
          {[1, 3, 7, 14, 30].map((days) => <option value={days} key={days}>{days} kun</option>)}
        </select>
      </label>
      <div className="ad-price-box">
        <div className="idesc">Hisoblangan reklama narxi</div>
        <div className="price">{v1656Money(recordNumber(quote ?? draft, "total", "price"))}</div>
        <div className="idesc">{quoteError || (quote
          ? `${Number(quote.district_count ?? 0)} tuman × ${Number(quote.hours_per_day ?? 0)} soat × ${Number(quote.duration_days ?? 1)} kun × ${v1656Money(Number(quote.district_hour_rate ?? 0))}`
          : targets.length
            ? `${targets.length} ta hudud · ${Number(draft.duration_days ?? 1)} kun`
            : "Hududni tanlang.")}</div>
      </div>
      <div className="ad-info">Kvitansiya yuborilgach to'lov administrator tomonidan tekshiriladi. Reklama tasdiqlangandan keyin jadval bo'yicha ko'rinadi.</div>
      {fileError && <div className="app-toast on" role="alert">{fileError}</div>}
      {error && <div className="app-toast on" role="alert">{error}</div>}
      <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void save()}>Reklamani joylashtirish</button>
      <button type="button" className="btn btn-soft btn-block" onClick={cancel}>Bekor qilish</button>
    </div>
  );
}
