import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { ApiClient } from "../api/client";
import type {
  BusinessProfile,
  BusinessProfilePatch,
} from "../api/types";
import {
  BUSINESS_DIRECTIONS,
  directionActivities,
  initials,
} from "./business-profile-config";
import "./BusinessProfileEditor.css";


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
  "map_visible",
] as const;

type PaymentQrAttachment = { object_key: string };

export type BusinessProfileEditorApi = Pick<
  ApiClient,
  | "updateBusinessProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachBusinessLogo"
> & {
  attachBusinessPaymentQr?: (
    body: PaymentQrAttachment,
  ) => Promise<BusinessProfile>;
};

type Props = {
  api: BusinessProfileEditorApi;
  profile: BusinessProfile;
  onBack: () => void;
  onProfile: (profile: BusinessProfile) => void;
};

type WorkHours = {
  from: string;
  to: string;
};

type MapPoint = {
  latitude: number;
  longitude: number;
};

type LeafletMarker = {
  setLatLng: (value: [number, number]) => void;
};

type LeafletMap = {
  on: (event: string, callback: (event: {
    latlng: { lat: number; lng: number };
  }) => void) => void;
  remove: () => void;
  setView: (point: [number, number], zoom: number) => LeafletMap;
};

type LeafletApi = {
  map: (element: HTMLElement) => LeafletMap;
  tileLayer: (url: string, options: Record<string, unknown>) => {
    addTo: (map: LeafletMap) => void;
  };
  marker: (point: [number, number]) => {
    addTo: (map: LeafletMap) => LeafletMarker;
  };
};

type QrConstructor = new (
  element: HTMLElement,
  options: {
    text: string;
    width: number;
    height: number;
    colorDark: string;
    colorLight: string;
    correctLevel?: number;
  },
) => unknown;


function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function finite(value: number | null, fallback: number) {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : fallback;
}

function parseHours(value: Record<string, unknown>): WorkHours {
  const directFrom = String(
    value.from ?? value.start ?? value.open ?? value.opens_at ?? "",
  ).slice(0, 5);
  const directTo = String(
    value.to ?? value.end ?? value.close ?? value.closes_at ?? "",
  ).slice(0, 5);
  if (/^\d{2}:\d{2}$/.test(directFrom) && /^\d{2}:\d{2}$/.test(directTo)) {
    return { from: directFrom, to: directTo };
  }
  const raw = String(value.raw ?? value.text ?? "");
  const matches = raw.match(/(\d{2}:\d{2})\D+(\d{2}:\d{2})/);
  return {
    from: matches?.[1] ?? "",
    to: matches?.[2] ?? "",
  };
}

function serializeHours(
  existing: Record<string, unknown>,
  hours: WorkHours,
): Record<string, unknown> {
  if (!hours.from && !hours.to) return {};
  return {
    ...existing,
    from: hours.from,
    to: hours.to,
    raw: `${hours.from}-${hours.to}`,
  };
}

function shareLink(profile: BusinessProfile) {
  const key = profile.public_username || String(profile.account_id);
  const url = new URL(window.location.origin);
  url.searchParams.set("shop", key);
  return url.toString();
}

function mapEmbedUrl(latitude: number, longitude: number) {
  const deltaLat = 0.0045;
  const deltaLng = 0.0075;
  const bbox = [
    longitude - deltaLng,
    latitude - deltaLat,
    longitude + deltaLng,
    latitude + deltaLat,
  ].join(",");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${latitude},${longitude}`)}`;
}

function QrCode({ value }: { value: string }) {
  const root = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    element.replaceChildren();
    const constructor = (window as unknown as { QRCode?: QrConstructor }).QRCode;
    if (!constructor) {
      element.textContent = "QR kod yuklanmadi";
      return;
    }
    new constructor(element, {
      text: value,
      width: 148,
      height: 148,
      colorDark: "#081c17",
      colorLight: "#ffffff",
    });
  }, [value]);

  return <div className="business-profile-share__qr" ref={root} aria-label="Do‘kon QR kodi" />;
}

function MapPicker({
  value,
  onCancel,
  onConfirm,
}: {
  value: MapPoint | null;
  onCancel: () => void;
  onConfirm: (value: MapPoint) => void;
}) {
  const mapRoot = useRef<HTMLDivElement | null>(null);
  const [point, setPoint] = useState<MapPoint>(value ?? {
    latitude: 38.861,
    longitude: 65.789,
  });
  const [mapAvailable, setMapAvailable] = useState(true);

  useEffect(() => {
    const root = mapRoot.current;
    const leaflet = (window as unknown as { L?: LeafletApi }).L;
    if (!root || !leaflet) {
      setMapAvailable(false);
      return;
    }
    const map = leaflet.map(root).setView(
      [point.latitude, point.longitude],
      value ? 15 : 6,
    );
    leaflet.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 19, attribution: "© OpenStreetMap" },
    ).addTo(map);
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
          <button type="button" onClick={onCancel} aria-label="Xaritani yopish">×</button>
        </header>
        <div className="business-map-modal__map" ref={mapRoot} />
        {!mapAvailable && (
          <div className="business-map-modal__fallback">
            <label>
              Kenglik
              <input
                type="number"
                step="any"
                value={point.latitude}
                onChange={(event) => setPoint((current) => ({
                  ...current,
                  latitude: Number(event.currentTarget.value),
                }))}
              />
            </label>
            <label>
              Uzunlik
              <input
                type="number"
                step="any"
                value={point.longitude}
                onChange={(event) => setPoint((current) => ({
                  ...current,
                  longitude: Number(event.currentTarget.value),
                }))}
              />
            </label>
          </div>
        )}
        <div className="business-map-modal__coordinates">
          <span>📍 {point.latitude.toFixed(6)}, {point.longitude.toFixed(6)}</span>
          <button type="button" onClick={locate}>Joriy joylashuvim</button>
        </div>
        <footer>
          <button type="button" className="button-secondary" onClick={onCancel}>Bekor qilish</button>
          <button type="button" onClick={() => onConfirm(point)}>Joyni tasdiqlash</button>
        </footer>
      </div>
    </div>
  );
}


export function BusinessProfileEditor({
  api,
  profile,
  onBack,
  onProfile,
}: Props) {
  const [draft, setDraft] = useState(profile);
  const [baseline, setBaseline] = useState(profile);
  const [hours, setHours] = useState(() => parseHours(profile.work_hours ?? {}));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [copyState, setCopyState] = useState("Nusxa");
  const [cropOpen, setCropOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const logoInput = useRef<HTMLInputElement | null>(null);
  const qrInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setDraft(profile);
    setBaseline(profile);
    setHours(parseHours(profile.work_hours ?? {}));
  }, [profile]);

  const activities = useMemo(
    () => directionActivities(draft.direction, draft.activity_type),
    [draft.direction, draft.activity_type],
  );
  const storeLink = useMemo(() => shareLink(draft), [
    draft.account_id,
    draft.public_username,
  ]);
  const mapPoint = (
    draft.latitude !== null && draft.longitude !== null
      ? {
        latitude: draft.latitude,
        longitude: draft.longitude,
      }
      : null
  );

  function setField<K extends keyof BusinessProfile>(
    field: K,
    value: BusinessProfile[K],
  ) {
    setSaved(false);
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function apply(value: BusinessProfile) {
    setDraft(value);
    setBaseline(value);
    setHours(parseHours(value.work_hours ?? {}));
    onProfile(value);
  }

  async function copyStoreLink() {
    try {
      await navigator.clipboard.writeText(storeLink);
      setCopyState("Nusxalandi");
      window.setTimeout(() => setCopyState("Nusxa"), 1500);
    } catch {
      setError("Havolani nusxalab bo‘lmadi.");
    }
  }

  function validateImage(file: File) {
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
    if (!validateImage(file)) return;
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
      const value = await api.attachBusinessLogo({
        object_key: grant.object_key,
        x: draft.logo_x,
        y: draft.logo_y,
        zoom: draft.logo_zoom,
      });
      apply(value);
      setCropOpen(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveCrop() {
    if (!draft.logo_object_key) return;
    setBusy(true);
    setError("");
    try {
      const value = await api.attachBusinessLogo({
        object_key: draft.logo_object_key,
        x: draft.logo_x,
        y: draft.logo_y,
        zoom: draft.logo_zoom,
      });
      apply(value);
      setCropOpen(false);
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function uploadPaymentQr(file: File) {
    if (!api.attachBusinessPaymentQr) {
      setError("To‘lov QR yuklash backendda yoqilmagan.");
      return;
    }
    if (!validateImage(file)) return;
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
      apply(await api.attachBusinessPaymentQr({
        object_key: grant.object_key,
      }));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removePaymentQr() {
    if (!api.attachBusinessPaymentQr) return;
    setBusy(true);
    setError("");
    try {
      apply(await api.attachBusinessPaymentQr({ object_key: "" }));
    } catch (reason) {
      setError(message(reason));
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
    if (!draft.name.trim()) {
      setError("Biznes nomini kiriting.");
      return;
    }
    if (!draft.direction) {
      setError("Faoliyat yo‘nalishini tanlang.");
      return;
    }
    if (!draft.activity_type) {
      setError("Faoliyat turini tanlang.");
      return;
    }

    const patch: BusinessProfilePatch = {};
    for (const field of EDITABLE_FIELDS) {
      if (draft[field] !== baseline[field]) {
        (patch as Record<string, unknown>)[field] = draft[field];
      }
    }
    const nextHours = serializeHours(baseline.work_hours ?? {}, hours);
    if (JSON.stringify(nextHours) !== JSON.stringify(baseline.work_hours ?? {})) {
      patch.work_hours = nextHours;
    }

    setBusy(true);
    setError("");
    setSaved(false);
    try {
      let value = Object.keys(patch).length
        ? await api.updateBusinessProfile(patch)
        : draft;
      const cropChanged = (
        draft.logo_x !== baseline.logo_x
        || draft.logo_y !== baseline.logo_y
        || draft.logo_zoom !== baseline.logo_zoom
      );
      if (cropChanged && draft.logo_object_key) {
        value = await api.attachBusinessLogo({
          object_key: draft.logo_object_key,
          x: draft.logo_x,
          y: draft.logo_y,
          zoom: draft.logo_zoom,
        });
      }
      apply(value);
      setSaved(true);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  const logoStyle = {
    objectPosition: `${finite(draft.logo_x, 50)}% ${finite(draft.logo_y, 50)}%`,
    transform: `scale(${clamp(finite(draft.logo_zoom, 1), 1, 5)})`,
  };

  return (
    <main className="business-profile-editor">
      <header className="business-profile-editor__heading">
        <div>
          <p>Profil</p>
          <h1>Profil / Mening sahifam</h1>
        </div>
        <button type="button" className="button-secondary" onClick={onBack}>
          Kabinetga qaytish
        </button>
      </header>

      <section className="business-profile-card">
        <button
          type="button"
          className="business-profile-card__logo"
          onClick={() => draft.logo_url && setLightboxOpen(true)}
          aria-label="Biznes rasmini kattalashtirish"
        >
          {draft.logo_url ? (
            <img src={draft.logo_url} alt="" style={logoStyle} />
          ) : (
            <span>{initials(draft.name)}</span>
          )}
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
          disabled={busy}
          onClick={() => logoInput.current?.click()}
          aria-label="Biznes rasmini yuklash"
          title="Biznes rasmini yuklash"
        >
          📷
        </button>
        <input
          ref={logoInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            if (file) void uploadLogo(file);
            event.currentTarget.value = "";
          }}
        />
      </section>

      {draft.logo_object_key && (
        <button
          type="button"
          className="business-profile-editor__adjust"
          onClick={() => setCropOpen((value) => !value)}
        >
          🖼 Rasm joylashuvini sozlash
        </button>
      )}

      {cropOpen && draft.logo_url && (
        <section className="business-logo-crop">
          <div className="business-logo-crop__stage">
            <img src={draft.logo_url} alt="Biznes rasmi" style={logoStyle} />
          </div>
          <label>
            Gorizontal joylashuv
            <input
              type="range"
              min="0"
              max="100"
              value={draft.logo_x}
              onChange={(event) => setField("logo_x", Number(event.currentTarget.value))}
            />
          </label>
          <label>
            Vertikal joylashuv
            <input
              type="range"
              min="0"
              max="100"
              value={draft.logo_y}
              onChange={(event) => setField("logo_y", Number(event.currentTarget.value))}
            />
          </label>
          <label>
            Kattalashtirish
            <input
              type="range"
              min="1"
              max="3"
              step="0.05"
              value={draft.logo_zoom}
              onChange={(event) => setField("logo_zoom", Number(event.currentTarget.value))}
            />
          </label>
          <p>Slayderlar orqali ko‘rinadigan qismini belgilang.</p>
          <div>
            <button
              type="button"
              className="button-secondary"
              onClick={() => {
                setField("logo_x", 50);
                setField("logo_y", 50);
                setField("logo_zoom", 1);
              }}
            >
              Markazga
            </button>
            <button type="button" disabled={busy} onClick={() => void saveCrop()}>
              Joylashuvni saqlash
            </button>
          </div>
        </section>
      )}

      <form className="business-profile-form" onSubmit={save}>
        <label>
          Biznes nomi
          <input
            required
            value={draft.name}
            onChange={(event) => setField("name", event.currentTarget.value)}
          />
        </label>
        <label>
          Telefon raqami
          <input
            type="tel"
            inputMode="tel"
            value={draft.phone}
            onChange={(event) => setField("phone", event.currentTarget.value)}
          />
        </label>
        <label>
          Qisqa tavsif
          <textarea
            placeholder="Biznesingiz haqida qisqacha"
            value={draft.description}
            onChange={(event) => setField("description", event.currentTarget.value)}
          />
        </label>
        <label>
          Username (do‘kon manzili)
          <span className="business-profile-form__username">
            <b>@</b>
            <input
              value={draft.public_username}
              onChange={(event) => setField("public_username", event.currentTarget.value)}
            />
          </span>
          <small>Kichik lotin harflari, raqam va _ (3–32 belgi). Ixtiyoriy.</small>
        </label>

        <section className="business-profile-share">
          <strong>🔗 <span>Do‘kon havolasi</span></strong>
          <p>Shu havola yoki QR orqali mijozlar to‘g‘ridan-to‘g‘ri do‘koningizga o‘tadi.</p>
          <div className="business-profile-share__row">
            <input readOnly value={storeLink} aria-label="Do‘kon havolasi manzili" />
            <button type="button" onClick={() => void copyStoreLink()}>{copyState}</button>
          </div>
          <QrCode value={storeLink} />
        </section>

        <label>
          Faoliyat yo‘nalishi
          <select
            value={draft.direction}
            onChange={(event) => {
              const direction = event.currentTarget.value;
              const first = directionActivities(direction)[0] ?? "";
              setSaved(false);
              setDraft((current) => ({
                ...current,
                direction,
                activity_type: first,
              }));
            }}
          >
            <option value="">Yo‘nalishni tanlang</option>
            {BUSINESS_DIRECTIONS.map((item) => (
              <option key={item.name} value={item.name}>
                {item.icon} {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Faoliyat turi
          <select
            value={draft.activity_type}
            disabled={!draft.direction}
            onChange={(event) => setField("activity_type", event.currentTarget.value)}
          >
            {!activities.length && <option value="">Avval yo‘nalishni tanlang</option>}
            {activities.map((activity) => (
              <option key={activity} value={activity}>{activity}</option>
            ))}
          </select>
        </label>

        <section className="business-profile-map">
          <div>
            <strong>Xaritadagi joy</strong>
            <p>Biznesingiz qidiruv va xaritada shu joyda ko‘rinadi.</p>
          </div>
          <button type="button" onClick={() => setMapOpen(true)}>
            📍 Xaritada joy belgilash
          </button>
          {mapPoint ? (
            <>
              <span className="business-profile-map__status">● Joy belgilangan</span>
              <iframe
                title="Belgilangan joy xaritasi"
                src={mapEmbedUrl(mapPoint.latitude, mapPoint.longitude)}
                loading="lazy"
              />
            </>
          ) : (
            <p className="business-profile-map__warning">
              ⚠️ Qidiruv va xaritada ko‘rinish uchun joylashuvni belgilang.
            </p>
          )}
        </section>

        <label>
          Manzil
          <textarea
            placeholder="Tuman, mahalla, ko‘cha"
            value={draft.address}
            onChange={(event) => setField("address", event.currentTarget.value)}
          />
        </label>

        <section className="business-payment-section">
          <header>
            <strong>💳 <span>To‘lov ma’lumotlari</span></strong>
            <p>Onlayn buyurtmada mijoz shu ma’lumotlar orqali to‘laydi. Ixtiyoriy.</p>
          </header>
          <label>
            To‘lov kartasi raqami
            <input
              inputMode="numeric"
              placeholder="8600 XXXX XXXX XXXX"
              value={draft.pay_card}
              onChange={(event) => setField("pay_card", event.currentTarget.value)}
            />
          </label>
          <label>
            Karta egasi (ism-familiya)
            <input
              placeholder="Masalan: Anvar Karimov"
              value={draft.pay_holder}
              onChange={(event) => setField("pay_holder", event.currentTarget.value)}
            />
          </label>
          <div className="business-payment-section__qr">
            <strong>To‘lov QR kodi (rasm)</strong>
            <input
              ref={qrInput}
              type="file"
              hidden
              accept="image/jpeg,image/png,image/webp,image/gif"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) void uploadPaymentQr(file);
                event.currentTarget.value = "";
              }}
            />
            <button
              type="button"
              className="button-secondary"
              disabled={busy}
              onClick={() => qrInput.current?.click()}
            >
              📷 QR rasm yuklash
            </button>
            {draft.pay_qr_url && (
              <div className="business-payment-section__preview">
                <img src={draft.pay_qr_url} alt="To‘lov QR kodi" />
                <button
                  type="button"
                  aria-label="To‘lov QR kodini o‘chirish"
                  onClick={() => void removePaymentQr()}
                >
                  ×
                </button>
              </div>
            )}
          </div>
        </section>

        <label>
          Ish vaqti
          <span className="business-hours-row">
            <input
              type="time"
              aria-label="Ish boshlanish vaqti"
              value={hours.from}
              onChange={(event) => {
                setSaved(false);
                setHours((current) => ({
                  ...current,
                  from: event.currentTarget.value,
                }));
              }}
            />
            <span>dan</span>
            <input
              type="time"
              aria-label="Ish tugash vaqti"
              value={hours.to}
              onChange={(event) => {
                setSaved(false);
                setHours((current) => ({
                  ...current,
                  to: event.currentTarget.value,
                }));
              }}
            />
          </span>
          <small>Ish boshlanish va tugash vaqtini belgilang.</small>
        </label>

        {error && <p className="form-error" role="alert">{error}</p>}
        {saved && <p className="form-success" role="status">Saqlandi</p>}
        <button type="submit" className="business-profile-form__save" disabled={busy}>
          {busy ? "Saqlanmoqda…" : "Saqlash"}
        </button>
      </form>

      {mapOpen && (
        <MapPicker
          value={mapPoint}
          onCancel={() => setMapOpen(false)}
          onConfirm={(value) => {
            setSaved(false);
            setDraft((current) => ({
              ...current,
              latitude: value.latitude,
              longitude: value.longitude,
              map_visible: true,
            }));
            setMapOpen(false);
          }}
        />
      )}

      {lightboxOpen && draft.logo_url && (
        <button
          type="button"
          className="business-logo-lightbox"
          onClick={() => setLightboxOpen(false)}
          aria-label="Kattalashtirilgan biznes rasmini yopish"
        >
          <img src={draft.logo_url} alt={draft.name} />
        </button>
      )}
    </main>
  );
}
