// `BusinessOnlineScreen.tsx` dan ajratildi.
import { useCallback, useEffect, useState } from "react";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
  type PaymentTarget,
} from "../PaymentRequestModal";

import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import type { PaymentCatalog } from "../../api/types";
import { supportsDiningApi } from "../../dining/BusinessDining";
import { supportsDiningKitchenApi } from "../../dining/BusinessKitchen";
import { OrdersCabinet } from "../../orders/OrdersCabinet";
import { supportsBusinessQueueApi } from "../../queues/BusinessQueue";
import { type OrderFilter, type SharedActions } from "../BusinessOnlineViews";
import { OwnerStories } from "../../stories/OwnerStories";
import { ReceivedReviews } from "../../reviews/Reviews";
import { Notifications } from "../../notifications/Notifications";
import "../BusinessOnlineScreen.css";
import "../BusinessExistingOnline.css";
import { renderContent } from "./renderContent";
import { createBusinessOnlineResourceActions } from "./resourceActions";
import {
  Props,
  ResourceState,
  VIEW_RESOURCE,
  rowsFromProfile,
  supportsNotifications,
  supportsOrders,
  supportsOwnerListings,
  supportsOwnerStories,
  supportsReceivedReviews,
  viewResources,
} from "./shared";

export function BusinessOnlineScreen({
  api,
  profile,
  view,
  title,
  onBack,
  onViewChange,
  initialOrderId,
  onOpenOrder,
  onOpenNotification,
  onNotificationUnreadChange,
  initialItemDraft,
  onInitialItemDraftConsumed,
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
    void load
      .call(api)
      .then((value) => {
        if (active) setCatalog(value);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setCatalog(null);
        setPaymentTarget(null);
        setPaymentError(
          reason instanceof Error ? reason.message : "To‘lov ma’lumotlari yuklanmadi.",
        );
      });
    return () => {
      active = false;
    };
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

  useEffect(() => {
    if (view !== "items" || !initialItemDraft) return;
    setDraft({ ...initialItemDraft });
    setForm("items:new");
    onInitialItemDraftConsumed?.();
  }, [initialItemDraft, onInitialItemDraftConsumed, view]);

  const items = primary ? (resources[primary] ?? []) : [];
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
      !primary ||
      !api.getBusinessOnlineResource ||
      (view === "listings" && supportsOwnerListings(api)) ||
      (view === "reviews" && supportsReceivedReviews(api)) ||
      (view === "notifications" && supportsNotifications(api)) ||
      (["orders", "service-orders"].includes(view) && supportsOrders(api)) ||
      (["medical-providers", "medical-queue"].includes(view) &&
        supportsBusinessQueueApi(api))
    )
      return;
    const names = viewResources(view, primary).filter(
      (name) =>
        !(
          view === "dining-places" &&
          supportsDiningApi(api) &&
          // Stollar va zakazlar endi `/api/v1/dining` dan keladi;
          // menyu (`items`) hali katalog resursida.
          (name === "dining_places" || name === "dining_orders")
        ) && !(view === "dining-kitchen" && supportsDiningKitchenApi(api)),
    );
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
      ].includes(view) ||
      !error
    )
      return;
    const timeout = window.setTimeout(() => setError(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [error, view]);

  useEffect(() => {
    setSubscreenBack(null);
    setSubscreenTitle("");
  }, [view]);

  const handleSubscreenBack = useCallback(
    (handler: (() => void) | null, nextTitle = "Zakaz qilish") => {
      setSubscreenBack(handler ? () => handler : null);
      setSubscreenTitle(handler ? nextTitle : "");
    },
    [],
  );

  const { create, patch, remove, action } = createBusinessOnlineResourceActions({
    api,
    resources,
    items,
    setResources,
    setBusy,
    setError,
    setNotice,
    setForm,
    setDraft,
  });

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

  if (view === "reviews" && supportsReceivedReviews(api)) {
    return (
      <ReceivedReviews
        api={api}
        onBack={() => {
          void onBack();
        }}
      />
    );
  }

  if (view === "stories" && supportsOwnerStories(api)) {
    return (
      <OwnerStories
        actor="business"
        api={api}
        ownerAvatar={profile.logo_url}
        ownerName={profile.name}
        onBack={() => void onBack()}
      />
    );
  }

  if (view === "notifications" && supportsNotifications(api)) {
    return (
      <Notifications
        api={api}
        onBack={() => {
          void onBack();
        }}
        onOpenNotification={onOpenNotification}
        onUnreadChange={onNotificationUnreadChange}
      />
    );
  }

  if (["orders", "service-orders"].includes(view) && supportsOrders(api)) {
    return (
      <OrdersCabinet
        key={view}
        api={api}
        side="provider"
        category={view === "service-orders" ? "service" : "product"}
        onBack={() => {
          void onBack();
        }}
        initialOrderId={initialOrderId}
      />
    );
  }

  const paymentApi = api as Partial<PaymentRequestApi>;
  const canPay = Boolean(
    paymentApi.getPaymentCatalog &&
    paymentApi.createPaymentRequest &&
    paymentApi.createUploadGrant &&
    paymentApi.uploadGrantedFile,
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

  const uploadItemImage =
    api.createUploadGrant && api.uploadGrantedFile
      ? async (file: File): Promise<string> => {
          const grant = await api.createUploadGrant!({
            purpose: "catalog_item_image",
            filename: file.name,
            content_type: file.type,
            size_bytes: file.size,
          });
          await api.uploadGrantedFile!(grant, file);
          return grant.object_key;
        }
      : undefined;

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
    onViewChange,
    uploadItemImage,
  });
  const exact = Boolean(primary);
  const screenTitle = ["advertisements", "listings"].includes(view)
    ? "E'lonlarim va reklamalarim"
    : title;

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
          <h1>{subscreenBack ? subscreenTitle : screenTitle}</h1>
          {!exact ? <p>v1656’dan ko‘chirilgan haqiqiy ma’lumotlar</p> : null}
        </div>
        {primary && api.getBusinessOnlineResource && !exact && (
          <button
            type="button"
            onClick={() => void refresh(...viewResources(view, primary))}
            disabled={loading}
          >
            Yangilash
          </button>
        )}
      </header>
      {onViewChange && ["dining-places", "dining-kitchen"].includes(view) ? (
        <div className="ad-tabs" aria-label="Ovqatlanish boshqaruvi">
          <button
            type="button"
            className={view === "dining-places" ? "ad-tab on" : "ad-tab"}
            onClick={() => onViewChange("dining-places")}
          >
            Stollar va xonalar
          </button>
          <button
            type="button"
            className={view === "dining-kitchen" ? "ad-tab on" : "ad-tab"}
            onClick={() => onViewChange("dining-kitchen")}
          >
            Oshpaz buyurtmalari
          </button>
        </div>
      ) : null}
      {error &&
        ([
          "dining-places",
          "medical-providers",
          "medical-queue",
          "education-enrollments",
        ].includes(view) ? (
          <div
            className={
              view === "dining-places"
                ? "business-dining-v1656"
                : view === "education-enrollments"
                  ? "business-education-enrollments-v1656"
                  : "business-medical-v1656"
            }
          >
            <div className="app-toast on" role="alert">
              {error}
            </div>
          </div>
        ) : (
          <p className="business-online__error" role="alert">
            {error}
          </p>
        ))}
      {notice && (
        <p className="business-online__notice" role="status">
          {notice}
        </p>
      )}
      {loading && view !== "education-enrollments" && (
        <div className="business-online__loading">Yuklanmoqda…</div>
      )}
      {content}
      {paymentError ? (
        <div className="payment-load-error" role="status">
          {paymentError}
        </div>
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
