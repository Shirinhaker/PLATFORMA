import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessProfile as BusinessProfileData,
  BusinessProfilePatch,
  SessionIdentity,
} from "../api/types";
import { CabinetDataView } from "./CabinetDataView";


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
>;

type Props = {
  api: BusinessProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};

type Metric = [label: string, key: string, sub: string, view: string, money?: boolean];
type Menu = [icon: string, label: string, caption: string, view: string, payload?: string];

const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const EDITABLE_FIELDS = [
  "name", "phone", "description", "public_username", "direction",
  "activity_type", "address", "latitude", "longitude", "pay_card",
  "pay_holder", "director", "tax_id", "map_visible",
] as const;

const DEFAULT_METRICS: Metric[] = [
  ["Bugungi tushum", "revenue", "Bugungi savdo tushumi", "sales", true],
  ["Yangi buyurtmalar", "new_orders", "Qabul qilinmagan buyurtmalar", "orders"],
  ["Faol buyurtmalar", "active_orders", "Jarayondagi buyurtmalar", "orders"],
  ["Bildirishnomalar", "problem_orders", "E’tibor talab holatlar", "notifications"],
];

const METRICS: Record<string, Metric[]> = {
  "Savdo": [
    ["Bugungi savdo", "revenue", "Bugungi tushum", "sales", true],
    ["Yangi buyurtma", "new_orders", "Qabul qilinmagan buyurtmalar", "orders"],
    ["Umumiy qarz", "debt_total", "Qarz daftaridagi qoldiq", "debtors", true],
    ["Ombor ogohlantirishi", "low_stock", "Kam qolgan mahsulotlar", "warehouse"],
  ],
  "Umumiy ovqatlanish": [
    ["Bugungi savdo", "sales_count", "Bugungi savdolar soni", "sales"],
    ["Ochiq buyurtmalar", "active_orders", "Jarayondagi buyurtmalar", "orders"],
    ["Band stol/xona", "occupied_places", "Faol band joylar", "dining_places"],
    ["Ombor ogohlantirishi", "low_stock", "Kam qolgan masalliqlar", "warehouse"],
  ],
  "Ta'lim faoliyati": [
    ["Bugungi darslar", "today_lessons", "Bugungi jadval", "education_groups"],
    ["Guruhlar", "groups", "Faol guruhlar", "education_groups"],
    ["O‘quvchilar", "students", "Faol o‘quvchilar", "education_students"],
    ["Muddati o‘tgan to‘lov", "debt_total", "To‘lov nazoratidagi qarz", "debtors", true],
  ],
  "Tibbiy xizmatlar": [
    ["Bugungi qabullar", "service_today", "Bugungi yozilishlar", "service-orders"],
    ["Navbat", "service_active", "Kutayotgan va qabuldagi", "service-orders"],
    ["Yangi yozilishlar", "new_orders", "Yangi qabul so‘rovlari", "service-orders"],
    ["Bugungi to‘lovlar", "revenue", "Bugungi tushum", "sales", true],
  ],
};

const ONLINE_MENUS: Menu[] = [
  ["🏪", "Profil / Mening sahifam", "Mijozlar ko‘radigan ma’lumotlar", "profile"],
  ["💎", "Obunalarim", "Bepul, Plus va Pro tariflari", "subscriptions", "business_subscriptions"],
  ["💳", "To‘lovlarim", "Yuborilgan to‘lovlar", "payments", "subscription_payments"],
  ["🛍️", "Mahsulot va xizmatlar", "Qo‘shilgan katalog yozuvlari", "items", "items"],
  ["📦", "Buyurtmalar", "Mahsulot buyurtmalari", "orders", "orders"],
  ["🧰", "Xizmat buyurtmalari", "Xizmat va navbatlar", "service-orders", "orders"],
  ["💬", "Suhbatlar", "Mijozlar bilan xabarlar", "messages", "messages"],
  ["⭐", "Mijoz fikrlari", "Baholar va javoblar", "reviews", "business_reviews"],
  ["📢", "Reklamalarim", "Bosh sahifa reklamalarini boshqarish", "advertisements", "advertisements"],
  ["🎞️", "Istoriya arxivi", "Faol va arxivdagi istoriyalar", "stories", "stories"],
  ["🔔", "Bildirishnomalarim", "Biznes xabarlari", "notifications", "notifications"],
];

const SYSTEM_MENUS: Menu[] = [
  ["🧾", "Kassa", "Savdo daftari va tushum", "sales", "sales"],
  ["💸", "Xarajatlar", "Kunlik xarajatlar hisobi", "expenses", "expenses"],
  ["📒", "Qarz daftari", "Mijozlar qarzlari", "debtors", "debtors"],
  ["📦", "Ombor", "Qoldiq va kirim-chiqim", "warehouse", "warehouse_items"],
  ["📊", "Statistika", "Tushum, xarajat va foyda", "statistics"],
  ["📄", "Hisobotlar", "Davriy hisobotlar", "reports"],
];

const TERMINAL = new Set(["done", "delivered", "cancelled", "canceled", "rejected", "pickup_waiting_customer"]);

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length ? words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("") : "B";
}

function money(value: number) {
  return `${Number(value || 0).toLocaleString("uz-UZ")} so‘m`;
}

function isService(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const data = row as Record<string, unknown>;
  return ["booking", "service", "queue", "medical"].includes(String(data.order_type ?? data.kind ?? ""));
}

function activityDate(value: number) {
  return value ? new Date(value * 1000).toLocaleString("uz-UZ") : "Vaqt ko‘rsatilmagan";
}


export function BusinessProfile({ api, identity, onLogout, onSwitched }: Props) {
  const [profile, setProfile] = useState<BusinessProfileData | null>(null);
  const [baseline, setBaseline] = useState<BusinessProfileData | null>(null);
  const [workHours, setWorkHours] = useState("{}");
  const [view, setView] = useState("dashboard");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  function applyLoaded(value: BusinessProfileData) {
    setProfile(value);
    setBaseline(value);
    setWorkHours(JSON.stringify(value.work_hours, null, 2));
  }

  async function load() {
    applyLoaded(await api.getBusinessProfile());
  }

  useEffect(() => {
    let active = true;
    api.getBusinessProfile()
      .then((value) => { if (active) applyLoaded(value); })
      .catch((reason) => { if (active) setError(message(reason)); });
    return () => { active = false; };
  }, [api]);

  const allMenus = [...ONLINE_MENUS, ...SYSTEM_MENUS];
  const selectedMenu = allMenus.find((menu) => menu[3] === view);
  const payload = profile?.cabinet_payload ?? {};
  const rows = useMemo(() => {
    if (!selectedMenu?.[4]) return [];
    const raw = payload[selectedMenu[4]];
    if (!Array.isArray(raw)) return [];
    if (view === "service-orders") return raw.filter(isService);
    if (view === "orders") return raw.filter((row) => !isService(row));
    return raw;
  }, [payload, selectedMenu, view]);

  function setField<K extends keyof BusinessProfileData>(field: K, value: BusinessProfileData[K]) {
    setSaved(false);
    setProfile((current) => current ? { ...current, [field]: value } : current);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !baseline) return;
    let parsedHours: Record<string, unknown>;
    try {
      const parsed = JSON.parse(workHours) as unknown;
      if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("not object");
      parsedHours = parsed as Record<string, unknown>;
    } catch {
      setError("Ish vaqti JSON formati noto‘g‘ri.");
      return;
    }
    const patch: BusinessProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (profile[field] !== baseline[field]) (patch as Record<string, unknown>)[field] = profile[field];
    }
    if (JSON.stringify(parsedHours) !== JSON.stringify(baseline.work_hours)) patch.work_hours = parsedHours;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length ? await api.updateBusinessProfile(patch) : profile;
      const cropChanged = profile.logo_x !== baseline.logo_x || profile.logo_y !== baseline.logo_y || profile.logo_zoom !== baseline.logo_zoom;
      if (cropChanged && profile.logo_object_key) {
        value = await api.attachBusinessLogo({ object_key: profile.logo_object_key, x: profile.logo_x, y: profile.logo_y, zoom: profile.logo_zoom });
      }
      applyLoaded(value);
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    if (!IMAGE_TYPES.has(file.type)) { setError("Faqat JPEG, PNG, WEBP yoki GIF rasm yuklang."); return; }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) { setError("Rasm hajmi 8 MB dan oshmasin."); return; }
    if (!profile) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({ purpose: "logo", filename: file.name, content_type: file.type, size_bytes: file.size });
      await api.uploadGrantedFile(grant, file);
      await api.attachBusinessLogo({ object_key: grant.object_key, x: profile.logo_x, y: profile.logo_y, zoom: profile.logo_zoom });
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
    try { await api.logout(); onLogout(); }
    catch (reason) { setError(message(reason)); setBusy(false); }
  }

  async function switchUser() {
    setBusy(true);
    setError("");
    try {
      await api.switchCabinet("user");
      onSwitched(await api.getSession());
    } catch (reason) {
      setError(message(reason));
      setBusy(false);
    }
  }

  if (!profile) return <main className="profile-shell">{error ? <p role="alert">{error}</p> : "Profil yuklanmoqda…"}</main>;

  if (selectedMenu?.[4]) {
    return <CabinetDataView title={selectedMenu[1]} rows={rows} onBack={() => setView("dashboard")} />;
  }

  if (view === "statistics" || view === "reports") {
    const snapshot = profile.dashboard_snapshot;
    return (
      <main className="cabinet-data-view">
        <header className="cabinet-data-view__heading"><button type="button" onClick={() => setView("dashboard")}>← Kabinetga qaytish</button><div><h1>{view === "statistics" ? "Statistika" : "Hisobotlar"}</h1><p>v1656 dan ko‘chirilgan haqiqiy ko‘rsatkichlar</p></div></header>
        <div className="cabinet-summary-grid">
          {Object.entries(snapshot).map(([key, value]) => <article key={key}><span>{key.replaceAll("_", " ")}</span><strong>{key.includes("revenue") || key.includes("debt") || key.includes("expenses") ? money(value) : value}</strong></article>)}
        </div>
      </main>
    );
  }

  if (view === "profile") {
    return (
      <main className="profile-shell">
        <header className="profile-heading"><div><p className="session-panel__eyebrow">{identity.login}</p><h1>Profil / Mening sahifam</h1></div><button type="button" className="button-secondary" onClick={() => setView("dashboard")}>Kabinetga qaytish</button></header>
        <form className="profile-form" onSubmit={save}>
          <label>Biznes nomi<input required value={profile.name} onChange={(event) => setField("name", event.currentTarget.value)} /></label>
          <label>Telefon<input type="tel" value={profile.phone} onChange={(event) => setField("phone", event.currentTarget.value)} /></label>
          <label>Tavsif<textarea value={profile.description} onChange={(event) => setField("description", event.currentTarget.value)} /></label>
          <label>Ochiq username<input value={profile.public_username} onChange={(event) => setField("public_username", event.currentTarget.value)} /></label>
          <label>Yo‘nalish<input value={profile.direction} onChange={(event) => setField("direction", event.currentTarget.value)} /></label>
          <label>Faoliyat turi<input value={profile.activity_type} onChange={(event) => setField("activity_type", event.currentTarget.value)} /></label>
          <label>Manzil<textarea value={profile.address} onChange={(event) => setField("address", event.currentTarget.value)} /></label>
          <label>Kenglik<input type="number" step="any" value={profile.latitude ?? ""} onChange={(event) => setField("latitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
          <label>Uzunlik<input type="number" step="any" value={profile.longitude ?? ""} onChange={(event) => setField("longitude", event.currentTarget.value === "" ? null : Number(event.currentTarget.value))} /></label>
          <label>Ish vaqti (JSON)<textarea value={workHours} onChange={(event) => { setSaved(false); setWorkHours(event.currentTarget.value); }} /></label>
          <label>To‘lov kartasi<input value={profile.pay_card} onChange={(event) => setField("pay_card", event.currentTarget.value)} /></label>
          <label>Karta egasi<input value={profile.pay_holder} onChange={(event) => setField("pay_holder", event.currentTarget.value)} /></label>
          <label>Rahbar<input value={profile.director} onChange={(event) => setField("director", event.currentTarget.value)} /></label>
          <label>STIR<input value={profile.tax_id} onChange={(event) => setField("tax_id", event.currentTarget.value)} /></label>
          <label className="checkbox-field"><input type="checkbox" checked={profile.map_visible} onChange={(event) => setField("map_visible", event.currentTarget.checked)} />Xaritada ko‘rinish</label>
          <fieldset><legend>Logotip kesimi</legend><label>X<input type="number" min="0" max="100" value={profile.logo_x} onChange={(event) => setField("logo_x", Number(event.currentTarget.value))} /></label><label>Y<input type="number" min="0" max="100" value={profile.logo_y} onChange={(event) => setField("logo_y", Number(event.currentTarget.value))} /></label><label>Zoom<input type="number" min="1" max="5" step="0.1" value={profile.logo_zoom} onChange={(event) => setField("logo_zoom", Number(event.currentTarget.value))} /></label></fieldset>
          <label>Logotip<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}{saved && <p className="form-success" role="status">Saqlandi</p>}<button type="submit" disabled={busy}>Saqlash</button>
        </form>
      </main>
    );
  }

  const metrics = METRICS[profile.direction] ?? DEFAULT_METRICS;
  const snapshot = profile.dashboard_snapshot;
  return (
    <main className="user-cabinet business-cabinet">
      <section className="user-cabinet__panel">
        <header className="user-cabinet__identity">
          <div className="user-cabinet__avatar">{initials(profile.name)}</div>
          <div className="user-cabinet__identity-copy"><h1>{profile.name}</h1><p>{profile.public_username ? `@${profile.public_username}` : identity.login}</p><span>● {profile.direction || "Faoliyat yo‘nalishi tanlanmagan"}</span><div className="cabinet-follow-chips"><button type="button" onClick={() => setView("followers")}>{profile.followers_count} obunachi</button><button type="button" onClick={() => setView("following")}>{profile.following_count} obuna</button></div></div>
          <div className="cabinet-identity-actions"><button type="button" className="user-cabinet__logout" onClick={() => void switchUser()}>Oddiy kabinet</button><button type="button" className="user-cabinet__logout" onClick={() => void logout()}>Chiqish</button></div>
        </header>

        <div className="user-cabinet__stats">
          {metrics.map(([label, key, sub, target, monetary], index) => <button type="button" key={key} className={`user-cabinet__stat${index === 0 ? " user-cabinet__stat--active" : ""}`} onClick={() => setView(target)}><span>{label}</span><strong>{monetary ? money(snapshot[key] ?? 0) : snapshot[key] ?? 0}</strong><small>{sub}</small></button>)}
        </div>

        <div className="user-cabinet__content business-cabinet__content">
          <section className="user-cabinet__sections">
            <div className="user-cabinet__section-heading"><h2>Boshqaruv bo‘limlari</h2><span>{profile.direction || "Faoliyat yo‘nalishi"}</span></div>
            <div className="business-cabinet__group"><header><span>🌐</span><div><h3>Onlaynlashtirish</h3><p>Mijozlar ko‘radigan va onlayn savdo bo‘limlari</p></div></header><div className="business-cabinet__menu">{ONLINE_MENUS.map(([icon, label, caption, target]) => <button type="button" key={target} onClick={() => setView(target)}><span>{icon}</span><div><strong>{label}</strong><small>{caption}</small></div><b>›</b></button>)}</div></div>
            <div className="business-cabinet__group"><header><span>🗂</span><div><h3>Tizimlashtirish</h3><p>Ichki tartib: hisob-kitob, ombor va boshqaruv</p></div></header><div className="business-cabinet__menu">{SYSTEM_MENUS.map(([icon, label, caption, target]) => <button type="button" key={target} onClick={() => setView(target)}><span>{icon}</span><div><strong>{label}</strong><small>{caption}</small></div><b>›</b></button>)}</div></div>
            {error && <p className="user-cabinet__notice" role="alert">{error}</p>}
          </section>

          <aside className="user-cabinet__activity"><div className="user-cabinet__section-heading"><h2>So‘nggi faoliyat</h2><span>{profile.recent_activity.length} ta</span></div>{!profile.recent_activity.length ? <div className="user-cabinet__empty"><span>◎</span><strong>Hozircha faollik yo‘q</strong><p>Yangi buyurtma yoki xizmat paydo bo‘lsa, shu yerda ko‘rinadi.</p></div> : <div className="cabinet-activity-list">{profile.recent_activity.map((activity) => <button type="button" key={`${activity.kind}-${activity.id}`} onClick={() => setView(activity.kind === "service" ? "service-orders" : "orders")}><span className="cabinet-activity-icon">{activity.kind === "service" ? "X" : "B"}</span><span><b>Buyurtma #{activity.id} — {activity.title}</b><small>{activityDate(activity.created_at)}</small></span><span><b>{activity.amount ? money(activity.amount) : activity.status}</b><small>{TERMINAL.has(activity.status) ? "Yakunlangan" : "Jarayonda"}</small></span></button>)}</div>}</aside>
        </div>
      </section>
    </main>
  );
}
