import { useState } from "react";

import type { ChallengeStarted } from "../api/types";
import type { AuthApi } from "./AuthFlow";


type Props = {
  api: AuthApi;
  onStarted: (challenge: ChallengeStarted) => void;
  onBack: () => void;
};


function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function LoginForm({ api, onStarted, onBack }: Props) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onStarted(await api.startLogin({ login, password }));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-card auth-form" onSubmit={submit}>
      <div>
        <p className="session-panel__eyebrow">Koprik</p>
        <h1>Kirish</h1>
        <p>Akkaunt turi login orqali avtomatik aniqlanadi.</p>
      </div>
      <label>
        Login
        <input
          autoComplete="username"
          required
          value={login}
          onChange={(event) => setLogin(event.currentTarget.value)}
        />
      </label>
      <label>
        Parol
        <input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.currentTarget.value)}
        />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? "Tekshirilmoqda…" : "Davom etish"}
      </button>
      <button type="button" className="button-secondary" onClick={onBack}>
        Orqaga
      </button>
    </form>
  );
}
