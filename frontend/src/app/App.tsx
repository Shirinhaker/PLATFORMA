import { useEffect, useMemo, useReducer, useState } from "react";

import type { ApiClient } from "../api/client";
import type { SessionIdentity } from "../api/types";
import { AuthFlow, type AuthApi } from "../auth/AuthFlow";
import type { AppSession } from "../auth/types";
import { CatalogScreen } from "../legacy/public/CatalogScreen";
import { CategoryScreen } from "../legacy/public/CategoryScreen";
import { findCatalogDirection } from "../legacy/public/catalog-data";
import { HomeScreen } from "../legacy/public/HomeScreen";
import { LocationScreen } from "../legacy/public/LocationScreen";
import {
  readHomeLocation,
  type HomeLocation,
} from "../legacy/public/location-storage";
import {
  initialPublicNavigationState,
  publicNavigationReducer,
} from "../legacy/public/public-navigation";
import type { PublicView } from "../legacy/public/public-contract";
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
type PublicSearchApi = Pick<
  ApiClient,
  "searchPublic" | "getCatalogItems" | "getAdvertisements"
>;
type AppApi = (
  SessionApi
  & Partial<AuthApi>
  & Partial<ProfileApi>
  & Partial<PublicSearchApi>
);


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
  const [navigation, dispatch] = useReducer(
    publicNavigationReducer,
    initialPublicNavigationState,
  );
  const [homeLocation, setHomeLocation] = useState<HomeLocation | null>(
    () => readHomeLocation(),
  );
  const searchPublic = useMemo(() => (
    typeof api.searchPublic === "function"
      ? api.searchPublic.bind(api)
      : undefined
  ), [api]);
  const getCatalogItems = useMemo(() => (
    typeof api.getCatalogItems === "function"
      ? api.getCatalogItems.bind(api)
      : undefined
  ), [api]);
  const getAdvertisements = useMemo(() => (
    typeof api.getAdvertisements === "function"
      ? api.getAdvertisements.bind(api)
      : undefined
  ), [api]);

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
        setSession({ status: "guest" });
        setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [api, attempt]);

  const authenticated = (
    session.status === "user" || session.status === "business"
  );
  const accountView = (
    navigation.view === "auth" || navigation.view === "cabinet"
  );

  const category = navigation.categoryId
    ? findCatalogDirection(navigation.categoryId)
    : null;
  const titles: Record<PublicView, string | undefined> = {
    auth: "Kirish",
    cabinet: "Kabinet",
    catalog: "Katalog",
    category: category?.name ?? "Yo‘nalish",
    home: undefined,
    location: "Manzil",
  };
  const title = titles[navigation.view];

  function openHome() {
    dispatch({ type: "GO_HOME" });
  }

  function completeAuthentication(identity: SessionIdentity) {
    setSession({
      status: identity.account_type,
      identity,
    });
    dispatch({ type: "OPEN_CABINET" });
  }

  function renderAccount() {
    if (session.status === "guest") {
      return supportsAuthFlow(api) ? (
        <AuthFlow api={api} onAuthenticated={completeAuthentication} />
      ) : (
        <main className="session-panel">
          <h1>Koprik’ga kirish</h1>
        </main>
      );
    }

    if (session.status === "loading") {
      return <SessionStatus state="loading" />;
    }

    if (supportsProfiles(api)) {
      const logout = () => {
        setSession({ status: "guest" });
        openHome();
      };

      return session.status === "user" ? (
        <UserProfile
          api={api}
          identity={session.identity}
          onLogout={logout}
        />
      ) : (
        <BusinessProfile
          api={api}
          identity={session.identity}
          onLogout={logout}
        />
      );
    }

    return <Cabinet kind={session.status} name={session.identity.name} />;
  }

  function renderPublicContent() {
    switch (navigation.view) {
      case "catalog":
        return (
          <CatalogScreen
            initialQuery={navigation.query}
            location={homeLocation}
            searchPublic={searchPublic}
            getCatalogItems={getCatalogItems}
            onOpenCategory={(categoryId) => dispatch({
              type: "OPEN_CATEGORY",
              categoryId,
            })}
          />
        );
      case "category":
        return (
          <CategoryScreen
            categoryId={navigation.categoryId ?? ""}
            searchPublic={searchPublic}
            getCatalogItems={getCatalogItems}
          />
        );
      case "location":
        return (
          <LocationScreen
            initialLocation={homeLocation}
            onSaved={(location) => {
              setHomeLocation(location);
              openHome();
            }}
          />
        );
      case "auth":
      case "cabinet":
        return renderAccount();
      case "home":
        return (
          <HomeScreen
            currentDistrict={homeLocation?.district}
            getAdvertisements={getAdvertisements}
            location={homeLocation}
            onSearch={(query) => dispatch({ type: "OPEN_CATALOG", query })}
            onOpenCatalog={() => dispatch({
              type: "OPEN_CATALOG",
              query: "",
            })}
            onOpenLocation={() => dispatch({ type: "OPEN_LOCATION" })}
          />
        );
    }
  }

  return (
    <AppShell
      authenticated={authenticated}
      title={title}
      isHome={navigation.view === "home"}
      onHome={openHome}
      onLocation={() => dispatch({ type: "OPEN_LOCATION" })}
      onAccount={() => dispatch({
        type: authenticated ? "OPEN_CABINET" : "OPEN_AUTH",
      })}
      onBack={() => dispatch({ type: "BACK" })}
    >
      <div className="app-shell__content" tabIndex={-1}>
        {failed && accountView ? (
          <SessionStatus
            state="error"
            onRetry={() => setAttempt((value) => value + 1)}
          />
        ) : renderPublicContent()}
      </div>
    </AppShell>
  );
}
