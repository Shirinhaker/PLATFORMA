import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessProfile as BusinessProfileData,
  CabinetActivity,
  NotificationRead,
  SessionIdentity,
} from "../api/types";
import { BusinessOnlineScreen } from "./BusinessOnlineScreen";
import { BusinessProfileEditor } from "./BusinessProfileEditor";
import {
  ADMIN_MENUS,
  adaptMenuForDirection,
  activityDate,
  DEFAULT_METRICS,
  DIRECTION_MENUS,
  initials,
  isOnlineMenuVisibleForDirection,
  isService,
  type Menu,
  METRICS,
  money,
  ONLINE_MENUS,
  payloadRows,
  SYSTEM_MENUS,
} from "./business-profile-config";
import { CabinetDataView } from "./CabinetDataView";
import {
  BusinessDiningCash,
  supportsDiningCashApi,
} from "../dining/BusinessDiningCash";
import { CashRegisterScreen, type CashRegisterApi } from "./CashRegister";
import { DebtLedger, type DebtLedgerApi } from "./DebtLedger";
import {
  EducationStatistics,
  type EducationStatisticsApi,
} from "./EducationStatistics";
import {
  EducationManagement,
  type EducationManagementApi,
  type EducationManagementView,
} from "../education/EducationManagement";
import { Expenses, type ExpensesApi } from "./Expenses";
import { StaffManagement, type StaffManagementApi } from "./StaffManagement";
import { Statistics, type StatisticsApi } from "./Statistics";
import { Warehouse, type WarehouseApi } from "../inventory/Warehouse";
import { Documents, type DocumentsApi } from "../documents/Documents";
import {
  AIAssistant,
  type AIAssistantApi,
} from "../ai-assistant/AIAssistant";
import { Messages, type MessagesApi } from "../messages/Messages";
import {
  ActionNotifications,
  type NotificationsApi,
} from "../notifications/Notifications";
import { FollowLists, type FollowListsApi } from "../follows/FollowLists";
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

export type BusinessProfileApi = Pick<
  ApiClient,
  | "getSession"
  | "getBusinessProfile"
  | "updateBusinessProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachBusinessLogo"
  | "switchCabinet"
  | "logout"
> &
  Partial<
    Pick<
      ApiClient,
      | "getBusinessCredentials"
      | "updateBusinessCredentials"
      | "attachBusinessPaymentQr"
      | "reverseGeocode"
      | "getBusinessOnlineResource"
      | "createBusinessOnlineRecord"
      | "patchBusinessOnlineRecord"
      | "deleteBusinessOnlineRecord"
      | "applyBusinessOnlineAction"
      | "getMyListings"
      | "createListing"
      | "deleteListing"
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
      | "getStaffSetup"
      | "createStaffMember"
      | "updateStaffMember"
      | "fireStaffMember"
      | "rehireStaffMember"
      | "deleteStaffMember"
      | "updateStaffAccess"
      | "updateStaffSchedule"
      | "createStaffProfession"
      | "getStaffAttendance"
      | "updateStaffAttendance"
      | "getCashRegister"
      | "getCashCatalog"
      | "createCashReceipt"
      | "deleteCashReceipt"
      | "updateCashOrderPayment"
      | "getDebtors"
      | "createDebtor"
      | "getDebtor"
      | "addDebtTransaction"
      | "getExpenses"
      | "getExpenseCategories"
      | "createExpenseCategory"
      | "createExpense"
      | "deleteExpense"
      | "getWarehouseItems"
      | "configureWarehouseItem"
      | "createWarehouseMove"
      | "deleteWarehouseMove"
      | "getWarehouseMoves"
      | "getWarehouseRecipe"
      | "getWarehouseProduction"
      | "getDocumentCounterparties"
      | "createDocumentCounterparty"
      | "updateDocumentCounterparty"
      | "deleteDocumentCounterparty"
      | "getDocuments"
      | "getDocument"
      | "createDocument"
      | "updateDocument"
      | "deleteDocument"
      | "sendDocument"
      | "respondDocument"
      | "getAIChatHistory"
      | "sendAIChatMessage"
      | "getAIStatus"
      | "getStatistics"
      | "getStatisticsNav"
      | "getEducationStatistics"
      | "getEducationGroups"
      | "createEducationGroup"
      | "updateEducationGroup"
      | "deleteEducationGroup"
      | "getEducationStudents"
      | "createEducationStudent"
      | "updateEducationStudent"
      | "deleteEducationStudent"
      | "getEducationStudentCard"
      | "transferEducationStudent"
      | "getEducationAttendance"
      | "saveEducationAttendance"
      | "getEducationPaymentControl"
      | "getEducationPayments"
      | "createEducationPayment"
      | "voidEducationPayment"
      | "getEducationTeachers"
      | "createEducationTeacher"
      | "updateEducationTeacher"
      | "deleteEducationTeacher"
      | "getEducationPayroll"
      | "createEducationPayroll"
      | "deleteEducationPayroll"
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
      | "getBusinessSubscription"
      | "getPaymentCatalog"
      | "createPaymentRequest"
      | "getMyPayments"
      | "resubmitPayment"
    >
  >;

type Props = {
  api: BusinessProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onOpenPublicListing?: (publicId: string) => void;
  onOpenPublicProfile?: (kind: "user" | "business", publicId: string) => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type DataView = { title: string; rows: unknown[] };
type Screen =
  | "cabinet"
  | "administration"
  | "profile"
  | "data"
  | "online"
  | "staff"
  | "cash"
  | "debt"
  | "expenses"
  | "warehouse"
  | "documents"
  | "ai-assistant"
  | "statistics"
  | "education-management"
  | "education-statistics"
  | "settings";

const HEADER_ONLINE_VIEWS = new Set(["followers", "following"]);

const MAIN_ONLINE_ORDER = [
  "profile",
  "subscriptions",
  "payments",
  "items",
  "dining-places",
  "medical-providers",
  "medical-queue",
  "education-enrollments",
  "orders",
  "service-orders",
  "messages",
  "reviews",
  "advertisements",
  "stories",
  "notifications",
] as const;

type MenuHubProps = {
  menus: Menu[];
  onBack: () => void;
  onOpen: (menu: Menu) => void;
};

function BusinessCabinetMenuHub({ menus, onBack, onOpen }: MenuHubProps) {
  return (
    <main className="business-online business-cabinet-menu-hub">
      <header className="business-online__heading">
        <button type="button" onClick={onBack}>
          ← Kabinetga qaytish
        </button>
        <div>
          <h1>Ma’muriyat</h1>
        </div>
      </header>
      <section
        className="business-cabinet__menu-grid"
        aria-label="Ma’muriyat bo‘limlari"
      >
        {menus.map((menu) => (
          <button type="button" key={menu.view} onClick={() => onOpen(menu)}>
            <span>{menu.icon}</span>
            <span>
              <b>{menu.label}</b>
              <small>{menu.caption}</small>
            </span>
          </button>
        ))}
      </section>
    </main>
  );
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function supportsFollowLists(
  api: BusinessProfileApi,
): api is BusinessProfileApi & FollowListsApi {
  return ["getFollowers", "getFollowing"].every(
    (method) => typeof api[method as keyof BusinessProfileApi] === "function",
  );
}

function supportsAIAssistant(
  api: BusinessProfileApi,
): api is BusinessProfileApi & AIAssistantApi {
  return ["getAIChatHistory", "sendAIChatMessage"].every(
    (method) => typeof api[method as keyof BusinessProfileApi] === "function",
  );
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function activeCount(payload: Record<string, unknown>) {
  return payloadRows(payload, "orders").filter((row) => {
    const status = String(record(row).status ?? "");
    return ![
      "done",
      "delivered",
      "cancelled",
      "canceled",
      "rejected",
      "pickup_waiting_customer",
    ].includes(status);
  }).length;
}

function activityLabel(row: CabinetActivity) {
  return row.kind === "order" ? `Buyurtma #${row.id} — ${row.title}` : row.title;
}

function menuRows(profile: BusinessProfileData | null, menu: Menu): unknown[] {
  if (!profile || !menu.payload) return [];
  const rows = payloadRows(profile.cabinet_payload, menu.payload);
  if (menu.view === "service-orders") return rows.filter(isService);
  if (menu.view === "orders") return rows.filter((row) => !isService(row));
  if (menu.view === "education-enrollments") {
    return rows.filter((row) => String(record(row).status ?? "") === "new");
  }
  return rows;
}

const MENU_PERMISSIONS: Record<string, readonly string[]> = {
  items: ["items"],
  "dining-places": ["dining_places"],
  "dining-kitchen": ["kitchen"],
  "education-enrollments": ["education_enrollments"],
  "medical-providers": ["service_orders"],
  "medical-queue": ["service_orders"],
  listings: ["ads"],
  orders: ["buyurtma", "dining_internal", "dining_external", "kitchen"],
  "service-orders": ["service_orders"],
  messages: ["chats"],
  reviews: ["reviews"],
  advertisements: ["ads"],
  stories: ["ads"],
  notifications: ["notifications"],
  sales: ["kassa"],
  expenses: ["expenses"],
  subscriptions: [],
  debtors: ["debts"],
  warehouse: ["ombor", "production"],
  statistics: ["statistics"],
  "education-statistics": ["education_statistics"],
  reports: ["reports"],
  "my-documents": [],
  documents: ["documents"],
  "education-groups": ["education_groups"],
  "education-students": ["education_students"],
  "education-schedule": ["education_schedule"],
  "education-attendance": ["education_attendance"],
  "education-payments": ["education_payments"],
  "education-teachers": ["education_teachers"],
  "education-payroll": ["education_payroll"],
};

const OWNER_ONLY_VIEWS = new Set([
  "profile",
  "subscriptions",
  "payments",
  "followers",
  "following",
  "staff",
  "my-documents",
  "settings",
]);

function canUseView(identity: SessionIdentity, view: string) {
  if (identity.actor_type !== "staff") return true;
  if (OWNER_ONLY_VIEWS.has(view)) return false;
  const required = MENU_PERMISSIONS[view];
  return Boolean(
    required?.some((permission) => (identity.permissions ?? []).includes(permission)),
  );
}

function supportsStaffManagement(
  api: BusinessProfileApi,
): api is BusinessProfileApi & StaffManagementApi {
  return [
    "getStaffSetup",
    "createStaffMember",
    "updateStaffMember",
    "fireStaffMember",
    "rehireStaffMember",
    "deleteStaffMember",
    "updateStaffAccess",
    "updateStaffSchedule",
    "createStaffProfession",
    "getStaffAttendance",
    "updateStaffAttendance",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsCashRegister(
  api: BusinessProfileApi,
): api is BusinessProfileApi & CashRegisterApi {
  return [
    "getCashRegister",
    "getCashCatalog",
    "createCashReceipt",
    "deleteCashReceipt",
    "updateCashOrderPayment",
    "getDebtors",
    "createDebtor",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsDebtLedger(
  api: BusinessProfileApi,
): api is BusinessProfileApi & DebtLedgerApi {
  return ["getDebtors", "createDebtor", "getDebtor", "addDebtTransaction"].every(
    (method) => typeof api[method as keyof BusinessProfileApi] === "function",
  );
}

function supportsExpenses(
  api: BusinessProfileApi,
): api is BusinessProfileApi & ExpensesApi {
  return [
    "getExpenses",
    "getExpenseCategories",
    "createExpenseCategory",
    "createExpense",
    "deleteExpense",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsStatistics(
  api: BusinessProfileApi,
): api is BusinessProfileApi & StatisticsApi {
  return ["getStatistics", "getStatisticsNav"].every(
    (method) => typeof api[method as keyof BusinessProfileApi] === "function",
  );
}

function supportsWarehouse(
  api: BusinessProfileApi,
): api is BusinessProfileApi & WarehouseApi {
  return [
    "getWarehouseItems",
    "createWarehouseMove",
    "deleteWarehouseMove",
    "getWarehouseMoves",
    "getWarehouseRecipe",
    "getWarehouseProduction",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsDocuments(
  api: BusinessProfileApi,
): api is BusinessProfileApi & DocumentsApi {
  return [
    "getDocumentCounterparties",
    "createDocumentCounterparty",
    "updateDocumentCounterparty",
    "deleteDocumentCounterparty",
    "getDocuments",
    "getDocument",
    "createDocument",
    "updateDocument",
    "deleteDocument",
    "sendDocument",
    "respondDocument",
    "updateBusinessProfile",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsEducationStatistics(
  api: BusinessProfileApi,
): api is BusinessProfileApi & EducationStatisticsApi {
  return typeof api.getEducationStatistics === "function";
}

function supportsEducationManagement(
  api: BusinessProfileApi,
): api is BusinessProfileApi & EducationManagementApi {
  return [
    "getBusinessOnlineResource",
    "getEducationGroups",
    "createEducationGroup",
    "updateEducationGroup",
    "deleteEducationGroup",
    "getEducationStudents",
    "createEducationStudent",
    "updateEducationStudent",
    "deleteEducationStudent",
    "getEducationStudentCard",
    "transferEducationStudent",
    "getEducationAttendance",
    "saveEducationAttendance",
    "getEducationPaymentControl",
    "getEducationPayments",
    "createEducationPayment",
    "voidEducationPayment",
    "getEducationTeachers",
    "createEducationTeacher",
    "updateEducationTeacher",
    "deleteEducationTeacher",
    "getEducationPayroll",
    "createEducationPayroll",
    "deleteEducationPayroll",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsMessages(
  api: BusinessProfileApi,
): api is BusinessProfileApi & MessagesApi {
  return [
    "getMessageConversations",
    "getMessageThread",
    "sendMessage",
    "sendMessageImage",
    "editMessage",
    "deleteMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function supportsNotifications(
  api: BusinessProfileApi,
): api is BusinessProfileApi & NotificationsApi {
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
  ].every((method) => typeof api[method as keyof BusinessProfileApi] === "function");
}

function visibleMenus(
  profile: BusinessProfileData | null,
  menus: Menu[],
  identity: SessionIdentity,
) {
  if (!profile) return [];
  return menus
    .filter(
      (menu) =>
        canUseView(identity, menu.view) &&
        !menu.excludedDirections?.includes(profile.direction) &&
        (isOnlineMenu(menu)
          ? isOnlineMenuVisibleForDirection(menu, profile.direction)
          : !menu.directions || menu.directions.includes(profile.direction)),
    )
    .map((menu) => adaptMenuForDirection(menu, profile.direction));
}

function isOnlineMenu(menu: Menu) {
  return ONLINE_MENUS.some((candidate) => candidate.view === menu.view);
}

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

  if (screen === "profile") {
    return withActionBanner(
      <BusinessProfileEditor
        api={api}
        profile={profile}
        onBack={() => setScreen("cabinet")}
        onProfile={setProfile}
        onOpenOnline={(view) => {
          const menu = visibleMenus(profile, ONLINE_MENUS, identity).find(
            (candidate) => candidate.view === view,
          );
          if (!menu) return;
          setOnlineMenu(menu);
          setScreen("online");
        }}
      />,
    );
  }

  if (screen === "online" && onlineMenu) {
    if (onlineMenu.view === "subscriptions" && supportsBusinessSubscriptionsApi(api)) {
      return withActionBanner(
        <BusinessSubscriptions
          api={api}
          onBack={() => {
            setOnlineMenu(null);
            setScreen("cabinet");
          }}
          onOpenPayments={() => {
            const payments = visibleMenus(profile, ONLINE_MENUS, identity).find(
              (menu) => menu.view === "payments",
            );
            if (payments) setOnlineMenu(payments);
          }}
        />,
      );
    }
    if (onlineMenu.view === "payments" && supportsPaymentsApi(api)) {
      return withActionBanner(
        <Payments
          api={api}
          onBack={() => {
            setOnlineMenu(null);
            setScreen("cabinet");
          }}
        />,
      );
    }
    if (HEADER_ONLINE_VIEWS.has(onlineMenu.view) && supportsFollowLists(api)) {
      return withActionBanner(
        <FollowLists
          api={api}
          kind={onlineMenu.view as "followers" | "following"}
          onOpenProfile={(kind, publicId) => {
            onOpenPublicProfile?.(kind, publicId);
          }}
          onBack={async () => {
            try {
              setProfile(await api.getBusinessProfile());
            } catch {
              // Hisoblagich keyingi kabinet refreshida yangilanadi.
            }
            setOnlineMenu(null);
            setScreen("cabinet");
          }}
        />,
      );
    }
    if (onlineMenu.view === "messages" && supportsMessages(api)) {
      return withActionBanner(
        <Messages
          api={api}
          onBack={() => {
            setOnlineMenu(null);
            setScreen("cabinet");
          }}
        />,
      );
    }
    return withActionBanner(
      <BusinessOnlineScreen
        api={api}
        profile={profile}
        view={onlineMenu.view}
        title={onlineMenu.label}
        onViewChange={(view) => {
          const menu = visibleMenus(profile, ONLINE_MENUS, identity).find(
            (candidate) => candidate.view === view,
          );
          if (menu) setOnlineMenu(menu);
        }}
        initialOrderId={orderTarget}
        onOpenNotification={openNotification}
        onNotificationUnreadChange={setNotificationUnread}
        initialItemDraft={initialItemDraft}
        onInitialItemDraftConsumed={() => setInitialItemDraft(null)}
        onOpenOrder={async (orderId) => {
          if (typeof api.getOrderInbox !== "function") return;
          const rows = await api.getOrderInbox();
          const target = rows.find((order) => order.id === orderId);
          if (!target) return;
          const targetView = isService(target) ? "service-orders" : "orders";
          const menu = visibleMenus(profile, ONLINE_MENUS, identity).find(
            (candidate) => candidate.view === targetView,
          );
          if (!menu) return;
          setOrderTarget(orderId);
          setOnlineMenu(menu);
        }}
        onBack={async () => {
          try {
            setProfile(await api.getBusinessProfile());
          } catch {
            // Saqlangan dedicated yozuvlar yo‘qolmaydi; keyingi refresh yangilaydi.
          }
          setOnlineMenu(null);
          setScreen("cabinet");
        }}
      />,
    );
  }

  if (screen === "data") {
    return withActionBanner(
      <CabinetDataView
        title={dataView.title}
        rows={dataView.rows}
        onBack={() => setScreen("cabinet")}
      />,
    );
  }

  if (screen === "staff" && supportsStaffManagement(api)) {
    return withActionBanner(
      <StaffManagement api={api} onBack={() => setScreen("administration")} />,
    );
  }

  if (screen === "cash" && supportsCashRegister(api)) {
    // v1656da ovqatlanish yo'nalishida kassa tepasida ichki hisoblar
    // turadi (`diningCashTabs`); boshqa yo'nalishlarda ko'rinmaydi.
    const dining =
      profile?.direction === "Umumiy ovqatlanish" && supportsDiningCashApi(api);
    return withActionBanner(
      <>
        {dining ? <BusinessDiningCash api={api} /> : null}
        <CashRegisterScreen api={api} onBack={() => setScreen("cabinet")} />
      </>,
    );
  }

  if (screen === "debt" && supportsDebtLedger(api)) {
    return withActionBanner(
      <DebtLedger api={api} onBack={() => setScreen("cabinet")} />,
    );
  }

  if (screen === "expenses" && supportsExpenses(api)) {
    return withActionBanner(
      <Expenses api={api} onBack={() => setScreen("cabinet")} />,
    );
  }

  if (screen === "warehouse" && supportsWarehouse(api)) {
    const permissions = identity.permissions ?? [];
    const owner = identity.actor_type !== "staff";
    const canManage = owner || permissions.includes("ombor");
    const canProduce = canManage || permissions.includes("production");
    const canViewCosts =
      owner ||
      permissions.some(
        (permission) => permission === "expenses" || permission === "statistics",
      );
    return withActionBanner(
      <Warehouse
        api={api}
        direction={profile.direction}
        canManage={canManage}
        canProduce={canProduce}
        canViewCosts={canViewCosts}
        onAddProduct={
          canUseView(identity, "items")
            ? (nextStockType) => {
                const itemsMenu = visibleMenus(profile, ONLINE_MENUS, identity).find(
                  (menu) => menu.view === "items",
                );
                if (!itemsMenu) return;
                setInitialItemDraft({
                  kind: "product",
                  unit: "dona",
                  track_stock: 1,
                  stock_type: nextStockType,
                  stock_qty: "",
                  min_qty: 0,
                });
                setOnlineMenu(itemsMenu);
                setScreen("online");
              }
            : undefined
        }
        onBack={() => setScreen("cabinet")}
      />,
    );
  }

  if (screen === "documents" && supportsDocuments(api)) {
    return withActionBanner(
      <Documents
        api={api}
        profile={profile}
        initialView={documentsInitialView}
        canManageCounterparties={identity.actor_type !== "staff"}
        onProfile={setProfile}
        onBack={() => setScreen("administration")}
      />,
    );
  }

  if (screen === "ai-assistant" && supportsAIAssistant(api)) {
    return withActionBanner(
      <AIAssistant api={api} onBack={() => setScreen("cabinet")} />,
    );
  }

  if (screen === "statistics" && supportsStatistics(api)) {
    return withActionBanner(
      <Statistics api={api} onBack={() => setScreen("cabinet")} />,
    );
  }

  if (screen === "education-management" && supportsEducationManagement(api)) {
    return withActionBanner(
      <EducationManagement
        api={api}
        view={educationView}
        canVoidPayments={identity.actor_type !== "staff"}
        onBack={() => setScreen("cabinet")}
      />,
    );
  }

  if (screen === "education-statistics" && supportsEducationStatistics(api)) {
    return withActionBanner(
      <EducationStatistics api={api} onBack={() => setScreen("cabinet")} />,
    );
  }

  if (screen === "settings") {
    const notificationsMenu = visibleMenus(profile, ONLINE_MENUS, identity).find(
      (menu) => menu.view === "notifications",
    );
    return withActionBanner(
      <AccountSettings
        api={api}
        identity={identity}
        onBack={() => setScreen("cabinet")}
        onNotifications={
          notificationsMenu && supportsNotifications(api)
            ? () => {
                setOnlineMenu(notificationsMenu);
                setScreen("online");
              }
            : undefined
        }
        onLogout={logout}
      />,
    );
  }

  const administrationMenus = visibleMenus(profile, ADMIN_MENUS, identity);
  if (screen === "administration") {
    return withActionBanner(
      <BusinessCabinetMenuHub
        menus={administrationMenus}
        onBack={() => setScreen("cabinet")}
        onOpen={(menu) => {
          if (menu.view === "staff" && supportsStaffManagement(api)) {
            setScreen("staff");
            return;
          }
          if (
            (menu.view === "documents" || menu.view === "my-documents") &&
            supportsDocuments(api)
          ) {
            setDocumentsInitialView(
              menu.view === "my-documents" ? "profile" : "center",
            );
            setScreen("documents");
          }
        }}
      />,
    );
  }

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
  const followersMenu = onlineMenus.find((menu) => menu.view === "followers");
  const followingMenu = onlineMenus.find((menu) => menu.view === "following");

  const onlineMenuCards = MAIN_ONLINE_ORDER.map((view) =>
    onlineMenus.find((menu) => menu.view === view),
  ).filter((menu): menu is Menu => Boolean(menu));

  const systemCard = (menus: Menu[], view: string, label: string): Menu | null => {
    const menu = menus.find((candidate) => candidate.view === view);
    return menu ? { ...menu, label } : null;
  };
  const baseSystemCards: Array<Menu | null> = [
    systemCard(systemMenus, "sales", "Kassa"),
    systemCard(systemMenus, "expenses", "Xarajatlar"),
    systemCard(systemMenus, "debtors", "Qarz daftari"),
    systemCard(systemMenus, "warehouse", "Ombor"),
    systemCard(systemMenus, "statistics", "Statistika"),
    systemCard(systemMenus, "reports", "Hisobotlar"),
  ];
  const representedSystemViews = new Set(
    baseSystemCards
      .filter((menu): menu is Menu => Boolean(menu))
      .map((menu) => menu.view),
  );
  const inlineDirectionMenus = directionMenus.filter(
    (menu) => !representedSystemViews.has(menu.view),
  );
  const systemMenuCards: Menu[] = [
    ...baseSystemCards.filter((menu): menu is Menu => Boolean(menu)),
    ...inlineDirectionMenus,
    ...[
      systemCard(systemMenus, "ai-assistant", "AI yordamchi"),
      identity.actor_type !== "staff" && adminMenus.length
        ? {
            icon: "🛡️",
            label: "Ma'muriyat",
            caption: "Xodimlar va hujjatlar",
            view: "administration",
          }
        : null,
      identity.actor_type !== "staff"
        ? systemCard(systemMenus, "settings", "Sozlamalar")
        : null,
    ].filter((menu): menu is Menu => Boolean(menu)),
  ];

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

  function group(title: string, caption: string, menus: Menu[]) {
    if (!menus.length) return null;
    return (
      <section className="business-cabinet__group">
        <div className="business-cabinet__group-heading">
          <div>
            <h2>{title}</h2>
            <p>{caption}</p>
          </div>
        </div>
        <div className="business-cabinet__menu-grid">
          {menus.map((menu) => {
            const liveUnread =
              menu.view === "orders"
                ? orderUnread.product
                : menu.view === "service-orders"
                  ? orderUnread.service
                  : menu.view === "messages"
                    ? messageUnread
                    : menu.view === "notifications"
                      ? notificationUnread
                      : 0;
            const count =
              liveUnread || (menu.payload ? menuRows(loadedProfile, menu).length : 0);
            return (
              <button
                type="button"
                key={`${title}-${menu.view}`}
                className={
                  menu.view === "education-enrollments" ? "menu-card" : undefined
                }
                onClick={() => openMenu(menu)}
              >
                <span
                  className={
                    menu.view === "education-enrollments" ? "menu-ic" : undefined
                  }
                >
                  {menu.icon}
                </span>
                <span
                  className={
                    menu.view === "education-enrollments" ? "menu-main" : undefined
                  }
                >
                  <b>{menu.label}</b>
                  <small>{menu.caption}</small>
                </span>
                {count > 0 && (
                  <em
                    className={
                      menu.view === "education-enrollments" ? "order-badge" : undefined
                    }
                  >
                    {count}
                  </em>
                )}
              </button>
            );
          })}
        </div>
      </section>
    );
  }

  return withActionBanner(
    <main className="business-cabinet" data-account={identity.account_id}>
      <section className="business-cabinet__panel">
        <header className="business-cabinet__identity">
          <div className="business-cabinet__avatar">
            {loadedProfile.logo_url ? (
              <img
                src={loadedProfile.logo_url}
                alt=""
                style={{
                  objectPosition: `${loadedProfile.logo_x}% ${loadedProfile.logo_y}%`,
                  transform: `scale(${loadedProfile.logo_zoom})`,
                }}
              />
            ) : (
              initials(loadedProfile.name)
            )}
          </div>
          <div className="business-cabinet__identity-copy">
            <h1>
              {identity.actor_type === "staff" ? identity.name : loadedProfile.name}
            </h1>
            <p>{loadedProfile.direction || "Yo‘nalish tanlanmagan"}</p>
            <span>
              {identity.actor_type === "staff"
                ? `${loadedProfile.name} xodimi`
                : loadedProfile.activity_type || "Faoliyat turi tanlanmagan"}
            </span>
            {identity.actor_type !== "staff" && (
              <div className="business-cabinet__identity-chips">
                <button
                  type="button"
                  aria-label="Obunachilar"
                  disabled={!followersMenu}
                  onClick={() => followersMenu && openMenu(followersMenu)}
                >
                  {loadedProfile.followers_count} obunachi
                </button>
                <button
                  type="button"
                  aria-label="Biznes obunalari"
                  disabled={!followingMenu}
                  onClick={() => followingMenu && openMenu(followingMenu)}
                >
                  {loadedProfile.following_count} obuna
                </button>
              </div>
            )}
          </div>
          {identity.actor_type === "staff" ? (
            <button type="button" disabled={busy} onClick={() => void logout()}>
              Chiqish
            </button>
          ) : (
            <button
              type="button"
              className="business-cabinet__user-switch-top"
              disabled={busy}
              onClick={() => void switchToUser()}
            >
              Oddiy kabinet
            </button>
          )}
        </header>

        <div className="business-cabinet__stats">
          {metrics.map((metric, index) => (
            <button
              type="button"
              className={
                index === 0
                  ? "business-cabinet__stat business-cabinet__stat--active"
                  : "business-cabinet__stat"
              }
              key={metric.key}
              onClick={() => {
                const menu = [
                  ...onlineMenus,
                  ...systemMenus,
                  ...adminMenus,
                  ...directionMenus,
                ].find((candidate) => candidate.view === metric.view);
                if (menu) openMenu(menu);
              }}
            >
              <span>{metric.label}</span>
              <strong>
                {metric.money
                  ? money(summary[metric.key] ?? 0)
                  : String(summary[metric.key] ?? 0)}
              </strong>
              <small>{metric.sub}</small>
            </button>
          ))}
        </div>

        {error && (
          <p className="business-cabinet__error" role="alert">
            {error}
          </p>
        )}

        <div className="business-cabinet__content">
          <div className="business-cabinet__menu-panel">
            <div className="business-cabinet__section-heading">
              <div>
                <h2>Boshqaruv bo‘limlari</h2>
                <p>{`${loadedProfile.direction || "Biznes"} bo‘yicha kerakli bo‘limlar`}</p>
              </div>
              <button type="button" onClick={() => setScreen("profile")}>
                Profilni ko‘rish
              </button>
            </div>
            {group(
              "Onlaynlashtirish",
              "Mijozlar, buyurtmalar va onlayn savdo",
              onlineMenuCards,
            )}
            {group("Tizimlashtirish", "Biznes ish jarayonlari", systemMenuCards)}
          </div>

          <aside className="business-cabinet__activity">
            <div className="business-cabinet__section-heading">
              <h2>So‘nggi faollik</h2>
              <span>{loadedProfile.recent_activity.length} ta</span>
            </div>
            {!loadedProfile.recent_activity.length ? (
              <div className="business-cabinet__empty">
                <b>Hozircha faollik yo‘q</b>
                <span>
                  Yangi buyurtma yoki xizmat paydo bo‘lsa shu yerda ko‘rinadi.
                </span>
              </div>
            ) : (
              loadedProfile.recent_activity.slice(0, 5).map((activity) => (
                <button
                  type="button"
                  className="business-cabinet__activity-row"
                  key={`${activity.kind}-${activity.id}`}
                  onClick={() => {
                    const target = isService(activity) ? "service-orders" : "orders";
                    const menu = onlineMenus.find(
                      (candidate) => candidate.view === target,
                    );
                    if (menu) openMenu(menu);
                  }}
                >
                  <span className="business-cabinet__activity-icon">
                    {activity.kind === "order" ? "B" : "X"}
                  </span>
                  <span className="business-cabinet__activity-copy">
                    <b>{activityLabel(activity)}</b>
                    <small>{activityDate(activity.created_at)}</small>
                  </span>
                  <span className="business-cabinet__activity-meta">
                    <b>{activity.amount ? money(activity.amount) : activity.status}</b>
                    <small>{activity.status}</small>
                  </span>
                </button>
              ))
            )}
          </aside>
        </div>
      </section>
    </main>,
  );
}
