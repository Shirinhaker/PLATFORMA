import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import type { BusinessProfile } from "../api/types";
import { money } from "./business-profile-config";
import "./BusinessOnlineScreen.css";


type OnlineApi = Partial<Pick<
  ApiClient,
  | "getBusinessOnlineResource"
  | "createBusinessOnlineRecord"
  | "patchBusinessOnlineRecord"
  | "deleteBusinessOnlineRecord"
  | "applyBusinessOnlineAction"
>>;

type Props = {
  api: OnlineApi;
  profile: BusinessProfile;
  view: string;
  title: string;
  onBack: () => void | Promise<void>;
};

type ResourceState = Partial<Record<BusinessOnlineResource, BusinessOnlineRecord[]>>;
type OrderFilter = "new" | "active" | "terminal";

const VIEW_RESOURCE: Record<string, BusinessOnlineResource> = {
  subscriptions: "business_subscriptions",
  payments: "subscription_payments",
  items: "items",
  listings: "listings",
  orders: "orders",
  "service-orders": "orders",
  messages: "messages",
  reviews: "business_reviews",
  advertisements: "advertisements",
  stories: "stories",
  notifications: "notifications",
  followers: "followers",
  following: "following",
};

const TERMINAL = new Set([
  "done", "delivered", "pickup_waiting_customer", "rejected",
  "cancelled", "canceled",
]);
const SERVICE_TYPES = new Set(["booking", "service", "queue", "medical"]);

function rowsFromProfile(
  profile: BusinessProfile,
  resource: BusinessOnlineResource,
): BusinessOnlineRecord[] {
  const value = profile.cabinet_payload[resource];
  return Array.isArray(value)
    ? value.filter((row): row is BusinessOnlineRecord => Boolean(
      row && typeof row === "object",
    ))
    : [];
}

function text(row: BusinessOnlineRecord, ...keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== "") {
      return String(value);
    }
  }
  return "";
}

function numeric(row: BusinessOnlineRecord, ...keys: string[]): number {
  for (const key of keys) {
    const value = Number(row[key] ?? 0);
    if (Number.isFinite(value) && value !== 0) return value;
  }
  return 0;
}

function rowId(row: BusinessOnlineRecord, index = 0): number | string {
  const value = row.id;
  return typeof value === "number" || typeof value === "string"
    ? value
    : index + 1;
}

function isService(row: BusinessOnlineRecord): boolean {
  return SERVICE_TYPES.has(text(row, "order_type", "kind", "order_category"));
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

function nextLocalId(rows: BusinessOnlineRecord[]): number {
  return Math.max(
    0,
    ...rows.map((row) => Number(row.id ?? 0)).filter(Number.isFinite),
  ) + 1;
}


export function BusinessOnlineScreen({ api, profile, view, title, onBack }: Props) {
  const primary = VIEW_RESOURCE[view];
  const [resources, setResources] = useState<ResourceState>(() => ({
    ...(primary ? { [primary]: rowsFromProfile(profile, primary) } : {}),
    ...(view === "items"
      ? { item_groups: rowsFromProfile(profile, "item_groups") }
      : {}),
  }));
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [duration, setDuration] = useState(1);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [orderFilter, setOrderFilter] = useState<OrderFilter>("new");
  const [form, setForm] = useState<string | null>(null);
  const [draft, setDraft] = useState<BusinessOnlineRecord>({});
  const [messageText, setMessageText] = useState("");
  const [replyId, setReplyId] = useState<number | string | null>(null);
  const [replyText, setReplyText] = useState("");

  const items = primary ? resources[primary] ?? [] : [];
  const groups = resources.item_groups ?? [];

  async function refresh(...names: BusinessOnlineResource[]) {
    if (!api.getBusinessOnlineResource || names.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const responses = await Promise.all(
        names.map((resource) => api.getBusinessOnlineResource!(resource)),
      );
      setResources((current) => {
        const next = { ...current };
        for (const response of responses) {
          next[response.resource] = response.items;
        }
        return next;
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bo‘lim yuklanmadi.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!primary || !api.getBusinessOnlineResource) return;
    const resourcesToLoad: BusinessOnlineResource[] = view === "items"
      ? [primary, "item_groups"]
      : [primary];
    void refresh(...resourcesToLoad);
    // API instance App davomida barqaror; view o‘zgarganda serverdan yangilanadi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, primary, api.getBusinessOnlineResource]);

  function setResource(
    resource: BusinessOnlineResource,
    rows: BusinessOnlineRecord[],
  ) {
    setResources((current) => ({ ...current, [resource]: rows }));
  }

  async function create(
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (api.createBusinessOnlineRecord) {
        const result = await api.createBusinessOnlineRecord(resource, record);
        setResource(resource, result.items);
      } else {
        const current = resources[resource] ?? [];
        setResource(resource, [
          ...current,
          {
            ...record,
            id: nextLocalId(current),
            created_at: Math.floor(Date.now() / 1000),
          },
        ]);
      }
      setForm(null);
      setDraft({});
      setNotice("Saqlandi");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv saqlanmadi.");
    } finally {
      setBusy(false);
    }
  }

  async function patch(
    resource: BusinessOnlineResource,
    id: number | string,
    value: BusinessOnlineRecord,
  ) {
    setBusy(true);
    setError("");
    try {
      if (api.patchBusinessOnlineRecord) {
        const result = await api.patchBusinessOnlineRecord(resource, id, value);
        setResource(resource, result.items);
      } else {
        setResource(resource, (resources[resource] ?? []).map((row, index) => (
          String(rowId(row, index)) === String(id) ? { ...row, ...value } : row
        )));
      }
      setNotice("Yangilandi");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv yangilanmadi.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(
    resource: BusinessOnlineResource,
    id: number | string,
  ) {
    setBusy(true);
    setError("");
    try {
      if (api.deleteBusinessOnlineRecord) {
        const result = await api.deleteBusinessOnlineRecord(resource, id);
        setResource(resource, result.items);
      } else {
        setResource(resource, (resources[resource] ?? []).filter(
          (row, index) => String(rowId(row, index)) !== String(id),
        ));
      }
      setNotice("O‘chirildi");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv o‘chirilmadi.");
    } finally {
      setBusy(false);
    }
  }

  async function action(
    resource: BusinessOnlineResource,
    name: string,
    recordId?: number | string,
    payload: BusinessOnlineRecord = {},
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (api.applyBusinessOnlineAction) {
        const result = await api.applyBusinessOnlineAction(resource, name, {
          record_id: recordId,
          payload,
        });
        setResource(resource, result.items);
      } else if (resource === "notifications" && name === "mark_all_read") {
        setResource(resource, items.map((row) => ({ ...row, is_read: 1 })));
      } else if (
        resource === "following"
        && name === "unfollow"
        && recordId !== undefined
      ) {
        setResource(resource, items.filter(
          (row, index) => String(rowId(row, index)) !== String(recordId),
        ));
      } else if (
        resource === "business_reviews"
        && name === "reply"
        && recordId !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(rowId(row, index)) === String(recordId)
            ? { ...row, business_reply: payload.reply }
            : row
        )));
      } else if (name === "set_status" && recordId !== undefined) {
        setResource(resource, items.map((row, index) => (
          String(rowId(row, index)) === String(recordId)
            ? { ...row, status: payload.status }
            : row
        )));
      }
      setNotice("Amal bajarildi");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Amal bajarilmadi.");
    } finally {
      setBusy(false);
    }
  }

  const shared: SharedActions = {
    busy,
    form,
    draft,
    setForm,
    setDraft,
    create,
    patch,
    remove,
    action,
  };

  let content: ReactNode;
  switch (view) {
    case "subscriptions":
      content = (
        <Subscriptions
          rows={items}
          duration={duration}
          setDuration={setDuration}
          busy={busy}
          requestPlan={(plan) => action(
            "business_subscriptions",
            "request_plan",
            undefined,
            { plan, duration_months: duration },
          )}
        />
      );
      break;
    case "payments":
      content = (
        <Payments
          rows={items}
          loading={loading}
          refresh={() => void refresh("subscription_payments")}
        />
      );
      break;
    case "items":
      content = (
        <Items
          {...shared}
          rows={items}
          groups={groups}
          query={query}
          setQuery={setQuery}
          kind={kind}
          setKind={setKind}
        />
      );
      break;
    case "listings":
      content = (
        <CrudCards
          {...shared}
          resource="listings"
          rows={items}
          addLabel="+ E’lon"
          empty="Hozircha e’lon yo‘q."
          fields={["title", "description", "price", "category"]}
        />
      );
      break;
    case "orders":
    case "service-orders":
      content = (
        <Orders
          rows={items.filter((row) => (
            isService(row) === (view === "service-orders")
          ))}
          filter={orderFilter}
          setFilter={setOrderFilter}
          busy={busy}
          setStatus={(id, status) => action(
            "orders", "set_status", id, { status },
          )}
        />
      );
      break;
    case "messages":
      content = (
        <Messages
          rows={items}
          value={messageText}
          setValue={setMessageText}
          busy={busy}
          send={async () => {
            const value = messageText.trim();
            if (!value) return;
            if (api.applyBusinessOnlineAction) {
              await action("messages", "send", undefined, { text: value });
            } else {
              await create("messages", {
                text: value,
                sender_kind: "business",
              });
            }
            setMessageText("");
          }}
        />
      );
      break;
    case "reviews":
      content = (
        <Reviews
          rows={items}
          ratingSum={profile.rating_sum}
          ratingCount={profile.rating_count}
          replyId={replyId}
          reply={replyText}
          setReplyId={setReplyId}
          setReply={setReplyText}
          busy={busy}
          save={async (id) => {
            await action("business_reviews", "reply", id, {
              reply: replyText,
            });
            setReplyId(null);
            setReplyText("");
          }}
        />
      );
      break;
    case "advertisements":
      content = (
        <CrudCards
          {...shared}
          resource="advertisements"
          rows={items}
          addLabel="+ Reklama"
          empty="Hozircha reklama yo‘q."
          fields={["title", "caption", "placement", "region", "district"]}
        />
      );
      break;
    case "stories":
      content = (
        <CrudCards
          {...shared}
          resource="stories"
          rows={items}
          addLabel="+ Istoriya"
          empty="Hozircha istoriya yo‘q."
          fields={["caption", "media_type", "media_url"]}
          extraAction={(row, index) => (
            <button
              type="button"
              disabled={busy}
              onClick={() => void action(
                "stories", "archive", rowId(row, index),
              )}
            >
              Arxivlash
            </button>
          )}
        />
      );
      break;
    case "notifications":
      content = (
        <Notifications
          rows={items}
          busy={busy}
          markAll={() => action("notifications", "mark_all_read")}
          markOne={(id) => action("notifications", "mark_read", id)}
        />
      );
      break;
    case "followers":
      content = <People rows={items} busy={busy} />;
      break;
    case "following":
      content = (
        <People
          rows={items}
          busy={busy}
          canUnfollow
          unfollow={(id) => action("following", "unfollow", id)}
        />
      );
      break;
    default:
      content = <div className="business-online__empty">Bo‘lim topilmadi.</div>;
  }

  return (
    <main className="business-online">
      <header className="business-online__heading">
        <button type="button" onClick={() => void onBack()}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>{title}</h1>
          <p>v1656’dan ko‘chirilgan haqiqiy ma’lumotlar</p>
        </div>
        {primary && api.getBusinessOnlineResource && (
          <button
            type="button"
            onClick={() => void refresh(primary)}
            disabled={loading}
          >
            Yangilash
          </button>
        )}
      </header>
      {error && <p className="business-online__error" role="alert">{error}</p>}
      {notice && <p className="business-online__notice" role="status">{notice}</p>}
      {loading && <div className="business-online__loading">Yuklanmoqda…</div>}
      {content}
    </main>
  );
}


type SharedActions = {
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

function Subscriptions({
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
    ["active", "approved"].includes(text(row, "status"))
  ));
  const currentPlan = text(current ?? {}, "plan", "tariff", "name") || "free";
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
          <p>Plus yoki Pro tarifini tanlang. Tarif administrator tasdiqlagandan keyin faollashadi.</p>
        </div>
      </div>
      <div className="subscription-screen__current">
        <small>Joriy tarif</small>
        <strong>{currentPlan.toUpperCase()}</strong>
        <span>{current ? statusLabel(current.status) : "Bepul tarif"}</span>
      </div>
      <SectionTitle title="Muddatni tanlang" note="Plus va Pro uchun" />
      <div className="subscription-screen__duration" role="group" aria-label="Obuna muddati">
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
      <SectionTitle title="Tariflar" note="Mahsulot va xizmatlarni joylash cheksiz" />
      <div className="subscription-screen__plans">
        {plans.map((plan) => (
          <article key={plan.key}>
            <header>
              <span>{plan.icon}</span>
              <div><h3>{plan.name}</h3><p>{plan.caption}</p></div>
              {currentPlan === plan.key && <em>Joriy</em>}
            </header>
            <ul>{plan.benefits.map((benefit) => <li key={benefit}>{benefit}</li>)}</ul>
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
          <article key={String(rowId(row, index))}>
            <b>{text(row, "plan", "tariff", "name") || "Tarif"}</b>
            <span>{statusLabel(row.status)}</span>
            <small>{dateLabel(row.created_at)}</small>
          </article>
        )) : <Empty>Obuna tarixi yo‘q.</Empty>}
      </div>
    </section>
  );
}

function Payments({
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
        <p>Kvitansiya yuborilgan xizmatlar va administrator tekshiruvi holati.</p>
        <button type="button" onClick={refresh} disabled={loading}>Yangilash</button>
      </div>
      <div className="business-online__cards">
        {rows.length ? rows.map((row, index) => (
          <article key={String(rowId(row, index))}>
            <header>
              <b>{text(row, "service", "plan", "purpose") || "To‘lov"}</b>
              <span>{statusLabel(row.status)}</span>
            </header>
            <strong>{money(numeric(row, "amount_snapshot", "amount", "total"))}</strong>
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

function Items({
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
    const rowKind = text(row, "kind", "item_type", "type") || "product";
    const haystack = `${text(row, "name", "title")} ${text(
      row, "description", "descr",
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
          {[["all", "Barchasi"], ["product", "Mahsulotlar"], ["service", "Xizmatlar"]].map(
            ([key, label]) => (
              <button
                type="button"
                className={kind === key ? "active" : ""}
                key={key}
                onClick={() => setKind(key)}
              >
                {label}
              </button>
            ),
          )}
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
          title={actions.form === "group" ? "Yangi guruh" : "Yangi mahsulot yoki xizmat"}
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
          <span key={String(rowId(group, index))}>
            {text(group, "name", "title") || "Guruh"}
          </span>
        ))}
      </div>
      <div className="business-online__product-grid">
        {filtered.length ? filtered.map((row, index) => (
          <article key={String(rowId(row, index))}>
            <div className="business-online__product-image">
              {text(row, "image_url", "photo_file")
                ? <img src={text(row, "image_url", "photo_file")} alt="" />
                : "🛍️"}
            </div>
            <h3>{text(row, "name", "title") || "Nomsiz"}</h3>
            <p>{text(row, "description", "descr", "note")}</p>
            <strong>{money(numeric(row, "price", "price_amount"))}</strong>
            <div>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.patch(
                  "items",
                  rowId(row, index),
                  { is_active: !Boolean(row.is_active ?? true) },
                )}
              >
                {Boolean(row.is_active ?? true) ? "Yashirish" : "Ko‘rsatish"}
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.remove("items", rowId(row, index))}
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

function CrudCards({
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
          <article key={String(rowId(row, index))}>
            <header>
              <b>{text(row, "title", "name", "caption") || `#${rowId(row, index)}`}</b>
              <span>{statusLabel(row.status)}</span>
            </header>
            <p>{text(row, "description", "descr", "caption", "note")}</p>
            {numeric(row, "price", "amount", "budget") > 0 && (
              <strong>{money(numeric(row, "price", "amount", "budget"))}</strong>
            )}
            <small>{dateLabel(row.created_at)}</small>
            <div className="business-online__card-actions">
              {extraAction?.(row, index)}
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.patch(
                  resource,
                  rowId(row, index),
                  { status: text(row, "status") === "active" ? "paused" : "active" },
                )}
              >
                {text(row, "status") === "active" ? "To‘xtatish" : "Faollashtirish"}
              </button>
              <button
                type="button"
                disabled={actions.busy}
                onClick={() => void actions.remove(resource, rowId(row, index))}
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

function Orders({
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
    const status = text(row, "status");
    if (filter === "new") return status === "new";
    if (filter === "terminal") return TERMINAL.has(status);
    return status !== "new" && !TERMINAL.has(status);
  });
  return (
    <section>
      <div className="business-online__filters business-online__filters--wide">
        <button type="button" className={filter === "new" ? "active" : ""} onClick={() => setFilter("new")}>Yangi</button>
        <button type="button" className={filter === "active" ? "active" : ""} onClick={() => setFilter("active")}>Jarayondagi</button>
        <button type="button" className={filter === "terminal" ? "active" : ""} onClick={() => setFilter("terminal")}>Yakunlangan</button>
      </div>
      <div className="business-online__orders">
        {visible.length ? visible.map((row, index) => (
          <article key={String(rowId(row, index))}>
            <header>
              <div>
                <h3>Buyurtma #{rowId(row, index)} — {text(row, "title", "name") || "Buyurtma"}</h3>
                <p>{dateLabel(row.created_at)}</p>
              </div>
              <span>{statusLabel(row.status)}</span>
            </header>
            <div className="business-online__order-lines">
              {Array.isArray(row.items) && row.items.map((item, itemIndex) => {
                const line = item as BusinessOnlineRecord;
                return (
                  <span key={String(rowId(line, itemIndex))}>
                    {text(line, "name", "title", "item_name") || "Mahsulot"}
                    {" × "}{text(line, "qty", "quantity") || "1"}
                  </span>
                );
              })}
            </div>
            <strong>{money(numeric(row, "total_amount", "total"))}</strong>
            {!TERMINAL.has(text(row, "status")) && (
              <select
                disabled={busy}
                value={text(row, "status") || "new"}
                onChange={(event) => void setStatus(
                  rowId(row, index),
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

function Messages({
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
            className={text(row, "sender_kind") === "business" ? "mine" : ""}
            key={String(rowId(row, index))}
          >
            <p>{text(row, "text", "message", "body") || "Xabar"}</p>
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

function Reviews({
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
        <div><small>O‘rtacha baho</small><strong>{average} ★</strong></div>
        <div><small>Jami fikr</small><strong>{rows.length}</strong></div>
      </div>
      <p className="business-online__hint">
        Mijoz fikrini o‘chirib bo‘lmaydi. Har bir fikrga javob berishingiz va javobingizni yangilashingiz mumkin.
      </p>
      <div className="business-online__reviews">
        {rows.length ? rows.map((row, index) => {
          const id = rowId(row, index);
          return (
            <article key={String(id)}>
              <header>
                <b>{text(row, "reviewer_name", "user_name", "name") || "Mijoz"}</b>
                <span>{text(row, "rating", "stars") || "0"} ★</span>
              </header>
              <p>{text(row, "text", "comment", "review") || "Fikr matni yo‘q"}</p>
              {text(row, "business_reply", "reply") && (
                <blockquote>{text(row, "business_reply", "reply")}</blockquote>
              )}
              {replyId === id ? (
                <div className="business-online__reply">
                  <textarea value={reply} onChange={(event) => setReply(event.currentTarget.value)} />
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
                    setReply(text(row, "business_reply", "reply"));
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

function Notifications({
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
  const unread = rows.filter((row) => !Boolean(Number(row.is_read ?? 0))).length;
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
              key={String(rowId(row, index))}
              disabled={busy}
              onClick={() => void markOne(rowId(row, index))}
            >
              <span>{read ? "✓" : "●"}</span>
              <span>
                <b>{text(row, "title", "name") || "Bildirishnoma"}</b>
                <small>{text(row, "message", "text", "body")}</small>
              </span>
              <time>{dateLabel(row.created_at)}</time>
            </button>
          );
        }) : <Empty>Bildirishnomalar yo‘q.</Empty>}
      </div>
    </section>
  );
}

function People({
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
          <article key={String(rowId(row, index))}>
            <div>
              {text(row, "avatar", "image_url")
                ? <img src={text(row, "avatar", "image_url")} alt="" />
                : "👤"}
            </div>
            <span>
              <b>{text(row, "name", "target_name", "business_name") || "Profil"}</b>
              <small>{text(row, "username", "public_username", "target_kind")}</small>
            </span>
            {canUnfollow && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void unfollow(rowId(row, index))}
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
