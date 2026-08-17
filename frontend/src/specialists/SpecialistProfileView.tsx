import type { Dispatch, ReactNode, SetStateAction } from "react";

import type { ApiClient } from "../api/client";
import type { SpecialistOffer, SpecialistProfile } from "../api/types";

type ProfileApi = Pick<
  ApiClient,
  "updateMySpecialist" | "deleteSpecialistCredential" | "deleteSpecialistPortfolio"
>;

export function SpecialistProfileView({
  api,
  profile,
  setProfile,
  busy,
  error,
  saved,
  setBusy,
  setError,
  setSaved,
  onBack,
  onReviews,
  addCredentials,
  addPortfolio,
  editOffer,
  remove,
  locationMap,
  formatError,
}: {
  api: ProfileApi;
  profile: SpecialistProfile;
  setProfile: Dispatch<SetStateAction<SpecialistProfile | null>>;
  busy: boolean;
  error: string;
  saved: boolean;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string>>;
  setSaved: Dispatch<SetStateAction<boolean>>;
  onBack(): void;
  onReviews?(): void;
  addCredentials(files: FileList | null): Promise<void>;
  addPortfolio(files: FileList | null): Promise<void>;
  editOffer(value?: SpecialistOffer): void;
  remove(prompt: string, action: () => Promise<void>): Promise<boolean>;
  locationMap: ReactNode;
  formatError(reason: unknown): string;
}) {
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
          {locationMap}
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
              .catch((reason) => setError(formatError(reason)))
              .finally(() => setBusy(false));
          }}
        >
          Saqlash
        </button>
      </div>
    </main>
  );
}
