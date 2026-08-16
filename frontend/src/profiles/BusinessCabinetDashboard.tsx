import type {
  BusinessProfile as BusinessProfileData,
  SessionIdentity,
} from "../api/types";
import {
  activityDate,
  initials,
  isService,
  type Menu,
  type Metric,
  money,
} from "./business-profile-config";
import { activityLabel, menuRows } from "./business-profile-helpers";

type Props = {
  identity: SessionIdentity;
  profile: BusinessProfileData;
  busy: boolean;
  error: string;
  metrics: Metric[];
  summary: Record<string, number>;
  onlineMenus: Menu[];
  systemMenus: Menu[];
  adminMenus: Menu[];
  directionMenus: Menu[];
  onlineMenuCards: Menu[];
  systemMenuCards: Menu[];
  orderUnread: { product: number; service: number };
  messageUnread: number;
  notificationUnread: number;
  onOpenMenu(menu: Menu): void;
  onOpenProfile(): void;
  onLogout(): void;
  onSwitchToUser(): void;
};

export function BusinessCabinetDashboard({
  identity,
  profile,
  busy,
  error,
  metrics,
  summary,
  onlineMenus,
  systemMenus,
  adminMenus,
  directionMenus,
  onlineMenuCards,
  systemMenuCards,
  orderUnread,
  messageUnread,
  notificationUnread,
  onOpenMenu,
  onOpenProfile,
  onLogout,
  onSwitchToUser,
}: Props) {
  const followersMenu = onlineMenus.find((menu) => menu.view === "followers");
  const followingMenu = onlineMenus.find((menu) => menu.view === "following");

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
              liveUnread || (menu.payload ? menuRows(profile, menu).length : 0);
            return (
              <button
                type="button"
                key={`${title}-${menu.view}`}
                className={
                  menu.view === "education-enrollments" ? "menu-card" : undefined
                }
                onClick={() => onOpenMenu(menu)}
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
                {count > 0 ? (
                  <em
                    className={
                      menu.view === "education-enrollments" ? "order-badge" : undefined
                    }
                  >
                    {count}
                  </em>
                ) : null}
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
            {profile.logo_url ? (
              <img
                src={profile.logo_url}
                alt=""
                style={{
                  objectPosition: `${profile.logo_x}% ${profile.logo_y}%`,
                  transform: `scale(${profile.logo_zoom})`,
                }}
              />
            ) : (
              initials(profile.name)
            )}
          </div>
          <div className="business-cabinet__identity-copy">
            <h1>{identity.actor_type === "staff" ? identity.name : profile.name}</h1>
            <p>{profile.direction || "Yo‘nalish tanlanmagan"}</p>
            <span>
              {identity.actor_type === "staff"
                ? `${profile.name} xodimi`
                : profile.activity_type || "Faoliyat turi tanlanmagan"}
            </span>
            {identity.actor_type !== "staff" ? (
              <div className="business-cabinet__identity-chips">
                <button
                  type="button"
                  aria-label="Obunachilar"
                  disabled={!followersMenu}
                  onClick={() => followersMenu && onOpenMenu(followersMenu)}
                >
                  {profile.followers_count} obunachi
                </button>
                <button
                  type="button"
                  aria-label="Biznes obunalari"
                  disabled={!followingMenu}
                  onClick={() => followingMenu && onOpenMenu(followingMenu)}
                >
                  {profile.following_count} obuna
                </button>
              </div>
            ) : null}
          </div>
          {identity.actor_type === "staff" ? (
            <button type="button" disabled={busy} onClick={onLogout}>
              Chiqish
            </button>
          ) : (
            <button
              type="button"
              className="business-cabinet__user-switch-top"
              disabled={busy}
              onClick={onSwitchToUser}
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
                if (menu) onOpenMenu(menu);
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

        {error ? (
          <p className="business-cabinet__error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="business-cabinet__content">
          <div className="business-cabinet__menu-panel">
            <div className="business-cabinet__section-heading">
              <div>
                <h2>Boshqaruv bo‘limlari</h2>
                <p>{`${profile.direction || "Biznes"} bo‘yicha kerakli bo‘limlar`}</p>
              </div>
              <button type="button" onClick={onOpenProfile}>
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
              <span>{profile.recent_activity.length} ta</span>
            </div>
            {!profile.recent_activity.length ? (
              <div className="business-cabinet__empty">
                <b>Hozircha faollik yo‘q</b>
                <span>
                  Yangi buyurtma yoki xizmat paydo bo‘lsa shu yerda ko‘rinadi.
                </span>
              </div>
            ) : (
              profile.recent_activity.slice(0, 5).map((activity) => (
                <button
                  type="button"
                  className="business-cabinet__activity-row"
                  key={`${activity.kind}-${activity.id}`}
                  onClick={() => {
                    const target = isService(activity) ? "service-orders" : "orders";
                    const menu = onlineMenus.find(
                      (candidate) => candidate.view === target,
                    );
                    if (menu) onOpenMenu(menu);
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
    </main>
  );
}
