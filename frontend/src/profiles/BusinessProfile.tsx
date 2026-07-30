import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessProfile as BusinessProfileData,
  CabinetActivity,
  SessionIdentity,
} from "../api/types";
import { BusinessProfileEditor } from "./BusinessProfileEditor";
import {
  ADMIN_MENUS,
  activityDate,
  DEFAULT_METRICS,
  DIRECTION_MENUS,
  initials,
  isService,
  Menu,
  METRICS,
  money,
  ONLINE_MENUS,
  payloadRows,
  SYSTEM_MENUS,
} from "./business-profile-config";
import { CabinetDataView } from "./CabinetDataView";
import "./Cabinet.css";


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
> & Partial<Pick<ApiClient, "attachBusinessPaymentQr">>;

type Props = {
  api: BusinessProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type View = {
  title: string;
  rows: unknown[];
};


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function activityLabel(row: CabinetActivity) {
  return row.kind === "order" ? `Buyurtma #${row.id} — ${row.title}` : row.title;
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

function metricValue(value: number, moneyValue?: boolean) {
  return moneyValue ? money(value) : String(Number(value || 0));
}

function menuRows(profile: BusinessProfileData, menu: Menu): unknown[] {
  if (!menu.payload) return [];
  const rows = payloadRows(profile.cabinet_payload, menu.payload);
  if (menu.view === "service-orders") return rows.filter(isService);
  if (menu.view === "orders") return rows.filter((row) => !isService(row));
  return rows;
}

function visibleMenus(profile: BusinessProfileData, menus: Menu[]) {
  return menus.filter((menu) => (
    !menu.directions || menu.directions.includes(profile.direction)
  ));
}


export function BusinessProfile({
  api,
  identity,
  onLogout,
  onSwitched,
}: Props) {
  const [profile, setProfile] = useState<BusinessProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [screen, setScreen] = useState<"cabinet" | "profile" | "data">("cabinet");
  const [view, setView] = useState<View>({ title: "", rows: [] });

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.getBusinessProfile()
      .then((value) => {
        if (active) setProfile(value);
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const metrics = useMemo(() => {
    if (!profile) return DEFAULT_METRICS;
    return METRICS[profile.direction] ?? DEFAULT_METRICS;
  }, [profile]);

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
      />
    );
  }

  if (screen === "data") {
    return (
      <CabinetDataView
        title={view.title}
        rows={view.rows}
        onBack={() => setScreen("cabinet")}
      />
    );
  }

  const payload = profile.cabinet_payload ?? {};
  const summary = {
    ...profile.dashboard_snapshot,
    active_orders: profile.dashboard_snapshot.active_orders ?? activeCount(payload),
    followers: profile.followers_count,
  };
  const onlineMenus = visibleMenus(profile, ONLINE_MENUS);
  const systemMenus = visibleMenus(profile, SYSTEM_MENUS);
  const adminMenus = visibleMenus(profile, ADMIN_MENUS);
  const directionMenus = visibleMenus(profile, DIRECTION_MENUS);

  function openMenu(menu: Menu) {
    if (menu.view === "profile") {
      setScreen("profile");
      return;
    }
    if (menu.view === "statistics") {
      setView({
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
      setView({
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
    setView({ title: menu.label, rows: menuRows(profile, menu) });
    setScreen("data");
  }

  async function switchToUser() {
    setBusy(true);
    setError("");
    try {
      await api.switchCabinet("user");
      onSwitched(await api.getSession());
    } catch (reason) {
      setError(errorMessage(reason));
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
      setError(errorMessage(reason));
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
            const count = menu.payload ? menuRows(profile, menu).length : 0;
            return (
              <button
                type="button"
                key={`${title}-${menu.view}`}
                onClick={() => openMenu(menu)}
              >
                <span>{menu.icon}</span>
                <span>
                  <b>{menu.label}</b>
                  <small>{menu.caption}</small>
                </span>
                {count > 0 && <em>{count}</em>}
              </button>
            );
          })}
        </div>
      </section>
    );
  }

  return (
    <main className="business-cabinet">
      <section className="business-cabinet__panel">
        <header className="business-cabinet__identity">
          <div className="business-cabinet__avatar">
            {profile.logo_url ? (
              <img
                src={profile.logo_url}
                alt=""
                style={{
                  objectPosition: `${profile.logo_x}% ${profile.logo_y}%`,
                  transform: `scale(${profile.logo_zoom})`,
                }}
              />
            ) : initials(profile.name)}
          </div>
          <div className="business-cabinet__identity-copy">
            <h1>{profile.name}</h1>
            <p>{profile.direction || "Yo‘nalish tanlanmagan"}</p>
            <span>{profile.activity_type || "Faoliyat turi tanlanmagan"}</span>
          </div>
          <button type="button" disabled={busy} onClick={() => void logout()}>
            Chiqish
          </button>
        </header>

        <div className="business-cabinet__stats">
          {metrics.map((metric, index) => (
            <button
              type="button"
              className={index === 0 ? "business-cabinet__stat business-cabinet__stat--active" : "business-cabinet__stat"}
              key={metric.key}
              onClick={() => {
                const candidate = [...onlineMenus, ...systemMenus, ...directionMenus]
                  .find((menu) => menu.view === metric.view);
                if (candidate) openMenu(candidate);
              }}
            >
              <span>{metric.label}</span>
              <strong>{metricValue(Number(summary[metric.key] ?? 0), metric.money)}</strong>
              <small>{metric.sub}</small>
            </button>
          ))}
        </div>

        {error && <p className="business-cabinet__error" role="alert">{error}</p>}

        <div className="business-cabinet__content">
          <div>
            {group("Onlaynlashtirish", "Mijozlar, buyurtmalar va onlayn savdo", onlineMenus)}
            {group("Tizimlashtirish", "Hisob-kitob, ombor va boshqaruv", systemMenus)}
            {group("Ma’muriyat", "Xodimlar, hujjatlar va hamkorlar", adminMenus)}
            {directionMenus.length > 0 && group(
              "Yo‘nalishga xos bo‘limlar",
              `${profile.direction} uchun maxsus boshqaruv`,
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
              <span>{profile.recent_activity.length} ta</span>
            </div>
            {!profile.recent_activity.length ? (
              <div className="business-cabinet__empty">
                <b>Hozircha faollik yo‘q</b>
                <span>Yangi buyurtma yoki xizmat paydo bo‘lsa shu yerda ko‘rinadi.</span>
              </div>
            ) : profile.recent_activity.slice(0, 5).map((activity) => (
              <button
                type="button"
                className="business-cabinet__activity-row"
                key={`${activity.kind}-${activity.id}`}
                onClick={() => {
                  const source = isService(activity) ? "service-orders" : "orders";
                  const candidate = onlineMenus.find((menu) => menu.view === source);
                  if (candidate) openMenu(candidate);
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
