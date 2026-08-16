import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  NotificationRead,
  SessionIdentity,
  UserProfile as UserProfileData,
} from "../api/types";
import { CabinetDataView } from "./CabinetDataView";
import {
  OwnerListingsV1656,
  type OwnerListingsApi,
} from "../listings/OwnerListings";
import { SavedListingsV1656 } from "../listings/SavedListings";
import { OrdersCabinetV1656, type OrdersApi } from "../orders/OrdersCabinet";
import { MyQueuesV1656, type MyQueuesApi } from "../queues/MyQueues";
import { OwnerStoriesV1656, type OwnerStoriesApi } from "../stories/OwnerStories";
import { MessagesV1656, type MessagesApi } from "../messages/Messages";
import { ReceivedReviewsV1656, type ReceivedReviewsApi } from "../reviews/Reviews";
import {
  ActionNotificationsV1656,
  NotificationsV1656,
  type NotificationsApi,
} from "../notifications/Notifications";
import { FollowListsV1656, type FollowListsApi } from "../follows/FollowLists";
import {
  PaymentsV1656,
  supportsPaymentsApi,
} from "../payments/SubscriptionsPayments";
import { SpecialistV1656, type SpecialistApi } from "../specialists/Specialist";
import { DriverCabinetV1656, type DriverCabinetApi } from "../taxi/DriverCabinet";
import { MyRidesV1656 } from "../taxi/MyRides";
import { AccountSettingsV1656 } from "../settings/AccountSettings";
import { BusinessOpeningV1656 } from "../business-opening/BusinessOpening";
import {
  UserCabinetDashboardV1656,
  type UserCabinetSectionV1656,
} from "./UserCabinetDashboard";
import { UserProfileEditorV1656 } from "./UserProfileEditor";
import { supportsAdvertisementApi } from "../advertisements/BusinessAdvertisements";
import {
  UserAdvertisementsV1656,
  type UserAdvertisementsApi,
} from "../advertisements/UserAdvertisements";

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
> &
  Partial<
    Pick<
      ApiClient,
      | "getBusinessCredentials"
      | "updateBusinessCredentials"
      | "openBusiness"
      | "getMyListings"
      | "createListing"
      | "deleteListing"
      | "getMyAdvertisements"
      | "createAdvertisement"
      | "deleteAdvertisement"
      | "quoteAdvertisement"
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
    >
  >;

type Props = {
  api: UserProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onOpenPublicListing?: (publicId: string) => void;
  onOpenPublicProfile?: (kind: "user" | "business", publicId: string) => void;
  onOpenDriverCabinet?: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type CabinetView = "dashboard" | "profile" | "specialist" | string;
type PayloadSource = string | readonly string[];

type Section = UserCabinetSectionV1656 & {
  payload?: PayloadSource;
};

const SECTIONS: Section[] = [
  {
    icon: "👤",
    label: "Profilim",
    caption: "Ism, telefon, yashash tumani",
    view: "profile",
  },
  {
    icon: "💳",
    label: "To‘lovlarim",
    caption: "Reklama to‘lovlari va tekshiruv holati",
    view: "payments",
    payload: "payments",
  },
  {
    icon: "📢",
    label: "Reklamalarim",
    caption: "Bosh sahifa reklamalarini boshqarish",
    view: "advertisements",
  },
  {
    icon: "🎞️",
    label: "Istoriya arxivi",
    caption: "Faol va arxivdagi shaxsiy istoriyalar",
    view: "stories",
    payload: "stories",
  },
  {
    icon: "💬",
    label: "Suhbatlar",
    caption: "Xabarlar va chatlar",
    view: "messages",
    payload: "messages",
  },
  {
    icon: "🔔",
    label: "Bildirishnomalarim",
    caption: "Qiziqishlaringizni belgilang",
    view: "notifications",
    payload: "notifications",
  },
  {
    icon: "🧰",
    label: "Mutaxassisligim va xizmatlarim",
    caption: "Qidiruv va xaritada mutaxassis sifatida chiqish",
    view: "specialist",
  },
  {
    icon: "📦",
    label: "Buyurtmalarim",
    caption: "Mahsulot buyurtmalarim",
    view: "orders",
    payload: "orders",
  },
  {
    icon: "🧰",
    label: "Xizmat buyurtmalarim",
    caption: "Xizmat va qabullarim",
    view: "service-orders",
    payload: "orders",
  },
  {
    icon: "🔖",
    label: "Saqlanganlar",
    caption: "Saqlangan e'lon va bizneslar",
    view: "saved",
    payload: "saved",
  },
  {
    icon: "⚙️",
    label: "Sozlamalar",
    caption: "Akkaunt, til, chiqish",
    view: "settings",
  },
];

function supportsOwnerStories(
  api: UserProfileApi,
): api is UserProfileApi & OwnerStoriesApi {
  return [
    "getMyStories",
    "createStory",
    "recordStoryView",
    "getStoryViewers",
    "deleteStory",
    "reportStory",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsTaxi(
  api: UserProfileApi,
): api is UserProfileApi &
  DriverCabinetApi &
  Required<Pick<UserProfileApi, "getMyTaxiRides">> {
  return [
    "getTaxiDriver",
    "getTaxiPricing",
    "saveTaxiDriver",
    "setTaxiDriverAvailable",
    "getMyTaxiRides",
    "getPendingTaxiRides",
    "acceptTaxiRide",
    "setTaxiRideStatus",
    "updateTaxiRideProgress",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
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

function supportsOwnerListings(
  api: UserProfileApi,
): api is UserProfileApi & OwnerListingsApi {
  return ["getMyListings", "createListing", "deleteListing"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

function supportsUserAdvertisements(
  api: UserProfileApi,
): api is UserProfileApi & UserAdvertisementsApi {
  return (
    supportsAdvertisementApi(api) &&
    [
      "getPaymentCatalog",
      "createPaymentRequest",
      "createUploadGrant",
      "uploadGrantedFile",
    ].every((method) => typeof api[method as keyof UserProfileApi] === "function")
  );
}

function supportsOrders(api: UserProfileApi): api is UserProfileApi & OrdersApi {
  return [
    "getMyOrders",
    "getOrderInbox",
    "markOrderSeen",
    "changeOrderStatus",
    "submitOrderPayment",
    "decideOrderPayment",
    "openOrderProblem",
    "chooseOrderProblemSolution",
    "handoffOrder",
    "receiveOrder",
    "getOrderChat",
    "sendOrderChatMessage",
    "sendOrderChatImage",
    "editOrderChatMessage",
    "deleteOrderChatMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsMyQueues(api: UserProfileApi): api is UserProfileApi & MyQueuesApi {
  return ["getMyQueues", "cancelMyQueue"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

function supportsMessages(api: UserProfileApi): api is UserProfileApi & MessagesApi {
  return [
    "getMessageConversations",
    "getMessageThread",
    "sendMessage",
    "sendMessageImage",
    "editMessage",
    "deleteMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsReceivedReviews(
  api: UserProfileApi,
): api is UserProfileApi & ReceivedReviewsApi {
  return ["getReceivedReviews", "replyToReview"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

function supportsNotifications(
  api: UserProfileApi,
): api is UserProfileApi & NotificationsApi {
  return [
    "getNotifications",
    "getActionNotifications",
    "markNotificationRead",
    "markAllNotificationsRead",
    "getNotificationPreference",
    "saveNotificationPreference",
    "getNotificationFilters",
    "createNotificationFilter",
    "deleteNotificationFilter",
    "getPushStatus",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsFollowLists(
  api: UserProfileApi,
): api is UserProfileApi & FollowListsApi {
  return ["getFollowers", "getFollowing"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

function supportsSpecialist(
  api: UserProfileApi,
): api is UserProfileApi & SpecialistApi {
  return [
    "getMySpecialist",
    "updateMySpecialist",
    "addSpecialistCredential",
    "deleteSpecialistCredential",
    "createSpecialistOffer",
    "updateSpecialistOffer",
    "deleteSpecialistOffer",
    "addSpecialistPortfolio",
    "deleteSpecialistPortfolio",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

function supportsBusinessOpening(
  api: UserProfileApi,
): api is UserProfileApi & Required<Pick<UserProfileApi, "openBusiness">> {
  return typeof api.openBusiness === "function";
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
  const [view, setView] = useState<CabinetView>("dashboard");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [orderUnread, setOrderUnread] = useState({ product: 0, service: 0 });
  const [messageUnread, setMessageUnread] = useState(0);
  const [notificationUnread, setNotificationUnread] = useState(0);
  const [orderTarget, setOrderTarget] = useState<number | null>(null);
  const [queueTarget, setQueueTarget] = useState<number | null>(null);

  function applyLoaded(value: UserProfileData) {
    setProfile(value);
    setNotificationUnread(value.dashboard_snapshot?.unread ?? 0);
  }

  useEffect(() => {
    let active = true;
    api
      .getUserProfile()
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
    api
      .getMessageUnreadCount()
      .then(({ count }) => {
        if (active) setMessageUnread(count);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [api, view]);

  useEffect(() => {
    if (typeof api.getMyOrders !== "function") return;
    let active = true;
    api
      .getMyOrders()
      .then((rows) => {
        if (!active) return;
        setOrderUnread({
          product: rows.filter((row) => !isServiceOrder(row) && row.is_unread).length,
          service: rows.filter((row) => isServiceOrder(row) && row.is_unread).length,
        });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    if (!supportsNotifications(api)) return;
    let active = true;
    api
      .getNotifications()
      .then((value) => {
        if (active) setNotificationUnread(value.unread);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
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
  const getSavedListings = useMemo(
    () =>
      typeof api.getSavedListings === "function"
        ? api.getSavedListings.bind(api)
        : undefined,
    [api],
  );

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
      const unread = notifications.filter(
        (value) =>
          value &&
          typeof value === "object" &&
          !Boolean(Number((value as Record<string, unknown>).is_read ?? 0)),
      ).length;
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
      notification.profile_kind &&
      notification.profile_public_id &&
      onOpenPublicProfile
    ) {
      onOpenPublicProfile(notification.profile_kind, notification.profile_public_id);
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
    <ActionNotificationsV1656 api={api} onOpenNotification={openNotification} />
  ) : null;
  const withActionBanner = (content: ReactNode) => (
    <>
      {actionBanner}
      {content}
    </>
  );

  if (view === "listings" && supportsOwnerListings(api)) {
    return withActionBanner(
      <OwnerListingsV1656
        actor="user"
        api={api}
        onBack={() => setView("dashboard")}
        onOpenAdvertisements={() => setView("advertisements")}
      />,
    );
  }

  if (view === "advertisements" && supportsUserAdvertisements(api)) {
    return withActionBanner(
      <UserAdvertisementsV1656
        api={api}
        onBack={() => setView("dashboard")}
        onOpenListings={() => setView("listings")}
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
      <PaymentsV1656 api={api} onBack={() => setView("dashboard")} />,
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
      <MessagesV1656 api={api} onBack={() => setView("dashboard")} />,
    );
  }

  if (view === "specialist-reviews" && supportsReceivedReviews(api)) {
    return withActionBanner(
      <ReceivedReviewsV1656 api={api} onBack={() => setView("specialist")} />,
    );
  }

  if (
    ["notifications", "notify-filters"].includes(view) &&
    supportsNotifications(api)
  ) {
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
    const queueSection =
      view === "service-orders" && supportsMyQueues(api) ? (
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
        onUnreadChange={(count) =>
          setOrderUnread((current) => ({
            ...current,
            [view === "service-orders" ? "service" : "product"]: count,
          }))
        }
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
        onNotifications={
          supportsNotifications(api) ? () => setView("notifications") : undefined
        }
        onLogout={logout}
      />,
    );
  }

  if (view === "business-opening" && supportsBusinessOpening(api)) {
    return withActionBanner(
      <BusinessOpeningV1656
        api={api}
        onBack={() => setView("dashboard")}
        onOpened={() =>
          setProfile((current) =>
            current ? { ...current, has_business: true } : current,
          )
        }
        onSwitch={switchBusiness}
      />,
    );
  }

  if (selectedSection?.payload) {
    return withActionBanner(
      <CabinetDataView
        title={selectedSection.label}
        rows={selectedRows}
        onBack={() => setView("dashboard")}
        onOpenRow={
          view === "notifications"
            ? (row) => {
                const queueId = Number(row.medical_queue_id ?? 0);
                if (queueId) {
                  const notificationId = Number(row.id ?? 0);
                  setQueueTarget(queueId);
                  setView("service-orders");
                  if (
                    notificationId &&
                    typeof api.markQueueNotificationRead === "function"
                  ) {
                    void api
                      .markQueueNotificationRead(notificationId)
                      .then(() => markLegacyNotificationRead(notificationId))
                      .catch((reason) => setError(message(reason)));
                  }
                  return;
                }
                const id = Number(row.order_id ?? 0);
                if (!id || typeof api.getMyOrders !== "function") return;
                void api
                  .getMyOrders()
                  .then((orders) => {
                    const target = orders.find((order) => order.id === id);
                    if (!target) return;
                    setOrderTarget(id);
                    setView(isServiceOrder(target) ? "service-orders" : "orders");
                  })
                  .catch(() => undefined);
              }
            : undefined
        }
      />,
    );
  }

  if (view === "specialist") {
    if (supportsSpecialist(api)) {
      return withActionBanner(
        <SpecialistV1656
          api={api}
          onBack={() => setView("dashboard")}
          onReviews={
            supportsReceivedReviews(api)
              ? () => setView("specialist-reviews")
              : undefined
          }
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
      <UserProfileEditorV1656
        api={api}
        profile={profile}
        onBack={() => setView("dashboard")}
        onFollowers={() => setView("followers")}
        onFollowing={() => setView("follows")}
        onProfile={applyLoaded}
      />,
    );
  }

  return withActionBanner(
    <UserCabinetDashboardV1656
      busy={busy}
      error={error}
      messageUnread={messageUnread}
      notificationUnread={notificationUnread}
      orderUnread={orderUnread}
      profile={profile}
      sections={SECTIONS}
      onNavigate={(target) => {
        if (target === "drivers" && onOpenDriverCabinet) {
          onOpenDriverCabinet();
          return;
        }
        setView(target);
      }}
      onOpenBusiness={() => {
        if (supportsBusinessOpening(api)) setView("business-opening");
      }}
      onSwitchBusiness={() => void switchBusiness()}
    />,
  );
}
