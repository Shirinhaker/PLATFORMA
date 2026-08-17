import type {
  CSSProperties,
  Dispatch,
  FormEvent,
  RefObject,
  SetStateAction,
} from "react";

import type { ApiClient } from "../api/client";
import type { BusinessProfile } from "../api/types";
import { BUSINESS_DIRECTIONS, directionActivities } from "./business-profile-config";
import {
  QrCode,
  errorText,
  mapUrl,
  type Hours,
  type Point,
} from "./BusinessProfileEditorShared";

type Props = {
  api: Partial<Pick<ApiClient, "attachBusinessPaymentQr">>;
  draft: BusinessProfile;
  hours: Hours;
  activities: string[];
  point: Point | null;
  logoStyle: CSSProperties;
  paymentInput: RefObject<HTMLInputElement | null>;
  busy: boolean;
  error: string;
  saved: boolean;
  crop: boolean;
  lightbox: boolean;
  link: string;
  copyText: string;
  field<K extends keyof BusinessProfile>(name: K, value: BusinessProfile[K]): void;
  setDraft: Dispatch<SetStateAction<BusinessProfile>>;
  setHours: Dispatch<SetStateAction<Hours>>;
  setSaved: (value: boolean) => void;
  setCrop: Dispatch<SetStateAction<boolean>>;
  setMapOpen: (value: boolean) => void;
  setLightbox: (value: boolean) => void;
  onSave: (event: FormEvent<HTMLFormElement>) => void;
  onSaveCrop: () => void | Promise<void>;
  onCopyLink: () => void | Promise<void>;
  onUploadPaymentQr: (file: File) => void | Promise<void>;
  onApply: (profile: BusinessProfile) => void;
  onError: (value: string) => void;
};

export function BusinessProfileEditorForm({
  api,
  draft,
  hours,
  activities,
  point,
  logoStyle,
  paymentInput,
  busy,
  error,
  saved,
  crop,
  lightbox,
  link,
  copyText,
  field,
  setDraft,
  setHours,
  setSaved,
  setCrop,
  setMapOpen,
  setLightbox,
  onSave,
  onSaveCrop,
  onCopyLink,
  onUploadPaymentQr,
  onApply,
  onError,
}: Props) {
  return (
    <>
      {draft.logo_object_key && (
        <button
          type="button"
          className="business-profile-editor__adjust btn btn-outline btn-block"
          onClick={() => setCrop((value) => !value)}
        >
          🖼 Rasm joylashuvini sozlash
        </button>
      )}
      {crop && draft.logo_url && (
        <section className="business-logo-crop avatar-crop-box">
          <div className="business-logo-crop__stage avatar-crop-stage">
            <img src={draft.logo_url} alt="Biznes rasmi" style={logoStyle} />
          </div>
          <label>
            Gorizontal joylashuv
            <input
              type="range"
              min="0"
              max="100"
              value={draft.logo_x}
              onChange={(event) => field("logo_x", Number(event.currentTarget.value))}
            />
          </label>
          <label>
            Vertikal joylashuv
            <input
              type="range"
              min="0"
              max="100"
              value={draft.logo_y}
              onChange={(event) => field("logo_y", Number(event.currentTarget.value))}
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
              onChange={(event) =>
                field("logo_zoom", Number(event.currentTarget.value))
              }
            />
          </label>
          <p className="idesc">
            Rasmni barmoq bilan surib, ko‘rinadigan qismini belgilang.
          </p>
          <div className="avatar-crop-actions">
            <button
              type="button"
              className="btn btn-outline"
              onClick={() =>
                setDraft((current) => ({
                  ...current,
                  logo_x: 50,
                  logo_y: 50,
                  logo_zoom: 1,
                }))
              }
            >
              Markazga
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void onSaveCrop()}
            >
              Saqlash
            </button>
          </div>
        </section>
      )}

      <form className="business-profile-form" onSubmit={onSave}>
        <label className="field">
          Biznes nomi
          <input
            className="input"
            placeholder="Biznes nomi"
            value={draft.name}
            onChange={(event) => field("name", event.currentTarget.value)}
          />
        </label>
        <label className="field">
          Telefon raqami
          <input
            className="input"
            type="tel"
            placeholder="+998 __ ___ __ __"
            value={draft.phone}
            onChange={(event) => field("phone", event.currentTarget.value)}
          />
        </label>
        <label className="field">
          Qisqa tavsif
          <textarea
            className="textarea"
            placeholder="Biznesingiz haqida qisqacha"
            value={draft.description}
            onChange={(event) => field("description", event.currentTarget.value)}
          />
        </label>
        <label className="field">
          Username (do'kon manzili)
          <span className="business-profile-form__username">
            <b>@</b>
            <input
              className="input"
              placeholder="dokonanvar"
              autoComplete="off"
              value={draft.public_username}
              onChange={(event) =>
                field(
                  "public_username",
                  event.currentTarget.value
                    .toLowerCase()
                    .replace(/^@+/, "")
                    .replace(/[^a-z0-9_]/g, ""),
                )
              }
            />
          </span>
          <small className="idesc">
            Kichik lotin harflari, raqam va _ (3–20 belgi). Mijozlar sizni shu nom
            orqali oson topadi. Ixtiyoriy.
          </small>
        </label>

        <section className="business-profile-share">
          <strong>
            🔗 <span>Do'kon havolasi</span>
          </strong>
          <p className="idesc">
            Shu havola yoki QR orqali mijozlar to'g'ridan-to'g'ri do'koningizga o'tadi.
          </p>
          <div className="business-profile-share__row">
            <input
              className="input"
              readOnly
              value={link}
              aria-label="Do'kon havolasi manzili"
            />
            <button
              type="button"
              className="mini-btn"
              onClick={() => void onCopyLink()}
            >
              {copyText}
            </button>
          </div>
          <QrCode value={link} />
        </section>

        <label className="field">
          Faoliyat yo'nalishi
          <select
            className="input"
            value={draft.direction}
            onChange={(event) => {
              const direction = event.currentTarget.value;
              const activity_type = directionActivities(direction)[0] ?? "";
              setSaved(false);
              setDraft((current) => ({ ...current, direction, activity_type }));
            }}
          >
            <option value="">Yo'nalishni tanlang</option>
            {BUSINESS_DIRECTIONS.map((item) => (
              <option value={item.name} key={item.name}>
                {item.icon} {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Faoliyat turi
          <select
            className="input"
            value={draft.activity_type}
            disabled={!draft.direction}
            onChange={(event) => field("activity_type", event.currentTarget.value)}
          >
            {!activities.length && <option value="">Avval yo'nalishni tanlang</option>}
            {activities.map((activity) => (
              <option key={activity} value={activity}>
                {activity}
              </option>
            ))}
          </select>
        </label>

        <section className="business-profile-map field">
          <strong>Xaritadagi joy</strong>
          <button
            type="button"
            className="btn btn-outline btn-block"
            onClick={() => setMapOpen(true)}
          >
            📍 Xaritada joy belgilash
          </button>
          {point ? (
            <>
              <span className="business-profile-map__status">✅ Joy belgilangan</span>
              <iframe
                title="Belgilangan joy xaritasi"
                src={mapUrl(point)}
                loading="lazy"
              />
            </>
          ) : (
            <>
              <p className="idesc">Biznesingiz xaritada shu joyda ko'rinadi</p>
              <p className="business-profile-map__warning">
                ⚠️ Qidiruv va xaritada ko‘rinish uchun biznes joylashuvini xaritada
                belgilang.
              </p>
            </>
          )}
        </section>

        <section className="business-payment-section">
          <header>
            <strong>
              💳 <span>To'lov ma'lumotlari</span>
            </strong>
            <p className="idesc">
              Onlayn buyurtmada mijoz shu yerga to'laydi va chekni suhbatga tashlaydi.
              Ixtiyoriy — to'ldirmasangiz onlayn to'lov ko'rsatilmaydi.
            </p>
          </header>
          <label className="field">
            To'lov kartasi raqami
            <input
              className="input"
              inputMode="numeric"
              placeholder="8600 XXXX XXXX XXXX"
              value={draft.pay_card}
              onChange={(event) => field("pay_card", event.currentTarget.value)}
            />
          </label>
          <label className="field">
            Karta egasi (ism-familiya)
            <input
              className="input"
              placeholder="Masalan: Anvar Karimov"
              value={draft.pay_holder}
              onChange={(event) => field("pay_holder", event.currentTarget.value)}
            />
          </label>
          <div className="business-payment-section__qr">
            <strong>To'lov QR kodi (rasm)</strong>
            <input
              ref={paymentInput}
              type="file"
              hidden
              accept="image/jpeg,image/png,image/webp,image/gif"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = "";
                if (file) void onUploadPaymentQr(file);
              }}
            />
            <button
              type="button"
              className="btn btn-outline btn-block"
              disabled={busy}
              onClick={() => paymentInput.current?.click()}
            >
              📷 QR rasm yuklash
            </button>
            {draft.pay_qr_url && (
              <div className="business-payment-section__preview">
                <img src={draft.pay_qr_url} alt="To'lov QR kodi" />
                <button
                  type="button"
                  aria-label="O'chirish"
                  onClick={() =>
                    api.attachBusinessPaymentQr &&
                    void api
                      .attachBusinessPaymentQr({ object_key: "" })
                      .then(onApply)
                      .catch((reason) => onError(errorText(reason)))
                  }
                >
                  ×
                </button>
              </div>
            )}
          </div>
        </section>

        <label className="field">
          Ish vaqti
          <span className="business-hours-row">
            <input
              className="input"
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
              className="input"
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
          <small className="idesc">Ish boshlanish va tugash vaqtini belgilang.</small>
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {saved && (
          <p className="form-success" role="status">
            Saqlandi
          </p>
        )}
        <button
          type="submit"
          className="business-profile-form__save btn btn-primary btn-block"
          disabled={busy}
        >
          {busy ? "Saqlanmoqda…" : "Saqlash"}
        </button>
      </form>

      {lightbox && draft.logo_url && (
        <button
          type="button"
          className="business-logo-lightbox"
          aria-label="Kattalashtirilgan biznes rasmini yopish"
          onClick={() => setLightbox(false)}
        >
          <img src={draft.logo_url} alt={draft.name} />
        </button>
      )}
    </>
  );
}
