import { useState } from "react";

import type { AccountType, ChallengeStarted } from "../api/types";
import type { AuthApi } from "./AuthFlow";


export type LoginDraft = {
  login: string;
  password: string;
  cabinetType?: AccountType;
};

type Props = {
  api: AuthApi;
  initialValue?: LoginDraft;
  reason?: string;
  onStarted: (challenge: ChallengeStarted, draft: LoginDraft) => void;
  onStaff?: () => void;
  onRegister: () => void;
};


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


function errorCode(error: unknown) {
  if (!error || typeof error !== "object" || !("code" in error)) return "";
  return typeof error.code === "string" ? error.code : "";
}


export function LoginForm({
  api,
  initialValue,
  reason = "",
  onStarted,
  onStaff,
  onRegister,
}: Props) {
  const [login, setLogin] = useState(initialValue?.login ?? "");
  const [password, setPassword] = useState(initialValue?.password ?? "");
  const [cabinetType, setCabinetType] = useState<"" | AccountType>(
    initialValue?.cabinetType ?? "",
  );
  const [needsCabinetType, setNeedsCabinetType] = useState(
    Boolean(initialValue?.cabinetType),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const draft: LoginDraft = {
      login: login.trim().toLowerCase(),
      password,
      ...(cabinetType ? { cabinetType } : {}),
    };
    try {
      const challenge = await api.startLogin({
        login: draft.login,
        password: draft.password,
        ...(draft.cabinetType ? { cabinet_type: draft.cabinetType } : {}),
      });
      onStarted(challenge, draft);
    } catch (requestError) {
      if (errorCode(requestError) === "account_type_required") {
        setNeedsCabinetType(true);
      }
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="koprik-auth-stage">
      <form className="koprik-flow-shell koprik-auth-shell auth-v1656" onSubmit={submit}>
        <h1 className="lead">Kabinetga kirish</h1>
        {reason ? (
          <p className="lead-sub auth-v1656__reason" id="loginReason">
            🔒 {reason} uchun tizimga kiring yoki ro'yxatdan o'ting.
          </p>
        ) : null}
        <p className="lead-sub">
          Ro'yxatdan o'tganda berilgan login va parolni kiriting.
        </p>
        <label className="field">
          <span>Login</span>
          <input
            className="input"
            autoComplete="username"
            placeholder="Login"
            required
            value={login}
            onChange={(event) => setLogin(event.currentTarget.value)}
          />
        </label>
        <label className="field">
          <span>Parol</span>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            placeholder="Parol"
            required
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
          />
        </label>
        {needsCabinetType ? (
          <label className="field">
            <span>Kabinet turi</span>
            <select
              className="input"
              required
              value={cabinetType}
              onChange={(event) => setCabinetType(
                event.currentTarget.value as "" | AccountType,
              )}
            >
              <option value="">Kabinet turini tanlang</option>
              <option value="user">Oddiy kabinet</option>
              <option value="business">Biznes kabinet</option>
            </select>
          </label>
        ) : null}
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? "Tekshirilmoqda..." : "Telegram orqali tasdiqlash"}
        </button>
        <p className="form-foot">
          Akkauntingiz yo'qmi?{" "}
          <button className="form-foot__action" type="button" onClick={onRegister}>
            Ro'yxatdan o'tish
          </button>
        </p>
        {onStaff ? (
          <div className="auth-v1656__staff-entry">
            <button className="btn btn-soft btn-block" type="button" onClick={onStaff}>
              👥 Xodimlar uchun kirish
            </button>
            <p className="idesc">
              Do'kon xodimi bo'lsangiz — firma va o'z login-parolingiz bilan kiring.
            </p>
          </div>
        ) : null}
      </form>
    </main>
  );
}
