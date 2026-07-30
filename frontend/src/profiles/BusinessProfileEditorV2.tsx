import { useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import type { BusinessProfile, BusinessProfilePatch } from "../api/types";
import {
  BUSINESS_DIRECTIONS,
  directionActivities,
  initials,
} from "./business-profile-config";
import "./BusinessProfileEditor.css";


type EditorApi = Pick<
  ApiClient,
  | "updateBusinessProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachBusinessLogo"
> & Partial<Pick<ApiClient, "attachBusinessPaymentQr">>;

type Props = {
  api: EditorApi;
  profile: BusinessProfile;
  onBack: () => void;
  onProfile: (profile: BusinessProfile) => void;
};

type Hours = { from: string; to: string };
type Point = { latitude: number; longitude: number };

type LeafletMap = {
  on: (event: string, callback: (event: { latlng: { lat: number; lng: number } }) => void) => void;
  remove: () => void;
  setView: (point: [number, number], zoom: number) => LeafletMap;
};

type LeafletMarker = { setLatLng: (point: [number, number]) => void };
type LeafletApi = {
  map: (element: HTMLElement) => LeafletMap;
  tileLayer: (url: string, options: Record<string, unknown>) => { addTo: (map: LeafletMap) => void };
  marker: (point: [number, number]) => { addTo: (map: LeafletMap) => LeafletMarker };
};

type QrCtor = new (
  element: HTMLElement,
  options: {
    text: string;
    width: number;
    height: number;
    colorDark: string;
    colorLight: string;
  },
) => unknown;

const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const PATCH_FIELDS = [
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
  "map_visible",
] as const;


function errorText(reason: unknown) {
  return reason instanceof Error ? reason.message : "So‘rov bajarilmadi.";
}

function finite(value: number | null | undefined, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function parseHours(value: Record<string, unknown>): Hours {
  const from = String(value.from ?? value.start ?? value.open ?? "").slice(0, 5);
  const to = String(value.to ?? value.end ?? value.close ?? "").slice(0, 5);
  if (/^\d{2}:\d{2}$/.test(from) && /^\d{2}:\d{2}$/.test(to)) {
    return { from, to };
  }
  const raw = String(value.raw ?? value.text ?? "");
  const match = raw.match(/(\d{2}:\d{2})\D+(\d{2}:\d{2})/);
  return { from: match?.[1] ?? "", to: match?.[2] ?? "" };
}

function workHours(existing: Record<string, unknown>, hours: Hours) {
  if (!hours.from && !hours.to) return {};
  return {
    ...existing,
    from: hours.from,
    to: hours.to,
    raw: `${hours.from}-${hours.to}`,
  };
}

function shopLink(profile: BusinessProfile) {
  const url = new URL(window.location.origin);
  url.searchParams.set("shop", profile.public_username || String(profile.account_id));
  return url.toString();
}

function mapUrl(point: Point) {
  const bbox = [
    point.longitude - 0.0075,
    point.latitude - 0.0045,
    point.longitude + 0.0075,
    point.latitude + 0.0045,
  ].join(",");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${point.latitude},${point.longitude}`)}`;
}

function QrCode({ value }: { value: string }) {
  const root = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = root.current;
    if (!node) return;
    node.replaceChildren();
    const QRCode = (window as unknown as { QRCode?: QrCtor }).QRCode;
    if (!QRCode) {
      node.textContent = "QR kod yuklanmadi";
      return;
    }
    new QRCode(node, {
      text: value,
      width: 148,
      height: 148,
      colorDark: "#081c17",
      colorLight: "#ffffff",
    });
  }, [value]);
  return <div ref={root} className="business-profile-share__qr" aria-label="Do‘kon QR kodi" />;
}

function MapPicker({ value, onClose, onSave }: {
  value: Point | null;
  onClose: () => void;
  onSave: (point: Point) => void;
}) {
  const root = useRef<HTMLDivElement | null>(null);
  const [point, setPoint] = useState<Point>(value ?? { latitude: 38.861, longitude: 65.789 });
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const node = root.current;
    const leaflet = (window as unknown as { L?: LeafletApi }).L;
    if (!node || !leaflet) {
      setFallback(true);
      return;
    }
    const map = leaflet.map(node).setView([point.latitude, point.longitude], value ? 15 : 6);
    leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap",
    }).addTo(map);
    const marker = leaflet.marker([point.latitude, point.longitude]).addTo(map);
    map.on("click", (event) => {
      const next = {
        latitude: Number(event.latlng.lat.toFixed(7)),
        longitude: Number(event.latlng.lng.toFixed(7)),
      };
      marker.setLatLng([next.latitude, next.longitude]);
      setPoint(next);
    });
    return () => map.remove();
  }, []);

  function locate() {
    navigator.geolocation?.getCurrentPosition((position) => {
      setPoint({
        latitude: Number(position.coords.latitude.toFixed(7)),
        longitude: Number(position.coords.longitude.toFixed(7)),
      });
    });
  }

  return (
    <div className="business-map-modal" role="dialog" aria-modal="true" aria-label="Xaritada joy belgilash">
      <div className="business-map-modal__card">
        <header>
          <div>
            <h2>Xaritada joy belgilash</h2>
            <p>Xaritada biznes joylashgan nuqtani bosing.</p>
          </div>
          <button type="button" aria-label="Xaritani yopish" onClick={onClose}>×</button>
        </header>
        <div ref={root} className="business-map-modal__map" />
        {fallback && (
          <div className="business-map-modal__fallback">
            <label>
              Kenglik
              <input
                type="number"
                step="any"
                value={point.latitude}
                onChange={(event) => {
                  const latitude = Number(event.currentTarget.value);
                  setPoint((current) => ({ ...current, latitude }));
                }}
              />
            </label>
            <label>
              Uzunlik
              <input
                type="number"
                step="any"
                value={point.longitude}
                onChange={(event) => {
                  const longitude = Number(event.currentTarget.value);
                  setPoint((current) => ({ ...current, longitude }));
                }}
              />
            </label>
          </div>
        )}
        <div className="business-map-modal__coordinates">
          <span>📍 {point.latitude.toFixed(6)}, {point.longitude.toFixed(6)}</span>
          <button type="button" onClick={locate}>Joriy joylashuvim</button>
        </div>
        <footer>
          <button type="button" className="button-secondary" onClick={onClose}>Bekor qilish</button>
          <button type="button" onClick={() => onSave(point)}>Joyni tasdiqlash</button>
        </footer>
      </div>
    </div>
  );
}


export function BusinessProfileEditorV2({ api, profile, onBack, onProfile }: Props) {
  const [draft, setDraft] = useState(profile);
  const [baseline, setBaseline] = useState(profile);
  const [hours, setHours] = useState(() => parseHours(profile.work_hours));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [crop, setCrop] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [lightbox, setLightbox] = useState(false);
  const [copyText, setCopyText] = useState("Nusxa");
  const logoInput = useRef<HTMLInputElement | null>(null);
  const paymentInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setDraft(profile);
    setBaseline(profile);
    setHours(parseHours(profile.work_hours));
  }, [profile]);

  const activities = useMemo(
    () => directionActivities(draft.direction, draft.activity_type),
    [draft.direction, draft.activity_type],
  );
  const link = useMemo(() => shopLink(draft), [draft.account_id, draft.public_username]);
  const point = draft.latitude !== null && draft.longitude !== null
    ? { latitude: draft.latitude, longitude: draft.longitude }
    : null;
  const logoStyle = {
    objectPosition: `${finite(draft.logo_x, 50)}% ${finite(draft.logo_y, 50)}%`,
    transform: `scale(${Math.min(5, Math.max(1, finite(draft.logo_zoom, 1)))})`,
  };

  function field<K extends keyof BusinessProfile>(name: K, value: BusinessProfile[K]) {
    setSaved(false);
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function apply(value: BusinessProfile) {
    setDraft(value);
    setBaseline(value);
    setHours(parseHours(value.work_hours));
    onProfile(value);
  }

  function validImage(file: File) {
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Faqat JPEG, PNG, WEBP yoki GIF rasm yuklang.");
      return false;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Rasm hajmi 8 MB dan oshmasin.");
      return false;
    }
    return true;
  }

  async function uploadLogo(file: File) {
    if (!validImage(file)) return;
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
      apply(await api.attachBusinessLogo({
        object_key: grant.object_key,
        x: draft.logo_x,
        y: draft.logo_y,
        zoom: draft.logo_zoom,
      }));
      setCrop(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function uploadPaymentQr(file: File) {
    if (!api.attachBusinessPaymentQr) {
      setError("To‘lov QR yuklash backendda yoqilmagan.");
      return;
    }
    if (!validImage(file)) return;
    setBusy(true);
    setError("");
    try {
      const grant = await api.createUploadGrant({
        purpose: "payment_qr",
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });
      await api.uploadGrantedFile(grant, file);
      apply(await api.attachBusinessPaymentQr({ object_key: grant.object_key }));
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveCrop() {
    if (!draft.logo_object_key) return;
    setBusy(true);
    setError("");
    try {
      apply(await api.attachBusinessLogo({
        object_key: draft.logo_object_key,
        x: draft.logo_x,
        y: draft.logo_y,
        zoom: draft.logo_zoom,
      }));
      setCrop(false);
      setSaved(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if ((hours.from && !hours.to) || (!hours.from && hours.to)) {
      setError("Ish vaqtining boshlanish va tugash vaqtini birga belgilang.");
      return;
    }
    if (!draft.name.trim() || !draft.direction || !draft.activity_type) {
      setError("Biznes nomi, yo‘nalish va faoliyat turini to‘ldiring.");
      return;
    }

    const patch: BusinessProfilePatch = {};
    for (const name of PATCH_FIELDS) {
      if (draft[name] !== baseline[name]) {
        (patch as Record<string, unknown>)[name] = draft[name];
      }
    }
    const nextHours = workHours(baseline.work_hours, hours);
    if (JSON.stringify(nextHours) !== JSON.stringify(baseline.work_hours)) {
      patch.work_hours = nextHours;
    }

    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const value = Object.keys(patch).length
        ? await api.updateBusinessProfile(patch)
        : draft;
      apply(value);
      setSaved(true);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      setCopyText("Nusxalandi");
      window.setTimeout(() => setCopyText("Nusxa"), 1200);
    } catch {
      setError("Havolani nusxalab bo‘lmadi.");
    }
  }

  return (
    <main className="business-profile-editor">
      <header className="business-profile-editor__heading">
        <div>
          <p>Profil</p>
          <h1>Profil / Mening sahifam</h1>
        </div>
        <button type="button" className="button-secondary" onClick={onBack}>Kabinetga qaytish</button>
      </header>

      <section className="business-profile-card">
        <button
          type="button"
          className="business-profile-card__logo"
          aria-label="Biznes rasmini kattalashtirish"
          onClick={() => draft.logo_url && setLightbox(true)}
        >
          {draft.logo_url
            ? <img src={draft.logo_url} alt="" style={logoStyle} />
            : <span>{initials(draft.name)}</span>}
        </button>
        <div className="business-profile-card__main">
          <h2>{draft.name || "Biznes nomi"}</h2>
          <p>{draft.direction || "Yo‘nalish tanlanmagan"}{draft.activity_type ? ` · ${draft.activity_type}` : ""}</p>
          <div>
            <span>{draft.followers_count ?? 0} obunachi</span>
            <span>{draft.following_count ?? 0} obuna</span>
          </div>
        </div>
        <button
          type="button"
          className="business-profile-card__camera"
          aria-label="Biznes rasmini yuklash"
          disabled={busy}
          onClick={() => logoInput.current?.click()}
        >📷</button>
        <input
          ref={logoInput}
          type="file"
          hidden
          aria-label="Logotip"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) void uploadLogo(file);
          }}
        />
      </section>

      {draft.logo_object_key && (
        <button type="button" className="business-profile-editor__adjust" onClick={() => setCrop((value) => !value)}>
          🖼 Rasm joylashuvini sozlash
        </button>
      )}
      {crop && draft.logo_url && (
        <section className="business-logo-crop">
          <div className="business-logo-crop__stage">
            <img src={draft.logo_url} alt="Biznes rasmi" style={logoStyle} />
          </div>
          <label>Gorizontal joylashuv
            <input type="range" min="0" max="100" value={draft.logo_x} onChange={(event) => field("logo_x", Number(event.currentTarget.value))} />
          </label>
          <label>Vertikal joylashuv
            <input type="range" min="0" max="100" value={draft.logo_y} onChange={(event) => field("logo_y", Number(event.currentTarget.value))} />
          </label>
          <label>Kattalashtirish
            <input type="range" min="1" max="3" step="0.05" value={draft.logo_zoom} onChange={(event) => field("logo_zoom", Number(event.currentTarget.value))} />
          </label>
          <p>Slayderlar orqali ko‘rinadigan qismini belgilang.</p>
          <div>
            <button type="button" className="button-secondary" onClick={() => setDraft((current) => ({ ...current, logo_x: 50, logo_y: 50, logo_zoom: 1 }))}>Markazga</button>
            <button type="button" disabled={busy} onClick={() => void saveCrop()}>Joylashuvni saqlash</button>
          </div>
        </section>
      )}

      <form className="business-profile-form" onSubmit={save}>
        <label>Biznes nomi
          <input required value={draft.name} onChange={(event) => field("name", event.currentTarget.value)} />
        </label>
        <label>Telefon raqami
          <input type="tel" value={draft.phone} onChange={(event) => field("phone", event.currentTarget.value)} />
        </label>
        <label>Qisqa tavsif
          <textarea placeholder="Biznesingiz haqida qisqacha" value={draft.description} onChange={(event) => field("description", event.currentTarget.value)} />
        </label>
        <label>Username (do‘kon manzili)
          <span className="business-profile-form__username">
            <b>@</b>
            <input value={draft.public_username} onChange={(event) => field("public_username", event.currentTarget.value)} />
          </span>
          <small>Kichik lotin harflari, raqam va _ (3–32 belgi). Ixtiyoriy.</small>
        </label>

        <section className="business-profile-share">
          <strong>🔗 <span>Do‘kon havolasi</span></strong>
          <p>Shu havola yoki QR orqali mijozlar to‘g‘ridan-to‘g‘ri do‘koningizga o‘tadi.</p>
          <div className="business-profile-share__row">
            <input readOnly value={link} aria-label="Do‘kon havolasi manzili" />
            <button type="button" onClick={() => void copyLink()}>{copyText}</button>
          </div>
          <QrCode value={link} />
        </section>

        <label>Faoliyat yo‘nalishi
          <select
            value={draft.direction}
            onChange={(event) => {
              const direction = event.currentTarget.value;
              const activity_type = directionActivities(direction)[0] ?? "";
              setSaved(false);
              setDraft((current) => ({ ...current, direction, activity_type }));
            }}
          >
            <option value="">Yo‘nalishni tanlang</option>
            {BUSINESS_DIRECTIONS.map((item) => (
              <option value={item.name} key={item.name}>{item.icon} {item.name}</option>
            ))}
          </select>
        </label>
        <label>Faoliyat turi
          <select value={draft.activity_type} disabled={!draft.direction} onChange={(event) => field("activity_type", event.currentTarget.value)}>
            {!activities.length && <option value="">Avval yo‘nalishni tanlang</option>}
            {activities.map((activity) => <option key={activity} value={activity}>{activity}</option>)}
          </select>
        </label>

        <section className="business-profile-map">
          <div><strong>Xaritadagi joy</strong><p>Biznesingiz qidiruv va xaritada shu joyda ko‘rinadi.</p></div>
          <button type="button" onClick={() => setMapOpen(true)}>📍 Xaritada joy belgilash</button>
          {point ? (
            <>
              <span className="business-profile-map__status">● Joy belgilangan</span>
              <iframe title="Belgilangan joy xaritasi" src={mapUrl(point)} loading="lazy" />
            </>
          ) : <p className="business-profile-map__warning">⚠️ Qidiruv va xaritada ko‘rinish uchun joylashuvni belgilang.</p>}
        </section>

        <label>Manzil
          <textarea placeholder="Tuman, mahalla, ko‘cha" value={draft.address} onChange={(event) => field("address", event.currentTarget.value)} />
        </label>

        <section className="business-payment-section">
          <header><strong>💳 <span>To‘lov ma’lumotlari</span></strong><p>Onlayn buyurtmada mijoz shu ma’lumotlar orqali to‘laydi. Ixtiyoriy.</p></header>
          <label>To‘lov kartasi raqami
            <input inputMode="numeric" value={draft.pay_card} onChange={(event) => field("pay_card", event.currentTarget.value)} />
          </label>
          <label>Karta egasi (ism-familiya)
            <input value={draft.pay_holder} onChange={(event) => field("pay_holder", event.currentTarget.value)} />
          </label>
          <div className="business-payment-section__qr">
            <strong>To‘lov QR kodi (rasm)</strong>
            <input
              ref={paymentInput}
              type="file"
              hidden
              accept="image/jpeg,image/png,image/webp,image/gif"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = "";
                if (file) void uploadPaymentQr(file);
              }}
            />
            <button type="button" className="button-secondary" disabled={busy} onClick={() => paymentInput.current?.click()}>📷 QR rasm yuklash</button>
            {draft.pay_qr_url && (
              <div className="business-payment-section__preview">
                <img src={draft.pay_qr_url} alt="To‘lov QR kodi" />
                <button
                  type="button"
                  aria-label="To‘lov QR kodini o‘chirish"
                  onClick={() => api.attachBusinessPaymentQr && void api.attachBusinessPaymentQr({ object_key: "" }).then(apply).catch((reason) => setError(errorText(reason)))}
                >×</button>
              </div>
            )}
          </div>
        </section>

        <label>Ish vaqti
          <span className="business-hours-row">
            <input
              type="time"
              aria-label="Ish boshlanish vaqti"
              value={hours.from}
              onChange={(event) => {
                const from = event.currentTarget.value;
                setSaved(false);
                setHours((current) => ({ ...current, from }));
              }}
            />
            <span>dan</span>
            <input
              type="time"
              aria-label="Ish tugash vaqti"
              value={hours.to}
              onChange={(event) => {
                const to = event.currentTarget.value;
                setSaved(false);
                setHours((current) => ({ ...current, to }));
              }}
            />
          </span>
          <small>Ish boshlanish va tugash vaqtini belgilang.</small>
        </label>

        {error && <p className="form-error" role="alert">{error}</p>}
        {saved && <p className="form-success" role="status">Saqlandi</p>}
        <button type="submit" className="business-profile-form__save" disabled={busy}>{busy ? "Saqlanmoqda…" : "Saqlash"}</button>
      </form>

      {mapOpen && (
        <MapPicker
          value={point}
          onClose={() => setMapOpen(false)}
          onSave={(next) => {
            setDraft((current) => ({ ...current, ...next, map_visible: true }));
            setSaved(false);
            setMapOpen(false);
          }}
        />
      )}
      {lightbox && draft.logo_url && (
        <button type="button" className="business-logo-lightbox" aria-label="Kattalashtirilgan biznes rasmini yopish" onClick={() => setLightbox(false)}>
          <img src={draft.logo_url} alt={draft.name} />
        </button>
      )}
    </main>
  );
}
