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

type Metric = {
  label: string;
  key: string;
  sub: string;
  view: string;
  money?: boolean;
};
type PayloadSource = string | readonly string[];
type Menu = {
  icon: string;
  label: string;
  caption: string;
  view: string;
  payload?: PayloadSource;
  directions?: readonly string[];
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
  "description",
  "public_username",
  "direction",
  "activity_type",
  "address",
  "latitude",
  "longitude",
  "pay_card",
  "pay_holder",
  "director",
  "tax_id",
  "map_visible",
] as const;

const DEFAULT_METRICS: Metric[] = [
  { label: "Bugungi tushum", key: "revenue", sub: "Bugungi savdo tushumi", view: "sales", money: true },
  { label: "Yangi buyurtmalar", key: "new_orders", sub: "Qabul qilinmagan buyurtmalar", view: "orders" },
  { label: "Faol buyurtmalar", key: "active_orders", sub: "Jarayondagi buyurtmalar", view: "orders" },
  { label: "Bildirishnomalar", key: "problem_orders", sub: "E’tibor talab holatlar", view: "notifications" },
];

const METRICS: Record<string, Metric[]> = {
  Savdo: [
    { label: "Bugungi savdo", key: "revenue", sub: "Bugungi tushum", view: "sales", money: true },
    { label: "Yangi buyurtma", key: "new_orders", sub: "Qabul qilinmagan buyurtmalar", view: "orders" },
    { label: "Umumiy qarz", key: "debt_total", sub: "Qarz daftaridagi qoldiq", view: "debtors", money: true },
    { label: "Ombor ogohlantirishi", key: "low_stock", sub: "Kam qolgan mahsulotlar", view: "warehouse" },
  ],
  "Umumiy ovqatlanish": [
    { label: "Bugungi savdo", key: "sales_count", sub: "Bugungi savdolar soni", view: "sales" },
    { label: "Ochiq buyurtmalar", key: "active_orders", sub: "Jarayondagi buyurtmalar", view: "orders" },
    { label: "Band stol/xona", key: "occupied_places", sub: "Faol band joylar", view: "dining-places" },
    { label: "Ombor ogohlantirishi", key: "low_stock", sub: "Kam qolgan masalliqlar", view: "warehouse" },
  ],
  "Ta'lim faoliyati": [
    { label: "Bugungi darslar", key: "today_lessons", sub: "Bugungi jadval", view: "education-groups" },
    { label: "Guruhlar", key: "groups", sub: "Faol guruhlar", view: "education-groups" },
    { label: "O‘quvchilar", key: "students", sub: "Faol o‘quvchilar", view: "education-students" },
    { label: "Muddati o‘tgan to‘lov", key: "debt_total", sub: "To‘lov nazoratidagi qarz", view: "debtors", money: true },
  ],
  "Tibbiy xizmatlar": [
    { label: "Bugungi qabullar", key: "service_today", sub: "Bugungi yozilishlar", view: "service-orders" },
    { label: "Navbat", key: "service_active", sub: "Kutayotgan va qabuldagi", view: "medical-queues" },
    { label: "Yangi yozilishlar", key: "new_orders", sub: "Yangi qabul so‘rovlari", view: "service-orders" },
    { label: "Bugungi to‘lovlar", key: "revenue", sub: "Bugungi tushum", view: "sales", money: true },
  ],
};

const ONLINE_MENUS: Menu[] = [
  { icon: "🏪", label: "Profil / Mening sahifam", caption: "Mijozlar ko‘radigan ma’lumotlar", view: "profile" },
  { icon: "💎", label: "Obunalarim", caption: "Bepul, Plus va Pro tariflari", view: "subscriptions", payload: "business_subscriptions" },
  { icon: "💳", label: "To‘lovlarim", caption: "Yuborilgan to‘lovlar va tarix", view: "payments", payload: "subscription_payments" },
  { icon: "🛍️", label: "Mahsulot va xizmatlar", caption: "Guruhlar va katalog yozuvlari", view: "items", payload: ["item_groups", "items"] },
  { icon: "📢", label: "E’lonlarim", caption: "Biznes nomidan joylangan e’lonlar", view: "listings", payload: "listings" },
  { icon: "📦", label: "Buyurtmalar", caption: "Mahsulot buyurtmalari", view: "orders", payload: "orders" },
  { icon: "🧰", label: "Xizmat buyurtmalari", caption: "Xizmat va navbatlar", view: "service-orders", payload: "orders" },
  { icon: "💬", label: "Suhbatlar", caption: "Mijozlar bilan xabarlar", view: "messages", payload: "messages" },
  { icon: "⭐", label: "Mijoz fikrlari", caption: "Baholar va javoblar", view: "reviews", payload: "business_reviews" },
  { icon: "📣", label: "Reklamalarim", caption: "Banner va ko‘rsatish tarixi", view: "advertisements", payload: "advertisements" },
  { icon: "🎞️", label: "Istoriya arxivi", caption: "Faol va arxivdagi istoriyalar", view: "stories", payload: "stories" },
  { icon: "🔔", label: "Bildirishnomalarim", caption: "Biznes xabarlari", view: "notifications", payload: "notifications" },
  { icon: "👥", label: "Obunachilar", caption: "Biznesni kuzatayotgan profillar", view: "followers", payload: "followers" },
  { icon: "🔗", label: "Biznes obunalari", caption: "Biznes nomidan kuzatilayotgan profillar", view: "following", payload: "following" },
];

const SYSTEM_MENUS: Menu[] = [
  { icon: "🧾", label: "Kassa", caption: "Savdo daftari va kassa harakatlari", view: "sales", payload: ["sales", "cash_transactions", "cash_register_transactions"] },
  { icon: "💸", label: "Xarajatlar", caption: "Kunlik xarajatlar hisobi", view: "expenses", payload: "expenses" },
  { icon: "📒", label: "Qarz daftari", caption: "Mijozlar qarzi va tranzaksiyalar", view: "debtors", payload: ["debtors", "qarz_transactions"] },
  { icon: "📦", label: "Ombor", caption: "Qoldiq va kirim-chiqim", view: "warehouse", payload: ["warehouse_items", "warehouse_tx"] },
  { icon: "📊", label: "Statistika", caption: "Tushum, xarajat va faoliyat", view: "statistics" },
  { icon: "📄", label: "Hisobotlar", caption: "Ko‘chirilgan davriy ko‘rsatkichlar", view: "reports" },
];

const ADMIN_MENUS: Menu[] = [
  { icon: "👨‍💼", label: "Xodimlar", caption: "Xodim va kirish ma’lumotlari", view: "staff", payload: ["staff", "business_staff", "employees"] },
  { icon: "🗃️", label: "Mening hujjatlarim", caption: "Biznesga tegishli hujjatlar", view: "documents", payload: ["documents", "business_documents"] },
  { icon: "📥", label: "Kiruvchi hujjatlar", caption: "Qabul qilingan hujjatlar", view: "incoming-documents", payload: "incoming_documents" },
  { icon: "📤", label: "Chiquvchi hujjatlar", caption: "Yuborilgan hujjatlar", view: "outgoing-documents", payload: "outgoing_documents" },
  { icon: "📝", label: "Ichki hujjatlar", caption: "Ichki buyruq va yozuvlar", view: "internal-documents", payload: "internal_documents" },
  { icon: "🤝", label: "Kontragentlar", caption: "Hamkor va ta’minotchilar", view: "counterparties", payload: "counterparties" },
];

const DIRECTION_MENUS: Menu[] = [
  { icon: "🍽️", label: "Stol va xonalar", caption: "Umumiy ovqatlanish joylashuvi", view: "dining-places", payload: "dining_places", directions: ["Umumiy ovqatlanish"] },
  { icon: "🧑‍🍳", label: "Ichki ovqatlanish buyurtmalari", caption: "Stol va tashqi buyurtmalar", view: "dining-orders", payload: "dining_orders", directions: ["Umumiy ovqatlanish"] },
  { icon: "👨‍🏫", label: "Ta’lim guruhlari", caption: "Guruh va dars ma’lumotlari", view: "education-groups", payload: "education_groups", directions: ["Ta'lim faoliyati", "Ta’lim faoliyati"] },
  { icon: "🎓", label: "O‘quvchilar", caption: "O‘quvchi va to‘lov holatlari", view: "education-students", payload: "education_students", directions: ["Ta'lim faoliyati", "Ta’lim faoliyati"] },
  { icon: "🧑‍🏫", label: "O‘qituvchilar", caption: "O‘qituvchi ma’lumotlari", view: "education-teachers", payload: "education_teachers", directions: ["Ta'lim faoliyati", "Ta’lim faoliyati"] },
  { icon: "🏥", label: "Tibbiy navbat", caption: "Kutayotgan va qabuldagi bemorlar", view: "medical-queues", payload: "medical_queues", directions: ["Tibbiy xizmatlar"] },
  { icon: "🩺", label: "Tibbiy qabullar", caption: "Yozilish va qabul ma’lumotlari", view: "medical-appointments", payload: "medical_appointments", directions: ["Tibbiy xizmatlar"] },
];

const TERMINAL = new Set([
  "done",
  "delivered",
  "cancelled",
  "canceled",
  "rejected",
  "pickup_waiting_customer",
]);


function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.length
    ? words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("")
    : "B";
}


function money(value: number) {
  return `${Number(value || 0).toLocaleString("uz-UZ")} so‘m`;
}


function isService(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const data = row as Record<string, unknown>;
  return ["booking", "service", "queue", "medical"].includes(
    String(data.order_type ?? data.kind ?? data.order_category ?? ""),
  );
}


function activityDate(value: number) {
  return value
    ? new Date(value * 1000).toLocaleString("uz-UZ")
    : "Vaqt ko‘rsatilmagan";
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


function hasPayload(
  payload: Record<string, unknown>,
  source?: PayloadSource,
): boolean {
  return Boolean(source && payloadRows(payload, source).length);
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
    setWorkHours(JSON.stringify(value.work_hours ?? {}, null, 2));
  }

  async function load() {
    applyLoaded(await api.getBusinessProfile());
  }

  useEffect(() => {
    let active = true;
    api.getBusinessProfile()
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
  const directionMenus = useMemo(() => DIRECTION_MENUS.filter((menu) => (
    menu.directions?.includes(profile?.direction ?? "")
    || hasPayload(payload, menu.payload)
  )), [payload, profile?.direction]);
  const allMenus = useMemo(() => [
    ...ONLINE_MENUS,
    ...SYSTEM_MENUS,
    ...ADMIN_MENUS,
    ...directionMenus,
  ], [directionMenus]);
  const selectedMenu = allMenus.find((menu) => menu.view === view);
  const rows = useMemo(() => {
    if (!selectedMenu?.payload) return [];
    const result = payloadRows(payload, selectedMenu.payload);
    if (view === "service-orders") return result.filter(isService);
    if (view === "orders") return result.filter((row) => !isService(row));
    return result;
  }, [payload, selectedMenu, view]);

  function setField<K extends keyof BusinessProfileData>(
    field: K,
    value: BusinessProfileData[K],
  ) {
    setSaved(false);
    setProfile((current) => (
      current ? { ...current, [field]: value } : current
    ));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !baseline) return;
    let parsedHours: Record<string, unknown>;
    try {
      const parsed = JSON.parse(workHours) as unknown;
      if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("not object");
      }
      parsedHours = parsed as Record<string, unknown>;
    } catch {
      setError("Ish vaqti JSON formati noto‘g‘ri.");
      return;
    }
    const patch: BusinessProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (profile[field] !== baseline[field]) {
        (patch as Record<string, unknown>)[field] = profile[field];
      }
    }
    if (JSON.stringify(parsedHours) !== JSON.stringify(baseline.work_hours)) {
      patch.work_hours = parsedHours;
    }
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length
        ? await api.updateBusinessProfile(patch)
        : profile;
      const cropChanged = (
        profile.logo_x !== baseline.logo_x
        || profile.logo_y !== baseline.logo_y
        || profile.logo_zoom !== baseline.logo_zoom
      );
      if (cropChanged && profile.logo_object_key) {
        value = await api.attachBusinessLogo({
          object_key: profile.logo_object_key,
          x: profile.logo_x,
          y: profile.logo_y,
          zoom: profile.logo_zoom,
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
        purpose: "logo",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      await api.attachBusinessLogo({
        object_key: grant.object_key,
        x: profile.logo_x,
        y: profile.logo_y,
        zoom: profile.logo_zoom,
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

  if (!profile) {
    return (
      <main className="profile-shell">
        {error ? <p role="alert">{error}</p> : "Profil yuklanmoqda…"}
      </main>
    );
  }

  if (selectedMenu?.payload) {
    return (
      <CabinetDataView
        title={selectedMenu.label}
        rows={rows}
        onBack={() => setView("dashboard")}
      />
    );
  }

  if (view === "statistics" || view === "reports") {
    const snapshot = profile.dashboard_snapshot ?? {};
    return (
      <main className="cabinet-data-view">
        <header className="cabinet-data-view__heading">
          <button type="button" onClick={() => setView("dashboard")}>
            ← Kabinetga qaytish
          </button>
          <div>
            <h1>{view === "statistics" ? "Statistika" : "Hisobotlar"}</h1>
            <p>v1656 dan ko‘chirilgan haqiqiy ko‘rsatkichlar</p>
          </div>
        </header>
        <div className="cabinet-summary-grid">
          {Object.entries(snapshot).map(([key, value]) => (
            <article key={key}>
              <span>{key.replaceAll("_", " ")}</span>
              <strong>
                {key.includes("revenue")
                  || key.includes("debt")
                  || key.includes("expenses")
                  ? money(value)
                  : value}
              </strong>
            </article>
          ))}
        </div>
      </main>
    );
  }

  if (view === "profile") {
    return (
      <main className="profile-shell">
        <header className="profile-heading">
          <div>
            <p className="session-panel__eyebrow">{identity.login}</p>
            <h1>Profil / Mening sahifam</h1>
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
          <label className="checkbox-field"><input type="checkbox" checked={profile.map_visible ?? false} onChange={(event) => setField("map_visible", event.currentTarget.checked)} />Xaritada ko‘rinish</label>
          <fieldset><legend>Logotip kesimi</legend><label>X<input type="number" min="0" max="100" value={profile.logo_x} onChange={(event) => setField("logo_x", Number(event.currentTarget.value))} /></label><label>Y<input type="number" min="0" max="100" value={profile.logo_y} onChange={(event) => setField("logo_y", Number(event.currentTarget.value))} /></label><label>Zoom<input type="number" min="1" max="5" step="0.1" value={profile.logo_zoom} onChange={(event) => setField("logo_zoom", Number(event.currentTarget.value))} /></label></fieldset>
          <label>Logotip<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); }} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          {saved && <p className="form-success" role="status">Saqlandi</p>}
          <button type="submit" disabled={busy}>Saqlash</button>
        </form>
      </main>
    );
  }

  const metrics = METRICS[profile.direction] ?? DEFAULT_METRICS;
  const snapshot = profile.dashboard_snapshot ?? {};
  const recentActivity = profile.recent_activity ?? [];
  const followersCount = profile.followers_count ?? 0;
  const followingCount = profile.following_count ?? 0;

  const menuGroup = (menus: Menu[]) => (
    <div className="business-cabinet__menu">
      {menus.map((menu) => (
        <button
          type="button"
          key={menu.view}
          onClick={() => setView(menu.view)}
        >
          <span>{menu.icon}</span>
          <div>
            <strong>{menu.label}</strong>
            <small>{menu.caption}</small>
          </div>
          <b>›</b>
        </button>
      ))}
    </div>
  );

  return (
    <main className="user-cabinet business-cabinet">
      <section className="user-cabinet__panel">
        <header className="user-cabinet__identity">
          <div className="user-cabinet__avatar">{initials(profile.name)}</div>
          <div className="user-cabinet__identity-copy">
            <h1>{profile.name}</h1>
            <p>{profile.public_username ? `@${profile.public_username}` : identity.login}</p>
            <span>● {profile.direction || "Faoliyat yo‘nalishi tanlanmagan"}</span>
            <div className="cabinet-follow-chips">
              <button type="button" onClick={() => setView("followers")}>
                {followersCount} obunachi
              </button>
              <button type="button" onClick={() => setView("following")}>
                {followingCount} obuna
              </button>
            </div>
          </div>
          <div className="cabinet-identity-actions">
            <button
              type="button"
              className="user-cabinet__logout"
              disabled={busy}
              onClick={() => void switchUser()}
            >
              Oddiy kabinet
            </button>
            <button
              type="button"
              className="user-cabinet__logout"
              disabled={busy}
              onClick={() => void logout()}
            >
              Chiqish
            </button>
          </div>
        </header>

        <div className="user-cabinet__stats">
          {metrics.map((metric, index) => (
            <button
              type="button"
              key={metric.key}
              className={`user-cabinet__stat${index === 0 ? " user-cabinet__stat--active" : ""}`}
              onClick={() => setView(metric.view)}
            >
              <span>{metric.label}</span>
              <strong>
                {metric.money
                  ? money(snapshot[metric.key] ?? 0)
                  : snapshot[metric.key] ?? 0}
              </strong>
              <small>{metric.sub}</small>
            </button>
          ))}
        </div>

        <div className="user-cabinet__content business-cabinet__content">
          <section className="user-cabinet__sections">
            <div className="user-cabinet__section-heading">
              <h2>Boshqaruv bo‘limlari</h2>
              <span>{profile.direction || "Faoliyat yo‘nalishi"}</span>
            </div>
            <div className="business-cabinet__group">
              <header><span>🌐</span><div><h3>Onlaynlashtirish</h3><p>Mijozlar ko‘radigan va onlayn savdo bo‘limlari</p></div></header>
              {menuGroup(ONLINE_MENUS)}
            </div>
            <div className="business-cabinet__group">
              <header><span>🗂</span><div><h3>Tizimlashtirish</h3><p>Hisob-kitob, ombor va ichki boshqaruv</p></div></header>
              {menuGroup(SYSTEM_MENUS)}
            </div>
            <div className="business-cabinet__group">
              <header><span>🏛️</span><div><h3>Ma’muriyat</h3><p>Xodimlar, hujjatlar va kontragentlar</p></div></header>
              {menuGroup(ADMIN_MENUS)}
            </div>
            {directionMenus.length > 0 && (
              <div className="business-cabinet__group">
                <header><span>🧩</span><div><h3>Yo‘nalishga xos bo‘limlar</h3><p>{profile.direction || "Faoliyat"} uchun ko‘chirilgan modullar</p></div></header>
                {menuGroup(directionMenus)}
              </div>
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
                      <b>{activity.amount ? money(activity.amount) : activity.status}</b>
                      <small>{TERMINAL.has(activity.status) ? "Yakunlangan" : "Jarayonda"}</small>
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
