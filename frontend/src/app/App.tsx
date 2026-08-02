import { useCallback, useEffect, useMemo, useReducer, useState } from "react";

import type { ApiClient } from "../api/client";
import type { PublicFeatures, SessionIdentity } from "../api/types";
import { AuthFlow, type AuthApi } from "../auth/AuthFlow";
import type { AppSession } from "../auth/types";
import { CatalogScreen } from "../legacy/public/CatalogScreen";
import { CategoryScreen } from "../legacy/public/CategoryScreen";
import { findCatalogDirection } from "../legacy/public/catalog-data";
import { HomeScreen } from "../legacy/public/HomeScreen";
import { LocationScreen } from "../legacy/public/LocationScreen";
import { PublicProfileV1656 } from "../legacy/public/PublicProfileV1656";
import { ListingPageV1656 } from "../listings/ListingPageV1656";
import { PublicListingsV1656 } from "../listings/PublicListingsV1656";
import { CartV1656 } from "../orders/CartV1656";
import {
  addCartItem,
  cartLineCount,
  type CartState,
} from "../orders/order-store";
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
import {
  QueueBookingV1656,
  supportsQueueBookingApi,
  type QueueBookingApi,
  type QueueBookingTarget,
} from "../queues/QueueBookingV1656";


type SessionApi = Pick<ApiClient, "getSession">;
type ProfileApi = UserProfileApi & BusinessProfileApi;
type PublicSearchApi = Pick<
  ApiClient,
  | "searchPublic"
  | "getCatalogItems"
  | "getAdvertisements"
  | "getPublicFeatures"
  | "getHomeMap"
  | "getDistrictOffers"
  | "getFollowedProfiles"
  | "getPublicProfile"
  | "recordAdvertisementViews"
  | "recordAdvertisementClick"
  | "getListingCounts"
  | "getPublicListings"
  | "getPublicListing"
  | "toggleListingSave"
>;
type OrderApi = Pick<ApiClient, "createOrder">;
type AppApi = (
  SessionApi
  & Partial<AuthApi>
  & Partial<ProfileApi>
  & Partial<PublicSearchApi>
  & Partial<OrderApi>
  & Partial<QueueBookingApi>
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
    "switchCabinet",
    "logout",
  ].every((method) => typeof api[method as keyof AppApi] === "function");
}


function Cabinet({ kind, name }: { kind: "user" | "business"; name: string }) {
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
  const initialLocation = useMemo(() => readHomeLocation(), []);
  const [session, setSession] = useState<AppSession>({ status: "loading" });
  const [failed, setFailed] = useState(false);
  const [homeSearchResultsActive, setHomeSearchResultsActive] = useState(false);
  const [openedProfile, setOpenedProfile] = useState<{
    kind: "user" | "business";
    publicId: string;
    title: string;
  } | null>(null);
  const [openedListing, setOpenedListing] = useState<{
    publicId: string;
    title: string;
  } | null>(null);
  const [carts, setCarts] = useState<CartState>({});
  const [cartFilter, setCartFilter] = useState<string | null>(null);
  const [orderCustomer, setOrderCustomer] = useState({ phone: "", address: "" });
  const [queueBooking, setQueueBooking] = useState<QueueBookingTarget | null>(null);
  const [queueMessage, setQueueMessage] = useState({ id: 0, text: "" });
  const [authReason, setAuthReason] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(() => (
    document.documentElement.dataset.theme === "dark" ? "dark" : "light"
  ));
  const [attempt, setAttempt] = useState(0);
  const [navigation, dispatch] = useReducer(
    publicNavigationReducer,
    initialLocation
      ? initialPublicNavigationState
      : { ...initialPublicNavigationState, view: "location" },
  );
  const [homeLocation, setHomeLocation] = useState<HomeLocation | null>(
    initialLocation,
  );
  const [publicFeatures, setPublicFeatures] = useState<PublicFeatures>({
    listings: false,
    stories: false,
    chat: false,
    systemization: false,
    taxi: false,
  });
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
  const getHomeMap = useMemo(() => (
    typeof api.getHomeMap === "function" ? api.getHomeMap.bind(api) : undefined
  ), [api]);
  const getDistrictOffers = useMemo(() => (
    typeof api.getDistrictOffers === "function"
      ? api.getDistrictOffers.bind(api)
      : undefined
  ), [api]);
  const getFollowedProfiles = useMemo(() => (
    typeof api.getFollowedProfiles === "function"
      ? api.getFollowedProfiles.bind(api)
      : undefined
  ), [api]);
  const getPublicProfile = useMemo(() => (
    typeof api.getPublicProfile === "function"
      ? api.getPublicProfile.bind(api)
      : undefined
  ), [api]);
  const recordAdvertisementViews = useMemo(() => (
    typeof api.recordAdvertisementViews === "function"
      ? api.recordAdvertisementViews.bind(api)
      : undefined
  ), [api]);
  const recordAdvertisementClick = useMemo(() => (
    typeof api.recordAdvertisementClick === "function"
      ? api.recordAdvertisementClick.bind(api)
      : undefined
  ), [api]);
  const getPublicListing = useMemo(() => (
    typeof api.getPublicListing === "function"
      ? api.getPublicListing.bind(api)
      : undefined
  ), [api]);
  const createOrder = useMemo(() => (
    typeof api.createOrder === "function"
      ? api.createOrder.bind(api)
      : async () => {
          throw new Error("Buyurtma xizmati hozircha ulanmagan.");
        }
  ), [api]);
  const listingApi = useMemo(() => (
    typeof api.getListingCounts === "function"
    && typeof api.getPublicListings === "function"
    && typeof api.toggleListingSave === "function"
      ? {
          getListingCounts: api.getListingCounts.bind(api),
          getPublicListings: api.getPublicListings.bind(api),
          toggleListingSave: api.toggleListingSave.bind(api),
        }
      : undefined
  ), [api]);

  useEffect(() => {
    if (typeof api.getPublicFeatures !== "function") return undefined;
    let active = true;
    api.getPublicFeatures()
      .then((features) => {
        if (active) setPublicFeatures(features);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    let active = true;
    setFailed(false);
    setSession({ status: "loading" });
    api.getSession()
      .then((identity) => {
        if (!active) return;
        setSession({ status: identity.account_type, identity });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const status = (
          error
          && typeof error === "object"
          && "status" in error
          && typeof error.status === "number"
        ) ? error.status : 0;
        setSession({ status: "guest" });
        if (status !== 401) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [api, attempt]);

  useEffect(() => {
    let active = true;
    if (session.status === "user" && typeof api.getUserProfile === "function") {
      api.getUserProfile().then((profile) => {
        if (!active) return;
        setOrderCustomer({
          phone: profile.phone || "",
          address: [profile.region, profile.district, profile.mahalla]
            .filter(Boolean)
            .join(", "),
        });
      }).catch(() => undefined);
    } else if (
      session.status === "business"
      && typeof api.getBusinessProfile === "function"
    ) {
      api.getBusinessProfile().then((profile) => {
        if (active) setOrderCustomer({
          phone: profile.phone || "",
          address: profile.address || "",
        });
      }).catch(() => undefined);
    } else if (session.status === "guest") {
      setOrderCustomer({ phone: "", address: "" });
    }
    return () => {
      active = false;
    };
  }, [api, session.status]);

  useEffect(() => {
    if (!queueMessage.text) return;
    const timeout = window.setTimeout(() => {
      setQueueMessage((current) => current.id === queueMessage.id
        ? { ...current, text: "" }
        : current);
    }, 2600);
    return () => window.clearTimeout(timeout);
  }, [queueMessage]);

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
    cabinet: "Mening kabinetim",
    catalog: "Katalog",
    category: category?.name ?? "Yo‘nalish",
    home: undefined,
    listings: "E’lonlar",
    location: "Manzil",
    cart: "Savat",
  };
  const title = titles[navigation.view];

  function openHome() {
    setOpenedProfile(null);
    setOpenedListing(null);
    setCartFilter(null);
    setQueueBooking(null);
    setAuthReason("");
    dispatch({ type: homeLocation ? "GO_HOME" : "OPEN_LOCATION" });
  }

  const openPublicResult = useCallback((
    kind: "user" | "business" | "product" | "service" | "listing",
    publicId: string,
  ) => {
    if ((kind === "user" || kind === "business") && getPublicProfile) {
      setOpenedListing(null);
      setOpenedProfile({ kind, publicId, title: "Profil" });
      setHomeSearchResultsActive(false);
    } else if (kind === "listing" && getPublicListing) {
      setOpenedProfile(null);
      setOpenedListing({ publicId, title: "E’lon" });
      setHomeSearchResultsActive(false);
    }
  }, [getPublicListing, getPublicProfile]);

  const updateOpenedProfileTitle = useCallback((title: string) => {
    setOpenedProfile((current) => (
      current ? { ...current, title } : current
    ));
  }, []);
  const updateOpenedListingTitle = useCallback((title: string) => {
    setOpenedListing((current) => current ? { ...current, title } : current);
  }, []);

  const showQueueMessage = useCallback((text: string) => {
    setQueueMessage((current) => ({ id: current.id + 1, text }));
  }, []);

  const openAuth = useCallback((reason = "") => {
    setAuthReason(reason);
    dispatch({ type: "OPEN_AUTH" });
  }, []);

  const openQueueBooking = useCallback((target: QueueBookingTarget) => {
    if (session.status === "guest") {
      openAuth("Navbat olish");
      return;
    }
    if (session.status !== "user") {
      showQueueMessage("Avval oddiy profilga o'ting.");
      return;
    }
    if (!supportsQueueBookingApi(api)) {
      showQueueMessage("Navbat xizmati hozircha ulanmagan.");
      return;
    }
    setQueueBooking(target);
  }, [api, openAuth, session.status, showQueueMessage]);

  function toggleTheme() {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      return next;
    });
  }

  function completeAuthentication(identity: SessionIdentity) {
    setAuthReason("");
    setSession({ status: identity.account_type, identity });
    dispatch({ type: "OPEN_CABINET" });
  }

  function renderAccount() {
    if (session.status === "guest") {
      return supportsAuthFlow(api) ? (
        <AuthFlow
          api={api}
          onAuthenticated={completeAuthentication}
          reason={authReason}
        />
      ) : (
        <main className="session-panel"><h1>Koprik’ga kirish</h1></main>
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
      const switched = (identity: SessionIdentity) => {
        setSession({ status: identity.account_type, identity });
        dispatch({ type: "OPEN_CABINET" });
      };
      return session.status === "user" ? (
        <UserProfile
          api={api}
          identity={session.identity}
          onLogout={logout}
          onOpenPublicListing={(publicId) => {
            setOpenedProfile(null);
            setOpenedListing({ publicId, title: "E’lon" });
            dispatch({ type: "GO_HOME" });
          }}
          onSwitched={switched}
        />
      ) : (
        <BusinessProfile
          api={api}
          identity={session.identity}
          onLogout={logout}
          onSwitched={switched}
        />
      );
    }
    return <Cabinet kind={session.status} name={session.identity.name} />;
  }

  function renderPublicContent() {
    if (navigation.view === "home" && openedListing && getPublicListing) {
      return (
        <ListingPageV1656
          authenticated={authenticated}
          getPublicListing={getPublicListing}
          publicId={openedListing.publicId}
          toggleListingSave={listingApi?.toggleListingSave}
          onNeedLogin={() => openAuth()}
          onOpenOwner={(kind, publicId) => {
            setOpenedListing(null);
            setOpenedProfile({ kind, publicId, title: "Profil" });
          }}
          onTitleChange={updateOpenedListingTitle}
        />
      );
    }
    if (
      navigation.view === "home"
      && openedProfile
      && getPublicProfile
    ) {
      return (
        <PublicProfileV1656
          authenticated={authenticated}
          cart={carts[openedProfile.publicId]}
          kind={openedProfile.kind}
          publicId={openedProfile.publicId}
          getPublicProfile={getPublicProfile}
          onAddCartItem={(item, provider) => {
            setCarts((current) => addCartItem(current, provider, item));
          }}
          onBookQueue={openQueueBooking}
          onNeedLogin={() => openAuth()}
          onNeedQueueLogin={() => openAuth("Navbat olish")}
          onOpenCart={() => {
            setCartFilter(openedProfile.publicId);
            dispatch({ type: "OPEN_CART" });
          }}
          onOpenListing={(publicId) => {
            setOpenedProfile(null);
            setOpenedListing({ publicId, title: "E’lon" });
          }}
          onQueueMessage={showQueueMessage}
          onTitleChange={updateOpenedProfileTitle}
        />
      );
    }
    switch (navigation.view) {
      case "catalog":
        return (
          <CatalogScreen
            authenticated={authenticated}
            initialQuery={navigation.query}
            location={homeLocation}
            searchPublic={searchPublic}
            getCatalogItems={getCatalogItems}
            onBookQueue={openQueueBooking}
            onNeedQueueLogin={() => openAuth("Navbat olish")}
            onOpenOwner={(publicId) => {
              setOpenedProfile({ kind: "business", publicId, title: "Profil" });
              dispatch({ type: "GO_HOME" });
            }}
            onOpenCategory={(categoryId) => dispatch({
              type: "OPEN_CATEGORY",
              categoryId,
            })}
            onQueueMessage={showQueueMessage}
          />
        );
      case "category":
        return (
          <CategoryScreen
            authenticated={authenticated}
            categoryId={navigation.categoryId ?? ""}
            searchPublic={searchPublic}
            getCatalogItems={getCatalogItems}
            onBookQueue={openQueueBooking}
            onNeedQueueLogin={() => openAuth("Navbat olish")}
            onOpenOwner={(publicId) => {
              setOpenedProfile({ kind: "business", publicId, title: "Profil" });
              dispatch({ type: "GO_HOME" });
            }}
            onQueueMessage={showQueueMessage}
          />
        );
      case "location":
        return (
          <LocationScreen
            initialLocation={homeLocation}
            onSaved={(location) => {
              setHomeLocation(location);
              dispatch({ type: "GO_HOME" });
            }}
          />
        );
      case "listings":
        return listingApi ? (
          <PublicListingsV1656
            api={listingApi}
            authenticated={authenticated}
            onNeedLogin={() => openAuth()}
            onOpenOwner={(kind, publicId) => {
              setOpenedListing(null);
              setOpenedProfile({ kind, publicId, title: "Profil" });
              dispatch({ type: "GO_HOME" });
            }}
          />
        ) : (
          <main className="screen active" data-screen="listings" />
        );
      case "cart":
        return (
          <CartV1656
            authenticated={authenticated}
            carts={carts}
            createOrder={createOrder}
            customer={orderCustomer}
            filterProviderPublicId={cartFilter}
            homeLocation={homeLocation}
            onCartsChange={setCarts}
            onNeedLogin={() => openAuth()}
          />
        );
      case "auth":
      case "cabinet":
        return renderAccount();
      case "home":
        return (
          <HomeScreen
            authenticated={authenticated}
            currentDistrict={homeLocation?.district}
            getAdvertisements={getAdvertisements}
            getDistrictOffers={getDistrictOffers}
            getFollowedProfiles={getFollowedProfiles}
            getHomeMap={getHomeMap}
            location={homeLocation}
            searchPublic={searchPublic}
            onOpenCatalog={() => dispatch({ type: "OPEN_CATALOG", query: "" })}
            onOpenLocation={() => dispatch({ type: "OPEN_LOCATION" })}
            onOpenPublicResult={openPublicResult}
            onResultsActiveChange={setHomeSearchResultsActive}
            recordAdvertisementClick={recordAdvertisementClick}
            recordAdvertisementViews={recordAdvertisementViews}
          />
        );
    }
  }

  return (
    <AppShell
      authenticated={authenticated}
      title={(openedProfile || openedListing) && navigation.view === "home"
        ? openedProfile?.title ?? openedListing?.title
        : title}
      isHome={navigation.view === "home" && !openedProfile && !openedListing}
      searchResultsActive={(
        navigation.view === "home" && homeSearchResultsActive
      )}
      publicFeatures={publicFeatures}
      cartCount={cartLineCount(carts)}
      theme={theme}
      onHome={openHome}
      onLocation={() => {
        setOpenedProfile(null);
        setOpenedListing(null);
        dispatch({ type: "OPEN_LOCATION" });
      }}
      onAccount={() => {
        setOpenedProfile(null);
        setOpenedListing(null);
        setAuthReason("");
        dispatch({
          type: authenticated ? "OPEN_CABINET" : "OPEN_AUTH",
        });
      }}
      onBack={() => {
        if (navigation.view === "cart") {
          dispatch({ type: homeLocation ? "BACK" : "OPEN_LOCATION" });
          return;
        }
        if (openedListing) {
          setOpenedListing(null);
          return;
        }
        if (openedProfile) {
          setOpenedProfile(null);
          return;
        }
        dispatch({ type: homeLocation ? "BACK" : "OPEN_LOCATION" });
      }}
      onListings={() => {
        setOpenedProfile(null);
        setOpenedListing(null);
        dispatch({ type: "OPEN_LISTINGS" });
      }}
      onCart={() => {
        setOpenedProfile(null);
        setOpenedListing(null);
        setCartFilter(null);
        dispatch({ type: "OPEN_CART" });
      }}
      onToggleTheme={toggleTheme}
    >
      <>
        <div className="app-shell__content" tabIndex={-1}>
          {failed && accountView ? (
            <SessionStatus
              state="error"
              onRetry={() => setAttempt((value) => value + 1)}
            />
          ) : renderPublicContent()}
        </div>
        {queueBooking && supportsQueueBookingApi(api) ? (
          <QueueBookingV1656
            api={api}
            key={`${queueBooking.businessPublicId}:${queueBooking.itemPublicId}`}
            target={queueBooking}
            onClose={() => setQueueBooking(null)}
            onMessage={showQueueMessage}
          />
        ) : null}
        {queueMessage.text ? (
          <div className="app-toast on" role="status">{queueMessage.text}</div>
        ) : null}
      </>
    </AppShell>
  );
}
