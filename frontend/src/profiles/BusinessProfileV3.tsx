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
>>;

type Props = {
  api: BusinessProfileApiV3;
  identity: SessionIdentity;
  onLogout: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type DataView = { title: string; rows: unknown[] };
type Screen = "cabinet" | "profile" | "data" | "online";

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

function visibleMenus(profile: BusinessProfileData | null, menus: Menu[]) {
  if (!profile) return [];
  return menus
    .filter((menu) => (
      isOnlineMenu(menu)
        ? isOnlineMenuVisibleForDirection(menu, profile.direction)
        : !menu.directions || menu.directions.includes(profile.direction)
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

  const metrics = useMemo(
    () => profile ? (METRICS[profile.direction] ?? DEFAULT_METRICS) : DEFAULT_METRICS,
    [profile],
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
          const menu = visibleMenus(profile, ONLINE_MENUS).find(
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

  const loadedProfile = profile;
  const payload = loadedProfile.cabinet_payload ?? {};
  const summary: Record<string, number> = {
    ...loadedProfile.dashboard_snapshot,
    active_orders: loadedProfile.dashboard_snapshot.active_orders ?? activeCount(payload),
    followers: loadedProfile.followers_count,
  };
  const onlineMenus = visibleMenus(loadedProfile, ONLINE_MENUS);
  const onlineMenuCards = onlineMenus.filter((menu) => !HEADER_ONLINE_VIEWS.has(menu.view));
  const followersMenu = onlineMenus.find((menu) => menu.view === "followers");
  const followingMenu = onlineMenus.find((menu) => menu.view === "following");
  const systemMenus = visibleMenus(loadedProfile, SYSTEM_MENUS);
  const adminMenus = visibleMenus(loadedProfile, ADMIN_MENUS);
  const directionMenus = visibleMenus(loadedProfile, DIRECTION_MENUS);

  function openMenu(menu: Menu) {
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
            const count = menu.payload ? menuRows(loadedProfile, menu).length : 0;
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
            <h1>{loadedProfile.name}</h1>
            <p>{loadedProfile.direction || "Yo‘nalish tanlanmagan"}</p>
            <span>{loadedProfile.activity_type || "Faoliyat turi tanlanmagan"}</span>
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
            <button
              type="button"
              className="business-cabinet__switch"
              disabled={busy}
              onClick={() => void switchToUser()}
            >
              👤 Oddiy kabinetga qaytish
            </button>
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
