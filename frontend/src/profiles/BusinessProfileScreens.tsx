import type { Dispatch, ReactNode, SetStateAction } from "react";

import type {
  BusinessProfile as BusinessProfileData,
  NotificationRead,
  SessionIdentity,
} from "../api/types";
import { AIAssistant } from "../ai-assistant/AIAssistant";
import {
  BusinessDiningCash,
  supportsDiningCashApi,
} from "../dining/BusinessDiningCash";
import { Documents } from "../documents/Documents";
import {
  EducationManagement,
  type EducationManagementView,
} from "../education/EducationManagement";
import { FollowLists } from "../follows/FollowLists";
import { Warehouse } from "../inventory/Warehouse";
import { Messages } from "../messages/Messages";
import { ActionNotifications } from "../notifications/Notifications";
import {
  BusinessSubscriptions,
  Payments,
  supportsBusinessSubscriptionsApi,
  supportsPaymentsApi,
} from "../payments/SubscriptionsPayments";
import { AccountSettings } from "../settings/AccountSettings";
import { BusinessOnlineScreen } from "./BusinessOnlineScreen";
import { BusinessProfileEditor } from "./BusinessProfileEditor";
import { CabinetDataView } from "./CabinetDataView";
import { CashRegisterScreen } from "./CashRegister";
import { DebtLedger } from "./DebtLedger";
import { EducationStatistics } from "./EducationStatistics";
import { Expenses } from "./Expenses";
import { StaffManagement } from "./StaffManagement";
import { Statistics } from "./Statistics";
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
  BusinessCabinetMenuHub,
  canUseView,
  type DataView,
  HEADER_ONLINE_VIEWS,
  type Screen,
  visibleMenus,
} from "./business-profile-helpers";
import {
  ADMIN_MENUS,
  isService,
  type Menu,
  ONLINE_MENUS,
} from "./business-profile-config";

type Props = {
  api: BusinessProfileApi;
  identity: SessionIdentity;
  profile: BusinessProfileData;
  screen: Screen;
  onlineMenu: Menu | null;
  dataView: DataView;
  orderTarget: number | null;
  initialItemDraft: Record<string, unknown> | null;
  documentsInitialView: "profile" | "center";
  educationView: EducationManagementView;
  withActionBanner(content: ReactNode): ReactNode;
  openNotification(notification: NotificationRead): Promise<void>;
  onOpenPublicProfile?: (kind: "user" | "business", publicId: string) => void;
  logout(): Promise<void>;
  setScreen: Dispatch<SetStateAction<Screen>>;
  setProfile: Dispatch<SetStateAction<BusinessProfileData | null>>;
  setOnlineMenu: Dispatch<SetStateAction<Menu | null>>;
  setNotificationUnread: Dispatch<SetStateAction<number>>;
  setInitialItemDraft: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setOrderTarget: Dispatch<SetStateAction<number | null>>;
  setDocumentsInitialView: Dispatch<SetStateAction<"profile" | "center">>;
};

export function renderBusinessProfileScreen({
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
}: Props): ReactNode | null {
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
    return withActionBanner(<Expenses api={api} onBack={() => setScreen("cabinet")} />);
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

  return null;
}
