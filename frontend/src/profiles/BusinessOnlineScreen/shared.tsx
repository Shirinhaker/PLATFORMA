// `BusinessOnlineScreen.tsx` dan ajratildi.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
  type PaymentTarget,
} from "../PaymentRequestModal";

import type { ApiClient } from "../../api/client";
import type {
  BusinessOnlineRecord,
  BusinessOnlineResource,
} from "../../api/business-online-types";
import type {
  BusinessProfile,
  NotificationRead,
  PaymentCatalog,
} from "../../api/types";
import { OwnerListings, type OwnerListingsApi } from "../../listings/OwnerListings";
import { BusinessDiningView } from "../BusinessDiningView";
import {
  BusinessAdvertisements,
  supportsAdvertisementApi,
} from "../../advertisements/BusinessAdvertisements";
import { BusinessDining, supportsDiningApi } from "../../dining/BusinessDining";
import {
  BusinessKitchen,
  supportsDiningKitchenApi,
} from "../../dining/BusinessKitchen";
import { OrdersCabinet, type OrdersApi } from "../../orders/OrdersCabinet";
import { BusinessEducationEnrollmentsView } from "../BusinessEducationEnrollmentsView";
import {
  BusinessMedicalProvidersView,
  BusinessMedicalQueueView,
} from "../BusinessMedicalView";
import { BusinessQueue, supportsBusinessQueueApi } from "../../queues/BusinessQueue";
import { CrudEditorView, ItemsEditorView } from "../BusinessOnlineEditingViews";
import {
  isServiceOrder,
  MessagesView,
  NotificationsView,
  type OrderFilter,
  OrdersView,
  PaymentsView,
  PeopleView,
  recordId,
  recordText,
  ReviewsView,
  type SharedActions,
  SubscriptionsView,
} from "../BusinessOnlineViews";
import { OwnerStories, type OwnerStoriesApi } from "../../stories/OwnerStories";
import { ReceivedReviews, type ReceivedReviewsApi } from "../../reviews/Reviews";
import {
  Notifications,
  type NotificationsApi,
} from "../../notifications/Notifications";
import "../BusinessOnlineScreen.css";
import "../BusinessExistingOnline.css";

export type OnlineApi = Partial<
  Pick<
    ApiClient,
    | "getBusinessOnlineResource"
    | "createBusinessOnlineRecord"
    | "patchBusinessOnlineRecord"
    | "deleteBusinessOnlineRecord"
    | "applyBusinessOnlineAction"
    | "getMyListings"
    | "createListing"
    | "deleteListing"
    | "createUploadGrant"
    | "uploadGrantedFile"
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
    | "getBusinessQueueSetup"
    | "getBusinessQueueProviders"
    | "createBusinessQueueProvider"
    | "updateBusinessQueueProvider"
    | "getBusinessQueueEntries"
    | "createBusinessOfflineQueue"
    | "changeBusinessQueueStatus"
    | "swapBusinessQueues"
    | "getMyStories"
    | "createStory"
    | "recordStoryView"
    | "getStoryViewers"
    | "deleteStory"
    | "reportStory"
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
  >
>;

export type Props = {
  api: OnlineApi;
  profile: BusinessProfile;
  view: string;
  title: string;
  onBack: () => void | Promise<void>;
  onViewChange?: (view: string) => void;
  initialOrderId?: number | null;
  onOpenOrder?: (orderId: number) => void | Promise<void>;
  onOpenNotification?: (notification: NotificationRead) => void | Promise<void>;
  onNotificationUnreadChange?: (count: number) => void;
  initialItemDraft?: BusinessOnlineRecord | null;
  onInitialItemDraftConsumed?: () => void;
};

export type ResourceState = Partial<
  Record<BusinessOnlineResource, BusinessOnlineRecord[]>
>;

export const VIEW_RESOURCE: Record<string, BusinessOnlineResource> = {
  subscriptions: "business_subscriptions",
  payments: "subscription_payments",
  items: "items",
  listings: "listings",
  orders: "orders",
  "service-orders": "orders",
  messages: "messages",
  reviews: "business_reviews",
  advertisements: "advertisements",
  stories: "stories",
  notifications: "notifications",
  followers: "followers",
  following: "following",
  "dining-places": "dining_places",
  "medical-providers": "medical_doctors",
  "medical-queue": "medical_queue",
  "education-enrollments": "education_enrollments",
};

export function viewResources(
  view: string,
  primary?: BusinessOnlineResource,
): BusinessOnlineResource[] {
  if (!primary) return [];
  if (view === "items") return [primary, "item_groups"];
  if (view === "dining-places") {
    return [primary, "dining_orders", "items", "item_groups"];
  }
  if (view === "medical-providers") {
    return [primary, "medical_staff", "items"];
  }
  if (view === "medical-queue") {
    return [primary, "medical_doctors", "medical_staff", "items"];
  }
  if (view === "education-enrollments") {
    return [primary, "education_groups"];
  }
  if (view === "notifications") {
    return [primary, "notify_filters", "push_preferences"];
  }
  return [primary];
}

export function rowsFromProfile(
  profile: BusinessProfile,
  resource: BusinessOnlineResource,
): BusinessOnlineRecord[] {
  const value = profile.cabinet_payload[resource];
  return Array.isArray(value)
    ? value.filter((row): row is BusinessOnlineRecord =>
        Boolean(row && typeof row === "object"),
      )
    : [];
}

export function nextLocalId(rows: BusinessOnlineRecord[]): number {
  return (
    Math.max(0, ...rows.map((row) => Number(row.id ?? 0)).filter(Number.isFinite)) + 1
  );
}

export function supportsOwnerListings(
  api: OnlineApi,
): api is OnlineApi & OwnerListingsApi {
  return [
    "getMyListings",
    "createListing",
    "deleteListing",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof OnlineApi] === "function");
}

export function supportsOrders(api: OnlineApi): api is OnlineApi & OrdersApi {
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
  ].every((method) => typeof api[method as keyof OnlineApi] === "function");
}

export function supportsOwnerStories(
  api: OnlineApi,
): api is OnlineApi & OwnerStoriesApi {
  return [
    "getMyStories",
    "createStory",
    "recordStoryView",
    "getStoryViewers",
    "deleteStory",
    "reportStory",
    "createUploadGrant",
    "uploadGrantedFile",
  ].every((method) => typeof api[method as keyof OnlineApi] === "function");
}

export function supportsReceivedReviews(
  api: OnlineApi,
): api is OnlineApi & ReceivedReviewsApi {
  return ["getReceivedReviews", "replyToReview"].every(
    (method) => typeof api[method as keyof OnlineApi] === "function",
  );
}

export function supportsNotifications(
  api: OnlineApi,
): api is OnlineApi & NotificationsApi {
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
  ].every((method) => typeof api[method as keyof OnlineApi] === "function");
}

export type RenderContext = {
  api: OnlineApi;
  view: string;
  items: BusinessOnlineRecord[];
  groups: BusinessOnlineRecord[];
  profile: BusinessProfile;
  shared: SharedActions;
  loading: boolean;
  duration: number;
  setDuration: (value: number) => void;
  openPayment: (plan: "plus" | "pro") => void;
  openPaymentTarget: (target: PaymentTarget) => void;
  query: string;
  setQuery: (value: string) => void;
  kind: string;
  setKind: (value: string) => void;
  orderFilter: OrderFilter;
  setOrderFilter: (value: OrderFilter) => void;
  messageText: string;
  setMessageText: (value: string) => void;
  replyId: number | string | null;
  setReplyId: (value: number | string | null) => void;
  replyText: string;
  setReplyText: (value: string) => void;
  refresh: (...names: BusinessOnlineResource[]) => Promise<void>;
  hasActionApi: boolean;
  resources: ResourceState;
  create: (
    resource: BusinessOnlineResource,
    record: BusinessOnlineRecord,
  ) => Promise<boolean>;
  patch: (
    resource: BusinessOnlineResource,
    id: number | string,
    value: BusinessOnlineRecord,
  ) => Promise<boolean>;
  remove: (resource: BusinessOnlineResource, id: number | string) => Promise<boolean>;
  action: (
    resource: BusinessOnlineResource,
    name: string,
    id?: number | string,
    payload?: BusinessOnlineRecord,
  ) => Promise<BusinessOnlineRecord | null>;
  setSubscreenBack: (handler: (() => void) | null, title?: string) => void;
  onOpenOrder?: (orderId: number) => void | Promise<void>;
  onViewChange?: (view: string) => void;
  uploadItemImage?: (file: File) => Promise<string>;
};
