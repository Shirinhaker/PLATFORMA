import type { ApiTransport } from "./http";
import type {
  ListingCreate,
  ListingPatch,
  ListingRead,
  PublicListingParams,
} from "./types";

export function createListingsClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getListingCounts(): Promise<Record<string, number>> {
      return request("GET", "/api/v1/public/listings/counts");
    },

    getPublicListings(params: PublicListingParams = {}): Promise<ListingRead[]> {
      const query = new URLSearchParams();
      if (params.cat) query.set("cat", params.cat);
      if (params.q) query.set("q", params.q);
      const suffix = query.size ? `?${query.toString()}` : "";
      return request("GET", `/api/v1/public/listings${suffix}`);
    },

    getPublicListing(publicId: string): Promise<ListingRead> {
      return request("GET", `/api/v1/public/listings/${encodeURIComponent(publicId)}`);
    },

    getMyListings(): Promise<ListingRead[]> {
      return request("GET", "/api/v1/listings/mine", undefined, true);
    },

    createListing(body: ListingCreate): Promise<ListingRead> {
      return request("POST", "/api/v1/listings", body, true);
    },

    patchListing(publicId: string, body: ListingPatch): Promise<ListingRead> {
      return request(
        "PUT",
        `/api/v1/listings/${encodeURIComponent(publicId)}`,
        body,
        true,
      );
    },

    deleteListing(publicId: string): Promise<void> {
      return request(
        "DELETE",
        `/api/v1/listings/${encodeURIComponent(publicId)}`,
        undefined,
        true,
      );
    },

    toggleListingSave(publicId: string): Promise<{ saved: boolean }> {
      return request(
        "POST",
        `/api/v1/listings/${encodeURIComponent(publicId)}/save`,
        {},
        true,
      );
    },

    getSavedListings(): Promise<ListingRead[]> {
      return request("GET", "/api/v1/listings/saved", undefined, true);
    },
  };
}

export type ListingsClient = ReturnType<typeof createListingsClient>;
