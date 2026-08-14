import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type { ApiClient } from "../api/client";
import type {
  PublicDistrictOffer,
  PublicFollowedProfile,
  PublicHomeMapResponse,
  PublicSearchItem,
  StoryGroup,
} from "../api/types";
import { AppToast } from "./AppToast";
import { HomeAdvertisements } from "./HomeAdvertisements";
import { HomeDistrictOffers } from "./home/HomeDistrictOffers";
import { HomeFollowedProfiles } from "./home/HomeFollowedProfiles";
import { HomeMap } from "./home/HomeMap";
import { HomeSearchResults } from "./home/HomeSearchResults";
import { findLocationCenter } from "./location-centers";
import type { HomeLocation } from "./location-storage";
import {
  StoryFeed,
  type StoryViewerApi,
} from "../stories/StoryFeed";


interface HomeScreenProps {
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
  ) => void;
  recordAdvertisementClick?: ApiClient["recordAdvertisementClick"];
  recordAdvertisementViews?: ApiClient["recordAdvertisementViews"];
  searchPublic?: ApiClient["searchPublic"];
  storyApi?: StoryViewerApi & Pick<ApiClient, "getStoryFeed">;
  taxiEnabled?: boolean;
  onTaxiCall?: () => void;
}


const EMPTY_MAP: PublicHomeMapResponse = { businesses: [], specialists: [] };
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
  const [query, setQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const [homeMap, setHomeMap] = useState<PublicHomeMapResponse>(EMPTY_MAP);
  const [followedProfiles, setFollowedProfiles] = useState<PublicFollowedProfile[]>([]);
  const [offers, setOffers] = useState<PublicDistrictOffer[]>([]);
  const [offersNeedDistrict, setOffersNeedDistrict] = useState(!currentDistrict);
  const [results, setResults] = useState<PublicSearchItem[] | null>(null);
  const [resultQuery, setResultQuery] = useState("");
  const [searchError, setSearchError] = useState("");
  const [searchPending, setSearchPending] = useState(false);
  const [searchCursor, setSearchCursor] = useState<string | null>(null);
  const [searchHasMore, setSearchHasMore] = useState(false);
  const [searchPage, setSearchPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const queryInput = useRef<HTMLInputElement>(null);
  const searchSequence = useRef(0);
  const district = currentDistrict?.trim() || "";
  const districtLabel = district || "Hudud tanlanmagan";
  const locationCenter = (
    location?.latitude != null
    && location.longitude != null
  ) ? {
      latitude: location.latitude,
      longitude: location.longitude,
    } : findLocationCenter(location?.region || "", location?.district || "");
  const loadStories = useCallback(() => {
    if (!storyApi) return Promise.resolve([]);
    return storyApi.getStoryFeed({
      ...(locationCenter?.latitude === undefined ? {} : { lat: locationCenter.latitude }),
      ...(locationCenter?.longitude === undefined ? {} : { lng: locationCenter.longitude }),
    });
  }, [locationCenter?.latitude, locationCenter?.longitude, storyApi]);

  useEffect(() => {
    let active = true;
    if (!district || !getHomeMap) {
      setHomeMap(EMPTY_MAP);
      return () => {
        active = false;
      };
    }
    getHomeMap({ district })
      .then((payload) => {
        if (active) setHomeMap(payload);
      })
      .catch(() => {
        if (active) setHomeMap(EMPTY_MAP);
      });
    return () => {
      active = false;
    };
  }, [district, getHomeMap]);

  useEffect(() => {
    let active = true;
    if (!district) {
      setOffers([]);
      setOffersNeedDistrict(true);
      return () => {
        active = false;
      };
    }
    if (!getDistrictOffers) {
      setOffers([]);
      setOffersNeedDistrict(false);
      return () => {
        active = false;
      };
    }
    getDistrictOffers({ district })
      .then((payload) => {
        if (!active) return;
        setOffers(payload.items);
        setOffersNeedDistrict(payload.needs_district);
      })
      .catch(() => {
        if (active) {
          setOffers([]);
          setOffersNeedDistrict(false);
        }
      });
    return () => {
      active = false;
    };
  }, [district, getDistrictOffers]);

  useEffect(() => {
    let active = true;
    if (!authenticated || !getFollowedProfiles) {
      setFollowedProfiles([]);
      return () => {
        active = false;
      };
    }
    getFollowedProfiles()
      .then((items) => {
        if (active) setFollowedProfiles(items);
      })
      .catch(() => {
        if (active) setFollowedProfiles([]);
      });
    return () => {
      active = false;
    };
  }, [authenticated, getFollowedProfiles]);

  const openResult = useCallback((
    kind: "user" | "business" | "product" | "service" | "listing",
    publicId: string,
  ) => {
    onOpenPublicResult(kind, publicId);
  }, [onOpenPublicResult]);

  const renderFollowedProfiles = useCallback((
    groups: StoryGroup[],
    onOpenStory: (index: number) => void,
  ) => (
    <HomeFollowedProfiles
      items={followedProfiles}
      storyGroups={groups}
      onOpenProfile={openResult}
      onOpenStory={onOpenStory}
    />
  ), [followedProfiles, openResult]);

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
    setSearchCursor(null);
    setSearchHasMore(false);
    setSearchPage(1);
    setLoadingMore(false);
    setToastMessage("");
    onResultsActiveChange?.(true);
    void searchPublic({
      q: normalizedQuery,
      region: location?.region || "",
      district: location?.district || "",
      page: 1,
      page_size: 20,
    }).then((payload) => {
      if (requestSequence !== searchSequence.current) return;
      setResults(payload.items);
      setSearchCursor(payload.next_cursor ?? null);
      setSearchHasMore(Boolean(payload.has_more ?? payload.page < payload.pages));
      setSearchPage(payload.page);
      setSearchPending(false);
    }).catch((error: unknown) => {
      if (requestSequence !== searchSequence.current) return;
      setResults([]);
      setSearchPending(false);
      setSearchError(
        error instanceof Error ? error.message : String(error || ""),
      );
    });
  }

  function loadMore() {
    if (
      !searchPublic
      || loadingMore
      || searchPending
      || !searchHasMore
    ) return;
    const requestSequence = searchSequence.current;
    setLoadingMore(true);
    void searchPublic({
      q: resultQuery,
      region: location?.region || "",
      district: location?.district || "",
      page_size: 20,
      ...(searchCursor
        ? { cursor: searchCursor }
        : { page: searchPage + 1 }),
    }).then((payload) => {
      if (requestSequence !== searchSequence.current) return;
      setResults((current) => {
        const merged = [...(current || []), ...payload.items];
        return merged.filter((item, index) => (
          merged.findIndex((candidate) => (
            candidate.kind === item.kind
            && candidate.public_id === item.public_id
          )) === index
        ));
      });
      setSearchCursor(payload.next_cursor ?? null);
      setSearchHasMore(Boolean(payload.has_more ?? payload.page < payload.pages));
      setSearchPage(payload.page);
    }).catch((error: unknown) => {
      if (requestSequence !== searchSequence.current) return;
      setToastMessage(
        error instanceof Error ? error.message : String(error || ""),
      );
    }).finally(() => {
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
    setLoadingMore(false);
    setToastMessage("");
    onResultsActiveChange?.(false);
  }

  function openOffer(item: PublicDistrictOffer) {
    openResult(item.kind, item.content_public_id);
  }

  return (
    <main className="screen active public-home-modular" data-screen="home">
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
        <HomeFollowedProfiles
          items={followedProfiles}
          onOpenProfile={openResult}
        />
      )}

      <div className="home-discovery" id="homeDiscovery">
        <div className={`home-search-card${searchFocused ? " mobile-search-focused" : ""}`}>
          <h1>Kerakli mahsulot va<br />xizmatni yaqiningizdan toping</h1>
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
              <span className="home-catalog-chevron" aria-hidden="true">⌄</span>
            </button>
            <button className="home-search-submit" type="submit">Qidirish</button>
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
              hasMore={searchHasMore}
              items={results}
              loadingMore={loadingMore}
              pending={searchPending}
              query={resultQuery}
              onLoadMore={loadMore}
              onOpenResult={(item) => openResult(item.kind, item.public_id)}
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
