import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

import type { ApiClient } from "../api/client";
import type {
  SpecialistOffer,
  SpecialistOfferWrite,
  SpecialistProfile,
} from "../api/types";
import "./Specialist.css";

export type SpecialistApi = Pick<
  ApiClient,
  | "getMySpecialist"
  | "updateMySpecialist"
  | "addSpecialistCredential"
  | "deleteSpecialistCredential"
  | "createSpecialistOffer"
  | "updateSpecialistOffer"
  | "deleteSpecialistOffer"
  | "addSpecialistPortfolio"
  | "deleteSpecialistPortfolio"
  | "createUploadGrant"
  | "uploadGrantedFile"
>;

type Props = {
  api: SpecialistApi;
  onBack(): void;
  onReviews?(): void;
};

const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/quicktime"]);
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const MAX_PORTFOLIO_BYTES = 30 * 1024 * 1024;
const EMPTY_OFFER: SpecialistOfferWrite = {
  kind: "service",
  name: "",
  price_text: "",
  note: "",
  image_object_key: "",
  clear_image: false,
};

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "So‘rov bajarilmadi.";
}

function SpecialistMap({
  latitude,
  longitude,
  onChange,
  onError,
}: {
  latitude: number | null;
  longitude: number | null;
  onChange(latitude: number, longitude: number): void;
  onError(message: string): void;
}) {
  const node = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!node.current) return;
    let disposed = false;
    let map: LeafletMap | null = null;
    const startLat = latitude ?? 41.311;
    const startLng = longitude ?? 69.28;
    void import("leaflet")
      .then(({ default: leaflet }) => {
        if (disposed || !node.current) return;
        map = leaflet
          .map(node.current, {
            zoomControl: true,
            attributionControl: false,
          })
          .setView([startLat, startLng], latitude === null ? 11 : 15);
        leaflet
          .tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
          })
          .addTo(map);
        map.on("moveend", () => {
          const center = map?.getCenter();
          if (center) onChangeRef.current(center.lat, center.lng);
        });
        mapRef.current = map;
        window.setTimeout(() => map?.invalidateSize(), 80);
      })
      .catch(() => onError("Xarita yuklanmadi. Qayta urinib ko‘ring."));
    return () => {
      disposed = true;
      mapRef.current = null;
      map?.remove();
    };
  }, []);

  function locate() {
    if (!navigator.geolocation) {
      onError("Qurilmada joylashuvni aniqlash mavjud emas.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        mapRef.current?.setView([coords.latitude, coords.longitude], 16);
        onChange(coords.latitude, coords.longitude);
      },
      () => onError("Joylashuv aniqlanmadi. Brauzer ruxsatini tekshiring."),
      { enableHighAccuracy: true, timeout: 12000 },
    );
  }

  return (
    <>
      <div className="specialist-map-v1656">
        <div ref={node} className="specialist-map-v1656__canvas" />
        <div className="specialist-map-v1656__pin">📍</div>
        <div className="specialist-map-v1656__help">
          <span>Xaritani suring — metka markazda turadi</span>
        </div>
      </div>
      <div className="specialist-v1656__muted specialist-v1656__map-info">
        {latitude === null || longitude === null
          ? "Joy hali belgilanmagan"
          : `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`}
      </div>
      {latitude === null || longitude === null ? (
        <div className="specialist-v1656__warning">
          ⚠️ Qidiruv va xaritada ko‘rinish uchun joylashuvingizni xaritada belgilang.
        </div>
      ) : null}
      <button className="specialist-v1656__soft" type="button" onClick={locate}>
        📍 Hozirgi joylashuvimni aniqlash
      </button>
    </>
  );
}

export function SpecialistV1656({ api, onBack, onReviews }: Props) {
  const [profile, setProfile] = useState<SpecialistProfile | null>(null);
  const [offer, setOffer] = useState<SpecialistOfferWrite>(EMPTY_OFFER);
  const [offerId, setOfferId] = useState<number | null>(null);
  const [offerImageUrl, setOfferImageUrl] = useState("");
  const [offerForm, setOfferForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function load() {
    setProfile(await api.getMySpecialist());
  }

  useEffect(() => {
    let active = true;
    api
      .getMySpecialist()
      .then((value) => {
        if (active) setProfile(value);
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [api]);

  function editOffer(value?: SpecialistOffer) {
    setOfferId(value?.id ?? null);
    setOffer({
      kind: value?.kind ?? "service",
      name: value?.name ?? "",
      price_text: value?.price_text ?? "",
      note: value?.note ?? "",
      image_object_key: value?.image_object_key ?? "",
      clear_image: false,
    });
    setOfferImageUrl(value?.image_url ?? "");
    setError("");
    setSaved(false);
    setOfferForm(true);
  }

  async function uploadFile(
    file: File,
    purpose: Parameters<ApiClient["createUploadGrant"]>[0]["purpose"],
  ) {
    const grant = await api.createUploadGrant({
      purpose,
      filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
    });
    await api.uploadGrantedFile(grant, file);
    return grant.object_key;
  }

  async function addCredentials(files: FileList | null) {
    if (!files?.length || !profile) return;
    if (profile.credentials.length + files.length > 12) {
      setError("Tasdiqlovchi hujjatlar 12 tadan oshmasin.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        if (!IMAGE_TYPES.has(file.type))
          throw new Error("Faqat JPG, PNG yoki WEBP rasm yuboring.");
        if (file.size < 1 || file.size > MAX_IMAGE_BYTES)
          throw new Error("Fayl hajmi 8 MB dan oshmasin.");
        const key = await uploadFile(file, "specialist_credential");
        await api.addSpecialistCredential(key);
      }
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function addPortfolio(files: FileList | null) {
    if (!files?.length || !profile) return;
    if (profile.portfolio.length + files.length > 40) {
      setError("Bajarilgan ishlar media fayllari 40 tadan oshmasin.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const video = VIDEO_TYPES.has(file.type);
        if (!video && !IMAGE_TYPES.has(file.type)) {
          throw new Error("Faqat JPG, PNG, WEBP rasm yoki MP4/WEBM video yuboring.");
        }
        if (file.size < 1 || file.size > MAX_PORTFOLIO_BYTES) {
          throw new Error("Fayl hajmi 30 MB dan oshmasin.");
        }
        const key = await uploadFile(
          file,
          video ? "specialist_portfolio_video" : "specialist_portfolio_image",
        );
        await api.addSpecialistPortfolio({
          media_type: video ? "video" : "photo",
          object_key: key,
        });
      }
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function uploadOfferImage(file: File | undefined) {
    if (!file) return;
    if (!IMAGE_TYPES.has(file.type)) {
      setError("Faqat JPG, PNG yoki WEBP rasm yuboring.");
      return;
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      setError("Rasm 8 MB dan oshmasin.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const key = await uploadFile(file, "specialist_offer_image");
      setOffer((current) => ({
        ...current,
        image_object_key: key,
        clear_image: false,
      }));
      setOfferImageUrl(URL.createObjectURL(file));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveOffer(event: React.FormEvent) {
    event.preventDefault();
    if (!offer.name.trim()) {
      setError("Nomi kiritilishi shart.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (offerId) await api.updateSpecialistOffer(offerId, offer);
      else await api.createSpecialistOffer(offer);
      await load();
      setOfferForm(false);
      setSaved(true);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove(prompt: string, action: () => Promise<void>): Promise<boolean> {
    if (!window.confirm(prompt)) return false;
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
      return true;
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
    return false;
  }

  if (!profile) {
    return (
      <main className="specialist-v1656">
        <p>Yuklanmoqda...</p>
      </main>
    );
  }

  if (offerForm) {
    return (
      <main className="specialist-v1656">
        <header className="specialist-v1656__toolbar">
          <button type="button" onClick={() => setOfferForm(false)}>
            ←
          </button>
          <h1>{offerId ? "Taklifni tahrirlash" : "Yangi taklif"}</h1>
        </header>
        <form className="specialist-v1656__form" onSubmit={saveOffer}>
          <label>Rasm — ixtiyoriy</label>
          <input
            id="specialist-offer-image"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => void uploadOfferImage(event.currentTarget.files?.[0])}
          />
          {offerImageUrl ? (
            <div className="specialist-v1656__image-preview">
              <img alt="" src={offerImageUrl} />
              <button
                type="button"
                onClick={() => {
                  setOffer((current) => ({
                    ...current,
                    image_object_key: "",
                    clear_image: true,
                  }));
                  setOfferImageUrl("");
                }}
              >
                ×
              </button>
            </div>
          ) : (
            <label
              className="specialist-v1656__photo-add"
              htmlFor="specialist-offer-image"
            >
              <span>📷</span> Rasm qo‘shish
            </label>
          )}
          <label>Turi</label>
          <div className="specialist-v1656__chips">
            {(["service", "product"] as const).map((kind) => (
              <button
                className={offer.kind === kind ? "on" : ""}
                key={kind}
                type="button"
                onClick={() => setOffer((current) => ({ ...current, kind }))}
              >
                {kind === "service" ? "Xizmat" : "Mahsulot"}
              </button>
            ))}
          </div>
          <label>
            Nomi
            <input
              value={offer.name}
              placeholder="Masalan: Huquqiy maslahat"
              onChange={(event) => {
                const value = event.currentTarget.value;
                setOffer((current) => ({ ...current, name: value }));
              }}
            />
          </label>
          <label>
            Narxi
            <input
              value={offer.price_text}
              placeholder="Masalan: 100 000 so'm yoki kelishilgan"
              onChange={(event) => {
                const value = event.currentTarget.value;
                setOffer((current) => ({ ...current, price_text: value }));
              }}
            />
          </label>
          <label>
            Qisqa tavsif
            <textarea
              value={offer.note}
              placeholder="Xizmat yoki mahsulot haqida"
              onChange={(event) => {
                const value = event.currentTarget.value;
                setOffer((current) => ({ ...current, note: value }));
              }}
            />
          </label>
          {error ? (
            <p className="specialist-v1656__error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="specialist-v1656__primary" disabled={busy} type="submit">
            Saqlash
          </button>
          {offerId ? (
            <button
              className="specialist-v1656__danger"
              disabled={busy}
              type="button"
              onClick={() =>
                void remove("Bu mahsulot/xizmat o'chirilsinmi?", () =>
                  api.deleteSpecialistOffer(offerId),
                ).then((deleted) => {
                  if (deleted) setOfferForm(false);
                })
              }
            >
              O‘chirish
            </button>
          ) : null}
        </form>
      </main>
    );
  }

  return (
    <main className="specialist-v1656">
      <header className="specialist-v1656__toolbar">
        <button type="button" onClick={onBack}>
          ←
        </button>
        <div>
          <h1>Mutaxassisligim</h1>
          <p>Profilingiz mijozlarga qanday ko‘rinishini boshqaring.</p>
        </div>
        {onReviews ? (
          <button
            className="specialist-v1656__reviews"
            type="button"
            onClick={onReviews}
          >
            💬 Mijoz fikrlari <b>{profile.review_count}</b>
          </button>
        ) : null}
      </header>

      <div className="specialist-v1656__form">
        <label>
          Kasb / yo‘nalish
          <input
            value={profile.profession}
            placeholder="Masalan: Shifokor, advokat, santexnik"
            onChange={(event) => {
              const value = event.currentTarget.value;
              setProfile((current) => current && { ...current, profession: value });
            }}
          />
        </label>
        <label>
          Qisqa tavsif
          <textarea
            value={profile.description}
            placeholder="Tajribangiz va qanday yordam bera olishingiz haqida qisqacha yozing"
            onChange={(event) => {
              const value = event.currentTarget.value;
              setProfile((current) => current && { ...current, description: value });
            }}
          />
        </label>

        <section className="specialist-v1656__section">
          <h2>Mutaxassislikni tasdiqlovchi hujjatlar</h2>
          <p>Diplom, sertifikat, litsenziya yoki guvohnoma rasmlarini joylang.</p>
          <div className="specialist-v1656__rail">
            <label className="specialist-v1656__add-card">
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                hidden
                disabled={busy}
                onChange={(event) => void addCredentials(event.currentTarget.files)}
              />
              <span>+</span>Hujjat rasmi qo‘shish
            </label>
            {profile.credentials.map((item) => (
              <div className="specialist-v1656__media-card" key={item.id}>
                <img alt="Hujjat" src={item.image_url} />
                <button
                  type="button"
                  onClick={() =>
                    void remove("Bu hujjat rasmi olib tashlansinmi?", () =>
                      api.deleteSpecialistCredential(item.id),
                    )
                  }
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="specialist-v1656__section">
          <h2>Xizmatlarim va mahsulotlarim</h2>
          <p>Takliflaringiz o‘ng-chapga suriladigan kartochkalarda ko‘rinadi.</p>
          <div className="specialist-v1656__rail">
            <button
              className="specialist-v1656__add-card"
              type="button"
              onClick={() => editOffer()}
            >
              <span>+</span>Xizmat yoki mahsulot qo‘shish
            </button>
            {profile.offers.map((item) => (
              <button
                className="specialist-v1656__offer-card"
                key={item.id}
                type="button"
                onClick={() => editOffer(item)}
              >
                <div className="specialist-v1656__offer-image">
                  {item.image_url ? (
                    <img alt="" src={item.image_url} />
                  ) : item.kind === "product" ? (
                    "📦"
                  ) : (
                    "🧰"
                  )}
                </div>
                <small>{item.kind === "product" ? "Mahsulot" : "Xizmat"}</small>
                <b>{item.name}</b>
                {item.price_text ? <span>{item.price_text}</span> : null}
              </button>
            ))}
          </div>
        </section>

        <section className="specialist-v1656__section">
          <h2>Bajargan ishlarim</h2>
          <p>Ish namunalari uchun rasm va videolar yuklang. Video 30 MB gacha.</p>
          <div className="specialist-v1656__rail">
            <label className="specialist-v1656__add-card">
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime"
                multiple
                hidden
                disabled={busy}
                onChange={(event) => void addPortfolio(event.currentTarget.files)}
              />
              <span>+</span>Rasm yoki video qo‘shish
            </label>
            {profile.portfolio.map((item) => (
              <div className="specialist-v1656__media-card" key={item.id}>
                {item.media_type === "video" ? (
                  <>
                    <video muted playsInline preload="metadata" src={item.media_url} />
                    <em>▶ VIDEO</em>
                  </>
                ) : (
                  <img alt="Ish namunasi" src={item.media_url} />
                )}
                <button
                  type="button"
                  onClick={() =>
                    void remove("Bu ish namunasi olib tashlansinmi?", () =>
                      api.deleteSpecialistPortfolio(item.id),
                    )
                  }
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="specialist-v1656__visibility">
          <h2>Ko‘rinishim</h2>
          <button
            className={profile.visible ? "on" : ""}
            type="button"
            onClick={() =>
              setProfile((current) => current && { ...current, visible: true })
            }
          >
            <span>✅</span>
            <div>
              <b>Ko‘rinaman</b>
              <p>Qidiruv va xaritada mutaxassis sifatida chiqaman.</p>
            </div>
          </button>
          <button
            className={!profile.visible ? "on" : ""}
            type="button"
            onClick={() =>
              setProfile((current) => current && { ...current, visible: false })
            }
          >
            <span>🚫</span>
            <div>
              <b>Ko‘rinmayman</b>
              <p>Profilim qidiruv va xaritada ko‘rinmaydi.</p>
            </div>
          </button>
        </section>

        <section>
          <h2>
            📍 Joylashuvingiz <small>(qidiruv va xaritada shu yerda chiqasiz)</small>
          </h2>
          <SpecialistMap
            latitude={profile.latitude}
            longitude={profile.longitude}
            onChange={(latitude, longitude) =>
              setProfile((current) => current && { ...current, latitude, longitude })
            }
            onError={setError}
          />
        </section>

        {error ? (
          <p className="specialist-v1656__error" role="alert">
            {error}
          </p>
        ) : null}
        {saved ? (
          <p className="specialist-v1656__success" role="status">
            Saqlandi ✅
          </p>
        ) : null}
        <button
          className="specialist-v1656__primary"
          disabled={busy}
          type="button"
          onClick={() => {
            setBusy(true);
            setError("");
            setSaved(false);
            void api
              .updateMySpecialist({
                profession: profile.profession,
                description: profile.description,
                visible: profile.visible,
                latitude: profile.latitude,
                longitude: profile.longitude,
              })
              .then((value) => {
                setProfile(value);
                setSaved(true);
              })
              .catch((reason) => setError(errorMessage(reason)))
              .finally(() => setBusy(false));
          }}
        >
          Saqlash
        </button>
      </div>
    </main>
  );
}
