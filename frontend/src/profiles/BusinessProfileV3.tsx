import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessProfile as BusinessProfileData,
  CabinetActivity,
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
  StaffManagementV1656,
  type StaffManagementApi,
} from "./StaffManagementV1656";
import "./Cabinet.css";
import "./BusinessFollowCounts.css";


export type BusinessProfileApiV3 = Pick<
  ApiClient,
  | "getSession"
  | "getBusinessProfile"
  | "updateBusinessProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachBusinessLogo"
  | "switchCabinet"
  | "logout"
> & Partial<Pick<
  ApiClient,
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
>>;

type Props = {
  api: BusinessProfileApiV3;
  identity: SessionIdentity;
  onLogout: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type DataView = { title: string; rows: unknown[] };
type Screen = "cabinet" | "profile" | "data" | "online" | "staff";

const HEADER_ONLINE_VIEWS = new Set(["followers", "following"]);

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? value as Record<string, unknown>
    : {};
}

function activeCount(payload: Record<string, unknown>) {
  return payloadRows(payload, "orders").filter((row) => {
    const status = String(record(row).status ?? "");
    return ![
      "done", "delivered", "cancelled", "canceled", "rejected",
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
  debtors: ["debts"],
  warehouse: ["ombor", "production"],
  statistics: ["statistics", "education_statistics"],
  reports: ["reports"],
  documents: ["documents"],
  "incoming-documents": ["documents"],
  "outgoing-documents": ["documents"],
  "internal-documents": ["documents"],
  counterparties: ["documents"],
  "education-groups": ["education_groups"],
  "education-students": ["education_students"],
  "education-teachers": ["education_teachers"],
};

const OWNER_ONLY_VIEWS = new Set([
  "profile", "subscriptions", "payments", "followers", "following", "staff",
]);

function canUseView(identity: SessionIdentity, view: string) {
  if (identity.actor_type !== "staff") return true;
  if (OWNER_ONLY_VIEWS.has(view)) return false;
  const required = MENU_PERMISSIONS[view];
  return Boolean(required?.some((permission) => (
    identity.permissions ?? []
  ).includes(permission)));
}

function supportsStaffManagement(
  api: BusinessProfileApiV3,
): api is BusinessProfileApiV3 & StaffManagementApi {
  return [
    "getStaffSetup", "createStaffMember", "updateStaffMember",
    "fireStaffMember", "rehireStaffMember", "deleteStaffMember",
    "updateStaffAccess", "updateStaffSchedule", "createStaffProfession",
    "getStaffAttendance", "updateStaffAttendance",
  ].every((method) => typeof api[method as keyof BusinessProfileApiV3] === "function");
}

function visibleMenus(
  profile: BusinessProfileData | null,
  menus: Menu[],
  identity: SessionIdentity,
) {
  if (!profile) return [];
  return menus
    .filter((menu) => (
      canUseView(identity, menu.view) && (isOnlineMenu(menu)
        ? isOnlineMenuVisibleForDirection(menu, profile.direction)
        : !menu.directions || menu.directions.includes(profile.direction))
    ))
    .map((menu) => adaptMenuForDirection(menu, profile.direction));
}

function isOnlineMenu(menu: Menu) {
  return ONLINE_MENUS.some((candidate) => candidate.view === menu.view);
}

export function BusinessProfileV3({ api, identity, onLogout, onSwitched }: Props) {
  const [profile, setProfile] = useState<BusinessProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [screen, setScreen] = useState<Screen>("cabinet");
  const [onlineMenu, setOnlineMenu] = useState<Menu | null>(null);
  const [dataView, setDataView] = useState<DataView>({ title: "", rows: [] });
  const [orderUnread, setOrderUnread] = useState({ product: 0, service: 0 });
  const [orderTarget, setOrderTarget] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError("");
    api.getBusinessProfile()
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
      typeof api.getOrderInbox !== "function"
      || (!canUseView(identity, "orders") && !canUseView(identity, "service-orders"))
    ) return;
    let active = true;
    api.getOrderInbox().then((rows) => {
      if (!active) return;
      setOrderUnread({
        product: rows.filter((row) => !isService(row) && row.is_unread).length,
        service: rows.filter((row) => isService(row) && row.is_unread).length,
      });
    }).catch(() => undefined);
    return () => { active = false; };
  }, [api, identity]);

  const metrics = useMemo(
    () => (profile ? (METRICS[profile.direction] ?? DEFAULT_METRICS) : DEFAULT_METRICS)
      .filter((metric) => canUseView(identity, metric.view)),
    [identity, profile],
  );

  if (loading) {
    return <main className="session-panel session-panel--message">Kabinet yuklanmoqda…</main>;
  }
  if (!profile) {
    return (
      <main className="session-panel">
        <p className="form-error" role="alert">{error || "Biznes profil topilmadi."}</p>
        <button type="button" onClick={() => window.location.reload()}>Qayta urinish</button>
      </main>
    );
  }

  if (screen === "profile") {
    return (
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
      />
    );
  }

  if (screen === "online" && onlineMenu) {
    return (
      <BusinessOnlineScreen
        api={api}
        profile={profile}
        view={onlineMenu.view}
        title={onlineMenu.label}
        initialOrderId={orderTarget}
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
      />
    );
  }

  if (screen === "data") {
    return (
      <CabinetDataView
        title={dataView.title}
        rows={dataView.rows}
        onBack={() => setScreen("cabinet")}
      />
    );
  }

  if (
    screen === "staff"
    && supportsStaffManagement(api)
  ) {
    return <StaffManagementV1656 api={api} onBack={() => setScreen("cabinet")} />;
  }

  const loadedProfile = profile;
  const payload = loadedProfile.cabinet_payload ?? {};
  const summary: Record<string, number> = {
    ...loadedProfile.dashboard_snapshot,
    active_orders: loadedProfile.dashboard_snapshot.active_orders ?? activeCount(payload),
    followers: loadedProfile.followers_count,
  };
  const onlineMenus = visibleMenus(loadedProfile, ONLINE_MENUS, identity);
  const onlineMenuCards = onlineMenus.filter((menu) => !HEADER_ONLINE_VIEWS.has(menu.view));
  const followersMenu = onlineMenus.find((menu) => menu.view === "followers");
  const followingMenu = onlineMenus.find((menu) => menu.view === "following");
  const systemMenus = visibleMenus(loadedProfile, SYSTEM_MENUS, identity);
  const adminMenus = visibleMenus(loadedProfile, ADMIN_MENUS, identity);
  const directionMenus = visibleMenus(loadedProfile, DIRECTION_MENUS, identity);

  function openMenu(menu: Menu) {
    if (menu.view === "staff") {
      setScreen("staff");
      return;
    }
    if (menu.view === "profile") {
      setScreen("profile");
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
            const liveUnread = menu.view === "orders"
              ? orderUnread.product
              : menu.view === "service-orders" ? orderUnread.service : 0;
            const count = liveUnread || (menu.payload ? menuRows(loadedProfile, menu).length : 0);
            return (
              <button
                type="button"
                key={`${title}-${menu.view}`}
                className={
                  menu.view === "education-enrollments" ? "menu-card" : undefined
                }
                onClick={() => openMenu(menu)}
              >
                <span className={
                  menu.view === "education-enrollments" ? "menu-ic" : undefined
                }>{menu.icon}</span>
                <span className={
                  menu.view === "education-enrollments" ? "menu-main" : undefined
                }>
                  <b>{menu.label}</b>
                  <small>{menu.caption}</small>
                </span>
                {count > 0 && (
                  <em className={
                    menu.view === "education-enrollments"
                      ? "order-badge"
                      : undefined
                  }>{count}</em>
                )}
              </button>
            );
          })}
        </div>
      </section>
    );
  }

  return (
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
            ) : initials(loadedProfile.name)}
          </div>
          <div className="business-cabinet__identity-copy">
            <h1>{identity.actor_type === "staff" ? identity.name : loadedProfile.name}</h1>
            <p>{loadedProfile.direction || "Yo‘nalish tanlanmagan"}</p>
            <span>{identity.actor_type === "staff"
              ? `${loadedProfile.name} xodimi`
              : loadedProfile.activity_type || "Faoliyat turi tanlanmagan"}</span>
            {identity.actor_type !== "staff" && <div className="business-cabinet__identity-chips">
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
            </div>}
          </div>
          <button type="button" disabled={busy} onClick={() => void logout()}>Chiqish</button>
        </header>

        <div className="business-cabinet__stats">
          {metrics.map((metric, index) => (
            <button
              type="button"
              className={index === 0
                ? "business-cabinet__stat business-cabinet__stat--active"
                : "business-cabinet__stat"}
              key={metric.key}
              onClick={() => {
                const menu = [...onlineMenus, ...systemMenus, ...directionMenus]
                  .find((candidate) => candidate.view === metric.view);
                if (menu) openMenu(menu);
              }}
            >
              <span>{metric.label}</span>
              <strong>{metric.money
                ? money(summary[metric.key] ?? 0)
                : String(summary[metric.key] ?? 0)}</strong>
              <small>{metric.sub}</small>
            </button>
          ))}
        </div>

        {error && <p className="business-cabinet__error" role="alert">{error}</p>}

        <div className="business-cabinet__content">
          <div>
            {group("Onlaynlashtirish", "Mijozlar, buyurtmalar va onlayn savdo", onlineMenuCards)}
            {group("Tizimlashtirish", "Hisob-kitob, ombor va boshqaruv", systemMenus)}
            {group("Ma’muriyat", "Xodimlar, hujjatlar va hamkorlar", adminMenus)}
            {directionMenus.length > 0 && group(
              "Yo‘nalishga xos bo‘limlar",
              `${loadedProfile.direction} uchun maxsus boshqaruv`,
              directionMenus,
            )}
            {identity.actor_type !== "staff" && <button
              type="button"
              className="business-cabinet__switch"
              disabled={busy}
              onClick={() => void switchToUser()}
            >
              👤 Oddiy kabinetga qaytish
            </button>}
          </div>

          <aside className="business-cabinet__activity">
            <div className="business-cabinet__section-heading">
              <h2>So‘nggi faollik</h2>
              <span>{loadedProfile.recent_activity.length} ta</span>
            </div>
            {!loadedProfile.recent_activity.length ? (
              <div className="business-cabinet__empty">
                <b>Hozircha faollik yo‘q</b>
                <span>Yangi buyurtma yoki xizmat paydo bo‘lsa shu yerda ko‘rinadi.</span>
              </div>
            ) : loadedProfile.recent_activity.slice(0, 5).map((activity) => (
              <button
                type="button"
                className="business-cabinet__activity-row"
                key={`${activity.kind}-${activity.id}`}
                onClick={() => {
                  const target = isService(activity) ? "service-orders" : "orders";
                  const menu = onlineMenus.find((candidate) => candidate.view === target);
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
            ))}
          </aside>
        </div>
      </section>
    </main>
  );
}
