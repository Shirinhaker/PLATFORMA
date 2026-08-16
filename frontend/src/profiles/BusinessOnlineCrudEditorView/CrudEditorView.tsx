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
import { AdvertisementForm } from "./AdvertisementForm";
import { EditorForm } from "./EditorForm";
import { ListingForm } from "./ListingForm";
import {
  Empty,
  PromotionTabs,
  cleanDraft,
  formId,
  localDateInputValue,
  storyRemaining,
  v1656Money,
} from "./shared";

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
  onPromotionChange,
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
  /** v1656 reklama/e'lon tablari orasida kabinet route'ini almashtiradi. */
  onPromotionChange?: (view: "advertisements" | "listings") => void;
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
      resource === "listings" &&
      (!Number.isFinite(Number(draft.lat)) || !Number.isFinite(Number(draft.lng)))
    ) {
      setValidationError(
        "Iltimos, e'lon joyini xaritada belgilang (📍 Xaritada joy belgilash).",
      );
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
            <button
              type="button"
              className="acf-cancel"
              onClick={() => setConfirm(null)}
            >
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
          {visible.length ? (
            visible.map((row, index) => {
              const id = recordId(row, index);
              const archived = ["archived", "expired"].includes(
                recordText(row, "state", "status"),
              );
              return (
                <article
                  className="my-story-card"
                  data-my-story-id={id}
                  key={String(id)}
                >
                  <div className="my-story-thumb">
                    {recordText(row, "thumbnail_url", "media_url") ? (
                      <img
                        src={recordText(row, "thumbnail_url", "media_url")}
                        alt="Istoriya muqovasi"
                      />
                    ) : (
                      <span className="my-story-thumb-fallback">Media topilmadi</span>
                    )}
                    {recordText(row, "media_type") === "video" && (
                      <span className="my-story-video-badge">▶ Video</span>
                    )}
                  </div>
                  <div className="my-story-main">
                    <div className="my-story-caption">
                      {recordText(row, "caption") || "Matnsiz istoriya"}
                    </div>
                    <div className="my-story-meta">
                      {new Date(Number(row.created_at ?? 0) * 1000).toLocaleString(
                        "uz-UZ",
                        {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        },
                      )}
                      <br />
                      👁 {Number(row.view_count ?? 0)} ko‘rish
                    </div>
                    <span
                      className={
                        archived ? "my-story-state archived" : "my-story-state"
                      }
                    >
                      {archived ? "Arxiv" : `Faol · ${storyRemaining(row.expires_at)}`}
                    </span>
                    <div className="my-story-actions">
                      <button type="button" onClick={() => setStoryViewer(row)}>
                        Ko‘rish
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() =>
                          setConfirm({
                            id,
                            title: "Istoriyani o‘chirish",
                            text: "Istoriya va uning media fayli butunlay o‘chiriladi.",
                            ok: "O‘chirish",
                          })
                        }
                      >
                        O‘chirish
                      </button>
                    </div>
                  </div>
                </article>
              );
            })
          ) : storyState === "archived" ? (
            <div className="empty my-stories-status">
              <h3>Arxiv hozircha bo‘sh</h3>
              <p>24 soati tugagan istoriyalar shu yerda saqlanadi.</p>
            </div>
          ) : (
            <div className="empty my-stories-status">
              <h3>Hali istoriya joylamagansiz</h3>
              <p>Rasm yoki 1 daqiqagacha video joylang.</p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => begin({ status: "active" })}
              >
                Istoriya joylash
              </button>
            </div>
          )}
        </div>
        {openForm && (
          <div className="story-layer on">
            <div
              className="story-sheet"
              role="dialog"
              aria-modal="true"
              aria-label="Istoriya joylash"
            >
              <div className="story-sheet-head">
                <div className="story-sheet-title">Istoriya joylash</div>
                <button
                  type="button"
                  className="story-text-btn"
                  onClick={() => setOpenForm(false)}
                >
                  Yopish
                </button>
              </div>
              <input
                type="file"
                hidden
                id="reactStoryFileInput"
                aria-label="Istoriya media fayli"
                accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0] ?? null;
                  if (
                    file &&
                    ![
                      "image/jpeg",
                      "image/png",
                      "image/webp",
                      "video/mp4",
                      "video/quicktime",
                      "video/webm",
                    ].includes(file.type)
                  ) {
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
                  if (
                    file?.type.startsWith("video/") &&
                    file.size > 100 * 1024 * 1024
                  ) {
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
                <button
                  type="button"
                  className="story-source-btn"
                  onClick={() => {
                    const input = document.getElementById("reactStoryFileInput");
                    input?.setAttribute("capture", "environment");
                    input?.click();
                  }}
                >
                  Kamera orqali<small>Hozir rasm yoki video oling</small>
                </button>
                <button
                  type="button"
                  className="story-source-btn"
                  onClick={() => {
                    const input = document.getElementById("reactStoryFileInput");
                    input?.removeAttribute("capture");
                    input?.click();
                  }}
                >
                  Galereyadan<small>Telefondagi rasm yoki videoni tanlang</small>
                </button>
              </div>
              {storyFile && (
                <div className="story-compose-fields on">
                  <div className="idesc">{storyFile.name}</div>
                  <label className="field">
                    Qisqa matn — ixtiyoriy
                    <textarea
                      className="textarea"
                      maxLength={200}
                      placeholder="Istoriya haqida qisqa yozing"
                      value={recordText(draft, "caption")}
                      onChange={(event) =>
                        setDraft({ ...draft, caption: event.currentTarget.value })
                      }
                    />
                    <span className="idesc">
                      {recordText(draft, "caption").length} / 200
                    </span>
                  </label>
                </div>
              )}
              {validationError && (
                <div className="story-upload-error on" role="alert">
                  {validationError}
                </div>
              )}
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
              >
                Joylash
              </button>
            </div>
          </div>
        )}
        {storyViewer && (
          <div className="story-viewer on">
            <div
              className="story-stage"
              role="dialog"
              aria-modal="true"
              aria-label="Istoriya"
            >
              <div className="story-viewer-media">
                {recordText(storyViewer, "media_type") === "video" ? (
                  <video src={recordText(storyViewer, "media_url")} controls />
                ) : (
                  <img
                    src={recordText(storyViewer, "media_url", "thumbnail_url")}
                    alt="Istoriya"
                  />
                )}
              </div>
              <button
                type="button"
                className="story-viewer-close"
                aria-label="Istoriyani yopish"
                onClick={() => setStoryViewer(null)}
              >
                ×
              </button>
              <div className="story-viewer-caption">
                {recordText(storyViewer, "caption")}
              </div>
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
        <PromotionTabs active="listings" onChange={onPromotionChange} />
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
              {rows.length ? (
                rows.map((row, index) => {
                  const id = recordId(row, index);
                  const icon =
                    (
                      {
                        uy: "🏠",
                        ish: "💼",
                        moshina: "🚙",
                        hayvon: "🐾",
                        texnika: "📱",
                        boshqa: "📦",
                      } as Record<string, string>
                    )[recordText(row, "cat", "category")] || "📦";
                  const visibility =
                    recordText(row, "visibility") === "own"
                      ? "🏪 Faqat mehmonlar"
                      : "🌍 Butun platforma";
                  const status =
                    recordText(row, "status") === "active" ? "Faol" : "O'chiq";
                  const mediaCount = Array.isArray(row.media) ? row.media.length : 0;
                  return (
                    <article className="elon-item" key={String(id)}>
                      <div className="li-thumb">
                        <span>{icon}</span>
                      </div>
                      <div className="li-main">
                        <div className="li-title">{recordText(row, "title")}</div>
                        <div className="li-price">{recordText(row, "price")}</div>
                        <div className="li-meta">
                          {visibility} · {status}
                          {mediaCount ? ` · 📎 ${mediaCount}` : ""}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="mini-ic"
                        aria-label="E'lonni o'chirish"
                        onClick={() =>
                          setConfirm({
                            id,
                            text: "Bu e'lon o'chirilsinmi?",
                            ok: "O'chirish",
                          })
                        }
                      >
                        🗑
                      </button>
                    </article>
                  );
                })
              ) : (
                <div className="empty listing-empty">
                  <h3>Hozircha e'lon yo'q</h3>
                  <p>Yuqoridagi tugma orqali joylang.</p>
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
        <PromotionTabs active="ads" onChange={onPromotionChange} />
        {!openForm ? (
          <div className="biz-ads-pane">
            <div className="ad-info">
              Bosh sahifadagi banner reklama. Hudud, boshlanish vaqti va davomiyligini
              o'zingiz tanlaysiz.
            </div>
            <button
              type="button"
              className="btn btn-primary btn-block"
              onClick={() =>
                begin({
                  status: "payment_pending",
                  daily_all_day: 1,
                  daily_start: "",
                  daily_end: "",
                  duration_days: 1,
                  start_date: localDateInputValue(),
                  target_level: "district",
                  targets: [],
                })
              }
            >
              + Reklama joylashtirish
            </button>
            <div>
              {rows.length ? (
                rows.map((row, index) => {
                  const id = recordId(row, index);
                  const status = recordText(row, "status");
                  const label =
                    (
                      {
                        active: "Faol",
                        scheduled: "Rejalashtirilgan",
                        payment_pending: "To‘lov kutilmoqda",
                        ended: "Yakunlangan",
                        cancelled: "Bekor qilingan",
                      } as Record<string, string>
                    )[status] || status;
                  const targets = Array.isArray(row.targets)
                    ? row.targets
                        .map((target) => {
                          const item = target as BusinessOnlineRecord;
                          if (item.level === "republic") return "🇺🇿 Respublika";
                          if (item.level === "region")
                            return `Viloyat: ${recordText(item, "region")}`;
                          return `${recordText(item, "region")} · ${recordText(item, "district")}`;
                        })
                        .join(", ")
                    : "";
                  return (
                    <article className="ad-own-card" key={String(id)}>
                      <div className="ad-own-top">
                        <div className="ad-own-thumb">
                          {recordText(row, "image_file", "image_url") && (
                            <img
                              src={recordText(row, "image_file", "image_url")}
                              alt=""
                            />
                          )}
                        </div>
                        <div className="ad-own-main">
                          <div className="li-title">{recordText(row, "title")}</div>
                          <div className="li-meta">{targets}</div>
                          <div className="li-meta">
                            {Number(row.duration_days ?? 1)} kun ·{" "}
                            {row.daily_all_day ? "Kun bo'yi" : "Belgilangan vaqtda"}
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
                      {!["cancelled", "ended"].includes(status) && (
                        <button
                          type="button"
                          className="btn btn-outline btn-block"
                          onClick={() =>
                            setConfirm({
                              id,
                              text: "Reklama bekor qilinsinmi?",
                              ok: "Bekor qilish",
                            })
                          }
                        >
                          Bekor qilish
                        </button>
                      )}
                    </article>
                  );
                })
              ) : (
                <div className="empty ad-empty">
                  <div className="ic">📣</div>
                  <h3>Reklama yo'q</h3>
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
