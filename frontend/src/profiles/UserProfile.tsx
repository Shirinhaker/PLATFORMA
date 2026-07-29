import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  SessionIdentity,
  UserProfile as UserProfileData,
  UserProfilePatch,
} from "../api/types";
import { CabinetDataView } from "./CabinetDataView";


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
>;

type Props = {
  api: UserProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type CabinetView = "dashboard" | "profile" | "specialist" | string;
type PayloadSource = string | readonly string[];

type Section = {
  icon: string;
  label: string;
  view: string;
  payload?: PayloadSource;
};

const IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const EDITABLE_FIELDS = [
  "name",
  "phone",
  "public_username",
  "region",
  "district",
  "mahalla",
  "latitude",
  "longitude",
  "location_exact",
] as const;

const SPECIALIST_FIELDS: ReadonlyArray<readonly [string, string]> = [
  ["kasb", "Kasb/mutaxassislik"],
  ["descr", "Tavsif"],
  ["narx", "Narx"],
  ["hudud", "Xizmat hududi"],
  ["org", "Tashkilot"],
  ["dept", "Bo‘lim"],
  ["lavozim", "Lavozim"],
  ["work_hours", "Ish vaqti"],
  ["after_hours", "Ishdan tashqari vaqt"],
];

const SECTIONS: Section[] = [
  { icon: "👤", label: "Profilim", view: "profile" },
  { icon: "📢", label: "E’lonlarim", view: "listings", payload: "listings" },
  { icon: "🎞️", label: "Istoriyalarim", view: "stories", payload: "stories" },
  { icon: "💎", label: "Obunalarim", view: "follows", payload: "follows" },
  { icon: "👥", label: "Obunachilarim", view: "followers", payload: "followers" },
  { icon: "💳", label: "To‘lovlarim", view: "payments", payload: "payments" },
  {
    icon: "🔔",
    label: "Bildirishnomalarim",
    view: "notifications",
    payload: "notifications",
  },
  {
    icon: "🪪",
    label: "Mutaxassisligim va xizmatlarim",
    view: "specialist",
  },
  { icon: "📦", label: "Buyurtmalarim", view: "orders", payload: "orders" },
  {
    icon: "🧰",
    label: "Xizmat buyurtmalarim",
    view: "service-orders",
    payload: "orders",
  },
  { icon: "🔖", label: "Saqlanganlar", view: "saved", payload: "saved" },
  { icon: "💬", label: "Suhbatlar", view: "messages", payload: "messages" },
  {
    icon: "🎯",
    label: "Bildirishnoma filtrlari",
    view: "notify-filters",
    payload: "notify_filters",
  },
  {
    icon: "🚘",
    label: "Haydovchilik profilim",
    view: "drivers",
    payload: "drivers",
  },
  {
    icon: "🚕",
    label: "Taxi va dostavka buyurtmalarim",
    view: "rides",
    payload: "rides",
  },
  { icon: "⚙️", label: "Sozlamalar", view: "settings" },
];

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


function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("")
    : "U";
}


function money(value: number) {
  return value > 0 ? `${value.toLocaleString("uz-UZ")} so‘m` : "";
}


function activityDate(value: number) {
  if (!value) return "Vaqt ko‘rsatilmagan";
  return new Date(value * 1000).toLocaleString("uz-UZ");
}


function isServiceOrder(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const value = row as Record<string, unknown>;
  return ["booking", "service", "queue", "medical"].includes(
    String(value.order_type ?? value.kind ?? value.order_category ?? ""),
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


export function UserProfile({ api, identity, onLogout, onSwitched }: Props) {
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [baseline, setBaseline] = useState<UserProfileData | null>(null);
  const [view, setView] = useState<CabinetView>("dashboard");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [specialist, setSpecialist] = useState<Record<string, unknown>>({});

  function applyLoaded(value: UserProfileData) {
    setProfile(value);
    setBaseline(value);
    setSpecialist({ ...(value.specialist_profile ?? {}) });
  }

  async function load() {
    applyLoaded(await api.getUserProfile());
  }

  useEffect(() => {
    let active = true;
    api.getUserProfile()
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

  const payload = profile?.cabinet_payload ?? {};
  const selectedSection = SECTIONS.find((section) => section.view === view);
  const selectedRows = useMemo(() => {
    if (!selectedSection?.payload) return [];
    const rows = payloadRows(payload, selectedSection.payload);
    if (view === "service-orders") return rows.filter(isServiceOrder);
    if (view === "orders") return rows.filter((row) => !isServiceOrder(row));
    return rows;
  }, [payload, selectedSection, view]);

  function setField<K extends keyof UserProfileData>(
    field: K,
    value: UserProfileData[K],
  ) {
    setSaved(false);
    setProfile((current) => (
      current ? { ...current, [field]: value } : current
    ));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !baseline) return;
    const patch: UserProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (profile[field] !== baseline[field]) {
        (patch as Record<string, unknown>)[field] = profile[field];
      }
    }
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length
        ? await api.updateUserProfile(patch)
        : profile;
      const cropChanged = (
        profile.avatar_x !== baseline.avatar_x
        || profile.avatar_y !== baseline.avatar_y
        || profile.avatar_zoom !== baseline.avatar_zoom
      );
      if (cropChanged && profile.avatar_object_key) {
        value = await api.attachUserAvatar({
          object_key: profile.avatar_object_key,
          x: profile.avatar_x,
          y: profile.avatar_y,
          zoom: profile.avatar_zoom,
        });
      }
      applyLoaded(value);
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveSpecialist(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      applyLoaded(await api.updateUserProfile({
        specialist_profile: specialist,
      }));
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Faqat JPEG, PNG, WEBP yoki GIF rasm yuklang.");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return;
    }
    if (!profile) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "avatar",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      await api.attachUserAvatar({
        object_key: grant.object_key,
        x: profile.avatar_x,
        y: profile.avatar_y,
        zoom: profile.avatar_zoom,
      });
      await load();
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

  if (selectedSection?.payload) {
    return (
      <CabinetDataView
        title={selectedSection.label}
        rows={selectedRows}
        onBack={() => setView("dashboard")}
      />
    );
  }

  if (view === "specialist") {
    const field = (name: string) => String(specialist[name] ?? "");
    return (
      <main className="profile-shell">
        <header className="profile-heading">
          <h1>Mutaxassisligim va xizmatlarim</h1>
          <button
            type="button"
            className="button-secondary"
            onClick={() => setView("dashboard")}
          >
            Kabinetga qaytish
          </button>
        </header>
        <form className="profile-form" onSubmit={saveSpecialist}>
          {SPECIALIST_FIELDS.map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                value={field(key)}
                onChange={(event) => setSpecialist((current) => ({
                  ...current,
                  [key]: event.currentTarget.value,
                }))}
              />
            </label>
          ))}
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={Boolean(specialist.visible)}
              onChange={(event) => setSpecialist((current) => ({
                ...current,
                visible: event.currentTarget.checked,
              }))}
            />
            Qidiruvda ko‘rinish
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={specialist.available !== false}
              onChange={(event) => setSpecialist((current) => ({
                ...current,
                available: event.currentTarget.checked,
              }))}
            />
            Xizmat uchun bo‘shman
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          {saved && <p className="form-success" role="status">Saqlandi</p>}
          <button type="submit" disabled={busy}>Saqlash</button>
        </form>
      </main>
    );
  }

  if (view === "profile" || view === "settings") {
    return (
      <main className="profile-shell">
        <header className="profile-heading">
          <div>
            <p className="session-panel__eyebrow">{identity.login}</p>
            <h1>{view === "settings" ? "Sozlamalar" : "Profilim"}</h1>
          </div>
          <button
            type="button"
            className="button-secondary"
            onClick={() => setView("dashboard")}
          >
            Kabinetga qaytish
          </button>
        </header>
        <form className="profile-form" onSubmit={save}>
          <label>Ism<input required value={profile.name} onChange={(event) => setField("name", event.currentTarget.value)} /></label>
          <label>Telefon<input type="tel" value={profile.phone} onChange={(event) => setField("phone", event.currentTarget.value)} /></label>
          <label>Ochiq username<input value={profile.public_username} onChange={(event) => setField("public_username", event.currentTarget.value)} /></label>
          <label>Viloyat<input value={profile.region} onChange={(event) => setField("region", event.currentTarget.value)} /></label>
          <label>Tuman<input value={profile.district} onChange={(event) => setField("district", event.currentTarget.value)} /></label>
          <label>Mahalla<input value={profile.mahalla} onChange={(event) => setField("mahalla", event.currentTarget.value)} /></label>
          <label>Kenglik<input type="number" step="any" value={profile.latitude ?? ""} onChange={(event) => setField("latitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
          <label>Uzunlik<input type="number" step="any" value={profile.longitude ?? ""} onChange={(event) => setField("longitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
          <label className="checkbox-field"><input type="checkbox" checked={profile.location_exact} onChange={(event) => setField("location_exact", event.currentTarget.checked)} />Joylashuv aniq</label>
          <fieldset><legend>Avatar kesimi</legend><label>X<input type="number" min="0" max="100" value={profile.avatar_x} onChange={(event) => setField("avatar_x", Number(event.currentTarget.value))} /></label><label>Y<input type="number" min="0" max="100" value={profile.avatar_y} onChange={(event) => setField("avatar_y", Number(event.currentTarget.value))} /></label><label>Zoom<input type="number" min="1" max="5" step="0.1" value={profile.avatar_zoom} onChange={(event) => setField("avatar_zoom", Number(event.currentTarget.value))} /></label></fieldset>
          <label>Avatar<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          {saved && <p className="form-success" role="status">Saqlandi</p>}
          <button type="submit" disabled={busy}>Saqlash</button>
        </form>
      </main>
    );
  }

  const snapshot = profile.dashboard_snapshot ?? {};
  const recentActivity = profile.recent_activity ?? [];
  const followersCount = profile.followers_count ?? 0;
  const followingCount = profile.following_count ?? 0;
  const username = profile.public_username
    ? `@${profile.public_username.replace(/^@/, "")}`
    : identity.login;
  const location = [profile.district, profile.region]
    .filter(Boolean)
    .join(", ");

  return (
    <main className="user-cabinet">
      <section className="user-cabinet__panel">
        <header className="user-cabinet__identity">
          <div className="user-cabinet__avatar" aria-hidden="true">
            {initials(profile.name)}
          </div>
          <div className="user-cabinet__identity-copy">
            <h1>{profile.name}</h1>
            <p>{username}</p>
            {location && <span>● {location}</span>}
            <div className="cabinet-follow-chips">
              <button type="button" onClick={() => setView("followers")}>
                {followersCount} obunachi
              </button>
              <button type="button" onClick={() => setView("follows")}>
                {followingCount} obuna
              </button>
            </div>
          </div>
          <button
            type="button"
            className="user-cabinet__logout"
            disabled={busy}
            onClick={() => void logout()}
          >
            Chiqish
          </button>
        </header>

        <div className="user-cabinet__stats" aria-label="Kabinet statistikasi">
          {[
            ["Faol buyurtmalar", snapshot.active_orders ?? 0, "Joriy buyurtmalar", "orders"],
            ["Obunalar", snapshot.following ?? followingCount, "Kuzatilayotgan profillar", "follows"],
            ["Saqlanganlar", snapshot.saved ?? 0, "E’lon va bizneslar", "saved"],
            ["Bildirishnomalar", snapshot.unread ?? 0, "O‘qilmagan xabarlar", "notifications"],
          ].map(([label, value, sub, target], index) => (
            <button
              type="button"
              key={String(label)}
              className={`user-cabinet__stat${index === 0 ? " user-cabinet__stat--active" : ""}`}
              onClick={() => setView(String(target))}
            >
              <span>{label}</span>
              <strong>{String(value)}</strong>
              <small>{sub}</small>
            </button>
          ))}
        </div>

        <div className="user-cabinet__content">
          <section className="user-cabinet__sections">
            <div className="user-cabinet__section-heading">
              <h2>Mening bo‘limlarim</h2>
              <span>Profil va barcha faoliyatlar</span>
            </div>
            <div className="user-cabinet__grid">
              {SECTIONS.map((section) => (
                <button
                  type="button"
                  key={section.view}
                  onClick={() => setView(section.view)}
                >
                  <span aria-hidden="true">{section.icon}</span>
                  <strong>{section.label}</strong>
                </button>
              ))}
            </div>
            {(profile.has_business ?? false) && (
              <button
                type="button"
                className="user-cabinet__switch"
                disabled={busy}
                onClick={() => void switchBusiness()}
              >
                🏢 Biznes kabinetga o‘tish
              </button>
            )}
            {error && <p className="user-cabinet__notice" role="alert">{error}</p>}
          </section>

          <aside className="user-cabinet__activity">
            <div className="user-cabinet__section-heading">
              <h2>So‘nggi faoliyat</h2>
              <span>{recentActivity.length} ta</span>
            </div>
            {!recentActivity.length ? (
              <div className="user-cabinet__empty">
                <span>◎</span>
                <strong>Hozircha faollik yo‘q</strong>
                <p>Yangi buyurtma yoki xizmat paydo bo‘lsa, shu yerda ko‘rinadi.</p>
              </div>
            ) : (
              <div className="cabinet-activity-list">
                {recentActivity.map((activity) => (
                  <button
                    type="button"
                    key={`${activity.kind}-${activity.id}`}
                    onClick={() => setView(
                      activity.kind === "service" ? "service-orders" : "orders"
                    )}
                  >
                    <span className="cabinet-activity-icon">
                      {activity.kind === "service" ? "X" : "B"}
                    </span>
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
