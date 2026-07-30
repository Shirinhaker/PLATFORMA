export type BusinessOnlineResource =
  | "business_subscriptions"
  | "subscription_payments"
  | "item_groups"
  | "items"
  | "listings"
  | "orders"
  | "messages"
  | "business_reviews"
  | "advertisements"
  | "stories"
  | "notifications"
  | "followers"
  | "following";

export type BusinessOnlineRecord = Record<string, unknown>;

export type BusinessOnlineResourceRead = {
  resource: BusinessOnlineResource;
  items: BusinessOnlineRecord[];
};

export type BusinessOnlineMutationRead = {
  resource: BusinessOnlineResource;
  item: BusinessOnlineRecord | null;
  items: BusinessOnlineRecord[];
};

export type BusinessOnlineActionInput = {
  record_id?: number | string;
  payload?: BusinessOnlineRecord;
};
