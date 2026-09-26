import { useMemo } from "react";
import type { AppApi } from "./app-api";

export function usePublicApi(api: AppApi) {
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

  return {
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
  };
}
