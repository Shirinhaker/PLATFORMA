import { useEffect, useState } from "react";

import type { ApiClient, BuildInfo } from "../api/client";
import "./App.css";


type BuildApi = Pick<ApiClient, "getBuild">;


function CheckIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="24" r="22" />
      <path d="m14 24 7 7 14-15" />
    </svg>
  );
}


function FoundationStatus({ build }: { build: BuildInfo }) {
  return (
    <main className="foundation">
      <div className="foundation__status-icon">
        <CheckIcon />
      </div>
      <h1>Koprik yangi platforma foundation’i tayyor</h1>
      <p className="foundation__phase">Phase 1</p>
      <dl className="foundation__facts">
        <div>
          <dt>API</dt>
          <dd>API {build.api_version}</dd>
        </div>
        <div>
          <dt>Faol interfeys</dt>
          <dd>Eski faol BUILD: {build.legacy_build}</dd>
        </div>
      </dl>
      <aside className="foundation__notice">
        <strong>Yangi texnik foundation ichki foydalanish uchun tayyor.</strong>
        <span>Mavjud production UI va jarayonlar o‘z holicha davom etadi.</span>
      </aside>
    </main>
  );
}


export function App({ api }: { api: BuildApi }) {
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api.getBuild()
      .then((value) => {
        if (active) setBuild(value);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [api]);

  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <span>Koprik</span>
      </header>
      {failed ? (
        <main className="foundation foundation--message" role="alert">
          Yangi platforma foundation’iga ulanib bo‘lmadi.
        </main>
      ) : build === null ? (
        <main className="foundation foundation--message">Yuklanmoqda…</main>
      ) : (
        <FoundationStatus build={build} />
      )}
    </div>
  );
}
