import { useLayoutEffect, useRef } from "react";
import type { CourseEnrollmentTarget } from "../education/CourseEnrollment";
import type { PublicNavigationState } from "../legacy/public/public-navigation";
import type { MessagePeer } from "../messages/Messages";
import type { QueueBookingTarget } from "../queues/QueueBooking";
import type { OpenedListing, OpenedProfile } from "./PublicContent";
import type { HomeSearchMemory } from "../legacy/public/home/home-search-memory";

export type NavigationSnapshot = {
  homeSearch: HomeSearchMemory | null;
  navigation: PublicNavigationState;
  openedProfile: OpenedProfile | null;
  openedListing: OpenedListing | null;
  openedChat: MessagePeer | null;
  openedItemId: string | null;
  cartFilter: string | null;
  queueBooking: QueueBookingTarget | null;
  courseEnrollment: CourseEnrollmentTarget | null;
};

function routeKey(state: NavigationSnapshot) {
  return JSON.stringify({
    ...state,
    homeSearch:
      state.navigation.view === "home" &&
      !state.openedProfile &&
      !state.openedListing &&
      !state.openedChat
        ? Boolean(state.homeSearch?.results)
        : false,
    openedProfile: state.openedProfile && [
      state.openedProfile.kind,
      state.openedProfile.publicId,
      state.openedProfile.focusItemPublicId,
    ],
    openedListing: state.openedListing?.publicId,
    openedChat: state.openedChat && [state.openedChat.kind, state.openedChat.publicId],
  });
}

// History stores only an index. Account data and form drafts stay out of it.
export function useNavigationHistory(
  state: NavigationSnapshot,
  restore: (state: NavigationSnapshot) => void,
  accountScope: string | null,
) {
  const entries = useRef<NavigationSnapshot[]>([]);
  const index = useRef(0);
  const key = routeKey(state);
  const lastKey = useRef("");
  const restoring = useRef(false);
  const restoreRef = useRef(restore);
  const owner = useRef(`koprik-${Date.now()}-${Math.random()}`);
  const scope = useRef(accountScope);
  restoreRef.current = restore;

  useLayoutEffect(() => {
    if (
      accountScope &&
      scope.current &&
      scope.current !== "guest" &&
      accountScope !== scope.current
    ) {
      entries.current = [];
      index.current = 0;
      lastKey.current = "";
      restoring.current = false;
      owner.current = `koprik-${Date.now()}-${Math.random()}`;
    }
    if (accountScope) scope.current = accountScope;
    if (lastKey.current === key) {
      entries.current[index.current] = state;
      return;
    }
    const previous = entries.current[index.current];
    if (
      previous?.navigation.view === "home" &&
      !previous.openedProfile &&
      !previous.openedListing &&
      !previous.openedChat &&
      Boolean(previous.homeSearch?.results) === Boolean(state.homeSearch?.results)
    ) {
      previous.homeSearch = state.homeSearch;
    }
    const replace =
      !previous ||
      previous.navigation.view === "auth" ||
      (previous.navigation.view === "location" && state.navigation.view === "home");
    if (!replace) index.current += 1;
    entries.current = entries.current.slice(0, index.current + 1);
    entries.current[index.current] = state;
    lastKey.current = key;
    try {
      window.history[replace ? "replaceState" : "pushState"](
        { koprikNavigation: owner.current, index: index.current },
        "",
        window.location.href,
      );
    } catch {
      /* Embedded browsers may disable the History API. */
    }
  }, [key, state, accountScope]);

  useLayoutEffect(() => {
    function pop(event: PopStateEvent) {
      if (event.state?.koprikNavigation !== owner.current) return;
      const target = entries.current[event.state.index];
      if (!target) return;
      index.current = event.state.index;
      lastKey.current = routeKey(target);
      restoring.current = false;
      restoreRef.current(target);
    }
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);

  return () => {
    if (restoring.current) return true;
    if (index.current < 1 || window.history.state?.koprikNavigation !== owner.current)
      return false;
    restoring.current = true;
    const target = entries.current[index.current - 1];
    if (!target) {
      restoring.current = false;
      return false;
    }
    index.current -= 1;
    lastKey.current = routeKey(target);
    restoreRef.current(target);
    window.history.back();
    return true;
  };
}
