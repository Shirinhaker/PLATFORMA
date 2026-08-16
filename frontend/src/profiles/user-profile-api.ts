import type { ApiClient } from "../api/client";
import type { SessionIdentity } from "../api/types";

export type UserProfileApi = Pick<
  ApiClient,
  | "getSession"
  | "getUserProfile"
  | "updateUserProfile"
  | "createUploadGrant"
  | "uploadGrantedFile"
  | "attachUserAvatar"
  | "switchCabinet"
  | "logout"
> &
  Partial<
    Pick<
      ApiClient,
      | "getBusinessCredentials"
      | "updateBusinessCredentials"
      | "openBusiness"
      | "getMyListings"
      | "createListing"
      | "deleteListing"
      | "getMyAdvertisements"
      | "createAdvertisement"
      | "deleteAdvertisement"
      | "quoteAdvertisement"
      | "getSavedListings"
      | "getPaymentCatalog"
      | "createPaymentRequest"
      | "getMyOrders"
      | "getOrderInbox"
      | "markOrderSeen"
      | "changeOrderStatus"
      | "submitOrderPayment"
      | "decideOrderPayment"
      | "openOrderProblem"
      | "chooseOrderProblemSolution"
      | "handoffOrder"
      | "receiveOrder"
      | "getOrderChat"
      | "sendOrderChatMessage"
      | "sendOrderChatImage"
      | "editOrderChatMessage"
      | "deleteOrderChatMessage"
      | "getMyQueues"
      | "cancelMyQueue"
      | "markQueueNotificationRead"
      | "getMyStories"
      | "createStory"
      | "recordStoryView"
      | "getStoryViewers"
      | "deleteStory"
      | "reportStory"
      | "getMessageConversations"
      | "getMessageThread"
      | "sendMessage"
      | "sendMessageImage"
      | "editMessage"
      | "deleteMessage"
      | "getMessageUnreadCount"
      | "getReceivedReviews"
      | "replyToReview"
      | "getNotifications"
      | "getActionNotifications"
      | "markNotificationRead"
      | "markAllNotificationsRead"
      | "getNotificationPreference"
      | "saveNotificationPreference"
      | "getNotificationFilters"
      | "createNotificationFilter"
      | "deleteNotificationFilter"
      | "getPushStatus"
      | "getFollowers"
      | "getFollowing"
      | "getMyPayments"
      | "resubmitPayment"
      | "getMySpecialist"
      | "updateMySpecialist"
      | "addSpecialistCredential"
      | "deleteSpecialistCredential"
      | "createSpecialistOffer"
      | "updateSpecialistOffer"
      | "deleteSpecialistOffer"
      | "addSpecialistPortfolio"
      | "deleteSpecialistPortfolio"
      | "getTaxiPricing"
      | "getTaxiDriver"
      | "saveTaxiDriver"
      | "setTaxiDriverAvailable"
      | "getMyTaxiRides"
      | "getPendingTaxiRides"
      | "acceptTaxiRide"
      | "setTaxiRideStatus"
      | "updateTaxiRideProgress"
    >
  >;

export type UserProfileProps = {
  api: UserProfileApi;
  identity: SessionIdentity;
  onLogout: () => void;
  onOpenPublicListing?: (publicId: string) => void;
  onOpenPublicProfile?: (kind: "user" | "business", publicId: string) => void;
  onOpenDriverCabinet?: () => void;
  onSwitched: (identity: SessionIdentity) => void;
};
