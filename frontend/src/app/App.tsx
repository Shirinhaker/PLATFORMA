import { useCallback, useEffect, useMemo, useRef, useReducer, useState } from "react";

import type { PublicFeatures, SessionIdentity } from "../api/types";
import type { AppSession } from "../auth/types";
import type { CourseEnrollmentTarget } from "../education/CourseEnrollment";
import { usePersistentCart } from "../orders/use-persistent-cart";
import {
  useNavigationHistory,
  type NavigationSnapshot,
} from "./use-navigation-history";
import { usePublicApi } from "./use-public-api";
import { readHomeLocation, type HomeLocation } from "../legacy/public/location-storage";
import {
  initialPublicNavigationState,
  publicNavigationReducer,
} from "../legacy/public/public-navigation";
import "./App.css";
import {
  supportsQueueBookingApi,
  type QueueBookingTarget,
} from "../queues/QueueBooking";
import type { HomeSearchMemory } from "../legacy/public/home/home-search-memory";
import type { AuthIntent } from "./auth-intent";
import type { MessagePeer } from "../messages/Messages";
import { useOrderCustomerProfile } from "./use-order-customer-profile";
import { AccountContent } from "./AccountContent";
import { CatalogResultDialog } from "./CatalogResultDialog";
import { AppFrame } from "./AppFrame";
import type { AppApi } from "./app-api";
import { appTitle } from "./app-title";
import { type OpenedListing, type OpenedProfile, PublicContent } from "./PublicContent";

export function App({ api }: { api: AppApi }) {
  const initialLocation = useMemo(() => readHomeLocation(), []);
  const sharedUserId = useMemo(() => {
    const value = new URLSearchParams(window.location.search).get("user") ?? "";
    return /^u_[0-9a-f]{16}$/.test(value) ? value : "";
  }, []);
  const [session, setSession] = useState<AppSession>({ status: "loading" });
  const [failed, setFailed] = useState(false);
  const searchMemory = useRef<HomeSearchMemory | null>(null);
  const [, refreshSearchSnapshot] = useReducer((value: number) => value + 1, 0);
  const [homeRevision, setHomeRevision] = useState(0);
  const [homeSearchResultsActive, setHomeSearchResultsActive] = useState(false);
  const [openedProfile, setOpenedProfile] = useState<OpenedProfile | null>(null);
  const [openedItemId, setOpenedItemId] = useState<string | null>(null);
  const [openedListing, setOpenedListing] = useState<OpenedListing | null>(null);
  const [openedChat, setOpenedChat] = useState<MessagePeer | null>(null);
  const [carts, setCarts] = usePersistentCart(session);
  const [cartFilter, setCartFilter] = useState<string | null>(null);
  const orderCustomer = useOrderCustomerProfile(api, session);
  const [queueBooking, setQueueBooking] = useState<QueueBookingTarget | null>(null);
  const [courseEnrollment, setCourseEnrollment] =
    useState<CourseEnrollmentTarget | null>(null);
  const [queueMessage, setQueueMessage] = useState({ id: 0, text: "" });
  const [authReason, setAuthReason] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );
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
  const {
    searchPublic,
    getCatalogItems,
    getAdvertisements,
    getHomeMap,
    getDistrictOffers,
    getFollowedProfiles,
    getPublicProfile,
    recordAdvertisementViews,
    recordAdvertisementClick,
    getPublicListing,
    createOrder,
    listingApi,
    storyApi,
  } = usePublicApi(api);
  useEffect(() => {
    if (!sharedUserId || !getPublicProfile) return;
    setOpenedListing(null);
    setOpenedProfile({
      kind: "user",
      publicId: sharedUserId,
      title: "Profil",
    });
    dispatch({ type: "GO_HOME" });
  }, [getPublicProfile, sharedUserId]);
  useEffect(() => {
    if (typeof api.getPublicFeatures !== "function") return undefined;
    let active = true;
    api
      .getPublicFeatures()
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
    api
      .getSession()
      .then((identity) => {
        if (!active) return;
        setSession({ status: identity.account_type, identity });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const status =
          error &&
          typeof error === "object" &&
          "status" in error &&
          typeof error.status === "number"
            ? error.status
            : 0;
        setSession({ status: "guest" });
        if (status !== 401) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [api, attempt]);

  useEffect(() => {
    if (!queueMessage.text) return;
    const timeout = window.setTimeout(() => {
      setQueueMessage((current) =>
        current.id === queueMessage.id ? { ...current, text: "" } : current,
      );
    }, 2600);
    return () => window.clearTimeout(timeout);
  }, [queueMessage]);

  const authenticated = session.status === "user" || session.status === "business";
  const accountView = navigation.view === "auth" || navigation.view === "cabinet";
  const title = appTitle(navigation);

  function openHome() {
    searchMemory.current = null;
    setHomeRevision((value) => value + 1);
    setHomeSearchResultsActive(false);
    setOpenedItemId(null);
    setOpenedProfile(null);
    setOpenedListing(null);
    setOpenedChat(null);
    setCartFilter(null);
    setQueueBooking(null);
    setCourseEnrollment(null);
    setAuthReason("");
    authReturn.current = null;
    dispatch({ type: homeLocation ? "GO_HOME" : "OPEN_LOCATION" });
  }

  const openPublicResult = useCallback(
    (
      kind: "user" | "business" | "product" | "service" | "listing",
      publicId: string,
      ownerPublicId?: string,
    ) => {
      if ((kind === "user" || kind === "business") && getPublicProfile) {
        setOpenedListing(null);
        setOpenedChat(null);
        setOpenedProfile({ kind, publicId, title: "Profil" });
        setHomeSearchResultsActive(false);
      } else if (
        (kind === "product" || kind === "service") &&
        ownerPublicId &&
        getPublicProfile
      ) {
        setOpenedListing(null);
        setOpenedChat(null);
        setOpenedProfile({
          kind: "business",
          publicId: ownerPublicId,
          title: "Profil",
          focusItemPublicId: publicId,
        });
        setHomeSearchResultsActive(false);
      } else if ((kind === "product" || kind === "service") && api.getCatalogItem) {
        setOpenedItemId(publicId);
      } else if (kind === "listing" && getPublicListing) {
        setOpenedProfile(null);
        setOpenedListing({ publicId, title: "E’lon" });
        setHomeSearchResultsActive(false);
      }
    },
    [api, getPublicListing, getPublicProfile],
  );

  const updateOpenedProfileTitle = useCallback((title: string) => {
    setOpenedProfile((current) => (current ? { ...current, title } : current));
  }, []);
  const updateOpenedListingTitle = useCallback((title: string) => {
    setOpenedListing((current) => (current ? { ...current, title } : current));
  }, []);

  const showQueueMessage = useCallback((text: string) => {
    setQueueMessage((current) => ({ id: current.id + 1, text }));
  }, []);

  const snapshot: NavigationSnapshot = {
    homeSearch: searchMemory.current,
    navigation,
    openedProfile,
    openedListing,
    openedChat,
    openedItemId,
    cartFilter,
    queueBooking,
    courseEnrollment,
  };
  const authReturn = useRef<{ state: NavigationSnapshot; intent?: AuthIntent } | null>(
    null,
  );
  function restoreNavigation(state: NavigationSnapshot) {
    searchMemory.current = state.homeSearch;
    setHomeRevision((value) => value + 1);
    setHomeSearchResultsActive(Boolean(state.homeSearch?.results));
    dispatch({ type: "RESTORE", state: state.navigation });
    setOpenedProfile(state.openedProfile);
    setOpenedListing(state.openedListing);
    setOpenedChat(state.openedChat);
    setOpenedItemId(state.openedItemId);
    setCartFilter(state.cartFilter);
    setQueueBooking(state.queueBooking);
    setCourseEnrollment(state.courseEnrollment);
  }
  const navigateBack = useNavigationHistory(
    snapshot,
    restoreNavigation,
    session.status === "loading"
      ? null
      : session.status === "guest"
        ? "guest"
        : `${session.status}:${session.identity.account_id}`,
  );
  const openAuth = (reason = "", intent?: AuthIntent) => {
    authReturn.current = { state: { ...snapshot, openedItemId: null }, intent };
    setOpenedItemId(null);
    setAuthReason(reason);
    dispatch({ type: "OPEN_AUTH" });
  };

  const openQueueBooking = useCallback(
    (target: QueueBookingTarget) => {
      if (session.status === "guest") {
        openAuth("Navbat olish", { queue: target });
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
    },
    [api, openAuth, session.status, showQueueMessage],
  );

  const openCourseEnrollment = useCallback(
    (target: CourseEnrollmentTarget) => {
      if (session.status === "guest") {
        openAuth("Kursga yozilish", { course: target });
        return;
      }
      if (session.status !== "user") {
        showQueueMessage("Avval oddiy profilga o'ting.");
        return;
      }
      if (typeof api.createCourseEnrollment !== "function") {
        showQueueMessage("Kursga yozilish xizmati hozircha ulanmagan.");
        return;
      }
      setCourseEnrollment(target);
    },
    [api, openAuth, session.status, showQueueMessage],
  );

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
    const pending = authReturn.current;
    authReturn.current = null;
    if (!pending) {
      dispatch({ type: "OPEN_CABINET" });
      return;
    }
    restoreNavigation(pending.state);
    if (pending.intent?.chat) {
      setOpenedChat(pending.intent.chat);
      dispatch({ type: "GO_HOME" });
    }
    if (pending.intent?.queue || pending.intent?.course) {
      if (identity.account_type !== "user")
        showQueueMessage("Avval oddiy profilga o'ting.");
      else {
        if (pending.intent.queue && supportsQueueBookingApi(api))
          setQueueBooking(pending.intent.queue);
        else if (pending.intent.queue)
          showQueueMessage("Navbat xizmati hozircha ulanmagan.");
        if (pending.intent.course && typeof api.createCourseEnrollment === "function")
          setCourseEnrollment(pending.intent.course);
        else if (pending.intent.course)
          showQueueMessage("Kursga yozilish xizmati hozircha ulanmagan.");
      }
    }
  }

  function renderAccount() {
    return (
      <AccountContent
        api={api}
        session={session}
        authReason={authReason}
        onAuthenticated={completeAuthentication}
        onLogout={() => {
          setSession({ status: "guest" });
          openHome();
        }}
        onSwitched={(identity) => {
          setSession({ status: identity.account_type, identity });
          dispatch({ type: "OPEN_CABINET" });
        }}
        onOpenDriverCabinet={() => dispatch({ type: "OPEN_TAXI_DRIVER" })}
        onOpenPublicListing={(publicId) => {
          setOpenedProfile(null);
          setOpenedListing({ publicId, title: "E’lon" });
          dispatch({ type: "GO_HOME" });
        }}
        onOpenPublicProfile={(kind, publicId) => {
          setOpenedListing(null);
          setOpenedProfile({ kind, publicId, title: "Profil" });
          dispatch({ type: "GO_HOME" });
        }}
      />
    );
  }

  const publicContent = (
    <>
      <PublicContent
        searchMemory={searchMemory}
        onSearchStateChange={refreshSearchSnapshot}
        homeRevision={homeRevision}
        api={api}
        session={session}
        navigation={navigation}
        authenticated={authenticated}
        publicFeatures={publicFeatures}
        openedChat={openedChat}
        openedListing={openedListing}
        openedProfile={openedProfile}
        carts={carts}
        cartFilter={cartFilter}
        orderCustomer={orderCustomer}
        homeLocation={homeLocation}
        getPublicListing={getPublicListing}
        getPublicProfile={getPublicProfile}
        getCatalogItems={getCatalogItems}
        searchPublic={searchPublic}
        getAdvertisements={getAdvertisements}
        getDistrictOffers={getDistrictOffers}
        getFollowedProfiles={getFollowedProfiles}
        getHomeMap={getHomeMap}
        recordAdvertisementClick={recordAdvertisementClick}
        recordAdvertisementViews={recordAdvertisementViews}
        listingApi={listingApi}
        storyApi={storyApi}
        createOrder={createOrder}
        accountContent={renderAccount()}
        dispatch={dispatch}
        setOpenedChat={setOpenedChat}
        setOpenedListing={setOpenedListing}
        setOpenedProfile={setOpenedProfile}
        setCarts={setCarts}
        setCartFilter={setCartFilter}
        setHomeLocation={setHomeLocation}
        setHomeSearchResultsActive={setHomeSearchResultsActive}
        openAuth={openAuth}
        openQueueBooking={openQueueBooking}
        openCourseEnrollment={openCourseEnrollment}
        openPublicResult={openPublicResult}
        showQueueMessage={showQueueMessage}
        updateOpenedListingTitle={updateOpenedListingTitle}
        updateOpenedProfileTitle={updateOpenedProfileTitle}
      />
      {openedItemId ? (
        <CatalogResultDialog
          key={openedItemId}
          api={api}
          publicId={openedItemId}
          authenticated={authenticated}
          onClose={() => setOpenedItemId(null)}
          onOpenOwner={(publicId) => openPublicResult("business", publicId)}
          onNeedQueueLogin={(target) => openAuth("Navbat olish", { queue: target })}
          onBookQueue={openQueueBooking}
          onQueueMessage={showQueueMessage}
        />
      ) : null}
    </>
  );

  return (
    <AppFrame
      api={api}
      session={session}
      navigation={navigation}
      authenticated={authenticated}
      title={title}
      publicFeatures={publicFeatures}
      openedChat={openedChat}
      openedListing={openedListing}
      openedProfile={openedProfile}
      courseEnrollment={courseEnrollment}
      queueBooking={queueBooking}
      homeLocation={homeLocation}
      homeSearchResultsActive={homeSearchResultsActive}
      carts={carts}
      theme={theme}
      failed={failed}
      accountView={accountView}
      orderCustomer={orderCustomer}
      queueMessage={queueMessage}
      content={publicContent}
      dispatch={dispatch}
      setOpenedChat={setOpenedChat}
      setOpenedListing={setOpenedListing}
      setOpenedProfile={setOpenedProfile}
      setCartFilter={setCartFilter}
      setCourseEnrollment={setCourseEnrollment}
      setQueueBooking={setQueueBooking}
      onHome={openHome}
      onClearAuthReason={() => {
        setAuthReason("");
        authReturn.current = null;
      }}
      onNavigateBack={navigateBack}
      onOpenAuth={openAuth}
      onMessage={showQueueMessage}
      onRetry={() => setAttempt((value) => value + 1)}
      onToggleTheme={toggleTheme}
    />
  );
}
