import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  NotificationRead,
  SessionIdentity,
  UserProfile as UserProfileData,
  UserProfilePatch,
} from "../api/types";
import { CabinetDataView } from "./CabinetDataView";
import {
  OwnerListingsV1656,
  type OwnerListingsApi,
} from "../listings/OwnerListingsV1656";
import { SavedListingsV1656 } from "../listings/SavedListingsV1656";
import {
  OrdersCabinetV1656,
  type OrdersApi,
} from "../orders/OrdersCabinetV1656";
import {
  MyQueuesV1656,
  type MyQueuesApi,
} from "../queues/MyQueuesV1656";
import {
  OwnerStoriesV1656,
  type OwnerStoriesApi,
} from "../stories/OwnerStoriesV1656";
import {
  MessagesV1656,
  type MessagesApi,
} from "../messages/MessagesV1656";
import {
  ReceivedReviewsV1656,
  type ReceivedReviewsApi,
} from "../reviews/ReviewsV1656";
import {
  ActionNotificationsV1656,
  NotificationsV1656,
  type NotificationsApi,
} from "../notifications/NotificationsV1656";
import {
  FollowListsV1656,
  type FollowListsApi,
} from "../follows/FollowListsV1656";
import {
  PaymentsV1656,
  supportsPaymentsApi,
} from "../payments/SubscriptionsPaymentsV1656";
import {
  SpecialistV1656,
  type SpecialistApi,
} from "../specialists/SpecialistV1656";
import {
  DriverCabinetV1656,
  type DriverCabinetApi,
} from "../taxi/DriverCabinetV1656";
import { MyRidesV1656 } from "../taxi/MyRidesV1656";
import { AccountSettingsV1656 } from "../settings/AccountSettingsV1656";


export type UserProfileApi = Pick<
  ApiClient,
  | "getSession"
  | "getUserProfile"
  | "updateUserProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachUserAvatar"
  | "switchCabinet"
  | "logout"
> & Partial<Pick<
  ApiClient,
  | "getBusinessCredentials"
  | "updateBusinessCredentials"
  | "getMyListings"
  | "createListing"
  | "deleteListing"
  | "getSavedListings"
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
  | "getMyQueues"
  | "cancelMyQueue"
  | "markQueueNotificationRead"
  | "getMyStories"
  | "createStory"
  | "recordStoryView"
  | "getStoryViewers"
  | "deleteStory"
  | "reportStory"
  | "getMessageConversations"
  | "getMessageThread"
  | "sendMessage"
  | "sendMessageImage"
  | "editMessage"
  | "deleteMessage"
  | "getMessageUnreadCount"
  | "getReceivedReviews"
  | "replyToReview"
  | "getNotifications"
  | "getActionNotifications"
  | "markNotificationRead"
  | "markAllNotificationsRead"
  | "getNotificationPreference"
  | "saveNotificationPreference"
  | "getNotificationFilters"
  | "createNotificationFilter"
  | "deleteNotificationFilter"
  | "getPushStatus"
  | "getFollowers"
  | "getFollowing"
  | "getMyPayments"
  | "resubmitPayment"
  | "getMySpecialist"
  | "updateMySpecialist"
  | "addSpecialistCredential"
  | "deleteSpecialistCredential"
  | "createSpecialistOffer"
  | "updateSpecialistOffer"
  | "deleteSpecialistOffer"
  | "addSpecialistPortfolio"
  | "deleteSpecialistPortfolio"
  | "getTaxiPricing"
  | "getTaxiDriver"
  | "saveTaxiDriver"
  | "setTaxiDriverAvailable"
  | "getMyTaxiRides"
  | "getPendingTaxiRides"
  | "acceptTaxiRide"
  | "setTaxiRideStatus"
  | "updateTaxiRideProgress"
>>;

type Props = {
  api: UserProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onOpenPublicListing?: (publicId: string) => void;
  onOpenPublicProfile?: (
    kind: "user" | "business",
    publicId: string,
  ) => void;
  onOpenDriverCabinet?: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type CabinetView = "dashboard" | "profile" | "specialist" | string;
type PayloadSource = string | readonly string[];

type Section = {
  icon: string;
  label: string;
  view: string;
  payload?: PayloadSource;
};

const IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const EDITABLE_FIELDS = [
  "name",
  "phone",
  "public_username",
  "region",
  "district",
  "mahalla",
  "latitude",
  "longitude",
  "location_exact",
] as const;

const SECTIONS: Section[] = [
  { icon: "👤", label: "Profilim", view: "profile" },
  { icon: "📢", label: "E’lonlarim", view: "listings", payload: "listings" },
  { icon: "🎞️", label: "Istoriyalarim", view: "stories", payload: "stories" },
  { icon: "💎", label: "Obunalarim", view: "follows", payload: "follows" },
  { icon: "👥", label: "Obunachilarim", view: "followers", payload: "followers" },
  { icon: "💳", label: "To‘lovlarim", view: "payments", payload: "payments" },
  {
    icon: "🔔",
    label: "Bildirishnomalarim",
    view: "notifications",
    payload: "notifications",
  },
  {
    icon: "🪪",
    label: "Mutaxassisligim va xizmatlarim",
    view: "specialist",
  },
  { icon: "📦", label: "Buyurtmalarim", view: "orders", payload: "orders" },
  {
    icon: "🧰",
    label: "Xizmat buyurtmalarim",
    view: "service-orders",
    payload: "orders",
  },
  { icon: "🔖", label: "Saqlanganlar", view: "saved", payload: "saved" },
  { icon: "💬", label: "Suhbatlar", view: "messages", payload: "messages" },
  {
    icon: "🎯",
    label: "Bildirishnoma filtrlari",
    view: "notify-filters",
    payload: "notify_filters",
  },
  {
    icon: "🚘",
    label: "Haydovchilik profilim",
    view: "drivers",
    payload: "drivers",
  },
  {
    icon: "🚕",
    label: "Taxi va dostavka buyurtmalarim",
    view: "rides",
    payload: "rides",
  },
  { icon: "⚙️", label: "Sozlamalar", view: "settings" },
];


function supportsOwnerStories(api: UserProfileApi): api is UserProfileApi & OwnerStoriesApi {
  return [
    "getMyStories", "createStory", "recordStoryView", "getStoryViewers",
    "deleteStory", "reportStory", "createUploadGrant", "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}


function supportsTaxi(
  api: UserProfileApi,
): api is UserProfileApi & DriverCabinetApi & Required<Pick<UserProfileApi, "getMyTaxiRides">> {
  return [
    "getTaxiDriver", "getTaxiPricing", "saveTaxiDriver",
    "setTaxiDriverAvailable", "getMyTaxiRides", "getPendingTaxiRides",
    "acceptTaxiRide", "setTaxiRideStatus", "updateTaxiRideProgress",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

const STATUS_LABELS: Record<string, string> = {
  new: "Yangi",
  accepted: "Qabul qilindi",
  preparing: "Tayyorlanmoqda",
  in_delivery: "Yetkazilmoqda",
  done: "Yakunlandi",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilindi",
  rejected: "Rad etildi",
};


function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("")
    : "U";
}


function money(value: number) {
  return value > 0 ? `${value.toLocaleString("uz-UZ")} so‘m` : "";
}


function activityDate(value: number) {
  if (!value) return "Vaqt ko‘rsatilmagan";
  return new Date(value * 1000).toLocaleString("uz-UZ");
}


function isServiceOrder(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const value = row as Record<string, unknown>;
  if (String(value.order_category ?? "") === "service") return true;
  return ["booking", "service", "queue", "medical"].includes(
    String(value.order_type ?? value.kind ?? ""),
  );
}


function payloadRows(
  payload: Record<string, unknown>,
  source: PayloadSource,
): unknown[] {
  const keys = typeof source === "string" ? [source] : source;
  return keys.flatMap((key) => {
    const value = payload[key];
    return Array.isArray(value) ? value : [];
  });
}

function supportsOwnerListings(api: UserProfileApi): api is UserProfileApi & OwnerListingsApi {
  return ["getMyListings", "createListing", "deleteListing"]
    .every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsOrders(api: UserProfileApi): api is UserProfileApi & OrdersApi {
  return [
    "getMyOrders", "getOrderInbox", "markOrderSeen", "changeOrderStatus",
    "submitOrderPayment", "decideOrderPayment", "openOrderProblem",
    "chooseOrderProblemSolution", "handoffOrder", "receiveOrder",
    "getOrderChat", "sendOrderChatMessage", "sendOrderChatImage",
    "editOrderChatMessage", "deleteOrderChatMessage", "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsMyQueues(api: UserProfileApi): api is UserProfileApi & MyQueuesApi {
  return ["getMyQueues", "cancelMyQueue"]
    .every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsMessages(api: UserProfileApi): api is UserProfileApi & MessagesApi {
  return [
    "getMessageConversations", "getMessageThread", "sendMessage",
    "sendMessageImage", "editMessage", "deleteMessage", "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsReceivedReviews(
  api: UserProfileApi,
): api is UserProfileApi & ReceivedReviewsApi {
  return ["getReceivedReviews", "replyToReview"]
    .every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsNotifications(
  api: UserProfileApi,
): api is UserProfileApi & NotificationsApi {
  return [
    "getNotifications", "getActionNotifications", "markNotificationRead",
    "markAllNotificationsRead", "getNotificationPreference",
    "saveNotificationPreference", "getNotificationFilters",
    "createNotificationFilter", "deleteNotificationFilter", "getPushStatus",
  ].every((method) => (
    typeof api[method as keyof UserProfileApi] === "function"
  ));
}

function supportsFollowLists(
  api: UserProfileApi,
): api is UserProfileApi & FollowListsApi {
  return ["getFollowers", "getFollowing"].every((method) => (
    typeof api[method as keyof UserProfileApi] === "function"
  ));
}

function supportsSpecialist(api: UserProfileApi): api is UserProfileApi & SpecialistApi {
  return [
    "getMySpecialist", "updateMySpecialist", "addSpecialistCredential",
    "deleteSpecialistCredential", "createSpecialistOffer",
    "updateSpecialistOffer", "deleteSpecialistOffer",
    "addSpecialistPortfolio", "deleteSpecialistPortfolio",
    "createUploadGrant", "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}


export function UserProfile({
  api,
  identity,
  onLogout,
  onOpenDriverCabinet,
  onOpenPublicListing,
  onOpenPublicProfile,
  onSwitched,
}: Props) {
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [baseline, setBaseline] = useState<UserProfileData | null>(null);
  const [view, setView] = useState<CabinetView>("dashboard");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [orderUnread, setOrderUnread] = useState({ product: 0, service: 0 });
  const [messageUnread, setMessageUnread] = useState(0);
  const [notificationUnread, setNotificationUnread] = useState(0);
  const [orderTarget, setOrderTarget] = useState<number | null>(null);
  const [queueTarget, setQueueTarget] = useState<number | null>(null);

  function applyLoaded(value: UserProfileData) {
    setProfile(value);
    setBaseline(value);
    setNotificationUnread(value.dashboard_snapshot?.unread ?? 0);
  }

  async function load() {
    applyLoaded(await api.getUserProfile());
  }

  useEffect(() => {
    let active = true;
    api.getUserProfile()
      .then((value) => {
        if (active) applyLoaded(value);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    if (typeof api.getMessageUnreadCount !== "function") return;
    let active = true;
    api.getMessageUnreadCount().then(({ count }) => {
      if (active) setMessageUnread(count);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [api, view]);

  useEffect(() => {
    if (typeof api.getMyOrders !== "function") return;
    let active = true;
    api.getMyOrders().then((rows) => {
      if (!active) return;
      setOrderUnread({
        product: rows.filter((row) => !isServiceOrder(row) && row.is_unread).length,
        service: rows.filter((row) => isServiceOrder(row) && row.is_unread).length,
      });
    }).catch(() => undefined);
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    if (!supportsNotifications(api)) return;
    let active = true;
    api.getNotifications().then((value) => {
      if (active) setNotificationUnread(value.unread);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [api]);

  const payload = profile?.cabinet_payload ?? {};
  const selectedSection = SECTIONS.find((section) => section.view === view);
  const selectedRows = useMemo(() => {
    if (!selectedSection?.payload) return [];
    const rows = payloadRows(payload, selectedSection.payload);
    if (view === "service-orders") return rows.filter(isServiceOrder);
    if (view === "orders") return rows.filter((row) => !isServiceOrder(row));
    return rows;
  }, [payload, selectedSection, view]);
  const getSavedListings = useMemo(() => (
    typeof api.getSavedListings === "function"
      ? api.getSavedListings.bind(api)
      : undefined
  ), [api]);

  function setField<K extends keyof UserProfileData>(
    field: K,
    value: UserProfileData[K],
  ) {
    setSaved(false);
    setProfile((current) => (
      current ? { ...current, [field]: value } : current
    ));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !baseline) return;
    const patch: UserProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (profile[field] !== baseline[field]) {
        (patch as Record<string, unknown>)[field] = profile[field];
      }
    }
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length
        ? await api.updateUserProfile(patch)
        : profile;
      const cropChanged = (
        profile.avatar_x !== baseline.avatar_x
        || profile.avatar_y !== baseline.avatar_y
        || profile.avatar_zoom !== baseline.avatar_zoom
      );
      if (cropChanged && profile.avatar_object_key) {
        value = await api.attachUserAvatar({
          object_key: profile.avatar_object_key,
          x: profile.avatar_x,
          y: profile.avatar_y,
          zoom: profile.avatar_zoom,
        });
      }
      applyLoaded(value);
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Faqat JPEG, PNG, WEBP yoki GIF rasm yuklang.");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return;
    }
    if (!profile) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "avatar",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      await api.attachUserAvatar({
        object_key: grant.object_key,
        x: profile.avatar_x,
        y: profile.avatar_y,
        zoom: profile.avatar_zoom,
      });
      await load();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError("");
    try {
      await api.logout();
      onLogout();
    } catch (reason) {
      setError(message(reason));
      setBusy(false);
    }
  }

  async function switchBusiness() {
    setBusy(true);
    setError("");
    try {
      await api.switchCabinet("business");
      onSwitched(await api.getSession());
    } catch (reason) {
      setError(message(reason));
      setBusy(false);
    }
  }

  function markLegacyNotificationRead(notificationId: number) {
    setProfile((current) => {
      if (!current) return current;
      const payload = { ...(current.cabinet_payload ?? {}) };
      const notifications = Array.isArray(payload.notifications)
        ? payload.notifications.map((value) => {
          if (!value || typeof value !== "object") return value;
          const row = value as Record<string, unknown>;
          return Number(row.id ?? 0) === notificationId
            ? { ...row, is_read: 1 }
            : row;
        })
        : [];
      payload.notifications = notifications;
      const unread = notifications.filter((value) => (
        value
        && typeof value === "object"
        && !Boolean(Number((value as Record<string, unknown>).is_read ?? 0))
      )).length;
      setNotificationUnread(unread);
      return {
        ...current,
        cabinet_payload: payload,
        dashboard_snapshot: {
          ...(current.dashboard_snapshot ?? {}),
          unread,
        },
      };
    });
  }

  if (!profile) {
    return (
      <main className="profile-shell">
        {error ? <p role="alert">{error}</p> : "Profil yuklanmoqda…"}
      </main>
    );
  }

  async function openNotification(notification: NotificationRead) {
    if (
      notification.profile_kind
      && notification.profile_public_id
      && onOpenPublicProfile
    ) {
      onOpenPublicProfile(
        notification.profile_kind,
        notification.profile_public_id,
      );
      return;
    }
    if (notification.listing_public_id && onOpenPublicListing) {
      onOpenPublicListing(notification.listing_public_id);
      return;
    }
    if (notification.medical_queue_id) {
      setQueueTarget(notification.medical_queue_id);
      setView("service-orders");
      return;
    }
    if (notification.order_id && typeof api.getMyOrders === "function") {
      const orders = await api.getMyOrders();
      const target = orders.find((order) => order.id === notification.order_id);
      if (target) {
        setOrderTarget(notification.order_id);
        setView(isServiceOrder(target) ? "service-orders" : "orders");
        return;
      }
    }
    if (notification.ride_id) setView("rides");
  }

  const actionBanner = supportsNotifications(api) ? (
    <ActionNotificationsV1656
      api={api}
      onOpenNotification={openNotification}
    />
  ) : null;
  const withActionBanner = (content: ReactNode) => <>{actionBanner}{content}</>;

  if (view === "listings" && supportsOwnerListings(api)) {
    return withActionBanner(
      <OwnerListingsV1656
        actor="user"
        api={api}
        onBack={() => setView("dashboard")}
      />,
    );
  }

  if (view === "stories" && supportsOwnerStories(api)) {
    return withActionBanner(
      <OwnerStoriesV1656
        actor="user"
        api={api}
        ownerName={profile.name}
        onBack={() => setView("dashboard")}
      />,
    );
  }

  if (["followers", "follows"].includes(view) && supportsFollowLists(api)) {
    return withActionBanner(
      <FollowListsV1656
        api={api}
        kind={view === "followers" ? "followers" : "following"}
        onBack={() => setView("dashboard")}
        onOpenProfile={(kind, publicId) => {
          onOpenPublicProfile?.(kind, publicId);
        }}
      />,
    );
  }

  if (view === "payments" && supportsPaymentsApi(api)) {
    return withActionBanner(
      <PaymentsV1656
        api={api}
        onBack={() => setView("dashboard")}
      />,
    );
  }

  if (view === "saved" && getSavedListings) {
    return withActionBanner(
      <SavedListingsV1656
        getSavedListings={getSavedListings}
        legacyRows={selectedRows}
        onBack={() => setView("dashboard")}
        onOpenListing={(publicId) => onOpenPublicListing?.(publicId)}
      />,
    );
  }

  if (view === "messages" && supportsMessages(api)) {
    return withActionBanner(
      <MessagesV1656
        api={api}
        onBack={() => setView("dashboard")}
      />,
    );
  }

  if (view === "specialist-reviews" && supportsReceivedReviews(api)) {
    return withActionBanner(
      <ReceivedReviewsV1656
        api={api}
        onBack={() => setView("specialist")}
      />,
    );
  }

  if (["notifications", "notify-filters"].includes(view) && supportsNotifications(api)) {
    return withActionBanner(
      <NotificationsV1656
        api={api}
        onBack={() => setView("dashboard")}
        onOpenNotification={openNotification}
        onUnreadChange={setNotificationUnread}
      />,
    );
  }

  if (["orders", "service-orders"].includes(view) && supportsOrders(api)) {
    const queueSection = view === "service-orders" && supportsMyQueues(api) ? (
      <>
        <MyQueuesV1656
          api={api}
          focusQueueId={queueTarget}
          onFocusHandled={() => setQueueTarget(null)}
        />
        <h2 className="queue-orders-v1656__heading">Boshqa xizmat buyurtmalari</h2>
      </>
    ) : null;
    return withActionBanner(
      <OrdersCabinetV1656
        key={view}
        api={api}
        side="customer"
        category={view === "service-orders" ? "service" : "product"}
        onBack={() => setView("dashboard")}
        initialOrderId={orderTarget}
        beforeList={queueSection}
        onUnreadChange={(count) => setOrderUnread((current) => ({
          ...current,
          [view === "service-orders" ? "service" : "product"]: count,
        }))}
      />,
    );
  }

  if (view === "drivers" && supportsTaxi(api)) {
    return withActionBanner(
      <DriverCabinetV1656 api={api} onBack={() => setView("dashboard")} />,
    );
  }

  if (view === "rides" && supportsTaxi(api)) {
    return withActionBanner(
      <MyRidesV1656 api={api} onBack={() => setView("dashboard")} />,
    );
  }

  if (view === "settings") {
    return withActionBanner(
      <AccountSettingsV1656
        api={api}
        identity={identity}
        canManageBusinessCredentials={Boolean(profile.has_business)}
        onBack={() => setView("dashboard")}
        onNotifications={supportsNotifications(api)
          ? () => setView("notifications")
          : undefined}
        onLogout={logout}
      />,
    );
  }

  if (selectedSection?.payload) {
    return withActionBanner(
      <CabinetDataView
        title={selectedSection.label}
        rows={selectedRows}
        onBack={() => setView("dashboard")}
        onOpenRow={view === "notifications"
          ? (row) => {
            const queueId = Number(row.medical_queue_id ?? 0);
            if (queueId) {
              const notificationId = Number(row.id ?? 0);
              setQueueTarget(queueId);
              setView("service-orders");
              if (
                notificationId
                && typeof api.markQueueNotificationRead === "function"
              ) {
                void api.markQueueNotificationRead(notificationId)
                  .then(() => markLegacyNotificationRead(notificationId))
                  .catch((reason) => setError(message(reason)));
              }
              return;
            }
            const id = Number(row.order_id ?? 0);
            if (!id || typeof api.getMyOrders !== "function") return;
            void api.getMyOrders().then((orders) => {
              const target = orders.find((order) => order.id === id);
              if (!target) return;
              setOrderTarget(id);
              setView(isServiceOrder(target) ? "service-orders" : "orders");
            }).catch(() => undefined);
          }
          : undefined}
      />,
    );
  }

  if (view === "specialist") {
    if (supportsSpecialist(api)) {
      return withActionBanner(
        <SpecialistV1656
          api={api}
          onBack={() => setView("dashboard")}
          onReviews={supportsReceivedReviews(api)
            ? () => setView("specialist-reviews")
            : undefined}
        />,
      );
    }
    return withActionBanner(
      <CabinetDataView
        title="Mutaxassisligim"
        rows={[]}
        onBack={() => setView("dashboard")}
      />,
    );
  }

  if (view === "profile") {
    return withActionBanner(
      <main className="profile-shell">
        <header className="profile-heading">
          <div>
            <p className="session-panel__eyebrow">{identity.login}</p>
            <h1>Profilim</h1>
          </div>
          <button
            type="button"
            className="button-secondary"
            onClick={() => setView("dashboard")}
          >
            Kabinetga qaytish
          </button>
        </header>
        <form className="profile-form" onSubmit={save}>
          <label>Ism<input required value={profile.name} onChange={(event) => setField("name", event.currentTarget.value)} /></label>
          <label>Telefon<input type="tel" value={profile.phone} onChange={(event) => setField("phone", event.currentTarget.value)} /></label>
          <label>Ochiq username<input value={profile.public_username} onChange={(event) => setField("public_username", event.currentTarget.value)} /></label>
          <label>Viloyat<input value={profile.region} onChange={(event) => setField("region", event.currentTarget.value)} /></label>
          <label>Tuman<input value={profile.district} onChange={(event) => setField("district", event.currentTarget.value)} /></label>
          <label>Mahalla<input value={profile.mahalla} onChange={(event) => setField("mahalla", event.currentTarget.value)} /></label>
          <label>Kenglik<input type="number" step="any" value={profile.latitude ?? ""} onChange={(event) => setField("latitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
          <label>Uzunlik<input type="number" step="any" value={profile.longitude ?? ""} onChange={(event) => setField("longitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
          <label className="checkbox-field"><input type="checkbox" checked={profile.location_exact} onChange={(event) => setField("location_exact", event.currentTarget.checked)} />Joylashuv aniq</label>
          <fieldset><legend>Avatar kesimi</legend><label>X<input type="number" min="0" max="100" value={profile.avatar_x} onChange={(event) => setField("avatar_x", Number(event.currentTarget.value))} /></label><label>Y<input type="number" min="0" max="100" value={profile.avatar_y} onChange={(event) => setField("avatar_y", Number(event.currentTarget.value))} /></label><label>Zoom<input type="number" min="1" max="5" step="0.1" value={profile.avatar_zoom} onChange={(event) => setField("avatar_zoom", Number(event.currentTarget.value))} /></label></fieldset>
          <label>Avatar<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          {saved && <p className="form-success" role="status">Saqlandi</p>}
          <button type="submit" disabled={busy}>Saqlash</button>
        </form>
      </main>,
    );
  }

  const snapshot = profile.dashboard_snapshot ?? {};
  const recentActivity = profile.recent_activity ?? [];
  const followersCount = profile.followers_count ?? 0;
  const followingCount = profile.following_count ?? 0;
  const username = profile.public_username
    ? `@${profile.public_username.replace(/^@/, "")}`
    : identity.login;
  const location = [profile.district, profile.region]
    .filter(Boolean)
    .join(", ");

  return withActionBanner(
    <main className="user-cabinet">
      <section className="user-cabinet__panel">
        <header className="user-cabinet__identity">
          <div className="user-cabinet__avatar" aria-hidden="true">
            {initials(profile.name)}
          </div>
          <div className="user-cabinet__identity-copy">
            <h1>{profile.name}</h1>
            <p>{username}</p>
            {location && <span>● {location}</span>}
            <div className="cabinet-follow-chips">
              <button type="button" onClick={() => setView("followers")}>
                {followersCount} obunachi
              </button>
              <button type="button" onClick={() => setView("follows")}>
                {followingCount} obuna
              </button>
            </div>
          </div>
          <button
            type="button"
            className="user-cabinet__logout"
            disabled={busy}
            onClick={() => void logout()}
          >
            Chiqish
          </button>
        </header>

        <div className="user-cabinet__stats" aria-label="Kabinet statistikasi">
          {[
            ["Faol buyurtmalar", snapshot.active_orders ?? 0, "Joriy buyurtmalar", "orders"],
            ["Obunalar", snapshot.following ?? followingCount, "Kuzatilayotgan profillar", "follows"],
            ["Saqlanganlar", snapshot.saved ?? 0, "E’lon va bizneslar", "saved"],
            ["Bildirishnomalar", notificationUnread, "O‘qilmagan xabarlar", "notifications"],
          ].map(([label, value, sub, target], index) => (
            <button
              type="button"
              key={String(label)}
              className={`user-cabinet__stat${index === 0 ? " user-cabinet__stat--active" : ""}`}
              onClick={() => setView(String(target))}
            >
              <span>{label}</span>
              <strong>{String(value)}</strong>
              <small>{sub}</small>
            </button>
          ))}
        </div>

        <div className="user-cabinet__content">
          <section className="user-cabinet__sections">
            <div className="user-cabinet__section-heading">
              <h2>Mening bo‘limlarim</h2>
              <span>Profil va barcha faoliyatlar</span>
            </div>
            <div className="user-cabinet__grid">
              {SECTIONS.map((section) => (
                <button
                  type="button"
                  key={section.view}
                  onClick={() => {
                    if (section.view === "drivers" && onOpenDriverCabinet) {
                      onOpenDriverCabinet();
                      return;
                    }
                    setView(section.view);
                  }}
                >
                  <span aria-hidden="true">{section.icon}</span>
                  <strong>{section.label}</strong>
                  {section.view === "orders" && orderUnread.product > 0 ? (
                    <em className="order-badge">{orderUnread.product > 99 ? "99+" : orderUnread.product}</em>
                  ) : null}
                  {section.view === "service-orders" && orderUnread.service > 0 ? (
                    <em className="order-badge">{orderUnread.service > 99 ? "99+" : orderUnread.service}</em>
                  ) : null}
                  {section.view === "messages" && messageUnread > 0 ? (
                    <em className="order-badge">{messageUnread > 99 ? "99+" : messageUnread}</em>
                  ) : null}
                  {section.view === "notifications" && notificationUnread > 0 ? (
                    <em className="order-badge">{notificationUnread > 99 ? "99+" : notificationUnread}</em>
                  ) : null}
                </button>
              ))}
            </div>
            {(profile.has_business ?? false) && (
              <button
                type="button"
                className="user-cabinet__switch"
                disabled={busy}
                onClick={() => void switchBusiness()}
              >
                🏢 Biznes kabinetga o‘tish
              </button>
            )}
            {error && <p className="user-cabinet__notice" role="alert">{error}</p>}
          </section>

          <aside className="user-cabinet__activity">
            <div className="user-cabinet__section-heading">
              <h2>So‘nggi faoliyat</h2>
              <span>{recentActivity.length} ta</span>
            </div>
            {!recentActivity.length ? (
              <div className="user-cabinet__empty">
                <span>◎</span>
                <strong>Hozircha faollik yo‘q</strong>
                <p>Yangi buyurtma yoki xizmat paydo bo‘lsa, shu yerda ko‘rinadi.</p>
              </div>
            ) : (
              <div className="cabinet-activity-list">
                {recentActivity.map((activity) => (
                  <button
                    type="button"
                    key={`${activity.kind}-${activity.id}`}
                    onClick={() => setView(
                      activity.kind === "service" ? "service-orders" : "orders"
                    )}
                  >
                    <span className="cabinet-activity-icon">
                      {activity.kind === "service" ? "X" : "B"}
                    </span>
                    <span>
                      <b>Buyurtma #{activity.id} — {activity.title}</b>
                      <small>{activityDate(activity.created_at)}</small>
                    </span>
                    <span>
                      <b>{money(activity.amount) || (STATUS_LABELS[activity.status] ?? activity.status)}</b>
                      <small>{STATUS_LABELS[activity.status] ?? activity.status}</small>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </aside>
        </div>
      </section>
    </main>,
  );
}
