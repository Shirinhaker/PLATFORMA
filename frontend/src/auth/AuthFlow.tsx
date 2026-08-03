import { useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  AccountType,
  ChallengeStarted,
  SessionIdentity,
} from "../api/types";
import { LoginForm } from "./LoginForm";
import { RegistrationForm } from "./RegistrationForm";
import { StaffLoginForm } from "./StaffLoginForm";
import { TelegramCodeForm } from "./TelegramCodeForm";


export type AuthApi = Pick<
  ApiClient,
  | "startRegistration"
  | "startLogin"
  | "verifyRegistration"
  | "verifyLogin"
  | "resendChallenge"
  | "getSession"
> & Partial<Pick<ApiClient, "loginStaff">>;

type AuthStep =
  | { name: "choice" }
  | { name: "registration-choice" }
  | { name: "login" }
  | { name: "staff-login" }
  | { name: "registration"; accountType: AccountType }
  | {
      name: "telegram";
      purpose: "login" | "register";
      requestId: number;
      deepLink: string;
      codeSent: boolean;
      resendAfter: number;
    };


export function AuthFlow({
  api,
  onAuthenticated,
  reason = "",
}: {
  api: AuthApi;
  onAuthenticated: (identity: SessionIdentity) => void;
  reason?: string;
}) {
  const [step, setStep] = useState<AuthStep>({ name: "choice" });

  function telegramStep(
    purpose: "login" | "register",
    challenge: ChallengeStarted,
  ) {
    setStep({
      name: "telegram",
      purpose,
      requestId: challenge.request_id,
      deepLink: challenge.deep_link,
      codeSent: challenge.code_sent ?? false,
      resendAfter: challenge.resend_after,
    });
  }

  if (step.name === "login") {
    return (
      <LoginForm
        api={api}
        onStarted={(challenge) => telegramStep("login", challenge)}
        onBack={() => setStep({ name: "choice" })}
      />
    );
  }
  if (step.name === "staff-login" && api.loginStaff) {
    return (
      <StaffLoginForm
        api={{ loginStaff: api.loginStaff.bind(api) }}
        onAuthenticated={onAuthenticated}
        onBack={() => setStep({ name: "choice" })}
      />
    );
  }
  if (step.name === "registration") {
    return (
      <RegistrationForm
        api={api}
        accountType={step.accountType}
        onStarted={(challenge) => telegramStep("register", challenge)}
        onBack={() => setStep({ name: "registration-choice" })}
      />
    );
  }
  if (step.name === "telegram") {
    return (
      <TelegramCodeForm
        api={api}
        purpose={step.purpose}
        requestId={step.requestId}
        deepLink={step.deepLink}
        codeSent={step.codeSent}
        resendAfter={step.resendAfter}
        onAuthenticated={onAuthenticated}
        onBack={() => setStep({ name: "choice" })}
      />
    );
  }
  if (step.name === "registration-choice") {
    return (
      <main className="auth-card auth-choice">
        <p className="session-panel__eyebrow">Ro‘yxatdan o‘tish</p>
        <h1>Akkaunt turini tanlang</h1>
        <button
          type="button"
          onClick={() => setStep({
            name: "registration",
            accountType: "user",
          })}
        >
          Oddiy akkaunt
        </button>
        <button
          type="button"
          onClick={() => setStep({
            name: "registration",
            accountType: "business",
          })}
        >
          Biznes akkaunt
        </button>
        <button
          type="button"
          className="button-secondary"
          onClick={() => setStep({ name: "choice" })}
        >
          Orqaga
        </button>
      </main>
    );
  }
  return (
    <main className="auth-card auth-choice">
      <p className="session-panel__eyebrow">Koprik</p>
      <h1>Koprik’ga kirish</h1>
      {reason ? (
        <p id="loginReason">🔒 {reason} uchun tizimga kiring yoki ro'yxatdan o'ting.</p>
      ) : null}
      <p>Telegram orqali xavfsiz kirish yoki ro‘yxatdan o‘tish.</p>
      <button type="button" onClick={() => setStep({ name: "login" })}>
        Kirish
      </button>
      {api.loginStaff && (
        <button
          type="button"
          className="button-secondary"
          onClick={() => setStep({ name: "staff-login" })}
        >
          Xodimlar uchun kirish
        </button>
      )}
      <button
        type="button"
        className="button-secondary"
        onClick={() => setStep({ name: "registration-choice" })}
      >
        Ro‘yxatdan o‘tish
      </button>
    </main>
  );
}
