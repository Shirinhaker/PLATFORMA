import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../../../api/client";
import type { PublicDistrictOffer, PublicFollowedProfile, PublicHomeMapResponse } from "../../../api/types";

const EMPTY_MAP: PublicHomeMapResponse = { businesses: [], specialists: [] };
const EMPTY_OFFERS: { items: PublicDistrictOffer[]; needs_district: boolean } = { items: [], needs_district: false };
const EMPTY_PROFILES: PublicFollowedProfile[] = [];

function useDiscoveryResource<T>(load: () => Promise<T> | undefined, empty: T) {
  const [data, setData] = useState(empty);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError(false);
    setData(empty);
    load()?.then((value) => { if (active) setData(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [load, empty, attempt]);
  return { data, error, retry: () => setAttempt((value) => value + 1) };
}

export function useHomeDiscovery({ district, authenticated, getHomeMap, getDistrictOffers, getFollowedProfiles }: {
  district: string;
  authenticated: boolean;
  getHomeMap?: ApiClient["getHomeMap"];
  getDistrictOffers?: ApiClient["getDistrictOffers"];
  getFollowedProfiles?: ApiClient["getFollowedProfiles"];
}) {
  const map = useDiscoveryResource(useCallback(() => district ? getHomeMap?.({ district }) : undefined, [district, getHomeMap]), EMPTY_MAP);
  const offers = useDiscoveryResource(useCallback(() => district ? getDistrictOffers?.({ district }) : undefined, [district, getDistrictOffers]), EMPTY_OFFERS);
  const followed = useDiscoveryResource(useCallback(() => authenticated ? getFollowedProfiles?.() : undefined, [authenticated, getFollowedProfiles]), EMPTY_PROFILES);
  return {
    homeMap: map.data,
    offers: offers.data.items,
    offersNeedDistrict: !district || offers.data.needs_district,
    followedProfiles: followed.data,
    failures: [
      { name: "Xaritadagi profillar", ...map },
      { name: "Hududiy takliflar", ...offers },
      { name: "Kuzatilayotgan profillar", ...followed },
    ].filter((resource) => resource.error),
  };
}
