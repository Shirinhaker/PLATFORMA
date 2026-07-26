import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import { AuthFlow, type AuthApi } from "../auth/AuthFlow";
import type { AppSession } from "../auth/types";
import {
  BusinessProfile,
  type BusinessProfileApi,
} from "../profiles/BusinessProfile";
import {
  UserProfile,
  type UserProfileApi,
} from "../profiles/UserProfile";
import "./App.css";


type SessionApi = Pick<ApiClient, "getSession">;
type ProfileApi = UserProfileApi & BusinessProfileApi;
type AppApi = SessionApi & Partial<AuthApi> & Partial<ProfileApi>;


function supportsAuthFlow(api: AppApi): api is SessionApi & AuthApi {
  return [
    "startRegistration",
    "startLogin",
    "verifyRegistration",
    "verifyLogin",
    "resendChallenge",
  ].every((method) => typeof api[method as keyof AppApi] === "function");
}


function supportsProfiles(api: AppApi): api is SessionApi & ProfileApi {
  return [
    "getUserProfile",
    "updateUserProfile",
    "getBusinessProfile",
    "updateBusinessProfile",
    "createUploadGrant",
    "uploadGrantedFile",
    "attachUserAvatar",
    "attachBusinessLogo",
    "logout",
  ].every((method) => typeof api[method as keyof AppApi] === "function");
}


function Cabinet({
  kind,
  name,
}: {
  kind: "user" | "business";
  name: string;
}) {
  const title = kind === "user" ? "Oddiy kabinet" : "Biznes kabinet";
  return (
    <main className="session-panel">
      <p className="session-panel__eyebrow">Koprik Phase 2</p>
      <h1>{title}</h1>
      <p>{name}</p>
    </main>
  );
}


export function App({ api }: { api: AppApi }) {
  const [session, setSession] = useState<AppSession>({ status: "loading" });
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setFailed(false);
    setSession({ status: "loading" });
    api.getSession()
      .then((identity) => {
        if (!active) return;
        setSession({
          status: identity.account_type,
          identity,
        });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const status = (
          error
          && typeof error === "object"
          && "status" in error
          && typeof error.status === "number"
        ) ? error.status : 0;
        if (status === 401) {
          setSession({ status: "guest" });
          return;
        }
        setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [api, attempt]);

  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <span>Koprik</span>
      </header>
      {failed ? (
        <main className="session-panel session-panel--message" role="alert">
          <p>Server bilan bog‘lanib bo‘lmadi.</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>
            Qayta urinish
          </button>
        </main>
      ) : session.status === "loading" ? (
        <main className="session-panel session-panel--message">
          Yuklanmoqda…
        </main>
      ) : session.status === "guest" ? (
        supportsAuthFlow(api) ? (
          <AuthFlow
            api={api}
            onAuthenticated={(identity) => setSession({
              status: identity.account_type,
              identity,
            })}
          />
        ) : (
          <main className="session-panel">
            <h1>Koprik’ga kirish</h1>
          </main>
        )
      ) : supportsProfiles(api) ? (
        session.status === "user" ? (
          <UserProfile
            api={api}
            identity={session.identity}
            onLogout={() => setSession({ status: "guest" })}
          />
        ) : (
          <BusinessProfile
            api={api}
            identity={session.identity}
            onLogout={() => setSession({ status: "guest" })}
          />
        )
      ) : (
        <Cabinet kind={session.status} name={session.identity.name} />
      )}
    </div>
  );
}
