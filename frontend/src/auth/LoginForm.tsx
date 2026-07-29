import { useState } from "react";

import type { AccountType, ChallengeStarted } from "../api/types";
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
  const [cabinetType, setCabinetType] = useState<"" | AccountType>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        login,
        password,
        ...(cabinetType ? { cabinet_type: cabinetType } : {}),
      };
      onStarted(await api.startLogin(payload));
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
        <p>
          Bitta login ikkala kabinetga tegishli bo‘lsa, kabinet turini tanlang.
        </p>
      </div>
      <label>
        Kabinet turi
        <select
          value={cabinetType}
          onChange={(event) => setCabinetType(
            event.currentTarget.value as "" | AccountType,
          )}
        >
          <option value="">Avtomatik aniqlash</option>
          <option value="user">Oddiy kabinet</option>
          <option value="business">Biznes kabinet</option>
        </select>
      </label>
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
