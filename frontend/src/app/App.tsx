import { useCallback, useEffect, useMemo, useReducer, useState } from "react";

import type { PublicFeatures, SessionIdentity } from "../api/types";
import type { AppSession } from "../auth/types";
import type { CourseEnrollmentTarget } from "../education/CourseEnrollment";
import type { CartState } from "../orders/order-store";
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
import type { MessagePeer } from "../messages/Messages";
import { useOrderCustomerProfile } from "./use-order-customer-profile";
import { AccountContent } from "./AccountContent";
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
  const [homeSearchResultsActive, setHomeSearchResultsActive] = useState(false);
  const [openedProfile, setOpenedProfile] = useState<OpenedProfile | null>(null);
  const [openedListing, setOpenedListing] = useState<OpenedListing | null>(null);
  const [openedChat, setOpenedChat] = useState<MessagePeer | null>(null);
  const [carts, setCarts] = useState<CartState>({});
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
  const searchPublic = useMemo(
    () =>
      typeof api.searchPublic === "function" ? api.searchPublic.bind(api) : undefined,
    [api],
  );
  const getCatalogItems = useMemo(
    () =>
      typeof api.getCatalogItems === "function"
        ? api.getCatalogItems.bind(api)
        : undefined,
    [api],
  );
  const getAdvertisements = useMemo(
    () =>
      typeof api.getAdvertisements === "function"
        ? api.getAdvertisements.bind(api)
        : undefined,
    [api],
  );
  const getHomeMap = useMemo(
    () => (typeof api.getHomeMap === "function" ? api.getHomeMap.bind(api) : undefined),
    [api],
  );
  const getDistrictOffers = useMemo(
    () =>
      typeof api.getDistrictOffers === "function"
        ? api.getDistrictOffers.bind(api)
        : undefined,
    [api],
  );
  const getFollowedProfiles = useMemo(
    () =>
      typeof api.getFollowedProfiles === "function"
        ? api.getFollowedProfiles.bind(api)
        : undefined,
    [api],
  );
  const getPublicProfile = useMemo(
    () =>
      typeof api.getPublicProfile === "function"
        ? api.getPublicProfile.bind(api)
        : undefined,
    [api],
  );
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
  const recordAdvertisementViews = useMemo(
    () =>
      typeof api.recordAdvertisementViews === "function"
        ? api.recordAdvertisementViews.bind(api)
        : undefined,
    [api],
  );
  const recordAdvertisementClick = useMemo(
    () =>
      typeof api.recordAdvertisementClick === "function"
        ? api.recordAdvertisementClick.bind(api)
        : undefined,
    [api],
  );
  const getPublicListing = useMemo(
    () =>
      typeof api.getPublicListing === "function"
        ? api.getPublicListing.bind(api)
        : undefined,
    [api],
  );
  const createOrder = useMemo(
    () =>
      typeof api.createOrder === "function"
        ? api.createOrder.bind(api)
        : async () => {
            throw new Error("Buyurtma xizmati hozircha ulanmagan.");
          },
    [api],
  );
  const listingApi = useMemo(
    () =>
      typeof api.getListingCounts === "function" &&
      typeof api.getPublicListings === "function" &&
      typeof api.toggleListingSave === "function"
        ? {
            getListingCounts: api.getListingCounts.bind(api),
            getPublicListings: api.getPublicListings.bind(api),
            toggleListingSave: api.toggleListingSave.bind(api),
          }
        : undefined,
    [api],
  );
  const storyApi = useMemo(
    () =>
      typeof api.getStoryFeed === "function" &&
      typeof api.getOwnerStories === "function" &&
      typeof api.recordStoryView === "function" &&
      typeof api.getStoryViewers === "function" &&
      typeof api.deleteStory === "function" &&
      typeof api.reportStory === "function"
        ? {
            getStoryFeed: api.getStoryFeed.bind(api),
            getOwnerStories: api.getOwnerStories.bind(api),
            recordStoryView: api.recordStoryView.bind(api),
            getStoryViewers: api.getStoryViewers.bind(api),
            deleteStory: api.deleteStory.bind(api),
            reportStory: api.reportStory.bind(api),
          }
        : undefined,
    [api],
  );

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
    setOpenedProfile(null);
    setOpenedListing(null);
    setOpenedChat(null);
    setCartFilter(null);
    setQueueBooking(null);
    setCourseEnrollment(null);
    setAuthReason("");
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
      } else if (kind === "listing" && getPublicListing) {
        setOpenedProfile(null);
        setOpenedListing({ publicId, title: "E’lon" });
        setHomeSearchResultsActive(false);
      }
    },
    [getPublicListing, getPublicProfile],
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

  const openAuth = useCallback((reason = "") => {
    setAuthReason(reason);
    dispatch({ type: "OPEN_AUTH" });
  }, []);

  const openQueueBooking = useCallback(
    (target: QueueBookingTarget) => {
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
    },
    [api, openAuth, session.status, showQueueMessage],
  );

  const openCourseEnrollment = useCallback(
    (target: CourseEnrollmentTarget) => {
      if (session.status === "guest") {
        openAuth("Kursga yozilish");
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
    dispatch({ type: "OPEN_CABINET" });
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
    <PublicContent
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
      onClearAuthReason={() => setAuthReason("")}
      onOpenAuth={openAuth}
      onMessage={showQueueMessage}
      onRetry={() => setAttempt((value) => value + 1)}
      onToggleTheme={toggleTheme}
    />
  );
}
