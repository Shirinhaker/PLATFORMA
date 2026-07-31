import { useMemo, useState, type ReactNode } from "react";

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
  const category = recordText(row, "order_category");
  if (category) return category === "service";
  return SERVICE_TYPES.has(recordText(
    row,
    "order_type",
    "kind",
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

function subscriptionPlanName(value: unknown): string {
  const code = String(value ?? "").toLocaleLowerCase("uz");
  return code === "pro" ? "Pro" : code === "plus" ? "Plus" : "Bepul";
}

function subscriptionDate(value: unknown): string {
  const seconds = Number(value ?? 0);
  if (!seconds) return "—";
  return new Date(seconds * 1000).toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function paymentDate(value: unknown): string {
  const timestamp = Number(value ?? 0);
  return timestamp
    ? new Date(timestamp * 1000).toLocaleString("uz-UZ")
    : "";
}

function notifyTime(value: unknown): string {
  const timestamp = Number(value ?? 0);
  if (!timestamp) return "";
  const date = new Date(timestamp * 1000);
  return `${date.toLocaleDateString("uz-UZ")} · ${date.toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function orderCreatedText(value: unknown): string {
  const timestamp = Number(value ?? 0);
  if (!timestamp) return "—";
  const date = new Date(timestamp * 1000);
  return `${date.toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })} · ${date.toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function v1656Money(value: number): string {
  return `${new Intl.NumberFormat("uz-UZ").format(Number(value || 0))} so'm`;
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
    "plan_code",
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
        "Mahsulot yoki xizmatlarni “Sizga yaqin” bo‘limiga chiqarish huquqi",
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
  const paid = currentPlan !== "free";
  const history = rows.filter((row) => row !== current);
  return (
    <section className="subscription-shell">
      <div className="subscription-demo-note">
        <span>🧾</span>
        <div>
          <b>To‘lov tartibi</b><br />
          Plus yoki Pro tarifini tanlang, kvitansiyani yuboring. Tarif
          administrator tasdiqlagandan keyin faollashadi.
        </div>
      </div>
      <div className="subscription-current">
        <div className="subscription-current-top">
          <div className="subscription-current-copy">
            <div className="subscription-current-label">Joriy tarif</div>
            <div className="subscription-current-name">
              {subscriptionPlanName(currentPlan)}
            </div>
          </div>
          <span className="subscription-current-badge">Faol</span>
        </div>
        <div className="subscription-current-dates">
          <div className="subscription-date">
            <span>Boshlangan sana</span>
            <b>{current
              ? current.starts_at
                ? subscriptionDate(current.starts_at)
                : "—"
              : "Avtomatik Bepul"}</b>
          </div>
          <div className="subscription-date">
            <span>Tugash sanasi</span>
            <b>{paid ? subscriptionDate(current?.expires_at) : "Muddatsiz"}</b>
          </div>
        </div>
      </div>
      <div className="subscription-section-title">
        <h3>Muddatni tanlang</h3><p>Plus va Pro uchun</p>
      </div>
      <div
        className="subscription-duration"
        role="group"
        aria-label="Obuna muddati"
      >
        {[1, 3, 12].map((month) => (
          <button
            type="button"
            key={month}
            className={duration === month ? "on" : ""}
            aria-pressed={duration === month}
            disabled={busy}
            onClick={() => setDuration(month)}
          >
            {month} oy
          </button>
        ))}
      </div>
      <div className="subscription-section-title">
        <h3>Tariflar</h3><p>Mahsulot va xizmatlarni joylash cheksiz</p>
      </div>
      <div className="subscription-plan-grid">
        {plans.map((plan) => (
          <article
            className={currentPlan === plan.key
              ? "subscription-plan-card current"
              : "subscription-plan-card"}
            data-plan={plan.key}
            key={plan.key}
          >
            <div className="subscription-plan-top">
              <div className="subscription-plan-copy">
                <div className="subscription-plan-icon">{plan.icon}</div>
                <div>
                  <div className="subscription-plan-name">{plan.name}</div>
                  <div className="subscription-plan-caption">{plan.caption}</div>
                </div>
              </div>
              <span className="subscription-current-pill">Joriy</span>
            </div>
            <ul className="subscription-benefits">
              {plan.benefits.map((benefit) => (
                <li key={benefit}>{benefit}</li>
              ))}
            </ul>
            <button
              type="button"
              className="subscription-action"
              disabled={busy || plan.key === "free"}
              onClick={() => void requestPlan(plan.key)}
            >
              {plan.key === "free"
                ? currentPlan === "free"
                  ? "Joriy bepul tarif"
                  : "Bepul tarif avtomatik"
                : currentPlan === plan.key
                  ? "Muddatni uzaytirish"
                  : `${plan.name} uchun to‘lov qilish`}
            </button>
          </article>
        ))}
      </div>
      <div className="subscription-section-title">
        <h3>Obuna tarixi</h3><p>Avvalgi tariflar</p>
      </div>
      <div className="subscription-history">
        {history.length ? history.map((row, index) => {
          const status = recordText(row, "status") === "expired"
            ? "Muddati tugagan"
            : "Almashtirilgan";
          return (
            <div className="subscription-history-row" key={String(recordId(row, index))}>
              <div>
                <b>{subscriptionPlanName(recordText(row, "plan", "plan_code", "tariff"))}</b>
                <p>
                  {subscriptionDate(row.starts_at)} — {row.expires_at
                    ? subscriptionDate(row.expires_at)
                    : "Muddatsiz"}
                  {row.duration_months ? ` · ${Number(row.duration_months)} oy` : ""}
                </p>
              </div>
              <span className="subscription-history-status">{status}</span>
            </div>
          );
        }) : (
          <div className="subscription-state">
            <h3>Tarix hozircha bo‘sh</h3>
            <p>
              Tarif almashtirilganda yoki muddati tugaganda avvalgi obunalar
              shu yerda ko‘rinadi.
            </p>
          </div>
        )}
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
  function serviceLabel(row: BusinessOnlineRecord) {
    const service = recordText(row, "service_type", "service");
    const plan = recordText(row, "plan_code", "plan");
    if (service === "subscription" || plan) {
      return `${plan === "pro" ? "Pro" : "Plus"} obuna`;
    }
    if (service === "advertisement") return "Reklama joylashtirish";
    if (service === "listing") return "E’lon joylashtirish";
    return "To‘lov";
  }
  function paymentStatus(value: unknown) {
    const status = String(value ?? "");
    return status === "approved"
      ? "Tasdiqlangan"
      : status === "rejected"
        ? "Rad etilgan"
        : status === "cancelled"
          ? "Bekor qilingan"
          : "Tekshirilmoqda";
  }
  return (
    <section className="form-wrap">
      <div className="lead">To‘lovlarim</div>
      <div className="lead-sub">
        Kvitansiya yuborilgan xizmatlar va administrator tekshiruvi holati.
      </div>
      <button
        type="button"
        className="btn btn-outline btn-block"
        onClick={refresh}
        disabled={loading}
      >
        Yangilash
      </button>
      <div className="payment-list">
        {rows.length ? rows.map((row, index) => {
          const status = recordText(row, "status") || "pending";
          return (
            <article className="payment-card" key={String(recordId(row, index))}>
              <div className="payment-card-head">
                <div>
                  <b>{serviceLabel(row)}</b>
                  <div className="payment-card-code">
                    {recordText(row, "request_code") || `#${recordId(row, index)}`}
                    {" · "}{paymentDate(row.created_at)}
                  </div>
                </div>
                <span className={`payment-status ${status}`}>
                  {paymentStatus(status)}
                </span>
              </div>
              <div className="payment-card-amount">
                {v1656Money(recordNumber(row, "amount", "amount_snapshot", "total"))}
              </div>
              {recordText(row, "reason") && (
                <div className="subscription-action-message error">
                  {recordText(row, "reason")}
                </div>
              )}
              {status === "rejected" && (
                <>
                  <button type="button" className="btn btn-outline btn-block">
                    Yangi kvitansiya tanlash
                  </button>
                  <button type="button" className="btn btn-primary btn-block">
                    Qayta yuborish
                  </button>
                </>
              )}
            </article>
          );
        }) : (
          <div className="subscription-state">
            <h3>To‘lovlar yo‘q</h3>
            <p>Yuborgan kvitansiyalaringiz shu yerda ko‘rinadi.</p>
          </div>
        )}
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
            <small>{notifyTime(row.created_at)}</small>
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
  const activeStatuses = new Set([
    "new", "accepted", "preparing", "ready", "tayyor",
    "courier_assigned", "courier_arrived_store", "handoff_waiting_seller",
    "in_delivery", "courier_arrived_customer", "delivered_waiting_customer",
    "pickup_waiting_customer",
  ]);
  const problems = rows.filter((row) => Boolean(row.problem_open));
  const active = rows.filter((row) => (
    !row.problem_open && activeStatuses.has(recordText(row, "status"))
  ));
  const done = rows.filter((row) => (
    !row.problem_open && !activeStatuses.has(recordText(row, "status"))
  ));
  const current = filter === "active"
    ? "problem"
    : filter === "terminal"
      ? "done"
      : "active";
  const visible = current === "problem"
    ? problems
    : current === "done"
      ? done
      : active;

  function setTab(value: "active" | "problem" | "done") {
    setFilter(value === "active" ? "new" : value === "problem" ? "active" : "terminal");
  }

  function orderStatus(value: unknown) {
    const labels: Record<string, string> = {
      new: "Yangi",
      accepted: "To'lov kutilmoqda",
      preparing: "Tayyorlanmoqda",
      rejected: "Rad etildi",
      done: "Yakunlandi",
      cancelled: "Bekor qilindi",
      canceled: "Bekor qilindi",
      ready: "Tayyor",
      tayyor: "Tayyor",
      courier_assigned: "Dostavkachi biriktirildi",
      courier_arrived_store: "Dostavkachi sotuvchiga yetib keldi",
      handoff_waiting_seller: "Topshirish tasdig'i kutilmoqda",
      in_delivery: "Yo'lda",
      courier_arrived_customer: "Dostavkachi yetib keldi",
      delivered_waiting_customer: "Qabul tasdig'i kutilmoqda",
      pickup_waiting_customer: "Qabul tasdig'i kutilmoqda",
    };
    const status = String(value ?? "");
    return labels[status] ?? status ?? "—";
  }

  function orderStatusClass(value: unknown) {
    const status = String(value ?? "");
    if (["accepted", "preparing", "done", "ready", "tayyor"].includes(status)) {
      return "credit";
    }
    return ["rejected", "cancelled", "canceled"].includes(status)
      ? "debit"
      : "";
  }

  function orderType(value: unknown) {
    const type = String(value ?? "");
    return ({
      delivery: "Yetkazib berish",
      pickup: "Olib ketish",
      booking: "Navbat/qabul",
    } as Record<string, string>)[type] ?? type ?? "—";
  }

  return (
    <section>
      <div className="order-tabs-v1656">
        <button
          type="button"
          className={current === "active" ? "seg-b on" : "seg-b"}
          onClick={() => setTab("active")}
        >
          Buyurtmalar ({active.length})
          {active.some((row) => Boolean(row.is_unread)) ? " 🔔" : ""}
        </button>
        <button
          type="button"
          className={current === "problem" ? "seg-b on" : "seg-b"}
          onClick={() => setTab("problem")}
        >
          Muammoli ({problems.length})
        </button>
        <button
          type="button"
          className={current === "done" ? "seg-b on" : "seg-b"}
          onClick={() => setTab("done")}
        >
          Yakunlangan ({done.length})
          {done.some((row) => Boolean(row.is_unread)) ? " 🔔" : ""}
        </button>
      </div>
      <div className="orders-v1656-list">
        {visible.length ? visible.map((row, index) => {
          const id = recordId(row, index);
          const status = recordText(row, "status");
          const classes = [
            "item",
            "order-card",
            status === "new" ? "order-new" : "",
            row.is_unread ? "order-unread" : "",
          ].filter(Boolean).join(" ");
          return (
          <article className={classes} key={String(id)}>
            <div className="order-card-top">
              <span className="order-no-pill">BUYURTMA №{id}</span>
              <span className="idesc order-card-time">🕒 {orderCreatedText(row.created_at)}</span>
            </div>
            <div className="order-card-main">
              <div>
                <div className="iname">{recordText(row, "title", "name") || "Buyurtma"}</div>
                <div className="idesc">
                  Mijoz: {recordText(row, "customer_name") || "—"}
                </div>
                {Boolean(row.is_unread) && (
                  <div className="order-unread-pill">
                    {recordText(row, "last_event") === "msg"
                      ? "💬 Xabar keldi"
                      : "🔔 Yangi buyurtma"}
                  </div>
                )}
                <div className="idesc">Turi: {orderType(row.order_type)}</div>
                {recordText(row, "address") && (
                  <div className="idesc">📍 {recordText(row, "address")}</div>
                )}
                {recordText(row, "phone") && (
                  <div className="idesc">☎ {recordText(row, "phone")}</div>
                )}
                {recordText(row, "note") && (
                  <div className="idesc">{recordText(row, "note")}</div>
                )}
              </div>
              <span className={`tx-amt ${orderStatusClass(status)}`.trim()}>
                {orderStatus(status)}
              </span>
            </div>
            {Array.isArray(row.items) && row.items.length > 0 && (
              <div className="order-card-items">
                {row.items.map((item, itemIndex) => {
                const line = item as BusinessOnlineRecord;
                return (
                  <div className="idesc order-card-line" key={String(recordId(line, itemIndex))}>
                    <span>
                      {recordText(line, "name", "title", "item_name") || "Mahsulot"}
                      {" × "}{recordText(line, "qty", "quantity") || "1"}
                      {recordText(line, "unit") && recordText(line, "unit") !== "dona"
                        ? ` ${recordText(line, "unit")}`
                        : ""}
                    </span>
                    <b>{recordNumber(line, "line_total")
                      ? v1656Money(recordNumber(line, "line_total"))
                      : recordText(line, "price") || "—"}</b>
                  </div>
                );
                })}
                {recordText(row, "total_text") && (
                  <div className="iprice order-card-total">
                    Jami: {recordText(row, "total_text")}
                  </div>
                )}
              </div>
            )}
            {status === "new" && (
              <div className="order-card-actions">
                <button
                  type="button"
                  className="mini-btn"
                  disabled={busy}
                  onClick={() => void setStatus(id, "accepted")}
                >
                  Qabul qilish
                </button>
                <button
                  type="button"
                  className="mini-btn danger"
                  disabled={busy}
                  onClick={() => void setStatus(id, "rejected")}
                >
                  Rad etish
                </button>
              </div>
            )}
            {status === "accepted" && !row.problem_open && (
              <button
                type="button"
                className="mini-btn danger"
                disabled={busy}
                onClick={() => void setStatus(id, "cancelled")}
              >
                Bekor qilish
              </button>
            )}
            {status === "preparing" && (
              <button
                type="button"
                className="mini-btn success"
                disabled={busy}
                onClick={() => void setStatus(id, "ready")}
              >
                ✅ Buyurtma tayyor
              </button>
            )}
            <div className="idesc order-card-hint">
              Batafsil ko‘rish va chat uchun bosing
            </div>
          </article>
        );}) : (
          <div className="empty order-empty">
            <h3>{current === "done"
              ? "Yakunlangan buyurtma yo'q"
              : current === "problem"
                ? "Muammoli buyurtma yo'q"
                : "Faol buyurtma yo'q"}</h3>
          </div>
        )}
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
  send: (
    peer: { id: string; kind: string },
    text: string,
  ) => Promise<void>;
}) {
  const [peerKey, setPeerKey] = useState<string | null>(null);
  const conversations = useMemo(() => {
    const result = new Map<string, BusinessOnlineRecord>();
    rows.forEach((row, index) => {
      const id = recordText(row, "target_id", "peer_id", "receiver_id", "user_id")
        || String(recordId(row, index));
      const kind = recordText(row, "target_kind", "peer_kind", "receiver_kind") || "user";
      const key = `${kind}:${id}`;
      const previous = result.get(key);
      result.set(key, {
        ...(previous ?? {}),
        ...row,
        _key: key,
        _peer_id: id,
        _peer_kind: kind,
      });
    });
    return [...result.values()];
  }, [rows]);
  const peer = conversations.find((row) => row._key === peerKey) ?? null;
  const peerName = peer
    ? recordText(peer, "name", "target_name", "peer_name", "receiver_name") || "Suhbat"
    : "";
  const thread = peer ? rows.filter((row, index) => {
    const id = recordText(row, "target_id", "peer_id", "receiver_id", "user_id")
      || String(recordId(row, index));
    const kind = recordText(row, "target_kind", "peer_kind", "receiver_kind") || "user";
    return `${kind}:${id}` === peerKey;
  }) : [];

  if (!peer) {
    return (
      <section className="chats-list">
        {conversations.length ? conversations.map((row) => {
          const name = recordText(row, "name", "target_name", "peer_name", "receiver_name") || "Suhbat";
          const initials = name.trim().split(/\s+/).slice(0, 2)
            .map((part) => part.charAt(0)).join("").toLocaleUpperCase("uz");
          return (
            <button
              type="button"
              className="conv"
              key={String(row._key)}
              onClick={() => setPeerKey(String(row._key))}
            >
              <span className="conv-av">{initials || "S"}</span>
              <span className="conv-main">
                <span className="conv-name">{name}</span>
                <span className="conv-last">
                  {recordText(row, "last", "text", "message", "body")}
                </span>
              </span>
              {Number(row.unread ?? 0) > 0 && (
                <span className="conv-badge">{Number(row.unread)}</span>
              )}
            </button>
          );
        }) : (
          <div className="empty chat-empty">
            <h3>Suhbatlar yo'q</h3>
            <p>E'lon yoki sahifadan «Xabar yozish» orqali suhbat boshlang.</p>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="chat-screen" aria-label={peerName}>
      <button type="button" className="chat-back" onClick={() => setPeerKey(null)}>
        ← Suhbatlar
      </button>
      <div className="chat-thread">
        {thread.length ? thread.map((row, index) => {
          const deleted = Boolean(row.is_deleted);
          const mine = recordText(row, "sender_kind") === "business" || Boolean(row.mine);
          return (
            <div className={`msg ${mine ? "me" : "them"}`} key={String(recordId(row, index))}>
              {!deleted && (
                <button type="button" className="order-msg-menu-btn" aria-label="Xabar amallari">
                  ⋯
                </button>
              )}
              {deleted ? (
                <div className="order-chat-deleted">Xabar o‘chirildi</div>
              ) : (
                <div className="order-chat-text">
                  {recordText(row, "text", "message", "body")}
                </div>
              )}
              <span className="msg-time">{notifyTime(row.created_at)}</span>
            </div>
          );
        }) : <div className="chat-day">Hozircha xabar yo'q. Birinchi bo'lib yozing!</div>}
      </div>
      <div className="chat-compose">
        <div className="chat-attach-row">
          <label className="chat-attach-btn">
            📎 Rasm qo‘shish
            <input className="chat-file" type="file" accept="image/*" />
          </label>
        </div>
        <div className="chat-bar">
          <input
            className="chat-input"
            value={value}
            onChange={(event) => setValue(event.currentTarget.value)}
            placeholder="Xabar yozing..."
            autoComplete="off"
          />
          <button
            type="button"
            className="chat-send"
            aria-label="Yuborish"
            disabled={busy || !value.trim()}
            onClick={() => void send({
              id: String(peer._peer_id),
              kind: String(peer._peer_kind),
            }, value.trim())}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
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
  save: (id: number | string, reply: string) => Promise<void>;
}) {
  const average = ratingCount ? (ratingSum / ratingCount).toFixed(1) : "0";
  const [replyError, setReplyError] = useState("");
  return (
    <section>
      {replyError && (
        <div className="app-toast on" role="alert">{replyError}</div>
      )}
      <div className="panel-card business-review-summary">
        <div>
          <div className="idesc">O'rtacha baho</div>
          <div className="business-review-average">{average} <span>★</span></div>
        </div>
        <div className="business-review-count">
          <div className="idesc">Jami fikr</div>
          <div>{rows.length}</div>
        </div>
      </div>
      <div className="idesc business-review-hint">
        Mijoz fikrini o'chirib bo'lmaydi. Har bir fikrga javob
        berishingiz va javobingizni yangilashingiz mumkin.
      </div>
      <div className="business-review-list">
        {rows.length ? rows.map((row, index) => {
          const id = recordId(row, index);
          const ownerReply = recordText(row, "owner_reply", "business_reply", "reply");
          const activeReply = replyId === id ? reply : ownerReply;
          return (
            <article className="sp-review-card" key={String(id)}>
              <div className="business-review-card-head">
                <div>
                  <b>{recordText(row, "user_name", "reviewer_name", "name") || "Mijoz"}</b>
                  <div className="idesc business-review-date">{notifyTime(row.created_at)}</div>
                </div>
                <span className="business-review-stars">
                  {"★".repeat(Math.max(0, Number(row.stars ?? row.rating ?? 0)))}
                </span>
              </div>
              <div className="idesc business-review-comment">
                {recordText(row, "comment", "text", "review") || "Matnsiz baho"}
              </div>
              {ownerReply && (
                <div className="sp-owner-reply">
                  <b>Sizning javobingiz</b>
                  <div>{ownerReply}</div>
                </div>
              )}
              <textarea
                className="textarea"
                placeholder="Mijozga javob yozing..."
                value={activeReply}
                onFocus={() => {
                  if (replyId !== id) {
                    setReplyId(id);
                    setReply(ownerReply);
                  }
                }}
                onChange={(event) => {
                  if (replyId !== id) setReplyId(id);
                  setReplyError("");
                  setReply(event.currentTarget.value);
                }}
              />
              <button
                type="button"
                className="btn btn-soft btn-block"
                disabled={busy}
                onClick={() => {
                  const value = activeReply.trim();
                  if (!value) {
                    setReplyError("Javob matnini kiriting.");
                    return;
                  }
                  setReplyError("");
                  void save(id, value);
                }}
              >
                {ownerReply ? "Javobni yangilash" : "Javob berish"}
              </button>
            </article>
          );
        }) : (
          <div className="empty business-review-empty">
            <h3>Hozircha fikr yo'q</h3>
            <p>Mijozlar qoldirgan baho va fikrlar shu yerda ko'rinadi.</p>
          </div>
        )}
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
  return (
    <section className="form-wrap notify-v1656">
      <div className="lead">Bildirishnomalarim</div>
      <div className="lead-sub">
        Buyurtma jarayonidagi muhim xabarlar shu yerda saqlanadi.
      </div>
      <div className="set-row notify-push-row">
        <span>📲 Push notification</span>
        <label>
          <input type="checkbox" defaultChecked /> Yoqilgan
        </label>
      </div>
      <div className="elon-hint">Mobil ilova qurilmasi ulanmagan.</div>
      <div className="notify-v1656-head">
        <b>Buyurtma bildirishnomalari</b>
        <button
          type="button"
          className="mini-btn"
          disabled={busy}
          onClick={() => void markAll()}
        >
          Barchasini o'qish
        </button>
      </div>
      <div className="order-notify-list">
        {rows.length ? rows.map((row, index) => {
          const read = Boolean(Number(row.is_read ?? 0));
          return (
            <button
              type="button"
              className="menu-card"
              style={!read ? { borderColor: "var(--koprik-primary)" } : undefined}
              key={String(recordId(row, index))}
              disabled={busy}
              onClick={() => void markOne(recordId(row, index))}
            >
              <span className="menu-ic">{read ? "🔔" : "🟢"}</span>
              <span className="menu-main">
                <b>{recordText(row, "title", "name") || "Bildirishnoma"}</b>
                <span>{recordText(row, "body", "message", "text")}</span>
                <small>{notifyTime(row.created_at)}</small>
              </span>
              <span className="chev">›</span>
            </button>
          );
        }) : (
          <div className="empty notify-empty">
            <h3>Hozircha xabar yo'q</h3>
            <p>Buyurtma yangiliklari shu yerda chiqadi.</p>
          </div>
        )}
      </div>
      <div className="notify-divider" />
      <div className="lead notify-filter-title">E'lon filtrlari</div>
      <div className="lead-sub">
        Mos e'lon joylanganda Telegramingizga xabar keladi.
      </div>
      <button type="button" className="btn btn-primary btn-block">
        ➕ Yangi filtr qo'shish
      </button>
      <div className="empty notify-filter-empty">
        <h3>Filtr yo'q</h3>
        <p>«Yangi filtr» orqali qiziqishlaringizni belgilang.</p>
      </div>
    </section>
  );
}

export function PeopleView({
  rows,
  kind,
}: {
  rows: BusinessOnlineRecord[];
  busy: boolean;
  kind: "followers" | "following";
}) {
  return (
    <section>
      {rows.length ? (
        <>
          <div className="list-sub">
            {rows.length} ta {kind === "followers" ? "obunachi" : "kuzatilmoqda"}
          </div>
          {rows.map((row, index) => {
            const personKind = recordText(row, "kind", "target_kind") || "user";
            const name = recordText(row, "name", "target_name", "business_name") || "Profil";
            const initials = name.trim().split(/\s+/).slice(0, 2)
              .map((part) => part.charAt(0)).join("").toLocaleUpperCase("uz");
            const info = recordText(row, "info", "username", "public_username");
            return (
            <article className="elon-item" key={String(recordId(row, index))}>
              <div
                className="li-thumb"
                style={{ background: personKind === "business"
                  ? "var(--koprik-primary-tint)"
                  : "var(--koprik-amber-tint)" }}
              >
                {personKind === "business" ? "🏪" : initials || "?"}
              </div>
              <div className="li-main">
                <div className="li-title">{name}</div>
                <div className="li-meta">
                  {personKind === "business"
                    ? `Biznes · ${info}`
                    : `Foydalanuvchi${info ? ` · ${info}` : ""}`}
                </div>
              </div>
              <span className="chev">›</span>
            </article>
          );})}
        </>
      ) : (
        <div className="empty people-empty">
          <h3>{kind === "followers" ? "Obunachilar yo'q" : "Kuzatayotganlar yo'q"}</h3>
          <p>{kind === "followers"
            ? "Sizga obuna bo'lganlar shu yerda ko'rinadi."
            : "Biznes yoki mutaxassisni kuzatganingizda shu yerda ko'rinadi."}</p>
        </div>
      )}
    </section>
  );
}
