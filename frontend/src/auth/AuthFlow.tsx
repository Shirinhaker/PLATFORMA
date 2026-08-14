import { useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  AccountType,
  ChallengeStarted,
  RegistrationStart,
  SessionIdentity,
} from "../api/types";
import {
  clearPendingAuth,
  openTelegramLink,
  pendingResendSeconds,
  readPendingAuth,
  savePendingAuth,
} from "./auth-pending";
import { LoginForm, type LoginDraft } from "./LoginForm";
import { RegistrationForm } from "./RegistrationForm";
import { StaffLoginForm } from "./StaffLoginForm";
import { TelegramCodeForm } from "./TelegramCodeForm";
import "./Auth.css";


export type AuthApi = Pick<
  ApiClient,
  | "startRegistration"
  | "startLogin"
  | "verifyRegistration"
  | "verifyLogin"
  | "resendChallenge"
  | "getSession"
> & Partial<Pick<ApiClient, "loginStaff">>;

type TelegramStep = {
  name: "telegram";
  purpose: "login" | "register";
  accountType?: AccountType;
  requestId: number;
  deepLink: string;
  codeSent: boolean;
  resendAfter: number;
  loginDraft?: LoginDraft;
  registrationDraft?: RegistrationStart;
};

type AuthStep =
  | { name: "registration-choice" }
  | { name: "login"; initialValue?: LoginDraft }
  | { name: "staff-login" }
  | {
      name: "registration";
      accountType: AccountType;
      initialValue?: RegistrationStart;
    }
  | TelegramStep;


function initialStep(): AuthStep {
  const pending = readPendingAuth();
  if (!pending) return { name: "login" };
  return {
    name: "telegram",
    purpose: pending.kind,
    accountType: pending.kind === "register" ? pending.role : undefined,
    requestId: pending.request_id,
    deepLink: pending.deep_link,
    codeSent: pending.code_sent ?? false,
    resendAfter: pendingResendSeconds(pending),
    registrationDraft: pending.kind === "register" ? pending.payload : undefined,
  };
}


export function AuthFlow({
  api,
  onAuthenticated,
  reason = "",
}: {
  api: AuthApi;
  onAuthenticated: (identity: SessionIdentity) => void;
  reason?: string;
}) {
  const [step, setStep] = useState<AuthStep>(initialStep);

  function telegramStep(
    purpose: "login" | "register",
    challenge: ChallengeStarted,
    draft: LoginDraft | RegistrationStart,
  ) {
    const registration = purpose === "register"
      ? draft as RegistrationStart
      : undefined;
    savePendingAuth(purpose, challenge, registration);
    setStep({
      name: "telegram",
      purpose,
      accountType: registration?.account_type,
      requestId: challenge.request_id,
      deepLink: challenge.deep_link,
      codeSent: challenge.code_sent ?? false,
      resendAfter: challenge.resend_after,
      loginDraft: purpose === "login" ? draft as LoginDraft : undefined,
      registrationDraft: registration,
    });
    openTelegramLink(challenge.deep_link);
  }

  function completeAuthentication(identity: SessionIdentity) {
    clearPendingAuth();
    onAuthenticated(identity);
  }

  if (step.name === "login") {
    return (
      <LoginForm
        api={api}
        initialValue={step.initialValue}
        reason={reason}
        onStarted={(challenge, draft) => telegramStep("login", challenge, draft)}
        onRegister={() => setStep({ name: "registration-choice" })}
        onStaff={api.loginStaff
          ? () => setStep({ name: "staff-login" })
          : undefined}
      />
    );
  }
  if (step.name === "staff-login" && api.loginStaff) {
    return (
      <StaffLoginForm
        api={{ loginStaff: api.loginStaff.bind(api) }}
        onAuthenticated={completeAuthentication}
        onBack={() => setStep({ name: "login" })}
      />
    );
  }
  if (step.name === "registration") {
    return (
      <RegistrationForm
        api={api}
        accountType={step.accountType}
        initialValue={step.initialValue}
        onStarted={(challenge, registration) => (
          telegramStep("register", challenge, registration)
        )}
      />
    );
  }
  if (step.name === "telegram") {
    return (
      <TelegramCodeForm
        api={api}
        purpose={step.purpose}
        accountType={step.accountType}
        requestId={step.requestId}
        deepLink={step.deepLink}
        codeSent={step.codeSent}
        resendAfter={step.resendAfter}
        onAuthenticated={completeAuthentication}
        onVerified={clearPendingAuth}
        onBack={() => {
          clearPendingAuth();
          if (step.purpose === "register") {
            setStep({
              name: "registration",
              accountType: step.accountType ?? "user",
              initialValue: step.registrationDraft,
            });
          } else {
            setStep({ name: "login", initialValue: step.loginDraft });
          }
        }}
      />
    );
  }
  return (
    <main className="koprik-auth-stage">
      <section className="koprik-flow-shell koprik-auth-shell auth-modular">
        <h1 className="lead">Ro'yxatdan o'tish</h1>
        <div className="koprik-role-grid">
          <p className="lead-sub">Kim sifatida ro'yxatdan o'tmoqchisiz?</p>
          <button
            className="role-card"
            type="button"
            onClick={() => setStep({
              name: "registration",
              accountType: "business",
            })}
          >
            <span className="role-ic role-ic--business" aria-hidden="true">🏪</span>
            <span className="role-main">
              <strong>Biznes</strong>
              <span>Mahsulot va xizmatlaringizni joylashtiring, mijozlar bilan ishlang.</span>
            </span>
            <span className="chev" aria-hidden="true">›</span>
          </button>
          <button
            className="role-card"
            type="button"
            onClick={() => setStep({
              name: "registration",
              accountType: "user",
            })}
          >
            <span className="role-ic role-ic--user" aria-hidden="true">🙂</span>
            <span className="role-main">
              <strong>Oddiy foydalanuvchi</strong>
              <span>Bizneslarni toping, buyurtma bering, navbatga yoziling.</span>
            </span>
            <span className="chev" aria-hidden="true">›</span>
          </button>
        </div>
      </section>
    </main>
  );
}
