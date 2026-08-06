import { useState } from "react";

import type { AdminApiClient } from "./admin-client";


type Props = {
  api: Pick<AdminApiClient, "startLogin" | "verifyLogin">;
  onSignedIn(telegramUserId: number): void;
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}


export function AdminLogin({ api, onSignedIn }: Props) {
  const [challengeId, setChallengeId] = useState<number | null>(null);
  const [telegramId, setTelegramId] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function sendCode(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNote("");
    try {
      const started = await api.startLogin(Number(telegramId));
      setChallengeId(started.challenge_id);
      setNote("Kod Telegramga yuborildi.");
    } catch (error) {
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function signIn(event: React.FormEvent) {
    event.preventDefault();
    if (challengeId === null) return;
    setBusy(true);
    setNote("");
    try {
      const identity = await api.verifyLogin(challengeId, code);
      onSignedIn(identity.telegram_user_id);
    } catch (error) {
      setNote(message(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="login-shell">
      <div className="login-brand">
        <span className="brand-mark">K</span>
        <strong>Ko‘prik</strong>
        <small>ADMIN</small>
      </div>
      <div className="login-card">
        <div className="eyebrow">XAVFSIZ KIRISH</div>
        <h1>Admin paneli</h1>
        <p>
          Bir martalik kod faqat ruxsat berilgan Telegram ID’ga yuboriladi.
        </p>

        {challengeId === null ? (
          <form onSubmit={(event) => void sendCode(event)}>
            <label htmlFor="tgId">Telegram ID</label>
            <input
              id="tgId"
              inputMode="numeric"
              autoComplete="username"
              required
              value={telegramId}
              onChange={(event) => setTelegramId(event.target.value)}
            />
            <button type="submit" disabled={busy || !telegramId.trim()}>
              Kod yuborish
            </button>
          </form>
        ) : (
          <form onSubmit={(event) => void signIn(event)}>
            <label htmlFor="code">6 xonali kod</label>
            <input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
            <button type="submit" disabled={busy || code.length !== 6}>
              Kirish
            </button>
          </form>
        )}

        {note ? (
          <div className="message" role="status">{note}</div>
        ) : null}
      </div>
    </section>
  );
}
