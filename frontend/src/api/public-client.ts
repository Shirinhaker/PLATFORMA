import type { ApiTransport } from "./http";
import type {
  FollowListRead,
  PublicAdvertisement,
  PublicAdvertisementParams,
  PublicCatalogItem,
  PublicCatalogParams,
  PublicCatalogResponse,
  PublicDistrictOffersResponse,
  PublicFeatures,
  PublicFollowedProfile,
  PublicHomeMapParams,
  PublicHomeMapResponse,
  PublicProfileDetail,
  PublicSearchParams,
  PublicSearchResponse,
} from "./types";

export function createPublicClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    searchPublic(params: PublicSearchParams = {}): Promise<PublicSearchResponse> {
      const query = new URLSearchParams();
      const textFilters = [
        ["q", params.q],
        ["result_type", params.result_type],
        ["direction", params.direction],
        ["activity_type", params.activity_type],
        ["region", params.region],
        ["district", params.district],
        ["mahalla", params.mahalla],
      ] as const;
      textFilters.forEach(([name, value]) => {
        if (value) query.set(name, value);
      });
      if (params.page !== undefined) query.set("page", String(params.page));
      if (params.page_size !== undefined)
        query.set("page_size", String(params.page_size));
      const suffix = query.size ? `?${query.toString()}` : "";
      return request("GET", `/api/v1/public/search${suffix}`);
    },

    getCatalogItems(params: PublicCatalogParams = {}): Promise<PublicCatalogResponse> {
      const query = new URLSearchParams();
      const textFilters = [
        ["kind", params.kind],
        ["q", params.q],
        ["direction", params.direction],
        ["activity_type", params.activity_type],
        ["region", params.region],
        ["district", params.district],
        ["mahalla", params.mahalla],
      ] as const;
      textFilters.forEach(([name, value]) => {
        if (value) query.set(name, value);
      });
      if (params.page !== undefined) query.set("page", String(params.page));
      if (params.page_size !== undefined)
        query.set("page_size", String(params.page_size));
      const suffix = query.size ? `?${query.toString()}` : "";
      return request("GET", `/api/v1/public/catalog/items${suffix}`);
    },

    getCatalogItem(publicId: string): Promise<PublicCatalogItem> {
      return request(
        "GET",
        `/api/v1/public/catalog/items/${encodeURIComponent(publicId)}`,
      );
    },

    getAdvertisements(
      params: PublicAdvertisementParams = {},
    ): Promise<PublicAdvertisement[]> {
      const query = new URLSearchParams();
      for (const [name, value] of [
        ["placement", params.placement],
        ["region", params.region],
        ["district", params.district],
      ] as const) {
        if (value) query.set(name, value);
      }
      const suffix = query.size ? `?${query.toString()}` : "";
      return request("GET", `/api/v1/public/advertisements${suffix}`);
    },

    getPublicFeatures(): Promise<PublicFeatures> {
      return request("GET", "/api/v1/public/features");
    },

    getHomeMap(params: PublicHomeMapParams): Promise<PublicHomeMapResponse> {
      const query = new URLSearchParams({ district: params.district });
      return request("GET", `/api/v1/public/home/map?${query.toString()}`);
    },

    getDistrictOffers(
      params: PublicHomeMapParams,
    ): Promise<PublicDistrictOffersResponse> {
      const query = new URLSearchParams({ district: params.district });
      return request("GET", `/api/v1/public/home/district-offers?${query.toString()}`);
    },

    getFollowedProfiles(): Promise<PublicFollowedProfile[]> {
      return request("GET", "/api/v1/public/home/followed-profiles", undefined, true);
    },

    getFollowers(): Promise<FollowListRead> {
      return request("GET", "/api/v1/follows/followers", undefined, true);
    },

    getFollowing(): Promise<FollowListRead> {
      return request("GET", "/api/v1/follows/following", undefined, true);
    },

    getPublicProfile(
      kind: "user" | "business",
      publicId: string,
    ): Promise<PublicProfileDetail> {
      return request(
        "GET",
        `/api/v1/public/profiles/${kind}/${encodeURIComponent(publicId)}`,
      );
    },
  };
}

export type PublicClient = ReturnType<typeof createPublicClient>;
