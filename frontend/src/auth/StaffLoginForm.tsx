import { type FormEvent, useState } from "react";

import type { ApiClient } from "../api/client";
import type { SessionIdentity } from "../api/types";


export type StaffLoginApi = Pick<ApiClient, "loginStaff">;


export function StaffLoginForm({
  api,
  onAuthenticated,
  onBack,
}: {
  api: StaffLoginApi;
  onAuthenticated: (identity: SessionIdentity) => void;
  onBack: () => void;
}) {
  const [firmLogin, setFirmLogin] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onAuthenticated(await api.loginStaff({
        firm_login: firmLogin.trim().toLowerCase(),
        login: login.trim().toLowerCase(),
        password,
      }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Kirish amalga oshmadi.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="koprik-auth-stage">
      <form
        className="koprik-flow-shell koprik-auth-shell koprik-staff-shell auth-v1656"
        onSubmit={(event) => void submit(event)}
      >
        <div className="koprik-staff-shell__heading">
          <div className="koprik-staff-shell__icon" aria-hidden="true">🏪</div>
          <h1 className="lead">Xodim kirishi</h1>
          <p className="idesc">Do'kon rahbari bergan login va parol bilan kiring.</p>
        </div>
        <label className="field">
          <span>Firma logini</span>
          <input
            className="input auth-v1656__lowercase"
            autoComplete="off"
            placeholder="masalan: biz123456"
            value={firmLogin}
            onChange={(event) => setFirmLogin(event.currentTarget.value.toLowerCase())}
            required
          />
        </label>
        <label className="field">
          <span>Xodim logini</span>
          <input
            className="input auth-v1656__lowercase"
            autoComplete="username"
            placeholder="masalan: vali01"
            value={login}
            onChange={(event) => setLogin(event.currentTarget.value.toLowerCase())}
            required
          />
        </label>
        <label className="field">
          <span>Xodim paroli</span>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            placeholder="Parol"
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
            required
          />
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? "Kirilmoqda..." : "Kirish"}
        </button>
        <p className="form-foot">
          <button className="form-foot__action" type="button" onClick={onBack}>
            ← Oddiy kirishga qaytish
          </button>
        </p>
      </form>
    </main>
  );
}
