import type { DriverCabinetApi } from "../taxi/DriverCabinet";
import type { FollowListsApi } from "../follows/FollowLists";
import type { OwnerListingsApi } from "../listings/OwnerListings";
import type { MessagesApi } from "../messages/Messages";
import type { NotificationsApi } from "../notifications/Notifications";
import type { OrdersApi } from "../orders/OrdersCabinet";
import type { MyQueuesApi } from "../queues/MyQueues";
import type { ReceivedReviewsApi } from "../reviews/Reviews";
import type { SpecialistApi } from "../specialists/Specialist";
import type { OwnerStoriesApi } from "../stories/OwnerStories";
import { supportsAdvertisementApi } from "../advertisements/BusinessAdvertisements";
import type { UserAdvertisementsApi } from "../advertisements/UserAdvertisements";
import type { UserCabinetSection } from "./UserCabinetDashboard";
import type { UserProfileApi } from "./user-profile-api";

export type CabinetView = "dashboard" | "profile" | "specialist" | string;
type PayloadSource = string | readonly string[];

type Section = UserCabinetSection & {
  payload?: PayloadSource;
};

export const SECTIONS: Section[] = [
  {
    icon: "👤",
    label: "Profilim",
    caption: "Ism, telefon, yashash tumani",
    view: "profile",
  },
  {
    icon: "💳",
    label: "To‘lovlarim",
    caption: "Reklama to‘lovlari va tekshiruv holati",
    view: "payments",
    payload: "payments",
  },
  {
    icon: "📢",
    label: "Reklamalarim",
    caption: "Bosh sahifa reklamalarini boshqarish",
    view: "advertisements",
  },
  {
    icon: "🎞️",
    label: "Istoriya arxivi",
    caption: "Faol va arxivdagi shaxsiy istoriyalar",
    view: "stories",
    payload: "stories",
  },
  {
    icon: "💬",
    label: "Suhbatlar",
    caption: "Xabarlar va chatlar",
    view: "messages",
    payload: "messages",
  },
  {
    icon: "🔔",
    label: "Bildirishnomalarim",
    caption: "Qiziqishlaringizni belgilang",
    view: "notifications",
    payload: "notifications",
  },
  {
    icon: "🧰",
    label: "Mutaxassisligim va xizmatlarim",
    caption: "Qidiruv va xaritada mutaxassis sifatida chiqish",
    view: "specialist",
  },
  {
    icon: "📦",
    label: "Buyurtmalarim",
    caption: "Mahsulot buyurtmalarim",
    view: "orders",
    payload: "orders",
  },
  {
    icon: "🧰",
    label: "Xizmat buyurtmalarim",
    caption: "Xizmat va qabullarim",
    view: "service-orders",
    payload: "orders",
  },
  {
    icon: "🔖",
    label: "Saqlanganlar",
    caption: "Saqlangan e'lon va bizneslar",
    view: "saved",
    payload: "saved",
  },
  {
    icon: "⚙️",
    label: "Sozlamalar",
    caption: "Akkaunt, til, chiqish",
    view: "settings",
  },
];

export function supportsOwnerStories(
  api: UserProfileApi,
): api is UserProfileApi & OwnerStoriesApi {
  return [
    "getMyStories",
    "createStory",
    "recordStoryView",
    "getStoryViewers",
    "deleteStory",
    "reportStory",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

export function supportsTaxi(
  api: UserProfileApi,
): api is UserProfileApi &
  DriverCabinetApi &
  Required<Pick<UserProfileApi, "getMyTaxiRides">> {
  return [
    "getTaxiDriver",
    "getTaxiPricing",
    "saveTaxiDriver",
    "setTaxiDriverAvailable",
    "getMyTaxiRides",
    "getPendingTaxiRides",
    "acceptTaxiRide",
    "setTaxiRideStatus",
    "updateTaxiRideProgress",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

export function message(error: unknown) {
  return error instanceof Error ? error.message : "So‘rov bajarilmadi.";
}

export function isServiceOrder(row: unknown) {
  if (!row || typeof row !== "object") return false;
  const value = row as Record<string, unknown>;
  if (String(value.order_category ?? "") === "service") return true;
  return ["booking", "service", "queue", "medical"].includes(
    String(value.order_type ?? value.kind ?? ""),
  );
}

export function payloadRows(
  payload: Record<string, unknown>,
  source: PayloadSource,
): unknown[] {
  const keys = typeof source === "string" ? [source] : source;
  return keys.flatMap((key) => {
    const value = payload[key];
    return Array.isArray(value) ? value : [];
  });
}

export function supportsOwnerListings(
  api: UserProfileApi,
): api is UserProfileApi & OwnerListingsApi {
  return ["getMyListings", "createListing", "deleteListing"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

export function supportsUserAdvertisements(
  api: UserProfileApi,
): api is UserProfileApi & UserAdvertisementsApi {
  return (
    supportsAdvertisementApi(api) &&
    [
      "getPaymentCatalog",
      "createPaymentRequest",
      "createUploadGrant",
      "uploadGrantedFile",
    ].every((method) => typeof api[method as keyof UserProfileApi] === "function")
  );
}

export function supportsOrders(api: UserProfileApi): api is UserProfileApi & OrdersApi {
  return [
    "getMyOrders",
    "getOrderInbox",
    "markOrderSeen",
    "changeOrderStatus",
    "submitOrderPayment",
    "decideOrderPayment",
    "openOrderProblem",
    "chooseOrderProblemSolution",
    "handoffOrder",
    "receiveOrder",
    "getOrderChat",
    "sendOrderChatMessage",
    "sendOrderChatImage",
    "editOrderChatMessage",
    "deleteOrderChatMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

export function supportsMyQueues(
  api: UserProfileApi,
): api is UserProfileApi & MyQueuesApi {
  return ["getMyQueues", "cancelMyQueue"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

export function supportsMessages(
  api: UserProfileApi,
): api is UserProfileApi & MessagesApi {
  return [
    "getMessageConversations",
    "getMessageThread",
    "sendMessage",
    "sendMessageImage",
    "editMessage",
    "deleteMessage",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

export function supportsReceivedReviews(
  api: UserProfileApi,
): api is UserProfileApi & ReceivedReviewsApi {
  return ["getReceivedReviews", "replyToReview"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

export function supportsNotifications(
  api: UserProfileApi,
): api is UserProfileApi & NotificationsApi {
  return [
    "getNotifications",
    "getActionNotifications",
    "markNotificationRead",
    "markAllNotificationsRead",
    "getNotificationPreference",
    "saveNotificationPreference",
    "getNotificationFilters",
    "createNotificationFilter",
    "deleteNotificationFilter",
    "getPushStatus",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

export function supportsFollowLists(
  api: UserProfileApi,
): api is UserProfileApi & FollowListsApi {
  return ["getFollowers", "getFollowing"].every(
    (method) => typeof api[method as keyof UserProfileApi] === "function",
  );
}

export function supportsSpecialist(
  api: UserProfileApi,
): api is UserProfileApi & SpecialistApi {
  return [
    "getMySpecialist",
    "updateMySpecialist",
    "addSpecialistCredential",
    "deleteSpecialistCredential",
    "createSpecialistOffer",
    "updateSpecialistOffer",
    "deleteSpecialistOffer",
    "addSpecialistPortfolio",
    "deleteSpecialistPortfolio",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof UserProfileApi] === "function");
}

export function supportsBusinessOpening(
  api: UserProfileApi,
): api is UserProfileApi & Required<Pick<UserProfileApi, "openBusiness">> {
  return typeof api.openBusiness === "function";
}

export function markLegacyNotificationRead(
  setProfile: Dispatch<SetStateAction<UserProfileData | null>>,
  setNotificationUnread: Dispatch<SetStateAction<number>>,
  notificationId: number,
) {
  setProfile((current) => {
    if (!current) return current;
    const payload = { ...(current.cabinet_payload ?? {}) };
    const notifications = Array.isArray(payload.notifications)
      ? payload.notifications.map((value) => {
          if (!value || typeof value !== "object") return value;
          const row = value as Record<string, unknown>;
          return Number(row.id ?? 0) === notificationId ? { ...row, is_read: 1 } : row;
        })
      : [];
    payload.notifications = notifications;
    const unread = notifications.filter(
      (value) =>
        value &&
        typeof value === "object" &&
        !Boolean(Number((value as Record<string, unknown>).is_read ?? 0)),
    ).length;
    setNotificationUnread(unread);
    return {
      ...current,
      cabinet_payload: payload,
      dashboard_snapshot: { ...(current.dashboard_snapshot ?? {}), unread },
    };
  });
}
import type { Dispatch, SetStateAction } from "react";

import type { UserProfile as UserProfileData } from "../api/types";
