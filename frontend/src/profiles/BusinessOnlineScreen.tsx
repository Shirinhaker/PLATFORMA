import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
  type PaymentTarget,
} from "./PaymentRequestModal";

import type { ApiClient } from "../api/client";
import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../api/business-online-types";
import type { BusinessProfile, PaymentCatalog } from "../api/types";
import {
  OwnerListingsV1656,
  type OwnerListingsApi,
} from "../listings/OwnerListingsV1656";
import { BusinessDiningV1656View } from "./BusinessDiningV1656View";
import {
  BusinessAdvertisementsV1656,
  supportsAdvertisementApi,
} from "../advertisements/BusinessAdvertisementsV1656";
import {
  BusinessDiningV1656,
  supportsDiningApi,
} from "../dining/BusinessDiningV1656";
import {
  BusinessKitchenV1656,
  supportsDiningKitchenApi,
} from "../dining/BusinessKitchenV1656";
import {
  OrdersCabinetV1656,
  type OrdersApi,
} from "../orders/OrdersCabinetV1656";
import { BusinessEducationEnrollmentsV1656View } from "./BusinessEducationEnrollmentsV1656View";
import {
  BusinessMedicalProvidersV1656View,
  BusinessMedicalQueueV1656View,
} from "./BusinessMedicalV1656View";
import {
  BusinessQueueV1656,
  supportsBusinessQueueApi,
} from "../queues/BusinessQueueV1656";
import {
  CrudEditorView,
  ItemsEditorView,
} from "./BusinessOnlineEditingViews";
import {
  isServiceOrder,
  MessagesView,
  NotificationsView,
  type OrderFilter,
  OrdersView,
  PaymentsView,
  PeopleView,
  recordId,
  recordText,
  ReviewsView,
  type SharedActions,
  SubscriptionsView,
} from "./BusinessOnlineViews";
import "./BusinessOnlineScreen.css";
import "./BusinessExistingOnlineV1656.css";


type OnlineApi = Partial<Pick<
  ApiClient,
  | "getBusinessOnlineResource"
  | "createBusinessOnlineRecord"
  | "patchBusinessOnlineRecord"
  | "deleteBusinessOnlineRecord"
  | "applyBusinessOnlineAction"
  | "getMyListings"
  | "createListing"
  | "deleteListing"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "getPaymentCatalog"
  | "createPaymentRequest"
  | "getMyOrders"
  | "getOrderInbox"
  | "markOrderSeen"
  | "changeOrderStatus"
  | "submitOrderPayment"
  | "decideOrderPayment"
  | "openOrderProblem"
  | "chooseOrderProblemSolution"
  | "handoffOrder"
  | "receiveOrder"
  | "getOrderChat"
  | "sendOrderChatMessage"
  | "sendOrderChatImage"
  | "editOrderChatMessage"
  | "deleteOrderChatMessage"
  | "getBusinessQueueSetup"
  | "getBusinessQueueProviders"
  | "createBusinessQueueProvider"
  | "updateBusinessQueueProvider"
  | "getBusinessQueueEntries"
  | "createBusinessOfflineQueue"
  | "changeBusinessQueueStatus"
  | "swapBusinessQueues"
>>;

type Props = {
  api: OnlineApi;
  profile: BusinessProfile;
  view: string;
  title: string;
  onBack: () => void | Promise<void>;
  initialOrderId?: number | null;
  onOpenOrder?: (orderId: number) => void | Promise<void>;
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
  "dining-places": "dining_places",
  "medical-providers": "medical_doctors",
  "medical-queue": "medical_queue",
  "education-enrollments": "education_enrollments",
};

function viewResources(
  view: string,
  primary?: BusinessOnlineResource,
): BusinessOnlineResource[] {
  if (!primary) return [];
  if (view === "items") return [primary, "item_groups"];
  if (view === "dining-places") {
    return [primary, "dining_orders", "items", "item_groups"];
  }
  if (view === "medical-providers") {
    return [primary, "medical_staff", "items"];
  }
  if (view === "medical-queue") {
    return [primary, "medical_doctors", "medical_staff", "items"];
  }
  if (view === "education-enrollments") {
    return [primary, "education_groups"];
  }
  if (view === "notifications") {
    return [primary, "notify_filters", "push_preferences"];
  }
  return [primary];
}

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

function supportsOwnerListings(api: OnlineApi): api is OnlineApi & OwnerListingsApi {
  return [
    "getMyListings",
    "createListing",
    "deleteListing",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof OnlineApi] === "function");
}

function supportsOrders(api: OnlineApi): api is OnlineApi & OrdersApi {
  return [
    "getMyOrders", "getOrderInbox", "markOrderSeen", "changeOrderStatus",
    "submitOrderPayment", "decideOrderPayment", "openOrderProblem",
    "chooseOrderProblemSolution", "handoffOrder", "receiveOrder",
    "getOrderChat", "sendOrderChatMessage", "sendOrderChatImage",
    "editOrderChatMessage", "deleteOrderChatMessage", "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof OnlineApi] === "function");
}


export function BusinessOnlineScreen({
  api,
  profile,
  view,
  title,
  onBack,
  initialOrderId,
  onOpenOrder,
}: Props) {
  const primary = VIEW_RESOURCE[view];
  const [resources, setResources] = useState<ResourceState>(() => ({
    ...Object.fromEntries(
      viewResources(view, primary).map((resource) => [
        resource,
        rowsFromProfile(profile, resource),
      ]),
    ),
  }));
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [duration, setDuration] = useState(1);
  // Tarif tanlanganda ochiladigan to'lov oynasi (v1656 oqimi).
  const [paymentTarget, setPaymentTarget] = useState<PaymentTarget | null>(null);
  const [catalog, setCatalog] = useState<PaymentCatalog | null>(null);
  const [paymentError, setPaymentError] = useState("");
  // Katalog obuna ekranida oldindan, boshqa joyda esa to'lov oynasi
  // so'ralganda yuklanadi. Ilgari u faqat obuna ekranida yuklanardi,
  // shuning uchun reklama to'lovi bosilganda oyna jimgina ochilmasdi.
  useEffect(() => {
    const needed = view === "subscriptions" || paymentTarget !== null;
    if (!needed || catalog) return;
    const load = (api as Partial<PaymentRequestApi>).getPaymentCatalog;
    if (!load) return;
    let active = true;
    void load.call(api)
      .then((value) => { if (active) setCatalog(value); })
      .catch((reason: unknown) => {
        if (!active) return;
        setCatalog(null);
        setPaymentTarget(null);
        setPaymentError(
          reason instanceof Error
            ? reason.message
            : "To‘lov ma’lumotlari yuklanmadi.",
        );
      });
    return () => { active = false; };
  }, [api, view, catalog, paymentTarget]);

  useEffect(() => {
    if (!paymentError) return;
    const timeout = window.setTimeout(() => setPaymentError(""), 4000);
    return () => window.clearTimeout(timeout);
  }, [paymentError]);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [orderFilter, setOrderFilter] = useState<OrderFilter>("new");
  const [form, setForm] = useState<string | null>(null);
  const [draft, setDraft] = useState<BusinessOnlineRecord>({});
  const [messageText, setMessageText] = useState("");
  const [replyId, setReplyId] = useState<number | string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [subscreenBack, setSubscreenBack] = useState<(() => void) | null>(null);
  const [subscreenTitle, setSubscreenTitle] = useState("");

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
    if (
      !primary
      || !api.getBusinessOnlineResource
      || (view === "listings" && supportsOwnerListings(api))
      || (["orders", "service-orders"].includes(view) && supportsOrders(api))
      || (["medical-providers", "medical-queue"].includes(view)
        && supportsBusinessQueueApi(api))
    ) return;
    const names = viewResources(view, primary).filter((name) => !(
      view === "dining-places"
      && supportsDiningApi(api)
      // Stollar va zakazlar endi `/api/v1/dining` dan keladi;
      // menyu (`items`) hali katalog resursida.
      && (name === "dining_places" || name === "dining_orders")
    ) && !(
      view === "dining-kitchen" && supportsDiningKitchenApi(api)
    ));
    void refresh(...names);
    // API instance App davomida barqaror. View o‘zgarganda serverdan yangilanadi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, primary, api.getBusinessOnlineResource]);

  useEffect(() => {
    if (
      ![
        "dining-places",
        "medical-providers",
        "medical-queue",
        "education-enrollments",
      ].includes(view)
      || !error
    ) return;
    const timeout = window.setTimeout(() => setError(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [error, view]);

  useEffect(() => {
    setSubscreenBack(null);
    setSubscreenTitle("");
  }, [view]);

  const handleSubscreenBack = useCallback((
    handler: (() => void) | null,
    nextTitle = "Zakaz qilish",
  ) => {
    setSubscreenBack(handler ? () => handler : null);
    setSubscreenTitle(handler ? nextTitle : "");
  }, []);

  function setResource(
    resource: BusinessOnlineResource,
    rows: BusinessOnlineRecord[],
  ) {
    setResources((current) => ({ ...current, [resource]: rows }));
  }

  async function create(
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ): Promise<boolean> {
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
      if (
        !resource.startsWith("dining_")
        && !resource.startsWith("medical_")
        && !resource.startsWith("education_")
      ) {
        setNotice("Saqlandi");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv saqlanmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function patch(
    resource: BusinessOnlineResource,
    id: number | string,
    value: BusinessOnlineRecord,
  ): Promise<boolean> {
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
      if (
        !resource.startsWith("dining_")
        && !resource.startsWith("medical_")
        && !resource.startsWith("education_")
      ) {
        setNotice("Yangilandi");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv yangilanmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function remove(
    resource: BusinessOnlineResource,
    id: number | string,
  ): Promise<boolean> {
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
      if (
        !resource.startsWith("dining_")
        && !resource.startsWith("medical_")
        && !resource.startsWith("education_")
      ) {
        setNotice("O‘chirildi");
      }
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Yozuv o‘chirilmadi.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function action(
    resource: BusinessOnlineResource,
    name: string,
    recordIdValue?: number | string,
    payload: BusinessOnlineRecord = {},
  ): Promise<BusinessOnlineRecord | null> {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (api.applyBusinessOnlineAction) {
        const result = await api.applyBusinessOnlineAction(resource, name, {
          record_id: recordIdValue,
          payload,
        });
        if (resource === "advertisements" && name === "calculate_price") {
          return result.item;
        }
        setResource(resource, result.items);
        if (
          resource === "notifications"
          && name === "set_push_preferences"
          && result.item
        ) {
          setResource("push_preferences", [result.item]);
        }
        if (
          !resource.startsWith("dining_")
          && !resource.startsWith("medical_")
          && !resource.startsWith("education_")
        ) {
          setNotice(
            resource === "notifications" && name === "set_push_preferences"
              ? payload.enabled
                ? "Push notification yoqildi ✅"
                : "Push notification o'chirildi"
              : "Amal bajarildi",
          );
        }
        return result.item;
      } else if (resource === "notifications" && name === "mark_all_read") {
        setResource(resource, items.map((row) => ({ ...row, is_read: 1 })));
      } else if (
        resource === "notifications"
        && name === "set_push_preferences"
      ) {
        const preference = {
          id: 1,
          enabled: payload.enabled ? 1 : 0,
          orders_enabled: payload.orders_enabled ? 1 : 0,
        };
        setResource("push_preferences", [preference]);
        if (
          !resource.startsWith("dining_")
          && !resource.startsWith("medical_")
          && !resource.startsWith("education_")
        ) {
          setNotice(payload.enabled
            ? "Push notification yoqildi ✅"
            : "Push notification o'chirildi");
        }
        return preference;
      } else if (
        resource === "subscription_payments"
        && name === "resubmit"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? { ...row, status: "pending", reason: "" }
            : row
        )));
      } else if (
        resource === "orders"
        && name === "report_problem"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? {
              ...row,
              problem_open: 1,
              problem_reason: payload.reason,
              problem_note: payload.note,
            }
            : row
        )));
      } else if (
        resource === "messages"
        && name === "delete"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? {
              ...row,
              is_deleted: 1,
              deleted_at: Math.floor(Date.now() / 1000),
            }
            : row
        )));
      } else if (
        resource === "orders"
        && name === "handoff"
        && recordIdValue !== undefined
      ) {
        setResource(resource, items.map((row, index) => (
          String(recordId(row, index)) === String(recordIdValue)
            ? {
              ...row,
              status: recordText(row, "order_type") === "pickup"
                || ["ready", "tayyor"].includes(recordText(row, "status"))
                ? "pickup_waiting_customer"
                : "in_delivery",
            }
            : row
        )));
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
      if (
        !resource.startsWith("dining_")
        && !resource.startsWith("medical_")
        && !resource.startsWith("education_")
      ) {
        setNotice(
          resource === "notifications" && name === "set_push_preferences"
            ? payload.enabled
              ? "Push notification yoqildi ✅"
              : "Push notification o'chirildi"
            : "Amal bajarildi",
        );
      }
      return {};
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Amal bajarilmadi.");
      return null;
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
    create: async (...arguments_) => {
      await create(...arguments_);
    },
    patch: async (...arguments_) => {
      await patch(...arguments_);
    },
    remove: async (...arguments_) => {
      await remove(...arguments_);
    },
    action: async (...arguments_) => {
      await action(...arguments_);
    },
  };

  if (view === "listings" && supportsOwnerListings(api)) {
    return (
      <OwnerListingsV1656
        actor="business"
        api={api}
        onBack={() => { void onBack(); }}
      />
    );
  }

  if (["orders", "service-orders"].includes(view) && supportsOrders(api)) {
    return (
      <OrdersCabinetV1656
        key={view}
        api={api}
        side="provider"
        category={view === "service-orders" ? "service" : "product"}
        onBack={() => { void onBack(); }}
        initialOrderId={initialOrderId}
      />
    );
  }

  const paymentApi = api as Partial<PaymentRequestApi>;
  const canPay = Boolean(
    paymentApi.getPaymentCatalog
    && paymentApi.createPaymentRequest
    && paymentApi.createUploadGrant
    && paymentApi.uploadGrantedFile,
  );

  function openPayment(plan: "plus" | "pro") {
    if (!canPay) return;
    setPaymentTarget({
      priceCode: `subscription_${plan}_${duration}m`,
      label: `${plan === "plus" ? "Plus" : "Pro"} obuna · ${duration} oy`,
      planCode: plan,
      durationMonths: duration,
    });
  }

  /** Reklama kabi tayyor maqsad bilan to'lov oynasini ochadi. */
  function openPaymentTarget(target: PaymentTarget) {
    if (!canPay) return;
    setPaymentTarget(target);
  }

  const content = renderContent({
    api,
    view,
    items,
    groups,
    profile,
    shared,
    loading,
    duration,
    setDuration,
    openPayment,
    openPaymentTarget,
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
    resources,
    create,
    patch,
    remove,
    action,
    setSubscreenBack: handleSubscreenBack,
    onOpenOrder,
  });
  const exactV1656 = Boolean(primary);

  return (
    <main className="business-online">
      <header className="business-online__heading">
        <button
          type="button"
          onClick={() => {
            if (subscreenBack) subscreenBack();
            else void onBack();
          }}
        >
          {subscreenBack ? "← Orqaga" : "← Kabinetga qaytish"}
        </button>
        <div>
          <h1>{subscreenBack ? subscreenTitle : title}</h1>
          {!exactV1656 ? (
            <p>v1656’dan ko‘chirilgan haqiqiy ma’lumotlar</p>
          ) : null}
        </div>
        {primary && api.getBusinessOnlineResource && !exactV1656 && (
          <button
            type="button"
            onClick={() => void refresh(...viewResources(view, primary))}
            disabled={loading}
          >
            Yangilash
          </button>
        )}
      </header>
      {error && ([
        "dining-places",
        "medical-providers",
        "medical-queue",
        "education-enrollments",
      ].includes(view) ? (
        <div className={
          view === "dining-places"
            ? "business-dining-v1656"
            : view === "education-enrollments"
              ? "business-education-enrollments-v1656"
              : "business-medical-v1656"
        }>
          <div className="app-toast on" role="alert">{error}</div>
        </div>
      ) : (
        <p className="business-online__error" role="alert">{error}</p>
      ))}
      {notice && <p className="business-online__notice" role="status">{notice}</p>}
      {loading && view !== "education-enrollments" && (
        <div className="business-online__loading">Yuklanmoqda…</div>
      )}
      {content}
      {paymentError ? (
        <div className="payment-load-error" role="status">{paymentError}</div>
      ) : null}
      {paymentTarget && catalog ? (
        <PaymentRequestModal
          api={api as PaymentRequestApi}
          catalog={catalog}
          target={paymentTarget}
          onClose={() => setPaymentTarget(null)}
          onSubmitted={() => void refresh("business_subscriptions")}
        />
      ) : null}
    </main>
  );
}


type RenderContext = {
  api: OnlineApi;
  view: string;
  items: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  profile: BusinessProfile;
  shared: SharedActions;
  loading: boolean;
  duration: number;
  setDuration: (value: number) => void;
  openPayment: (plan: "plus" | "pro") => void;
  openPaymentTarget: (target: PaymentTarget) => void;
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
  resources: ResourceState;
  create: (
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ) => Promise<boolean>;
  patch: (
    resource: BusinessOnlineResource,
    id: number | string,
    value: BusinessOnlineRecord,
  ) => Promise<boolean>;
  remove: (
    resource: BusinessOnlineResource,
    id: number | string,
  ) => Promise<boolean>;
  action: (
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null>;
  setSubscreenBack: (
    handler: (() => void) | null,
    title?: string,
  ) => void;
  onOpenOrder?: (orderId: number) => void | Promise<void>;
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
          openPayment={context.openPayment}
        />
      );
    case "payments":
      return (
        <PaymentsView
          rows={items}
          loading={context.loading}
          refresh={() => void context.refresh("subscription_payments")}
          resubmit={async (id, file) => {
            await shared.action("subscription_payments", "resubmit", id, {
              receipt_name: file.name,
              receipt_type: file.type,
              receipt_size: file.size,
            });
          }}
        />
      );
    case "items":
      return (
        <ItemsEditorView
          {...shared}
          rows={items}
          groups={groups}
          query={context.query}
          setQuery={context.setQuery}
          kind={context.kind}
          setKind={context.setKind}
          direction={profile.direction}
        />
      );
    case "dining-kitchen":
      if (supportsDiningKitchenApi(context.api)) {
        return (
          <BusinessKitchenV1656
            api={context.api}
            // Bo'limning o'zi `kitchen` vakolati bilan ochiladi
            // (`MENU_PERMISSIONS`), server ham qayta tekshiradi.
            permissions={null}
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return null;
    case "dining-places":
      if (supportsDiningApi(context.api)) {
        return (
          <BusinessDiningV1656
            api={context.api}
            menuItems={context.resources.items ?? []}
            groups={context.resources.item_groups ?? []}
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return (
        <BusinessDiningV1656View
          places={context.resources.dining_places ?? []}
          menuItems={context.resources.items ?? []}
          groups={context.resources.item_groups ?? []}
          busy={shared.busy}
          createPlace={(record) => context.create("dining_places", record)}
          patchPlace={(id, patch) => context.patch("dining_places", id, patch)}
          removePlace={(id) => context.remove("dining_places", id)}
          action={context.action}
          refresh={context.refresh}
          onBackHandlerChange={context.setSubscreenBack}
        />
      );
    case "medical-providers":
      if (supportsBusinessQueueApi(context.api)) {
        return (
          <BusinessQueueV1656
            api={context.api}
            direction={profile.direction}
            view="medical-providers"
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return (
        <BusinessMedicalProvidersV1656View
          direction={profile.direction}
          doctors={context.resources.medical_doctors ?? []}
          staff={context.resources.medical_staff ?? []}
          items={context.resources.items ?? []}
          busy={shared.busy}
          loading={context.loading}
          createDoctor={(record) => context.create("medical_doctors", record)}
          patchDoctor={(id, patch) => context.patch("medical_doctors", id, patch)}
          onBackHandlerChange={context.setSubscreenBack}
        />
      );
    case "medical-queue":
      if (supportsBusinessQueueApi(context.api)) {
        return (
          <BusinessQueueV1656
            api={context.api}
            direction={profile.direction}
            view="medical-queue"
            onBackHandlerChange={context.setSubscreenBack}
          />
        );
      }
      return (
        <BusinessMedicalQueueV1656View
          direction={profile.direction}
          rows={context.resources.medical_queue ?? []}
          doctors={context.resources.medical_doctors ?? []}
          staff={context.resources.medical_staff ?? []}
          items={context.resources.items ?? []}
          busy={shared.busy}
          loading={context.loading}
          createDoctor={(record) => context.create("medical_doctors", record)}
          patchDoctor={(id, patch) => context.patch("medical_doctors", id, patch)}
          createOffline={async (input) => context.action(
            "medical_queue",
            "offline_add",
            undefined,
            {
              patient_name: input.patientName,
              phone: input.phone,
              item_id: Number(input.itemId),
              staff_id: Number(input.providerId),
              queue_date: input.queueDate,
            },
          )}
          changeStatus={async (id, status) => Boolean(await context.action(
            "medical_queue",
            "set_status",
            id,
            { status },
          ))}
          swapQueues={async (first, second) => Boolean(await context.action(
            "medical_queue",
            "swap",
            Number(first),
            { other_queue_id: Number(second) },
          ))}
          loadDate={async () => context.refresh("medical_queue")}
          onBackHandlerChange={context.setSubscreenBack}
        />
      );
    case "education-enrollments":
      return (
        <BusinessEducationEnrollmentsV1656View
          rows={context.resources.education_enrollments ?? []}
          groups={context.resources.education_groups ?? []}
          busy={shared.busy}
          loading={context.loading}
          action={context.action}
          refresh={context.refresh}
        />
      );
    case "listings":
      return (
        <CrudEditorView
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
          action={(id, name, payload) => shared.action("orders", name, id, payload)}
        />
      );
    case "messages":
      return (
        <MessagesView
          rows={items}
          value={context.messageText}
          setValue={context.setMessageText}
          busy={shared.busy}
          send={async (peer, value, replyToId) => {
            if (context.hasActionApi) {
              await shared.action("messages", "send", undefined, {
                text: value,
                receiver_id: Number(peer.id),
                receiver_kind: peer.kind,
                ...(replyToId === undefined ? {} : { reply_to_id: replyToId }),
              });
            } else {
              await shared.create("messages", {
                text: value,
                sender_kind: "business",
                receiver_id: Number(peer.id),
                receiver_kind: peer.kind,
                ...(replyToId === undefined ? {} : { reply_to_id: replyToId }),
              });
            }
            context.setMessageText("");
          }}
          edit={async (id, text) => {
            await shared.patch("messages", id, {
              text,
              edited_at: Math.floor(Date.now() / 1000),
            });
          }}
          remove={async (id) => {
            await shared.action("messages", "delete", id);
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
          save={async (id, reply) => {
            await shared.action("business_reviews", "reply", id, {
              reply,
            });
            context.setReplyId(null);
            context.setReplyText("");
          }}
        />
      );
    case "advertisements":
      if (supportsAdvertisementApi(context.api)) {
        return (
          <BusinessAdvertisementsV1656
            api={context.api}
            openPayment={context.openPaymentTarget}
          />
        );
      }
      return (
        <CrudEditorView
          {...shared}
          resource="advertisements"
          rows={items}
          addLabel="+ Reklama"
          empty="Hozircha reklama yo‘q."
          fields={[
            "title",
            "caption",
            "placement",
            "region",
            "district",
            "start_at",
            "end_at",
          ]}
          quoteAdvertisement={context.hasActionApi
            ? (request) => context.action(
              "advertisements",
              "calculate_price",
              undefined,
              request,
            )
            : undefined}
        />
      );
    case "stories":
      return (
        <CrudEditorView
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
          filters={context.resources.notify_filters ?? []}
          pushPreference={(context.resources.push_preferences ?? [])[0]}
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
          createFilter={(record) => shared.create("notify_filters", record)}
          removeFilter={(id) => shared.remove("notify_filters", id)}
          savePushPreference={async (enabled) => {
            await context.action(
              "notifications",
              "set_push_preferences",
              undefined,
              { enabled, orders_enabled: enabled },
            );
          }}
          onOpenOrder={context.onOpenOrder}
        />
      );
    case "followers":
      return <PeopleView kind="followers" rows={items} busy={shared.busy} />;
    case "following":
      return (
        <PeopleView
          kind="following"
          rows={items}
          busy={shared.busy}
        />
      );
    default:
      return <div className="business-online__empty">Bo‘lim topilmadi.</div>;
  }
}
