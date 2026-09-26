import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useLayoutEffect,
  type RefObject,
  useState,
} from "react";

import type { ApiClient } from "../../api/client";
import type {
  PublicDistrictOffer,
  PublicSearchItem,
  StoryGroup,
} from "../../api/types";
import { useHomeDiscovery } from "./home/use-home-discovery";
import type { HomeSearchMemory } from "./home/home-search-memory";
import { AppToast } from "./AppToast";
import { HomeAdvertisements } from "./HomeAdvertisements";
import { HomeDistrictOffers } from "./home/HomeDistrictOffers";
import { HomeFollowedProfiles } from "./home/HomeFollowedProfiles";
import { HomeMap } from "./home/HomeMap";
import { HomeSearchResults } from "./home/HomeSearchResults";
import { findLocationCenter } from "./location-centers";
import type { HomeLocation } from "./location-storage";
import { StoryFeed, type StoryViewerApi } from "../../stories/StoryFeed";

interface HomeScreenProps {
  onSearchStateChange?(): void;
  searchMemory?: RefObject<HomeSearchMemory | null>;
  authenticated?: boolean;
  currentDistrict?: string;
  getAdvertisements?: ApiClient["getAdvertisements"];
  getDistrictOffers?: ApiClient["getDistrictOffers"];
  getFollowedProfiles?: ApiClient["getFollowedProfiles"];
  getHomeMap?: ApiClient["getHomeMap"];
  location?: HomeLocation | null;
  onSearch?: (query: string) => void;
  onOpenCatalog(): void;
  onOpenLocation(): void;
  onResultsActiveChange?: (active: boolean) => void;
  onOpenPublicResult?: (
    kind: "user" | "business" | "product" | "service" | "listing",
    publicId: string,
    ownerPublicId?: string,
  ) => void;
  recordAdvertisementClick?: ApiClient["recordAdvertisementClick"];
  recordAdvertisementViews?: ApiClient["recordAdvertisementViews"];
  searchPublic?: ApiClient["searchPublic"];
  storyApi?: StoryViewerApi & Pick<ApiClient, "getStoryFeed">;
  taxiEnabled?: boolean;
  onTaxiCall?: () => void;
}

const noopResult = () => undefined;

function SearchIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

function CatalogIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M22 2 9.8 14.2" />
      <path d="m22 2-7.8 20-4.4-7.8L2 9.8 22 2Z" />
    </svg>
  );
}

export function HomeScreen({
  searchMemory,
  onSearchStateChange,
  authenticated = false,
  currentDistrict,
  getAdvertisements,
  getDistrictOffers,
  getFollowedProfiles,
  getHomeMap,
  location = null,
  onSearch,
  onOpenCatalog,
  onOpenLocation,
  onOpenPublicResult = noopResult,
  onResultsActiveChange,
  recordAdvertisementClick,
  recordAdvertisementViews,
  searchPublic,
  storyApi,
  taxiEnabled = false,
  onTaxiCall,
}: HomeScreenProps) {
  const saved =
    searchMemory?.current?.district === (currentDistrict?.trim() || "")
      ? searchMemory.current
      : null;
  const root = useRef<HTMLElement>(null);
  const [query, setQuery] = useState(saved?.query ?? "");
  const [searchFocused, setSearchFocused] = useState(false);
  const [results, setResults] = useState<PublicSearchItem[] | null>(
    saved?.results ?? null,
  );
  const [resultQuery, setResultQuery] = useState(saved?.resultQuery ?? "");
  const [searchError, setSearchError] = useState("");
  const [searchPending, setSearchPending] = useState(false);
  const [searchPage, setSearchPage] = useState(saved?.searchPage ?? 1);
  const [searchPages, setSearchPages] = useState(saved?.searchPages ?? 0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const queryInput = useRef<HTMLInputElement>(null);
  const searchSequence = useRef(0);
  const district = currentDistrict?.trim() || "";
  const districtLabel = district || "Hudud tanlanmagan";
  const locationCenter =
    location?.latitude != null && location.longitude != null
      ? {
          latitude: location.latitude,
          longitude: location.longitude,
        }
      : findLocationCenter(location?.region || "", location?.district || "");
  const loadStories = useCallback(() => {
    if (!storyApi) return Promise.resolve([]);
    return storyApi.getStoryFeed({
      ...(locationCenter?.latitude === undefined
        ? {}
        : { lat: locationCenter.latitude }),
      ...(locationCenter?.longitude === undefined
        ? {}
        : { lng: locationCenter.longitude }),
    });
  }, [locationCenter?.latitude, locationCenter?.longitude, storyApi]);

  const { homeMap, offers, followedProfiles, offersNeedDistrict, failures } =
    useHomeDiscovery({
      district,
      authenticated,
      getHomeMap,
      getDistrictOffers,
      getFollowedProfiles,
    });
  useLayoutEffect(() => {
    const scroller = root.current?.closest(".app-shell__content");
    if (scroller && saved) scroller.scrollTop = saved.scrollTop;
  }, []);
  useEffect(() => {
    if (searchMemory)
      searchMemory.current = {
        district,
        query,
        results,
        resultQuery,
        searchPage,
        searchPages,
        scrollTop: searchMemory.current?.scrollTop ?? 0,
      };
    onResultsActiveChange?.(results !== null);
    onSearchStateChange?.();
  }, [
    district,
    query,
    results,
    resultQuery,
    searchPage,
    searchPages,
    searchMemory,
    onResultsActiveChange,
    onSearchStateChange,
  ]);

  const openResult = useCallback(
    (
      kind: "user" | "business" | "product" | "service" | "listing",
      publicId: string,
      ownerPublicId?: string,
    ) => {
      if (searchMemory?.current) {
        searchMemory.current.scrollTop =
          root.current?.closest(".app-shell__content")?.scrollTop ?? 0;
      }
      if (ownerPublicId) {
        onOpenPublicResult(kind, publicId, ownerPublicId);
        return;
      }
      onOpenPublicResult(kind, publicId);
    },
    [onOpenPublicResult, searchMemory],
  );

  const renderFollowedProfiles = useCallback(
    (groups: StoryGroup[], onOpenStory: (index: number) => void) => (
      <HomeFollowedProfiles
        items={followedProfiles}
        storyGroups={groups}
        onOpenProfile={openResult}
        onOpenStory={onOpenStory}
      />
    ),
    [followedProfiles, openResult],
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      onOpenCatalog();
      return;
    }
    if (!searchPublic) {
      onSearch?.(normalizedQuery);
      return;
    }
    const requestSequence = ++searchSequence.current;
    setResultQuery(normalizedQuery);
    setResults([]);
    setSearchError("");
    setSearchPending(true);
    setSearchPage(1);
    setSearchPages(0);
    setLoadingMore(false);
    setToastMessage("");
    void searchPublic({
      q: normalizedQuery,
      region: location?.region || "",
      district: location?.district || "",
      page: 1,
      page_size: 20,
    })
      .then((payload) => {
        if (requestSequence !== searchSequence.current) return;
        setResults(payload.items);
        setSearchPage(payload.page);
        setSearchPages(payload.pages);
        setSearchPending(false);
      })
      .catch((error: unknown) => {
        if (requestSequence !== searchSequence.current) return;
        setResults([]);
        setSearchPending(false);
        setSearchError(error instanceof Error ? error.message : String(error || ""));
      });
  }

  function loadMore() {
    if (!searchPublic || loadingMore || searchPending || searchPage >= searchPages)
      return;
    const requestSequence = searchSequence.current;
    const nextPage = searchPage + 1;
    setLoadingMore(true);
    void searchPublic({
      q: resultQuery,
      region: location?.region || "",
      district: location?.district || "",
      page: nextPage,
      page_size: 20,
    })
      .then((payload) => {
        if (requestSequence !== searchSequence.current) return;
        setResults((current) => {
          const merged = [...(current || []), ...payload.items];
          return merged.filter(
            (item, index) =>
              merged.findIndex(
                (candidate) =>
                  candidate.kind === item.kind &&
                  candidate.public_id === item.public_id,
              ) === index,
          );
        });
        setSearchPage(payload.page);
        setSearchPages(payload.pages);
      })
      .catch((error: unknown) => {
        if (requestSequence !== searchSequence.current) return;
        setToastMessage(error instanceof Error ? error.message : String(error || ""));
      })
      .finally(() => {
        if (requestSequence === searchSequence.current) setLoadingMore(false);
      });
  }

  function clearQuery() {
    setQuery("");
    setSearchFocused(true);
    queryInput.current?.focus();
  }

  function closeResults() {
    searchSequence.current += 1;
    setQuery("");
    setResults(null);
    setResultQuery("");
    setSearchError("");
    setSearchPending(false);
    setSearchPage(1);
    setSearchPages(0);
    setLoadingMore(false);
    setToastMessage("");
  }

  function openOffer(item: PublicDistrictOffer) {
    openResult(
      item.kind,
      item.content_public_id,
      item.kind === "listing" ? undefined : item.business_public_id,
    );
  }

  return (
    <main ref={root} className="screen active public-home-v1656" data-screen="home">
      {failures.map(({ name, retry }) => (
        <div className="public-search-status" role="alert" key={name}>
          <p>{name} yuklanmadi. Internet aloqasini tekshiring.</p>
          <button type="button" className="btn btn-soft" onClick={retry}>
            Qayta urinish: {name}
          </button>
        </div>
      ))}
      {storyApi ? (
        <StoryFeed
          deleteStory={storyApi.deleteStory}
          getStoryViewers={storyApi.getStoryViewers}
          load={loadStories}
          recordStoryView={storyApi.recordStoryView}
          renderRail={renderFollowedProfiles}
          reportStory={storyApi.reportStory}
          onOpenOwner={openResult}
        />
      ) : (
        <HomeFollowedProfiles items={followedProfiles} onOpenProfile={openResult} />
      )}

      <div className="home-discovery" id="homeDiscovery">
        <div
          className={`home-search-card${searchFocused ? " mobile-search-focused" : ""}`}
        >
          <h1>
            Kerakli mahsulot va
            <br />
            xizmatni yaqiningizdan toping
          </h1>
          <form className="home-search-row" onSubmit={submitSearch}>
            <label className="home-query-shell" htmlFor="homeQueryInput">
              <SearchIcon />
              <input
                autoComplete="off"
                id="homeQueryInput"
                placeholder="Nima qidiryapsiz?"
                ref={queryInput}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.currentTarget.value)}
                onBlur={() => setSearchFocused(false)}
                onFocus={() => setSearchFocused(true)}
              />
              <button
                aria-label="Qidiruvni tozalash"
                className="home-query-clear"
                type="button"
                onClick={clearQuery}
              >
                ×
              </button>
            </label>
            <button
              className="home-catalog-open"
              id="homeCatalogOpen"
              type="button"
              onClick={onOpenCatalog}
            >
              <CatalogIcon />
              <span className="home-catalog-copy">
                <strong>Katalog bo‘yicha</strong>
                <small id="homeCatalogLocation">{districtLabel}</small>
              </span>
              <span className="home-catalog-chevron" aria-hidden="true">
                ⌄
              </span>
            </button>
            <button className="home-search-submit" type="submit">
              Qidirish
            </button>
          </form>
          <div className="home-location-note" id="homeLocationNote">
            Joriy hudud: {district ? <b>{district}</b> : "tanlanmagan"}
          </div>
        </div>

        <HomeMap
          businesses={homeMap.businesses}
          center={locationCenter ?? undefined}
          district={districtLabel}
          resultItems={results}
          specialists={homeMap.specialists}
          taxiEnabled={taxiEnabled}
          onCloseResults={closeResults}
          onOpenResult={openResult}
          onTaxiCall={onTaxiCall}
        />
      </div>

      {results ? (
        <div id="resWrap">
          <div className="search-results-summary" aria-live="polite">
            Natijalar — {results.length} ta
          </div>
          <div id="resList">
            <HomeSearchResults
              error={searchError}
              hasMore={searchPage < searchPages}
              items={results}
              loadingMore={loadingMore}
              pending={searchPending}
              query={resultQuery}
              onLoadMore={loadMore}
              onOpenResult={(item) =>
                openResult(item.kind, item.public_id, item.owner_public_id)
              }
            />
          </div>
        </div>
      ) : null}

      {getAdvertisements ? (
        <HomeAdvertisements
          getAdvertisements={getAdvertisements}
          location={location}
          onOpenOwner={openResult}
          recordAdvertisementClick={recordAdvertisementClick}
          recordAdvertisementViews={recordAdvertisementViews}
        />
      ) : null}

      <HomeDistrictOffers
        items={offers}
        needsDistrict={offersNeedDistrict}
        onOpenLocation={onOpenLocation}
        onOpenOffer={openOffer}
      />
      <AppToast message={toastMessage} />
    </main>
  );
}
