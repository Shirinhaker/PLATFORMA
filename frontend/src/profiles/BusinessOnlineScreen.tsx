import { useEffect, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import type { BusinessProfile } from "../api/types";
import {
  CrudCardsView,
  isServiceOrder,
  ItemsView,
  MessagesView,
  NotificationsView,
  type OrderFilter,
  OrdersView,
  PaymentsView,
  PeopleView,
  recordId,
  ReviewsView,
  type SharedActions,
  SubscriptionsView,
} from "./BusinessOnlineViews";
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

type ResourceState = Partial<Record<
  BusinessOnlineResource,
  BusinessOnlineRecord[]
>>;

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

function nextLocalId(rows: BusinessOnlineRecord[]): number {
  return Math.max(
    0,
    ...rows.map((row) => Number(row.id ?? 0)).filter(Number.isFinite),
  ) + 1;
}


export function BusinessOnlineScreen({
  api,
  profile,
  view,
  title,
  onBack,
}: Props) {
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
    const names: BusinessOnlineResource[] = view === "items"
      ? [primary, "item_groups"]
      : [primary];
    void refresh(...names);
    // API instance App davomida barqaror. View o‘zgarganda serverdan yangilanadi.
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
          String(recordId(row, index)) === String(id)
            ? { ...row, ...value }
            : row
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
          (row, index) => String(recordId(row, index)) !== String(id),
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
    recordIdValue?: number | string,
    payload: BusinessOnlineRecord = {},
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (api.applyBusinessOnlineAction) {
        const result = await api.applyBusinessOnlineAction(resource, name, {
          record_id: recordIdValue,
          payload,
        });
        setResource(resource, result.items);
      } else if (resource === "notifications" && name === "mark_all_read") {
        setResource(resource, items.map((row) => ({ ...row, is_read: 1 })));
      } else if (
        resource === "following"
        && name === "unfollow"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.filter(
          (row, index) => (
            String(recordId(row, index)) !== String(recordIdValue)
          ),
        ));
      } else if (
        resource === "business_reviews"
        && name === "reply"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? { ...row, business_reply: payload.reply }
            : row
        )));
      } else if (name === "set_status" && recordIdValue !== undefined) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? { ...row, status: payload.status }
            : row
        )));
      } else if (
        resource === "stories"
        && name === "archive"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? { ...row, status: "archived" }
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

  const content = renderContent({
    view,
    items,
    groups,
    profile,
    shared,
    loading,
    duration,
    setDuration,
    query,
    setQuery,
    kind,
    setKind,
    orderFilter,
    setOrderFilter,
    messageText,
    setMessageText,
    replyId,
    setReplyId,
    replyText,
    setReplyText,
    refresh,
    hasActionApi: Boolean(api.applyBusinessOnlineAction),
  });

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


type RenderContext = {
  view: string;
  items: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  profile: BusinessProfile;
  shared: SharedActions;
  loading: boolean;
  duration: number;
  setDuration: (value: number) => void;
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
  orderFilter: OrderFilter;
  setOrderFilter: (value: OrderFilter) => void;
  messageText: string;
  setMessageText: (value: string) => void;
  replyId: number | string | null;
  setReplyId: (value: number | string | null) => void;
  replyText: string;
  setReplyText: (value: string) => void;
  refresh: (...names: BusinessOnlineResource[]) => Promise<void>;
  hasActionApi: boolean;
};

function renderContent(context: RenderContext): ReactNode {
  const {
    view,
    items,
    groups,
    profile,
    shared,
  } = context;

  switch (view) {
    case "subscriptions":
      return (
        <SubscriptionsView
          rows={items}
          duration={context.duration}
          setDuration={context.setDuration}
          busy={shared.busy}
          requestPlan={(plan) => shared.action(
            "business_subscriptions",
            "request_plan",
            undefined,
            { plan, duration_months: context.duration },
          )}
        />
      );
    case "payments":
      return (
        <PaymentsView
          rows={items}
          loading={context.loading}
          refresh={() => void context.refresh("subscription_payments")}
        />
      );
    case "items":
      return (
        <ItemsView
          {...shared}
          rows={items}
          groups={groups}
          query={context.query}
          setQuery={context.setQuery}
          kind={context.kind}
          setKind={context.setKind}
        />
      );
    case "listings":
      return (
        <CrudCardsView
          {...shared}
          resource="listings"
          rows={items}
          addLabel="+ E’lon"
          empty="Hozircha e’lon yo‘q."
          fields={["title", "description", "price", "category"]}
        />
      );
    case "orders":
    case "service-orders":
      return (
        <OrdersView
          rows={items.filter((row) => (
            isServiceOrder(row) === (view === "service-orders")
          ))}
          filter={context.orderFilter}
          setFilter={context.setOrderFilter}
          busy={shared.busy}
          setStatus={(id, status) => shared.action(
            "orders",
            "set_status",
            id,
            { status },
          )}
        />
      );
    case "messages":
      return (
        <MessagesView
          rows={items}
          value={context.messageText}
          setValue={context.setMessageText}
          busy={shared.busy}
          send={async () => {
            const value = context.messageText.trim();
            if (!value) return;
            if (context.hasActionApi) {
              await shared.action("messages", "send", undefined, {
                text: value,
              });
            } else {
              await shared.create("messages", {
                text: value,
                sender_kind: "business",
              });
            }
            context.setMessageText("");
          }}
        />
      );
    case "reviews":
      return (
        <ReviewsView
          rows={items}
          ratingSum={profile.rating_sum}
          ratingCount={profile.rating_count}
          replyId={context.replyId}
          reply={context.replyText}
          setReplyId={context.setReplyId}
          setReply={context.setReplyText}
          busy={shared.busy}
          save={async (id) => {
            await shared.action("business_reviews", "reply", id, {
              reply: context.replyText,
            });
            context.setReplyId(null);
            context.setReplyText("");
          }}
        />
      );
    case "advertisements":
      return (
        <CrudCardsView
          {...shared}
          resource="advertisements"
          rows={items}
          addLabel="+ Reklama"
          empty="Hozircha reklama yo‘q."
          fields={["title", "caption", "placement", "region", "district"]}
        />
      );
    case "stories":
      return (
        <CrudCardsView
          {...shared}
          resource="stories"
          rows={items}
          addLabel="+ Istoriya"
          empty="Hozircha istoriya yo‘q."
          fields={["caption", "media_type", "media_url"]}
          extraAction={(row, index) => (
            <button
              type="button"
              disabled={shared.busy}
              onClick={() => void shared.action(
                "stories",
                "archive",
                recordId(row, index),
              )}
            >
              Arxivlash
            </button>
          )}
        />
      );
    case "notifications":
      return (
        <NotificationsView
          rows={items}
          busy={shared.busy}
          markAll={() => shared.action(
            "notifications",
            "mark_all_read",
          )}
          markOne={(id) => shared.action(
            "notifications",
            "mark_read",
            id,
          )}
        />
      );
    case "followers":
      return <PeopleView rows={items} busy={shared.busy} />;
    case "following":
      return (
        <PeopleView
          rows={items}
          busy={shared.busy}
          canUnfollow
          unfollow={(id) => shared.action("following", "unfollow", id)}
        />
      );
    default:
      return <div className="business-online__empty">Bo‘lim topilmadi.</div>;
  }
}
