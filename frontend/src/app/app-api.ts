import type { ApiClient } from "../api/client";
import type { AuthApi } from "../auth/AuthFlow";
import type { CourseEnrollmentApi } from "../education/CourseEnrollment";
import type { MessagesApi } from "../messages/Messages";
import type { BusinessProfileApi } from "../profiles/BusinessProfile";
import type { UserProfileApi } from "../profiles/UserProfile";
import type { QueueBookingApi } from "../queues/QueueBooking";
import type { PublicReviewsApi } from "../reviews/Reviews";

export type SessionApi = Pick<ApiClient, "getSession">;
type ProfileApi = UserProfileApi & BusinessProfileApi;
type PublicSearchApi = Pick<
  ApiClient,
  | "searchPublic"
  | "getCatalogItems"
  | "getCatalogItem"
  | "getAdvertisements"
  | "getPublicFeatures"
  | "getHomeMap"
  | "getDistrictOffers"
  | "getFollowedProfiles"
  | "getPublicProfile"
  | "recordAdvertisementViews"
  | "recordAdvertisementClick"
  | "getListingCounts"
  | "getPublicListings"
  | "getPublicListing"
  | "toggleListingSave"
  | "getStoryFeed"
  | "getOwnerStories"
  | "recordStoryView"
  | "getStoryViewers"
  | "deleteStory"
  | "reportStory"
>;
type OrderApi = Pick<ApiClient, "createOrder">;
type TaxiAppApi = Pick<
  ApiClient,
  | "getTaxiPricing"
  | "getTaxiDriver"
  | "saveTaxiDriver"
  | "setTaxiDriverAvailable"
  | "createTaxiRide"
  | "getMyTaxiRides"
  | "cancelTaxiRide"
  | "getPendingTaxiRides"
  | "acceptTaxiRide"
  | "setTaxiRideStatus"
  | "updateTaxiRideProgress"
  | "reverseGeocode"
>;

export type AppApi = SessionApi &
  Partial<AuthApi> &
  Partial<ProfileApi> &
  Partial<PublicSearchApi> &
  Partial<OrderApi> &
  Partial<QueueBookingApi> &
  Partial<CourseEnrollmentApi> &
  Partial<MessagesApi> &
  Partial<PublicReviewsApi> &
  Partial<TaxiAppApi>;

export function supportsAuthFlow(api: AppApi): api is SessionApi & AuthApi {
  return [
    "startRegistration",
    "startLogin",
    "verifyRegistration",
    "verifyLogin",
    "resendChallenge",
  ].every((method) => typeof api[method as keyof AppApi] === "function");
}

export function supportsProfiles(api: AppApi): api is SessionApi & ProfileApi {
  return [
    "getUserProfile",
    "updateUserProfile",
    "getBusinessProfile",
    "updateBusinessProfile",
    "createUploadGrant",
    "uploadGrantedFile",
    "attachUserAvatar",
    "attachBusinessLogo",
    "switchCabinet",
    "logout",
  ].every((method) => typeof api[method as keyof AppApi] === "function");
}

export function supportsMessages(api: AppApi): api is AppApi & MessagesApi {
  return [
    "getMessageConversations",
    "getMessageThread",
    "sendMessage",
    "sendMessageImage",
    "editMessage",
    "deleteMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof AppApi] === "function");
}

export function supportsPublicReviews(api: AppApi): api is AppApi & PublicReviewsApi {
  return ["getReviews", "saveReview", "deleteReview"].every(
    (method) => typeof api[method as keyof AppApi] === "function",
  );
}
