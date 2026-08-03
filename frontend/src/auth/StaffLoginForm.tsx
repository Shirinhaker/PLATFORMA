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
        firm_login: firmLogin,
        login,
        password,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Kirish amalga oshmadi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-card">
      <p className="session-panel__eyebrow">Xodim kirishi</p>
      <h1>Firma kabinetiga kirish</h1>
      <p>Rahbar bergan firma logini, shaxsiy login va yangi parolni kiriting.</p>
      <form onSubmit={(event) => void submit(event)}>
        <label>
          Firma logini
          <input
            autoComplete="organization"
            value={firmLogin}
            onChange={(event) => setFirmLogin(event.target.value.toLowerCase())}
            required
          />
        </label>
        <label>
          Xodim logini
          <input
            autoComplete="username"
            value={login}
            onChange={(event) => setLogin(event.target.value.toLowerCase())}
            required
          />
        </label>
        <label>
          Xodim paroli
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Kirilmoqda…" : "Kirish"}
        </button>
        <button type="button" className="button-secondary" onClick={onBack}>
          Orqaga
        </button>
      </form>
    </main>
  );
}
