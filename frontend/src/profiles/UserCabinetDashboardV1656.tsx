import type { UserProfile } from "../api/types";
import { avatarImageStyle } from "./UserAvatarCropV1656";
import "./UserProfileV1656.css";


export type UserCabinetSectionV1656 = {
  caption: string;
  icon: string;
  label: string;
  view: string;
};

type Props = {
  busy: boolean;
  error: string;
  messageUnread: number;
  notificationUnread: number;
  orderUnread: { product: number; service: number };
  profile: UserProfile;
  sections: readonly UserCabinetSectionV1656[];
  onNavigate(view: string): void;
  onOpenBusiness(): void;
  onSwitchBusiness(): void;
};

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


function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("")
    : "🙂";
}

function money(value: number) {
  return value > 0 ? `${value.toLocaleString("uz-UZ")} so‘m` : "";
}

function activityDate(value: number) {
  if (!value) return "Vaqt ko‘rsatilmagan";
  return new Date(value * 1000).toLocaleString("uz-UZ");
}


export function UserCabinetDashboardV1656({
  busy,
  error,
  messageUnread,
  notificationUnread,
  orderUnread,
  profile,
  sections,
  onNavigate,
  onOpenBusiness,
  onSwitchBusiness,
}: Props) {
  const snapshot = profile.dashboard_snapshot ?? {};
  const recentActivity = profile.recent_activity ?? [];
  const location = [profile.district, profile.region].filter(Boolean).join(", ");
  const metrics = [
    ["Faol buyurtmalar", snapshot.active_orders ?? 0, "Joriy buyurtmalar", "orders"],
    ["Obunalar", snapshot.following ?? profile.following_count, "Kuzatilayotgan profillar", "follows"],
    ["Saqlanganlar", snapshot.saved ?? 0, "E’lon va bizneslar", "saved"],
    ["Bildirishnomalar", notificationUnread, "O‘qilmagan xabarlar", "notifications"],
  ] as const;

  function badge(view: string) {
    if (view === "orders") return orderUnread.product;
    if (view === "service-orders") return orderUnread.service;
    if (view === "messages") return messageUnread;
    if (view === "notifications") return notificationUnread;
    return 0;
  }

  return (
    <main className="user-cabinet-v1656">
      <section className="user-cabinet-v1656__shell">
        <header className="user-cabinet-v1656__identity">
          <button
            type="button"
            className="user-cabinet-v1656__avatar"
            aria-label="Profilimni ochish"
            onClick={() => onNavigate("profile")}
          >
            {profile.avatar_url ? (
              <img
                alt={`${profile.name || "Foydalanuvchi"} profil rasmi`}
                src={profile.avatar_url}
                style={avatarImageStyle({
                  x: profile.avatar_x,
                  y: profile.avatar_y,
                  zoom: profile.avatar_zoom,
                })}
              />
            ) : initials(profile.name)}
          </button>
          <div>
            <h1>{profile.name || "Foydalanuvchi"}</h1>
            <p>{location || "Joylashuv kiritilmagan"}</p>
            <div className="user-cabinet-v1656__follow">
              <button type="button" onClick={() => onNavigate("followers")}>
                <b>{profile.followers_count || 0}</b> obunachi
              </button>
              <button type="button" onClick={() => onNavigate("follows")}>
                <b>{profile.following_count || 0}</b> obuna
              </button>
            </div>
          </div>
        </header>

        <div className="user-cabinet-v1656__metrics" aria-label="Kabinet statistikasi">
          {metrics.map(([label, value, caption, view], index) => (
            <button
              type="button"
              className={index === 0 ? "primary" : undefined}
              key={label}
              onClick={() => onNavigate(view)}
            >
              <span>{label}</span>
              <strong>{value}</strong>
              <small>{caption}</small>
            </button>
          ))}
        </div>

        <div className="user-cabinet-v1656__main">
          <section className="user-cabinet-v1656__menu-panel">
            <header className="user-cabinet-v1656__panel-title">
              <h2>Mening bo‘limlarim</h2>
              <span>Profil va faoliyatlar</span>
            </header>
            <div className="user-cabinet-v1656__menu">
              {sections.map((section) => {
                const count = badge(section.view);
                return (
                  <button
                    type="button"
                    key={section.view}
                    onClick={() => onNavigate(section.view)}
                  >
                    <span aria-hidden="true">{section.icon}</span>
                    <div>
                      <strong>{section.label}</strong>
                      <small>{section.caption}</small>
                    </div>
                    {count > 0 ? <em>{count > 99 ? "99+" : count}</em> : null}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              className="user-cabinet-v1656__business"
              disabled={busy}
              onClick={profile.has_business ? onSwitchBusiness : onOpenBusiness}
            >
              {profile.has_business
                ? "🏪 Biznes kabinetga o‘tish"
                : "🏪 Biznes ochish"}
            </button>
            {error ? <p className="user-cabinet-v1656__error" role="alert">{error}</p> : null}
          </section>

          <aside className="user-cabinet-v1656__activity">
            <header className="user-cabinet-v1656__panel-title">
              <h2>So‘nggi faollik</h2>
              <span>{recentActivity.length} ta</span>
            </header>
            {!recentActivity.length ? (
              <div className="user-cabinet-v1656__empty">
                <strong>Hozircha faollik yo‘q</strong>
                <p>Yangi buyurtma yoki xizmat paydo bo‘lsa, shu yerda ko‘rinadi.</p>
              </div>
            ) : (
              <div className="user-cabinet-v1656__activity-list">
                {recentActivity.map((activity) => (
                  <button
                    type="button"
                    key={`${activity.kind}-${activity.id}`}
                    onClick={() => onNavigate(
                      activity.kind === "service" ? "service-orders" : "orders",
                    )}
                  >
                    <span>{activity.kind === "service" ? "X" : "B"}</span>
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
    </main>
  );
}
