import type { AuthIntent } from "./auth-intent";
import type { RefObject } from "react";
import type { HomeSearchMemory } from "../legacy/public/home/home-search-memory";
import type { ComponentProps, Dispatch, ReactNode, SetStateAction } from "react";

import type { PublicFeatures } from "../api/types";
import type { AppSession } from "../auth/types";
import { CatalogScreen } from "../legacy/public/CatalogScreen";
import { CategoryScreen } from "../legacy/public/CategoryScreen";
import { HomeScreen } from "../legacy/public/HomeScreen";
import { LocationScreen } from "../legacy/public/LocationScreen";
import { PublicProfile } from "../legacy/public/PublicProfile";
import type { HomeLocation } from "../legacy/public/location-storage";
import type {
  PublicNavigationAction,
  PublicNavigationState,
} from "../legacy/public/public-navigation";
import { ListingPage } from "../listings/ListingPage";
import { PublicListings } from "../listings/PublicListings";
import { Messages, type MessagePeer } from "../messages/Messages";
import { Cart } from "../orders/Cart";
import { addCartItem, type CartState } from "../orders/order-store";
import { DriverCabinet } from "../taxi/DriverCabinet";
import { TaxiCall } from "../taxi/TaxiCall";
import { type AppApi, supportsMessages, supportsPublicReviews } from "./app-api";

export type OpenedProfile = {
  kind: "user" | "business";
  publicId: string;
  title: string;
  focusItemPublicId?: string;
};

export type OpenedListing = {
  publicId: string;
  title: string;
};

type HomeProps = ComponentProps<typeof HomeScreen>;
type ProfileProps = ComponentProps<typeof PublicProfile>;
type ListingsProps = ComponentProps<typeof PublicListings>;
type CartProps = ComponentProps<typeof Cart>;

type PublicContentProps = {
  searchMemory: RefObject<HomeSearchMemory | null>;
  homeRevision: number;
  onSearchStateChange(): void;
  api: AppApi;
  session: AppSession;
  navigation: PublicNavigationState;
  authenticated: boolean;
  publicFeatures: PublicFeatures;
  openedChat: MessagePeer | null;
  openedListing: OpenedListing | null;
  openedProfile: OpenedProfile | null;
  carts: CartState;
  cartFilter: string | null;
  orderCustomer: CartProps["customer"];
  homeLocation: HomeLocation | null;
  getPublicListing: ComponentProps<typeof ListingPage>["getPublicListing"] | undefined;
  getPublicProfile: ProfileProps["getPublicProfile"] | undefined;
  getCatalogItems: ComponentProps<typeof CatalogScreen>["getCatalogItems"];
  searchPublic: HomeProps["searchPublic"];
  getAdvertisements: HomeProps["getAdvertisements"];
  getDistrictOffers: HomeProps["getDistrictOffers"];
  getFollowedProfiles: HomeProps["getFollowedProfiles"];
  getHomeMap: HomeProps["getHomeMap"];
  recordAdvertisementClick: HomeProps["recordAdvertisementClick"];
  recordAdvertisementViews: HomeProps["recordAdvertisementViews"];
  listingApi: ListingsProps["api"] | undefined;
  storyApi:
    | (NonNullable<HomeProps["storyApi"]> & NonNullable<ProfileProps["storyApi"]>)
    | undefined;
  createOrder: CartProps["createOrder"];
  accountContent: ReactNode;
  dispatch: Dispatch<PublicNavigationAction>;
  setOpenedChat: Dispatch<SetStateAction<MessagePeer | null>>;
  setOpenedListing: Dispatch<SetStateAction<OpenedListing | null>>;
  setOpenedProfile: Dispatch<SetStateAction<OpenedProfile | null>>;
  setCarts: Dispatch<SetStateAction<CartState>>;
  setCartFilter: Dispatch<SetStateAction<string | null>>;
  setHomeLocation: Dispatch<SetStateAction<HomeLocation | null>>;
  setHomeSearchResultsActive: Dispatch<SetStateAction<boolean>>;
  openAuth(reason?: string, intent?: AuthIntent): void;
  openQueueBooking: ProfileProps["onBookQueue"];
  openCourseEnrollment: ProfileProps["onEnrollCourse"];
  openPublicResult: HomeProps["onOpenPublicResult"];
  showQueueMessage(text: string): void;
  updateOpenedListingTitle(title: string): void;
  updateOpenedProfileTitle(title: string): void;
};

export function PublicContent({
  searchMemory,
  homeRevision,
  onSearchStateChange,
  api,
  session,
  navigation,
  authenticated,
  publicFeatures,
  openedChat,
  openedListing,
  openedProfile,
  carts,
  cartFilter,
  orderCustomer,
  homeLocation,
  getPublicListing,
  getPublicProfile,
  getCatalogItems,
  searchPublic,
  getAdvertisements,
  getDistrictOffers,
  getFollowedProfiles,
  getHomeMap,
  recordAdvertisementClick,
  recordAdvertisementViews,
  listingApi,
  storyApi,
  createOrder,
  accountContent,
  dispatch,
  setOpenedChat,
  setOpenedListing,
  setOpenedProfile,
  setCarts,
  setCartFilter,
  setHomeLocation,
  setHomeSearchResultsActive,
  openAuth,
  openQueueBooking,
  openCourseEnrollment,
  openPublicResult,
  showQueueMessage,
  updateOpenedListingTitle,
  updateOpenedProfileTitle,
}: PublicContentProps) {
  const openChat =
    publicFeatures.chat && supportsMessages(api)
      ? (kind: "user" | "business", publicId: string, name: string) => {
          const peer = { kind, publicId, name };
          if (!authenticated) {
            openAuth("Xabar yozish", { chat: peer });
            return;
          }
          setOpenedChat(peer);
          dispatch({ type: "GO_HOME" });
        }
      : undefined;
  const catalogChat = openChat
    ? (publicId: string, name: string) => openChat("business", publicId, name)
    : undefined;
  if (
    navigation.view === "home" &&
    openedChat &&
    authenticated &&
    supportsMessages(api)
  ) {
    return (
      <Messages
        api={api}
        initialPeer={openedChat}
        onBack={() => setOpenedChat(null)}
        onOpenProfile={(kind, publicId) => {
          setOpenedChat(null);
          setOpenedListing(null);
          setOpenedProfile({ kind, publicId, title: "Profil" });
        }}
      />
    );
  }
  if (navigation.view === "home" && openedListing && getPublicListing) {
    return (
      <ListingPage
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
  if (navigation.view === "home" && openedProfile && getPublicProfile) {
    return (
      <PublicProfile
        authenticated={authenticated}
        cart={carts[openedProfile.publicId]}
        focusItemPublicId={openedProfile.focusItemPublicId}
        kind={openedProfile.kind}
        publicId={openedProfile.publicId}
        getPublicProfile={getPublicProfile}
        onAddCartItem={(item, provider) => {
          setCarts((current) => addCartItem(current, provider, item));
        }}
        onBookQueue={openQueueBooking}
        onEnrollCourse={openCourseEnrollment}
        onNeedLogin={() => openAuth()}
        onMessage={openChat}
        onNeedMessageLogin={openChat}
        onNeedCourseLogin={(target) => openAuth("Kursga yozilish", { course: target })}
        onNeedQueueLogin={(target) => openAuth("Navbat olish", { queue: target })}
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
        reviewApi={supportsPublicReviews(api) ? api : undefined}
        storyApi={publicFeatures.stories ? storyApi : undefined}
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
          onNeedQueueLogin={(target) => openAuth("Navbat olish", { queue: target })}
          onOpenChat={catalogChat}
          onOpenOwner={(publicId) => {
            setOpenedProfile({ kind: "business", publicId, title: "Profil" });
            dispatch({ type: "GO_HOME" });
          }}
          onOpenCategory={(categoryId) =>
            dispatch({ type: "OPEN_CATEGORY", categoryId })
          }
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
          onNeedQueueLogin={(target) => openAuth("Navbat olish", { queue: target })}
          onOpenChat={catalogChat}
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
        <PublicListings
          api={listingApi}
          openedListingId={openedListing?.publicId ?? null}
          onOpenListing={(publicId, title) => setOpenedListing({ publicId, title })}
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
        <Cart
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
    case "taxi-call":
      return (
        <TaxiCall
          api={api}
          authenticated={session.status === "user"}
          center={{
            latitude: homeLocation?.latitude ?? 41.3111,
            longitude: homeLocation?.longitude ?? 69.2797,
          }}
          district={homeLocation?.district}
          onBack={() => dispatch({ type: "GO_HOME" })}
          onNeedLogin={(reason) => {
            if (session.status === "business") {
              showQueueMessage("Avval oddiy profilga o'ting.");
            } else {
              openAuth(reason);
            }
          }}
        />
      );
    case "taxidrv":
      return session.status === "user" ? <DriverCabinet api={api} /> : accountContent;
    case "auth":
    case "cabinet":
      return accountContent;
    case "home":
      return (
        <HomeScreen
          key={homeRevision}
          searchMemory={searchMemory}
          onSearchStateChange={onSearchStateChange}
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
          storyApi={publicFeatures.stories ? storyApi : undefined}
          taxiEnabled={publicFeatures.taxi}
          onTaxiCall={() => dispatch({ type: "OPEN_TAXI_CALL" })}
        />
      );
  }
}
