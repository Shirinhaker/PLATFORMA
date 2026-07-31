import { useState, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
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
  ...actions
}: SharedActions & {
  resource: BusinessOnlineResource;
  rows: BusinessOnlineRecord[];
  addLabel: string;
  empty: string;
  fields: string[];
  extraAction?: (row: BusinessOnlineRecord, index: number) => ReactNode;
}) {
  const [openForm, setOpenForm] = useState(false);
  const [draft, setDraft] = useState<BusinessOnlineRecord>({});
  const [storyState, setStoryState] = useState<"active" | "archived">("active");
  const [confirm, setConfirm] = useState<{
    id: number | string;
    title?: string;
    text: string;
    ok: string;
  } | null>(null);
  const [validationError, setValidationError] = useState("");

  function begin(next: BusinessOnlineRecord) {
    setDraft(next);
    setValidationError("");
    setOpenForm(true);
    actions.setDraft(next);
    actions.setForm(formId(resource, "new"));
  }

  async function saveDraft() {
    const title = recordText(draft, "title", "caption").trim();
    if (!title) {
      setValidationError(resource === "stories"
        ? "Istoriya matnini kiriting."
        : "Sarlavha kiritilishi shart.");
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
          <p>{confirm.text}</p>
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
                    <button type="button">Ko‘rish</button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => setConfirm({
                        id,
                        title: "Istoriyani o‘chirish",
                        text: "Bu istoriya darhol o‘chiriladi.",
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
              onClick={() => begin({ status: "pending", daily_all_day: 1, duration_days: 1 })}
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
  const categories = [
    { key: "uy", name: "Uy-joy" },
    { key: "ish", name: "Ish o'rinlari" },
    { key: "moshina", name: "Moshinalar" },
    { key: "hayvon", name: "Hayvonlar" },
    { key: "texnika", name: "Texnika" },
    { key: "boshqa", name: "Boshqalar" },
  ];
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
        <button type="button" className="upload">📷 Galereya yoki papkadan tanlash</button>
      </div>
      <div className="field">
        <label>Joylashuv</label>
        <button type="button" className="upload">📍 Xaritada joy belgilash</button>
        <div className="idesc">Joy hali belgilanmagan</div>
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
  return (
    <div className="form-wrap advertisement-form-v1656">
      <div className="ad-quality">
        <b>Rasm talabi:</b> kompyuter uchun 2744 × 368 px (7.46:1), telefon
        uchun 800 × 250 px (3.2:1) tavsiya etiladi. JPG, PNG yoki WEBP;
        har biri 5 MB gacha.
      </div>
      <div className="field"><label>Kompyuter uchun rasm — majburiy</label>
        <button type="button" className="upload">🖼 Galereyadan rasm tanlash</button>
      </div>
      <div className="field"><label>Telefon uchun rasm — ixtiyoriy</label>
        <button type="button" className="upload">📱 Telefon rasmini tanlash</button>
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
        <select className="input"><option>Tuman kesimida</option><option>Viloyat kesimida</option><option>Respublika bo'ylab</option></select>
        <button type="button" className="mini-btn">+ Hududni qo'shish</button>
      </div>
      <label className="field">Qachondan ko'rinsin?<input className="input" type="date" /></label>
      <label className="field">Qancha vaqt?
        <select className="input"><option>1 kun</option><option>3 kun</option><option>7 kun</option><option>14 kun</option><option>30 kun</option></select>
      </label>
      <div className="ad-price-box"><div className="idesc">Hisoblangan reklama narxi</div><div className="price">0 so'm</div><div className="idesc">Hududni tanlang.</div></div>
      <div className="ad-info">Kvitansiya yuborilgach to'lov administrator tomonidan tekshiriladi. Reklama tasdiqlangandan keyin jadval bo'yicha ko'rinadi.</div>
      {error && <div className="app-toast on" role="alert">{error}</div>}
      <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={() => void save()}>Reklamani joylashtirish</button>
      <button type="button" className="btn btn-soft btn-block" onClick={cancel}>Bekor qilish</button>
    </div>
  );
}
