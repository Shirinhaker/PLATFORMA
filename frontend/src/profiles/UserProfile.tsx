import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { NotificationRead, UserProfile as UserProfileData } from "../api/types";
import { CabinetDataView } from "./CabinetDataView";
import { OwnerListings, type OwnerListingsApi } from "../listings/OwnerListings";
import { SavedListings } from "../listings/SavedListings";
import { OrdersCabinet, type OrdersApi } from "../orders/OrdersCabinet";
import { MyQueues, type MyQueuesApi } from "../queues/MyQueues";
import { OwnerStories, type OwnerStoriesApi } from "../stories/OwnerStories";
import { Messages, type MessagesApi } from "../messages/Messages";
import { ReceivedReviews, type ReceivedReviewsApi } from "../reviews/Reviews";
import {
  ActionNotifications,
  Notifications,
  type NotificationsApi,
} from "../notifications/Notifications";
import { FollowLists, type FollowListsApi } from "../follows/FollowLists";
import { Payments, supportsPaymentsApi } from "../payments/SubscriptionsPayments";
import { Specialist, type SpecialistApi } from "../specialists/Specialist";
import { DriverCabinet, type DriverCabinetApi } from "../taxi/DriverCabinet";
import { MyRides } from "../taxi/MyRides";
import { AccountSettings } from "../settings/AccountSettings";
import { BusinessOpening } from "../business-opening/BusinessOpening";
import { UserCabinetDashboard, type UserCabinetSection } from "./UserCabinetDashboard";
import { UserProfileEditor } from "./UserProfileEditor";
import { supportsAdvertisementApi } from "../advertisements/BusinessAdvertisements";
import {
  UserAdvertisements,
  type UserAdvertisementsApi,
} from "../advertisements/UserAdvertisements";
import {
  type CabinetView,
  isServiceOrder,
  markLegacyNotificationRead,
  message,
  payloadRows,
  SECTIONS,
  supportsBusinessOpening,
  supportsFollowLists,
  supportsMessages,
  supportsMyQueues,
  supportsNotifications,
  supportsOrders,
  supportsOwnerListings,
  supportsOwnerStories,
  supportsReceivedReviews,
  supportsSpecialist,
  supportsTaxi,
  supportsUserAdvertisements,
} from "./user-profile-helpers";

export type { UserProfileApi } from "./user-profile-api";
import type { UserProfileProps } from "./user-profile-api";

export function UserProfile({
  api,
  identity,
  onLogout,
  onOpenDriverCabinet,
  onOpenPublicListing,
  onOpenPublicProfile,
  onSwitched,
}: UserProfileProps) {
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
    <ActionNotifications api={api} onOpenNotification={openNotification} />
  ) : null;
  const withActionBanner = (content: ReactNode) => (
    <>
      {actionBanner}
      {content}
    </>
  );

  if (view === "listings" && supportsOwnerListings(api)) {
    return withActionBanner(
      <OwnerListings
        actor="user"
        api={api}
        onBack={() => setView("dashboard")}
        onOpenAdvertisements={() => setView("advertisements")}
      />,
    );
  }

  if (view === "advertisements" && supportsUserAdvertisements(api)) {
    return withActionBanner(
      <UserAdvertisements
        api={api}
        onBack={() => setView("dashboard")}
        onOpenListings={() => setView("listings")}
      />,
    );
  }

  if (view === "stories" && supportsOwnerStories(api)) {
    return withActionBanner(
      <OwnerStories
        actor="user"
        api={api}
        ownerName={profile.name}
        onBack={() => setView("dashboard")}
      />,
    );
  }

  if (["followers", "follows"].includes(view) && supportsFollowLists(api)) {
    return withActionBanner(
      <FollowLists
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
    return withActionBanner(<Payments api={api} onBack={() => setView("dashboard")} />);
  }

  if (view === "saved" && getSavedListings) {
    return withActionBanner(
      <SavedListings
        getSavedListings={getSavedListings}
        legacyRows={selectedRows}
        onBack={() => setView("dashboard")}
        onOpenListing={(publicId) => onOpenPublicListing?.(publicId)}
      />,
    );
  }

  if (view === "messages" && supportsMessages(api)) {
    return withActionBanner(<Messages api={api} onBack={() => setView("dashboard")} />);
  }

  if (view === "specialist-reviews" && supportsReceivedReviews(api)) {
    return withActionBanner(
      <ReceivedReviews api={api} onBack={() => setView("specialist")} />,
    );
  }

  if (
    ["notifications", "notify-filters"].includes(view) &&
    supportsNotifications(api)
  ) {
    return withActionBanner(
      <Notifications
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
          <MyQueues
            api={api}
            focusQueueId={queueTarget}
            onFocusHandled={() => setQueueTarget(null)}
          />
          <h2 className="queue-orders-v1656__heading">Boshqa xizmat buyurtmalari</h2>
        </>
      ) : null;
    return withActionBanner(
      <OrdersCabinet
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
      <DriverCabinet api={api} onBack={() => setView("dashboard")} />,
    );
  }

  if (view === "rides" && supportsTaxi(api)) {
    return withActionBanner(<MyRides api={api} onBack={() => setView("dashboard")} />);
  }

  if (view === "settings") {
    return withActionBanner(
      <AccountSettings
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
      <BusinessOpening
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
                      .then(() =>
                        markLegacyNotificationRead(
                          setProfile,
                          setNotificationUnread,
                          notificationId,
                        ),
                      )
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
        <Specialist
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
      <UserProfileEditor
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
    <UserCabinetDashboard
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
