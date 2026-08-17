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
import { CrudStoriesView } from "./CrudStoriesView";
import { EditorForm } from "./EditorForm";
import { ListingForm } from "./ListingForm";
import {
  Empty,
  PromotionTabs,
  cleanDraft,
  formId,
  localDateInputValue,
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
    return (
      <CrudStoriesView
        rows={rows}
        storyState={storyState}
        setStoryState={setStoryState}
        storyViewer={storyViewer}
        setStoryViewer={setStoryViewer}
        storyFile={storyFile}
        setStoryFile={setStoryFile}
        openForm={openForm}
        setOpenForm={setOpenForm}
        draft={draft}
        setDraft={setDraft}
        validationError={validationError}
        setValidationError={setValidationError}
        setConfirm={setConfirm}
        begin={begin}
        actions={actions}
        dialog={dialog()}
      />
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
