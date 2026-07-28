import { useEffect, useRef, useState } from "react";

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
import { AppShell } from "./AppShell";
import { SessionStatus } from "./SessionStatus";


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
      <p className="session-panel__eyebrow">Koprik</p>
      <h1>{title}</h1>
      <p>{name}</p>
    </main>
  );
}


export function App({ api }: { api: AppApi }) {
  const [session, setSession] = useState<AppSession>({ status: "loading" });
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

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

  const authenticated = (
    session.status === "user" || session.status === "business"
  );

  function focusContent() {
    contentRef.current?.focus();
  }

  return (
    <AppShell
      authenticated={authenticated}
      onCabinet={focusContent}
      onLogin={focusContent}
    >
      <div
        className="app-shell__content"
        ref={contentRef}
        tabIndex={-1}
      >
        {failed ? (
          <SessionStatus
            state="error"
            onRetry={() => setAttempt((value) => value + 1)}
          />
        ) : session.status === "loading" ? (
          <SessionStatus state="loading" />
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
        )
        }
      </div>
    </AppShell>
  );
}
