import { useState } from "react";

import type {
  AccountType,
  ChallengeStarted,
  RegistrationStart,
} from "../api/types";
import type { AuthApi } from "./AuthFlow";


type Props = {
  api: AuthApi;
  accountType: AccountType;
  onStarted: (challenge: ChallengeStarted) => void;
  onBack: () => void;
};


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function RegistrationForm({
  api,
  accountType,
  onStarted,
  onBack,
}: Props) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [direction, setDirection] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const business = accountType === "business";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body: RegistrationStart = {
      account_type: accountType,
      name,
      phone,
      ...(business ? { direction, address } : {}),
    };
    try {
      onStarted(await api.startRegistration(body));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-card auth-form" onSubmit={submit}>
      <div>
        <p className="session-panel__eyebrow">Ro‘yxatdan o‘tish</p>
        <h1>{business ? "Biznes akkaunt" : "Oddiy akkaunt"}</h1>
      </div>
      <label>
        {business ? "Biznes nomi" : "Ism"}
        <input
          autoComplete={business ? "organization" : "name"}
          minLength={2}
          maxLength={120}
          required
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
        />
      </label>
      <label>
        Telefon
        <input
          type="tel"
          autoComplete="tel"
          maxLength={32}
          value={phone}
          onChange={(event) => setPhone(event.currentTarget.value)}
        />
      </label>
      {business && (
        <>
          <label>
            Yo‘nalish
            <input
              maxLength={120}
              value={direction}
              onChange={(event) => setDirection(event.currentTarget.value)}
            />
          </label>
          <label>
            Manzil
            <textarea
              maxLength={300}
              value={address}
              onChange={(event) => setAddress(event.currentTarget.value)}
            />
          </label>
        </>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? "Yuborilmoqda…" : "Telegram orqali tasdiqlash"}
      </button>
      <button type="button" className="button-secondary" onClick={onBack}>
        Orqaga
      </button>
    </form>
  );
}
