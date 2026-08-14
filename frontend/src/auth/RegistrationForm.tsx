import { useState } from "react";

import type {
  AccountType,
  ChallengeStarted,
  RegistrationStart,
} from "../api/types";
import { CATALOG_DIRECTIONS } from "../public/catalog-data";
import type { AuthApi } from "./AuthFlow";


type Props = {
  api: AuthApi;
  accountType: AccountType;
  initialValue?: RegistrationStart;
  onStarted: (
    challenge: ChallengeStarted,
    registration: RegistrationStart,
  ) => void;
};


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function RegistrationForm({
  api,
  accountType,
  initialValue,
  onStarted,
}: Props) {
  const [name, setName] = useState(initialValue?.name ?? "");
  const [phone, setPhone] = useState(initialValue?.phone ?? "");
  const [direction, setDirection] = useState(initialValue?.direction ?? "");
  const [address, setAddress] = useState(initialValue?.address ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const business = accountType === "business";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body: RegistrationStart = {
      account_type: accountType,
      name: name.trim(),
      phone: phone.trim(),
      ...(business ? {
        direction,
        address: address.trim(),
      } : {}),
    };
    try {
      onStarted(await api.startRegistration(body), body);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="koprik-auth-stage">
      <form className="koprik-flow-shell koprik-auth-shell auth-modular" onSubmit={submit}>
        <h1 className="lead">
          {business ? "Biznes ro'yxati" : "Foydalanuvchi ro'yxati"}
        </h1>
        <p className="lead-sub">
          Ma'lumotlarni kiriting. Tasdiqlash kodi Ko‘prik Telegram boti orqali yuboriladi.
        </p>
        <label className="field">
          <span>{business ? "Biznes nomi" : "Ism familiya"}</span>
          <input
            className="input"
            autoComplete={business ? "organization" : "name"}
            minLength={2}
            maxLength={120}
            placeholder={business ? "Masalan: Anvar Market" : "Ismingiz"}
            required
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
          />
        </label>
        {business ? (
          <>
            <label className="field">
              <span>Faoliyat yo'nalishi</span>
              <select
                className="input"
                value={direction}
                onChange={(event) => setDirection(event.currentTarget.value)}
              >
                <option value="">Yo'nalishni tanlang</option>
                {CATALOG_DIRECTIONS.map((item) => (
                  <option key={item.id} value={item.name}>
                    {item.icon} {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Manzil</span>
              <input
                className="input"
                maxLength={300}
                placeholder="Tuman, mahalla, ko'cha"
                value={address}
                onChange={(event) => setAddress(event.currentTarget.value)}
              />
            </label>
          </>
        ) : null}
        <label className="field">
          <span>Telefon raqami — ixtiyoriy</span>
          <input
            className="input"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            maxLength={32}
            placeholder="+998 90 123 45 67"
            value={phone}
            onChange={(event) => setPhone(event.currentTarget.value)}
          />
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? "Telegram tayyorlanmoqda..." : "✈️ Telegram orqali kod olish"}
        </button>
      </form>
    </main>
  );
}
