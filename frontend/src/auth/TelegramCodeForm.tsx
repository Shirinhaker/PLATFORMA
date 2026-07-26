import { useEffect, useState } from "react";

import type { SessionIdentity } from "../api/types";
import type { AuthApi } from "./AuthFlow";


type Props = {
  api: AuthApi;
  purpose: "login" | "register";
  requestId: number;
  deepLink: string;
  codeSent: boolean;
  resendAfter: number;
  onAuthenticated: (identity: SessionIdentity) => void;
  onBack?: () => void;
};

type Credentials = {
  login: string;
  password: string;
  identity: SessionIdentity;
};


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function TelegramCodeForm({
  api,
  purpose,
  requestId,
  deepLink,
  codeSent,
  resendAfter,
  onAuthenticated,
  onBack,
}: Props) {
  const [code, setCode] = useState("");
  const [countdown, setCountdown] = useState(resendAfter);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [credentials, setCredentials] = useState<Credentials | null>(null);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = window.setInterval(() => {
      setCountdown((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [countdown > 0]);

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError("6 xonali kodni to‘liq kiriting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = {
        request_id: requestId,
        code,
        device_name: navigator.userAgent.slice(0, 200),
      };
      const result = purpose === "register"
        ? await api.verifyRegistration(body)
        : await api.verifyLogin(body);
      const identity = await api.getSession();
      if (purpose === "register") {
        if (!result.login || !result.password) {
          throw new Error("Yaratilgan login yoki parol olinmadi.");
        }
        setCredentials({
          login: result.login,
          password: result.password,
          identity,
        });
      } else {
        onAuthenticated(identity);
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    setError("");
    try {
      const result = await api.resendChallenge(requestId);
      setCountdown(result.resend_after);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function copyCredentials() {
    if (!credentials) return;
    await navigator.clipboard?.writeText(
      `Login: ${credentials.login}\nParol: ${credentials.password}`,
    );
  }

  if (credentials) {
    return (
      <section className="auth-card credential-card">
        <p className="session-panel__eyebrow">Akkaunt yaratildi</p>
        <h1>Login va parolni saqlang</h1>
        <p role="alert">
          Bu ma’lumotlar shu ekranda faqat bir marta ko‘rsatiladi.
        </p>
        <dl>
          <div><dt>Login</dt><dd>{credentials.login}</dd></div>
          <div><dt>Parol</dt><dd>{credentials.password}</dd></div>
        </dl>
        <button type="button" className="button-secondary" onClick={copyCredentials}>
          Nusxalash
        </button>
        <button
          type="button"
          onClick={() => onAuthenticated(credentials.identity)}
        >
          Kabinetga kirish
        </button>
      </section>
    );
  }

  return (
    <form className="auth-card auth-form" onSubmit={verify}>
      <div>
        <p className="session-panel__eyebrow">Telegram tasdiqlashi</p>
        <h1>6 xonali kod</h1>
        {codeSent ? (
          <p>Kod bog‘langan Telegram akkauntingizga yuborildi.</p>
        ) : (
          <p>
            Botni ochib tasdiqlashni boshlang.{" "}
            <a href={deepLink} target="_blank" rel="noreferrer">
              Telegramni ochish
            </a>
          </p>
        )}
      </div>
      <label>
        6 xonali kod
        <input
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          required
          value={code}
          onChange={(event) => setCode(
            event.currentTarget.value.replace(/\D/g, "").slice(0, 6),
          )}
        />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || code.length !== 6}>
        {busy ? "Tekshirilmoqda…" : "Tasdiqlash"}
      </button>
      <button
        type="button"
        className="button-secondary"
        disabled={busy || countdown > 0}
        onClick={resend}
      >
        {countdown > 0 ? `Qayta yuborish (${countdown})` : "Qayta yuborish"}
      </button>
      {onBack && (
        <button type="button" className="button-link" onClick={onBack}>
          Orqaga
        </button>
      )}
    </form>
  );
}
