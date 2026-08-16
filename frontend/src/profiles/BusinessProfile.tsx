import { useEffect, useMemo, useState, type ReactNode } from "react";

import type {
  BusinessProfile as BusinessProfileData,
  NotificationRead,
  SessionIdentity,
} from "../api/types";
import { BusinessOnlineScreen } from "./BusinessOnlineScreen";
import { BusinessProfileEditor } from "./BusinessProfileEditor";
import {
  ADMIN_MENUS,
  DEFAULT_METRICS,
  DIRECTION_MENUS,
  isService,
  type Menu,
  METRICS,
  ONLINE_MENUS,
  payloadRows,
  SYSTEM_MENUS,
} from "./business-profile-config";
import { CabinetDataView } from "./CabinetDataView";
import {
  BusinessDiningCash,
  supportsDiningCashApi,
} from "../dining/BusinessDiningCash";
import { CashRegisterScreen } from "./CashRegister";
import { DebtLedger } from "./DebtLedger";
import { EducationStatistics } from "./EducationStatistics";
import {
  EducationManagement,
  type EducationManagementView,
} from "../education/EducationManagement";
import { Expenses } from "./Expenses";
import { StaffManagement } from "./StaffManagement";
import { Statistics } from "./Statistics";
import { Warehouse } from "../inventory/Warehouse";
import { Documents } from "../documents/Documents";
import { AIAssistant } from "../ai-assistant/AIAssistant";
import { Messages } from "../messages/Messages";
import { ActionNotifications } from "../notifications/Notifications";
import { FollowLists } from "../follows/FollowLists";
import {
  BusinessSubscriptions,
  Payments,
  supportsBusinessSubscriptionsApi,
  supportsPaymentsApi,
} from "../payments/SubscriptionsPayments";
import { AccountSettings } from "../settings/AccountSettings";
import "./Cabinet.css";
import "./BusinessCabinetDashboardParity.css";
import "./BusinessFollowCounts.css";
import type { BusinessProfileApi } from "./business-profile-api";
import {
  supportsAIAssistant,
  supportsCashRegister,
  supportsDebtLedger,
  supportsDocuments,
  supportsEducationManagement,
  supportsEducationStatistics,
  supportsExpenses,
  supportsFollowLists,
  supportsMessages,
  supportsNotifications,
  supportsStaffManagement,
  supportsStatistics,
  supportsWarehouse,
} from "./business-profile-capabilities";
import {
  activeCount,
  BusinessCabinetMenuHub,
  canUseView,
  dashboardMenuCards,
  type DataView,
  HEADER_ONLINE_VIEWS,
  isOnlineMenu,
  menuRows,
  message,
  type Screen,
  visibleMenus,
} from "./business-profile-helpers";
import { BusinessCabinetDashboard } from "./BusinessCabinetDashboard";
import { renderBusinessProfileScreen } from "./BusinessProfileScreens";

export type { BusinessProfileApi } from "./business-profile-api";

type Props = {
  api: BusinessProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onOpenPublicListing?: (publicId: string) => void;
  onOpenPublicProfile?: (kind: "user" | "business", publicId: string) => void;
  onSwitched: (identity: SessionIdentity) => void;
};

export function BusinessProfile({
  api,
  identity,
  onLogout,
  onOpenPublicListing,
  onOpenPublicProfile,
  onSwitched,
}: Props) {
  const [profile, setProfile] = useState<BusinessProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [screen, setScreen] = useState<Screen>("cabinet");
  const [onlineMenu, setOnlineMenu] = useState<Menu | null>(null);
  const [dataView, setDataView] = useState<DataView>({ title: "", rows: [] });
  const [orderUnread, setOrderUnread] = useState({ product: 0, service: 0 });
  const [messageUnread, setMessageUnread] = useState(0);
  const [notificationUnread, setNotificationUnread] = useState(0);
  const [orderTarget, setOrderTarget] = useState<number | null>(null);
  const [educationView, setEducationView] =
    useState<EducationManagementView>("education-schedule");
  const [initialItemDraft, setInitialItemDraft] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [documentsInitialView, setDocumentsInitialView] = useState<
    "profile" | "center"
  >("center");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError("");
    api
      .getBusinessProfile()
      .then((value) => {
        if (mounted) setProfile(value);
      })
      .catch((reason) => {
        if (mounted) setError(message(reason));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [api]);

  useEffect(() => {
    if (
      typeof api.getOrderInbox !== "function" ||
      (!canUseView(identity, "orders") && !canUseView(identity, "service-orders"))
    )
      return;
    let active = true;
    api
      .getOrderInbox()
      .then((rows) => {
        if (!active) return;
        setOrderUnread({
          product: rows.filter((row) => !isService(row) && row.is_unread).length,
          service: rows.filter((row) => isService(row) && row.is_unread).length,
        });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [api, identity]);

  useEffect(() => {
    if (
      typeof api.getMessageUnreadCount !== "function" ||
      !canUseView(identity, "messages")
    )
      return;
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
  }, [api, identity, screen]);

  useEffect(() => {
    if (!supportsNotifications(api) || !canUseView(identity, "notifications")) return;
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
  }, [api, identity]);

  const metrics = useMemo(
    () =>
      (profile
        ? (METRICS[profile.direction] ?? DEFAULT_METRICS)
        : DEFAULT_METRICS
      ).filter((metric) => canUseView(identity, metric.view)),
    [identity, profile],
  );

  if (loading) {
    return (
      <main className="session-panel session-panel--message">Kabinet yuklanmoqda…</main>
    );
  }
  if (!profile) {
    return (
      <main className="session-panel">
        <p className="form-error" role="alert">
          {error || "Biznes profil topilmadi."}
        </p>
        <button type="button" onClick={() => window.location.reload()}>
          Qayta urinish
        </button>
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
    if (notification.order_id && typeof api.getOrderInbox === "function") {
      const rows = await api.getOrderInbox();
      const target = rows.find((row) => row.id === notification.order_id);
      if (target) {
        const targetView = isService(target) ? "service-orders" : "orders";
        const menu = visibleMenus(profile, ONLINE_MENUS, identity).find(
          (candidate) => candidate.view === targetView,
        );
        if (menu) {
          setOrderTarget(notification.order_id);
          setOnlineMenu(menu);
          setScreen("online");
          return;
        }
      }
    }
    const targetView = notification.medical_queue_id
      ? "medical-queue"
      : notification.dining_order_id
        ? "orders"
        : notification.ride_id
          ? "orders"
          : "notifications";
    const menu = visibleMenus(profile, ONLINE_MENUS, identity).find(
      (candidate) => candidate.view === targetView,
    );
    if (menu) {
      setOnlineMenu(menu);
      setScreen("online");
    }
  }

  const actionBanner =
    supportsNotifications(api) && canUseView(identity, "notifications") ? (
      <ActionNotifications api={api} onOpenNotification={openNotification} />
    ) : null;
  const withActionBanner = (content: ReactNode) => (
    <>
      {actionBanner}
      {content}
    </>
  );

  const routedScreen = renderBusinessProfileScreen({
    api,
    identity,
    profile,
    screen,
    onlineMenu,
    dataView,
    orderTarget,
    initialItemDraft,
    documentsInitialView,
    educationView,
    withActionBanner,
    openNotification,
    onOpenPublicProfile,
    logout,
    setScreen,
    setProfile,
    setOnlineMenu,
    setNotificationUnread,
    setInitialItemDraft,
    setOrderTarget,
    setDocumentsInitialView,
  });
  if (routedScreen) return routedScreen;

  const loadedProfile = profile;
  const payload = loadedProfile.cabinet_payload ?? {};
  const summary: Record<string, number> = {
    ...loadedProfile.dashboard_snapshot,
    active_orders:
      loadedProfile.dashboard_snapshot.active_orders ?? activeCount(payload),
    followers: loadedProfile.followers_count,
  };
  const onlineMenus = visibleMenus(loadedProfile, ONLINE_MENUS, identity);
  const systemMenus = visibleMenus(loadedProfile, SYSTEM_MENUS, identity);
  const adminMenus = visibleMenus(loadedProfile, ADMIN_MENUS, identity);
  const directionMenus = visibleMenus(loadedProfile, DIRECTION_MENUS, identity);
  const { onlineMenuCards, systemMenuCards } = dashboardMenuCards(
    onlineMenus,
    systemMenus,
    adminMenus,
    directionMenus,
    identity.actor_type === "staff",
  );

  function openMenu(menu: Menu) {
    if (menu.view === "administration") {
      setScreen("administration");
      return;
    }
    if (menu.view === "settings") {
      setScreen("settings");
      return;
    }
    if (menu.view === "staff") {
      setScreen("staff");
      return;
    }
    if (menu.view === "profile") {
      setScreen("profile");
      return;
    }
    if (menu.view === "sales" && supportsCashRegister(api)) {
      setScreen("cash");
      return;
    }
    if (menu.view === "debtors" && supportsDebtLedger(api)) {
      setScreen("debt");
      return;
    }
    if (menu.view === "expenses" && supportsExpenses(api)) {
      setScreen("expenses");
      return;
    }
    if (menu.view === "warehouse" && supportsWarehouse(api)) {
      setScreen("warehouse");
      return;
    }
    if (
      (menu.view === "documents" || menu.view === "my-documents") &&
      supportsDocuments(api)
    ) {
      setDocumentsInitialView(menu.view === "my-documents" ? "profile" : "center");
      setScreen("documents");
      return;
    }
    if (menu.view === "statistics" && supportsStatistics(api)) {
      setScreen("statistics");
      return;
    }
    if (menu.view === "ai-assistant" && supportsAIAssistant(api)) {
      setScreen("ai-assistant");
      return;
    }
    if (
      [
        "education-groups",
        "education-students",
        "education-schedule",
        "education-attendance",
        "education-payments",
        "education-teachers",
        "education-payroll",
      ].includes(menu.view) &&
      supportsEducationManagement(api)
    ) {
      setEducationView(menu.view as EducationManagementView);
      setScreen("education-management");
      return;
    }
    if (menu.view === "education-statistics" && supportsEducationStatistics(api)) {
      setScreen("education-statistics");
      return;
    }
    if (isOnlineMenu(menu)) {
      setOnlineMenu(menu);
      setScreen("online");
      return;
    }
    if (menu.view === "statistics") {
      setDataView({
        title: menu.label,
        rows: Object.entries(summary).map(([name, value], index) => ({
          id: index + 1,
          name,
          value,
        })),
      });
      setScreen("data");
      return;
    }
    if (menu.view === "reports") {
      setDataView({
        title: menu.label,
        rows: [
          ...payloadRows(payload, "sales"),
          ...payloadRows(payload, "expenses"),
          ...payloadRows(payload, "cash_transactions"),
        ],
      });
      setScreen("data");
      return;
    }
    setDataView({
      title: menu.label,
      rows: menuRows(loadedProfile, menu),
    });
    setScreen("data");
  }

  async function switchToUser() {
    setBusy(true);
    setError("");
    try {
      await api.switchCabinet("user");
      onSwitched(await api.getSession());
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
    } finally {
      setBusy(false);
    }
  }

  return withActionBanner(
    <BusinessCabinetDashboard
      identity={identity}
      profile={loadedProfile}
      busy={busy}
      error={error}
      metrics={metrics}
      summary={summary}
      onlineMenus={onlineMenus}
      systemMenus={systemMenus}
      adminMenus={adminMenus}
      directionMenus={directionMenus}
      onlineMenuCards={onlineMenuCards}
      systemMenuCards={systemMenuCards}
      orderUnread={orderUnread}
      messageUnread={messageUnread}
      notificationUnread={notificationUnread}
      onOpenMenu={openMenu}
      onOpenProfile={() => setScreen("profile")}
      onLogout={() => void logout()}
      onSwitchToUser={() => void switchToUser()}
    />,
  );
}
