import { useMemo, type ReactNode } from "react";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import { money } from "./business-profile-config";


export type OrderFilter = "new" | "active" | "terminal";

export type SharedActions = {
  busy: boolean;
  form: string | null;
  draft: BusinessOnlineRecord;
  setForm: (value: string | null) => void;
  setDraft: (value: BusinessOnlineRecord) => void;
  create: (
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ) => Promise<void>;
  patch: (
    resource: BusinessOnlineResource,
    id: number | string,
    patch: BusinessOnlineRecord,
  ) => Promise<void>;
  remove: (
    resource: BusinessOnlineResource,
    id: number | string,
  ) => Promise<void>;
  action: (
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ) => Promise<void>;
};

const TERMINAL = new Set([
  "done", "delivered", "pickup_waiting_customer", "rejected",
  "cancelled", "canceled",
]);
const SERVICE_TYPES = new Set(["booking", "service", "queue", "medical"]);
const ITEM_FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["all", "Barchasi"],
  ["product", "Mahsulotlar"],
  ["service", "Xizmatlar"],
];

export function recordText(
  row: BusinessOnlineRecord,
  ...keys: string[]
): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== "") {
      return String(value);
    }
  }
  return "";
}

export function recordNumber(
  row: BusinessOnlineRecord,
  ...keys: string[]
): number {
  for (const key of keys) {
    const value = Number(row[key] ?? 0);
    if (Number.isFinite(value) && value !== 0) return value;
  }
  return 0;
}

export function recordId(
  row: BusinessOnlineRecord,
  index = 0,
): number | string {
  const value = row.id;
  return typeof value === "number" || typeof value === "string"
    ? value
    : index + 1;
}

export function isServiceOrder(row: BusinessOnlineRecord): boolean {
  return SERVICE_TYPES.has(recordText(
    row,
    "order_type",
    "kind",
    "order_category",
  ));
}

function statusLabel(value: unknown): string {
  const status = String(value ?? "");
  const labels: Record<string, string> = {
    new: "Yangi",
    accepted: "Qabul qilindi",
    pending: "Kutilmoqda",
    pending_payment: "To‘lov kutilmoqda",
    payment_waiting: "To‘lov kutilmoqda",
    payment_confirmed: "To‘lov tasdiqlandi",
    preparing: "Tayyorlanmoqda",
    ready: "Tayyor",
    in_delivery: "Yetkazilmoqda",
    delivered: "Yetkazildi",
    done: "Yakunlandi",
    active: "Faol",
    paused: "To‘xtatilgan",
    archived: "Arxivda",
    approved: "Tasdiqlangan",
    rejected: "Rad etilgan",
    draft: "Qoralama",
  };
  return (labels[status] ?? status) || "Holat ko‘rsatilmagan";
}

function dateLabel(value: unknown): string {
  const timestamp = Number(value ?? 0);
  return timestamp
    ? new Date(timestamp * 1000).toLocaleString("uz-UZ")
    : "Vaqt ko‘rsatilmagan";
}

function SectionTitle({ title, note }: { title: string; note: string }) {
  return (
    <div className="business-online__section-title">
      <h2>{title}</h2>
      <span>{note}</span>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="business-online__empty">{children}</div>;
}

export function SubscriptionsView({
  rows,
  duration,
  setDuration,
  busy,
  requestPlan,
}: {
  rows: BusinessOnlineRecord[];
  duration: number;
  setDuration: (value: number) => void;
  busy: boolean;
  requestPlan: (plan: string) => Promise<void>;
}) {
  const current = [...rows].reverse().find((row) => (
    ["active", "approved"].includes(recordText(row, "status"))
  ));
  const currentPlan = recordText(
    current ?? {},
    "plan",
    "tariff",
    "name",
  ) || "free";
  const plans = [
    {
      key: "free",
      icon: "🌱",
      name: "Bepul",
      caption: "Asosiy biznes profil uchun",
      benefits: [
        "Biznes profilidan foydalanish",
        "Mahsulot va xizmatlarni cheksiz joylash",
      ],
    },
    {
      key: "plus",
      icon: "✨",
      name: "Plus",
      caption: "Yaqin mijozlarga ko‘rinish",
      benefits: [
        "Bepul tarifdagi barcha imkoniyatlar",
        "“Sizga yaqin” bo‘limiga chiqarish huquqi",
      ],
    },
    {
      key: "pro",
      icon: "💎",
      name: "Pro",
      caption: "Hudud bo‘yicha keng ko‘rinish",
      benefits: [
        "Plus tarifdagi barcha imkoniyatlar",
        "Biznes metkasini xaritada ko‘rsatish huquqi",
      ],
    },
  ];
  return (
    <section className="subscription-screen">
      <div className="subscription-screen__note">
        <span>🧾</span>
        <div>
          <b>To‘lov tartibi</b>
          <p>
            Plus yoki Pro tarifini tanlang. Tarif administrator
            tasdiqlagandan keyin faollashadi.
          </p>
        </div>
      </div>
      <div className="subscription-screen__current">
        <small>Joriy tarif</small>
        <strong>{currentPlan.toUpperCase()}</strong>
        <span>{current ? statusLabel(current.status) : "Bepul tarif"}</span>
      </div>
      <SectionTitle title="Muddatni tanlang" note="Plus va Pro uchun" />
      <div
        className="subscription-screen__duration"
        role="group"
        aria-label="Obuna muddati"
      >
        {[1, 3, 12].map((month) => (
          <button
            type="button"
            key={month}
            className={duration === month ? "active" : ""}
            onClick={() => setDuration(month)}
          >
            {month} oy
          </button>
        ))}
      </div>
      <SectionTitle
        title="Tariflar"
        note="Mahsulot va xizmatlarni joylash cheksiz"
      />
      <div className="subscription-screen__plans">
        {plans.map((plan) => (
          <article key={plan.key}>
            <header>
              <span>{plan.icon}</span>
              <div>
                <h3>{plan.name}</h3>
                <p>{plan.caption}</p>
              </div>
              {currentPlan === plan.key && <em>Joriy</em>}
            </header>
            <ul>
              {plan.benefits.map((benefit) => (
                <li key={benefit}>{benefit}</li>
              ))}
            </ul>
            <button
              type="button"
              disabled={busy || currentPlan === plan.key}
              onClick={() => void requestPlan(plan.key)}
            >
              {currentPlan === plan.key
                ? "Joriy tarif"
                : plan.key === "free"
                  ? "Bepul tarifga o‘tish"
                  : `${plan.name} uchun to‘lov qilish`}
            </button>
          </article>
        ))}
      </div>
      <SectionTitle title="Obuna tarixi" note={`${rows.length} ta yozuv`} />
      <div className="business-online__list">
        {rows.length ? rows.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <b>{recordText(row, "plan", "tariff", "name") || "Tarif"}</b>
            <span>{statusLabel(row.status)}</span>
            <small>{dateLabel(row.created_at)}</small>
          </article>
        )) : <Empty>Obuna tarixi yo‘q.</Empty>}
      </div>
    </section>
  );
}

export function PaymentsView({
  rows,
  loading,
  refresh,
}: {
  rows: BusinessOnlineRecord[];
  loading: boolean;
  refresh: () => void;
}) {
  return (
    <section>
      <div className="business-online__toolbar">
        <p>
          Kvitansiya yuborilgan xizmatlar va administrator tekshiruvi
          holati.
        </p>
        <button type="button" onClick={refresh} disabled={loading}>
          Yangilash
        </button>
      </div>
      <div className="business-online__cards">
        {rows.length ? rows.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <header>
              <b>{recordText(row, "service", "plan", "purpose") || "To‘lov"}</b>
              <span>{statusLabel(row.status)}</span>
            </header>
            <strong>
              {money(recordNumber(row, "amount_snapshot", "amount", "total"))}
            </strong>
            <small>{dateLabel(row.created_at)}</small>
            {Array.isArray(row.events) && row.events.length > 0 && (
              <p>{row.events.length} ta holat hodisasi</p>
            )}
          </article>
        )) : <Empty>To‘lovlar hozircha yo‘q.</Empty>}
      </div>
    </section>
  );
}

export function ItemsView({
  rows,
  groups,
  query,
  setQuery,
  kind,
  setKind,
  ...actions
}: SharedActions & {
  rows: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
}) {
  const filtered = useMemo(() => rows.filter((row) => {
    const rowKind = recordText(row, "kind", "item_type", "type") || "product";
    const haystack = `${recordText(row, "name", "title")} ${recordText(
      row,
      "description",
      "descr",
    )}`.toLocaleLowerCase("uz");
    return (kind === "all" || kind === rowKind)
      && haystack.includes(query.toLocaleLowerCase("uz"));
  }), [rows, kind, query]);

  return (
    <section>
      <div className="business-online__toolbar business-online__toolbar--wrap">
        <div className="business-online__search">
          <span>🔍</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Tovar qidirish..."
          />
        </div>
        <div className="business-online__filters">
          {ITEM_FILTERS.map(([filterKey, label]) => (
            <button
              type="button"
              className={kind === filterKey ? "active" : ""}
              key={filterKey}
              onClick={() => setKind(filterKey)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="business-online__actions">
          <button
            type="button"
            onClick={() => {
              actions.setDraft({ kind: "product" });
              actions.setForm("group");
            }}
          >
            + Guruh
          </button>
          <button
            type="button"
            onClick={() => {
              actions.setDraft({ kind: "product" });
              actions.setForm("item");
            }}
          >
            + Mahsulot/xizmat
          </button>
        </div>
      </div>
      {actions.form && (
        <InlineForm
          title={actions.form === "group"
            ? "Yangi guruh"
            : "Yangi mahsulot yoki xizmat"}
          fields={actions.form === "group"
            ? ["name", "kind"]
            : ["name", "kind", "group_id", "price", "description"]}
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={() => actions.create(
            actions.form === "group" ? "item_groups" : "items",
            actions.draft,
          )}
        />
      )}
      <div className="business-online__groups">
        {groups.map((group, index) => (
          <span key={String(recordId(group, index))}>
            {recordText(group, "name", "title") || "Guruh"}
          </span>
        ))}
      </div>
      <div className="business-online__product-grid">
        {filtered.length ? filtered.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <div className="business-online__product-image">
              {recordText(row, "image_url", "photo_file")
                ? (
                  <img
                    src={recordText(row, "image_url", "photo_file")}
                    alt=""
                  />
                )
                : "🛍️"}
            </div>
            <h3>{recordText(row, "name", "title") || "Nomsiz"}</h3>
            <p>{recordText(row, "description", "descr", "note")}</p>
            <strong>{money(recordNumber(row, "price", "price_amount"))}</strong>
            <div>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.patch(
                  "items",
                  recordId(row, index),
                  { is_active: !Boolean(row.is_active ?? true) },
                )}
              >
                {Boolean(row.is_active ?? true) ? "Yashirish" : "Ko‘rsatish"}
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.remove(
                  "items",
                  recordId(row, index),
                )}
              >
                O‘chirish
              </button>
            </div>
          </article>
        )) : <Empty>Mos mahsulot yoki xizmat topilmadi.</Empty>}
      </div>
    </section>
  );
}

export function CrudCardsView({
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
  return (
    <section>
      <div className="business-online__toolbar">
        <p>{rows.length} ta yozuv</p>
        <button
          type="button"
          onClick={() => {
            actions.setDraft({ status: "active" });
            actions.setForm(resource);
          }}
        >
          {addLabel}
        </button>
      </div>
      {actions.form === resource && (
        <InlineForm
          title={addLabel.replace(/^\+\s*/, "Yangi ")}
          fields={fields}
          draft={actions.draft}
          setDraft={actions.setDraft}
          busy={actions.busy}
          onCancel={() => actions.setForm(null)}
          onSave={() => actions.create(resource, actions.draft)}
        />
      )}
      <div className="business-online__cards">
        {rows.length ? rows.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <header>
              <b>
                {recordText(row, "title", "name", "caption")
                  || `#${recordId(row, index)}`}
              </b>
              <span>{statusLabel(row.status)}</span>
            </header>
            <p>{recordText(row, "description", "descr", "caption", "note")}</p>
            {recordNumber(row, "price", "amount", "budget") > 0 && (
              <strong>
                {money(recordNumber(row, "price", "amount", "budget"))}
              </strong>
            )}
            <small>{dateLabel(row.created_at)}</small>
            <div className="business-online__card-actions">
              {extraAction?.(row, index)}
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.patch(
                  resource,
                  recordId(row, index),
                  {
                    status: recordText(row, "status") === "active"
                      ? "paused"
                      : "active",
                  },
                )}
              >
                {recordText(row, "status") === "active"
                  ? "To‘xtatish"
                  : "Faollashtirish"}
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.remove(
                  resource,
                  recordId(row, index),
                )}
              >
                O‘chirish
              </button>
            </div>
          </article>
        )) : <Empty>{empty}</Empty>}
      </div>
    </section>
  );
}

function InlineForm({
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
    group_id: "Guruh ID",
    price: "Narxi",
    description: "Tavsif",
    caption: "Qisqa matn",
    placement: "Joylashuvi",
    region: "Viloyat",
    district: "Tuman",
    category: "Toifa",
    media_type: "Media turi",
    media_url: "Media manzili",
  };
  return (
    <div className="business-online__form">
      <h2>{title}</h2>
      {fields.map((field) => (
        <label key={field}>
          {labels[field] ?? field}
          <input
            value={String(draft[field] ?? "")}
            onChange={(event) => setDraft({
              ...draft,
              [field]: event.currentTarget.value,
            })}
          />
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

export function OrdersView({
  rows,
  filter,
  setFilter,
  busy,
  setStatus,
}: {
  rows: BusinessOnlineRecord[];
  filter: OrderFilter;
  setFilter: (value: OrderFilter) => void;
  busy: boolean;
  setStatus: (id: number | string, status: string) => Promise<void>;
}) {
  const visible = rows.filter((row) => {
    const status = recordText(row, "status");
    if (filter === "new") return status === "new";
    if (filter === "terminal") return TERMINAL.has(status);
    return status !== "new" && !TERMINAL.has(status);
  });
  return (
    <section>
      <div className="business-online__filters business-online__filters--wide">
        <button
          type="button"
          className={filter === "new" ? "active" : ""}
          onClick={() => setFilter("new")}
        >
          Yangi
        </button>
        <button
          type="button"
          className={filter === "active" ? "active" : ""}
          onClick={() => setFilter("active")}
        >
          Jarayondagi
        </button>
        <button
          type="button"
          className={filter === "terminal" ? "active" : ""}
          onClick={() => setFilter("terminal")}
        >
          Yakunlangan
        </button>
      </div>
      <div className="business-online__orders">
        {visible.length ? visible.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <header>
              <div>
                <h3>
                  Buyurtma #{recordId(row, index)} — {recordText(
                    row,
                    "title",
                    "name",
                  ) || "Buyurtma"}
                </h3>
                <p>{dateLabel(row.created_at)}</p>
              </div>
              <span>{statusLabel(row.status)}</span>
            </header>
            <div className="business-online__order-lines">
              {Array.isArray(row.items) && row.items.map((item, itemIndex) => {
                const line = item as BusinessOnlineRecord;
                return (
                  <span key={String(recordId(line, itemIndex))}>
                    {recordText(line, "name", "title", "item_name")
                      || "Mahsulot"}
                    {" × "}{recordText(line, "qty", "quantity") || "1"}
                  </span>
                );
              })}
            </div>
            <strong>{money(recordNumber(row, "total_amount", "total"))}</strong>
            {!TERMINAL.has(recordText(row, "status")) && (
              <select
                disabled={busy}
                value={recordText(row, "status") || "new"}
                onChange={(event) => void setStatus(
                  recordId(row, index),
                  event.currentTarget.value,
                )}
              >
                <option value="new">Yangi</option>
                <option value="accepted">Qabul qilish</option>
                <option value="payment_waiting">To‘lov kutilmoqda</option>
                <option value="payment_confirmed">To‘lov tasdiqlandi</option>
                <option value="preparing">Tayyorlanmoqda</option>
                <option value="ready">Tayyor</option>
                <option value="in_delivery">Yetkazilmoqda</option>
                <option value="done">Yakunlash</option>
                <option value="rejected">Rad etish</option>
              </select>
            )}
          </article>
        )) : <Empty>Bu holatda buyurtma yo‘q.</Empty>}
      </div>
    </section>
  );
}

export function MessagesView({
  rows,
  value,
  setValue,
  busy,
  send,
}: {
  rows: BusinessOnlineRecord[];
  value: string;
  setValue: (value: string) => void;
  busy: boolean;
  send: () => Promise<void>;
}) {
  return (
    <section className="business-online__conversation">
      <div className="business-online__messages">
        {rows.length ? rows.map((row, index) => (
          <article
            className={recordText(row, "sender_kind") === "business"
              ? "mine"
              : ""}
            key={String(recordId(row, index))}
          >
            <p>{recordText(row, "text", "message", "body") || "Xabar"}</p>
            <small>{dateLabel(row.created_at)}</small>
          </article>
        )) : <Empty>Suhbatlar hozircha yo‘q.</Empty>}
      </div>
      <div className="business-online__composer">
        <input
          value={value}
          onChange={(event) => setValue(event.currentTarget.value)}
          placeholder="Xabar yozing..."
        />
        <button
          type="button"
          disabled={busy || !value.trim()}
          onClick={() => void send()}
        >
          Yuborish
        </button>
      </div>
    </section>
  );
}

export function ReviewsView({
  rows,
  ratingSum,
  ratingCount,
  replyId,
  reply,
  setReplyId,
  setReply,
  busy,
  save,
}: {
  rows: BusinessOnlineRecord[];
  ratingSum: number;
  ratingCount: number;
  replyId: number | string | null;
  reply: string;
  setReplyId: (id: number | string | null) => void;
  setReply: (value: string) => void;
  busy: boolean;
  save: (id: number | string) => Promise<void>;
}) {
  const average = ratingCount ? (ratingSum / ratingCount).toFixed(1) : "0";
  return (
    <section>
      <div className="business-online__rating">
        <div>
          <small>O‘rtacha baho</small>
          <strong>{average} ★</strong>
        </div>
        <div>
          <small>Jami fikr</small>
          <strong>{rows.length}</strong>
        </div>
      </div>
      <p className="business-online__hint">
        Mijoz fikrini o‘chirib bo‘lmaydi. Har bir fikrga javob
        berishingiz va javobingizni yangilashingiz mumkin.
      </p>
      <div className="business-online__reviews">
        {rows.length ? rows.map((row, index) => {
          const id = recordId(row, index);
          return (
            <article key={String(id)}>
              <header>
                <b>
                  {recordText(row, "reviewer_name", "user_name", "name")
                    || "Mijoz"}
                </b>
                <span>{recordText(row, "rating", "stars") || "0"} ★</span>
              </header>
              <p>
                {recordText(row, "text", "comment", "review")
                  || "Fikr matni yo‘q"}
              </p>
              {recordText(row, "business_reply", "reply") && (
                <blockquote>
                  {recordText(row, "business_reply", "reply")}
                </blockquote>
              )}
              {replyId === id ? (
                <div className="business-online__reply">
                  <textarea
                    value={reply}
                    onChange={(event) => setReply(event.currentTarget.value)}
                  />
                  <button
                    type="button"
                    disabled={busy || !reply.trim()}
                    onClick={() => void save(id)}
                  >
                    Javobni saqlash
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setReplyId(id);
                    setReply(recordText(row, "business_reply", "reply"));
                  }}
                >
                  Javob berish
                </button>
              )}
            </article>
          );
        }) : <Empty>Mijoz fikrlari yo‘q.</Empty>}
      </div>
    </section>
  );
}

export function NotificationsView({
  rows,
  busy,
  markAll,
  markOne,
}: {
  rows: BusinessOnlineRecord[];
  busy: boolean;
  markAll: () => Promise<void>;
  markOne: (id: number | string) => Promise<void>;
}) {
  const unread = rows.filter((row) => (
    !Boolean(Number(row.is_read ?? 0))
  )).length;
  return (
    <section>
      <div className="business-online__toolbar">
        <p>{unread} ta o‘qilmagan xabar</p>
        <button type="button" disabled={busy} onClick={() => void markAll()}>
          Barchasini o‘qilgan qilish
        </button>
      </div>
      <div className="business-online__notifications">
        {rows.length ? rows.map((row, index) => {
          const read = Boolean(Number(row.is_read ?? 0));
          return (
            <button
              type="button"
              className={read ? "read" : ""}
              key={String(recordId(row, index))}
              disabled={busy}
              onClick={() => void markOne(recordId(row, index))}
            >
              <span>{read ? "✓" : "●"}</span>
              <span>
                <b>{recordText(row, "title", "name") || "Bildirishnoma"}</b>
                <small>{recordText(row, "message", "text", "body")}</small>
              </span>
              <time>{dateLabel(row.created_at)}</time>
            </button>
          );
        }) : <Empty>Bildirishnomalar yo‘q.</Empty>}
      </div>
    </section>
  );
}

export function PeopleView({
  rows,
  busy,
  canUnfollow = false,
  unfollow = async () => undefined,
}: {
  rows: BusinessOnlineRecord[];
  busy: boolean;
  canUnfollow?: boolean;
  unfollow?: (id: number | string) => Promise<void>;
}) {
  return (
    <section>
      <div className="business-online__people">
        {rows.length ? rows.map((row, index) => (
          <article key={String(recordId(row, index))}>
            <div>
              {recordText(row, "avatar", "image_url")
                ? (
                  <img
                    src={recordText(row, "avatar", "image_url")}
                    alt=""
                  />
                )
                : "👤"}
            </div>
            <span>
              <b>
                {recordText(row, "name", "target_name", "business_name")
                  || "Profil"}
              </b>
              <small>
                {recordText(
                  row,
                  "username",
                  "public_username",
                  "target_kind",
                )}
              </small>
            </span>
            {canUnfollow && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void unfollow(recordId(row, index))}
              >
                Obunani bekor qilish
              </button>
            )}
          </article>
        )) : <Empty>Ro‘yxat hozircha bo‘sh.</Empty>}
      </div>
    </section>
  );
}
