import { useEffect, useRef, useState } from "react";

import type { AccountType, Authenticated, SessionIdentity } from "../api/types";
import type { AuthApi } from "./AuthFlow";
import { openTelegramLink, refreshPendingAuth } from "./auth-pending";

type Props = {
  api: AuthApi;
  purpose: "login" | "register";
  accountType?: AccountType;
  requestId: number;
  deepLink: string;
  codeSent: boolean;
  resendAfter: number;
  onAuthenticated: (identity: SessionIdentity) => void;
  onVerified?: () => void;
  onBack?: () => void;
};

type Credentials = {
  login: string;
  password: string;
  accountType: AccountType;
  identity: SessionIdentity;
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

export function TelegramCodeForm({
  api,
  purpose,
  accountType,
  requestId,
  deepLink,
  resendAfter,
  onAuthenticated,
  onVerified,
  onBack,
}: Props) {
  const [code, setCode] = useState("");
  const [countdown, setCountdown] = useState(resendAfter);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [verified, setVerified] = useState<Authenticated | null>(null);
  const inFlight = useRef(false);
  const [credentials, setCredentials] = useState<Credentials | null>(null);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = window.setTimeout(() => {
      setCountdown((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [countdown]);

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    if (!verified && !/^\d{6}$/.test(code)) {
      setError("6 xonali kodni kiriting.");
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const body = {
        request_id: requestId,
        code,
        device_name: navigator.userAgent.slice(0, 100),
      };
      let result = verified;
      if (!result) {
        result =
          purpose === "register"
            ? await api.verifyRegistration(body)
            : await api.verifyLogin(body);
        setVerified(result);
        onVerified?.();
      }
      const identity = await api.getSession();
      if (purpose === "register") {
        if (!result.login || !result.password) {
          throw new Error("Yaratilgan login yoki parol olinmadi.");
        }
        setCredentials({
          login: result.login,
          password: result.password,
          accountType: result.account_type ?? accountType ?? identity.account_type,
          identity,
        });
      } else {
        onAuthenticated(identity);
      }
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function resend() {
    if (inFlight.current || verified) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api.resendChallenge(requestId);
      refreshPendingAuth(result);
      setCode("");
      setCountdown(result.resend_after);
      openTelegramLink(deepLink);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  if (credentials) {
    const business = credentials.accountType === "business";
    return (
      <main className="koprik-auth-stage">
        <section className="koprik-flow-shell koprik-auth-shell auth-v1656 credential-card">
          <h1 className="lead">
            {business ? "Biznes profilingiz ochildi! ✅" : "Ro'yxatdan o'tdingiz! ✅"}
          </h1>
          <p className="lead-sub">
            {business
              ? "Biznes kabinet uchun yagona login va parolni xavfsiz joyda saqlab qo'ying."
              : "Quyidagi login va parolni xavfsiz joyda saqlab qo'ying."}
          </p>
          <dl className="cred-box">
            <div>
              <dt>🔑 Login</dt>
              <dd>{credentials.login}</dd>
            </div>
            <div>
              <dt>🔐 Parol</dt>
              <dd>{credentials.password}</dd>
            </div>
          </dl>
          <button
            className="btn btn-primary btn-block"
            type="button"
            onClick={() => onAuthenticated(credentials.identity)}
          >
            Kabinetga kirish
          </button>
        </section>
      </main>
    );
  }

  const resendLabel =
    purpose === "register" ? "Yangi kod olish" : "Kodni qayta yuborish";
  const backLabel =
    purpose === "register"
      ? "Ma'lumotlarni o'zgartirish"
      : "← Login va parolga qaytish";

  return (
    <main className="koprik-auth-stage">
      <form
        className="koprik-flow-shell koprik-auth-shell auth-v1656"
        onSubmit={verify}
      >
        <h1 className="lead">Telegram orqali tasdiqlash</h1>
        <p className="lead-sub">Telegram bot yuborgan 6 xonali kodni kiriting.</p>
        <label className="field">
          <span>Tasdiqlash kodi</span>
          <input
            className="input"
            autoFocus
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            placeholder="000000"
            required
            disabled={busy || Boolean(verified)}
            value={code}
            onChange={(event) =>
              setCode(event.currentTarget.value.replace(/\D/g, "").slice(0, 6))
            }
          />
        </label>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button
          className="btn btn-primary btn-block"
          type="submit"
          disabled={busy || (!verified && code.length !== 6)}
        >
          {busy
            ? "Tekshirilmoqda..."
            : verified
              ? "Kirishni davom ettirish"
              : "Tasdiqlash va kirish"}
        </button>
        {verified ? (
          <p role="status">Kod tasdiqlandi. Kirishni davom ettiring.</p>
        ) : null}
        {deepLink && !verified ? (
          <button
            className="btn btn-soft btn-block"
            type="button"
            onClick={() => openTelegramLink(deepLink)}
          >
            ✈️ Telegramni ochish
          </button>
        ) : null}
        <button
          className="btn btn-outline btn-block"
          type="button"
          disabled={busy || Boolean(verified) || countdown > 0}
          onClick={resend}
        >
          {countdown > 0 ? `${resendLabel} (${countdown})` : resendLabel}
        </button>
        {onBack && !busy && !verified ? (
          purpose === "login" ? (
            <p className="form-foot">
              <button className="form-foot__action" type="button" onClick={onBack}>
                {backLabel}
              </button>
            </p>
          ) : (
            <button
              className="btn btn-outline btn-block"
              type="button"
              onClick={onBack}
            >
              {backLabel}
            </button>
          )
        ) : null}
      </form>
    </main>
  );
}
