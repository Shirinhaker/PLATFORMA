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
  | "following"
  | "dining_places"
  | "dining_orders"
  | "medical_staff"
  | "medical_doctors"
  | "medical_doctor_services"
  | "medical_queue"
  | "medical_queue_history"
  | "education_groups"
  | "education_students"
  | "education_enrollments";

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
