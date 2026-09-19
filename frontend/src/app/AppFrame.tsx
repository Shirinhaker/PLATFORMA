import type { Dispatch, ReactNode, SetStateAction } from "react";

import type { PublicFeatures } from "../api/types";
import type { AppSession } from "../auth/types";
import {
  CourseEnrollment,
  type CourseEnrollmentApi,
  type CourseEnrollmentTarget,
} from "../education/CourseEnrollment";
import type { HomeLocation } from "../legacy/public/location-storage";
import type {
  PublicNavigationAction,
  PublicNavigationState,
} from "../legacy/public/public-navigation";
import type { MessagePeer } from "../messages/Messages";
import { cartLineCount, type CartState } from "../orders/order-store";
import {
  QueueBooking,
  supportsQueueBookingApi,
  type QueueBookingTarget,
} from "../queues/QueueBooking";
import { AppShell } from "./AppShell";
import { SessionStatus } from "./SessionStatus";
import type { AppApi } from "./app-api";
import type { OpenedListing, OpenedProfile } from "./PublicContent";

type AppFrameProps = {
  api: AppApi;
  session: AppSession;
  navigation: PublicNavigationState;
  authenticated: boolean;
  title: string | undefined;
  publicFeatures: PublicFeatures;
  openedChat: MessagePeer | null;
  openedListing: OpenedListing | null;
  openedProfile: OpenedProfile | null;
  courseEnrollment: CourseEnrollmentTarget | null;
  queueBooking: QueueBookingTarget | null;
  homeLocation: HomeLocation | null;
  homeSearchResultsActive: boolean;
  carts: CartState;
  theme: "light" | "dark";
  failed: boolean;
  accountView: boolean;
  orderCustomer: { phone: string; address: string };
  queueMessage: { id: number; text: string };
  content: ReactNode;
  dispatch: Dispatch<PublicNavigationAction>;
  setOpenedChat: Dispatch<SetStateAction<MessagePeer | null>>;
  setOpenedListing: Dispatch<SetStateAction<OpenedListing | null>>;
  setOpenedProfile: Dispatch<SetStateAction<OpenedProfile | null>>;
  setCartFilter: Dispatch<SetStateAction<string | null>>;
  setCourseEnrollment: Dispatch<SetStateAction<CourseEnrollmentTarget | null>>;
  setQueueBooking: Dispatch<SetStateAction<QueueBookingTarget | null>>;
  onHome(): void;
  onClearAuthReason(): void;
  onOpenAuth(reason?: string): void;
  onMessage(text: string): void;
  onRetry(): void;
  onToggleTheme(): void;
};

export function AppFrame({
  api,
  session,
  navigation,
  authenticated,
  title,
  publicFeatures,
  openedChat,
  openedListing,
  openedProfile,
  courseEnrollment,
  queueBooking,
  homeLocation,
  homeSearchResultsActive,
  carts,
  theme,
  failed,
  accountView,
  orderCustomer,
  queueMessage,
  content,
  dispatch,
  setOpenedChat,
  setOpenedListing,
  setOpenedProfile,
  setCartFilter,
  setCourseEnrollment,
  setQueueBooking,
  onHome,
  onClearAuthReason,
  onOpenAuth,
  onMessage,
  onRetry,
  onToggleTheme,
}: AppFrameProps) {
  function clearOpenedContent() {
    setOpenedChat(null);
    setOpenedProfile(null);
    setOpenedListing(null);
  }

  return (
    <AppShell
      authenticated={authenticated}
      title={
        (openedChat || openedProfile || openedListing) &&
        (navigation.view === "home" || navigation.view === "listings")
          ? openedChat
            ? "Suhbat"
            : (openedProfile?.title ?? openedListing?.title)
          : title
      }
      isHome={
        navigation.view === "home" && !openedChat && !openedProfile && !openedListing
      }
      searchResultsActive={navigation.view === "home" && homeSearchResultsActive}
      publicFeatures={publicFeatures}
      cartCount={cartLineCount(carts)}
      theme={theme}
      onHome={onHome}
      onLocation={() => {
        clearOpenedContent();
        dispatch({ type: "OPEN_LOCATION" });
      }}
      onAccount={() => {
        clearOpenedContent();
        onClearAuthReason();
        dispatch({ type: authenticated ? "OPEN_CABINET" : "OPEN_AUTH" });
      }}
      onBack={() => {
        if (courseEnrollment) {
          setCourseEnrollment(null);
        } else if (navigation.view === "cart") {
          dispatch({ type: homeLocation ? "BACK" : "OPEN_LOCATION" });
        } else if (openedChat) {
          setOpenedChat(null);
        } else if (openedListing) {
          setOpenedListing(null);
        } else if (openedProfile) {
          setOpenedProfile(null);
        } else {
          dispatch({ type: homeLocation ? "BACK" : "OPEN_LOCATION" });
        }
      }}
      onListings={() => {
        clearOpenedContent();
        dispatch({ type: "OPEN_LISTINGS" });
      }}
      onCart={() => {
        clearOpenedContent();
        setCartFilter(null);
        dispatch({ type: "OPEN_CART" });
      }}
      onTaxi={() => {
        clearOpenedContent();
        if (session.status === "guest") {
          onOpenAuth("Taxi bo'limi");
        } else if (session.status !== "user") {
          onMessage("Avval oddiy profilga o'ting.");
        } else {
          dispatch({ type: "OPEN_TAXI_DRIVER" });
        }
      }}
      onToggleTheme={onToggleTheme}
    >
      <>
        <div className="app-shell__content" tabIndex={-1}>
          {failed && accountView ? (
            <SessionStatus state="error" onRetry={onRetry} />
          ) : (
            content
          )}
        </div>
        {queueBooking && supportsQueueBookingApi(api) ? (
          <QueueBooking
            api={api}
            key={`${queueBooking.businessPublicId}:${queueBooking.itemPublicId}`}
            target={queueBooking}
            onClose={() => setQueueBooking(null)}
            onMessage={onMessage}
          />
        ) : null}
        {courseEnrollment && typeof api.createCourseEnrollment === "function" ? (
          <CourseEnrollment
            api={api as CourseEnrollmentApi}
            customerPhone={session.status === "user" ? orderCustomer.phone : ""}
            target={courseEnrollment}
            onClose={() => setCourseEnrollment(null)}
            onMessage={onMessage}
          />
        ) : null}
        {queueMessage.text ? (
          <div className="app-toast on" role="status">
            {queueMessage.text}
          </div>
        ) : null}
      </>
    </AppShell>
  );
}
