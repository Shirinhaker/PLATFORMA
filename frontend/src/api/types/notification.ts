// `api/types.ts` dan ajratildi — domen bo'yicha.

export type NotificationRead = {
  id: number;
  title: string;
  body: string;
  order_id: number | null;
  listing_id: number | null;
  listing_public_id: string;
  profile_kind?: "user" | "business" | null;
  profile_public_id?: string;
  dining_order_id: number | null;
  medical_queue_id: number | null;
  ride_id: number | null;
  action_type: string;
  requires_action: boolean;
  is_read: boolean;
  created_at: number;
  read_at: number | null;
  resolved_at: number | null;
};

export type NotificationListRead = {
  items: NotificationRead[];
  unread: number;
};

export type NotificationPreference = {
  enabled: boolean;
  orders_enabled: boolean;
};

export type NotificationFilterCategory =
  "uy" | "ish" | "moshina" | "hayvon" | "texnika" | "boshqa";

export type NotificationFilterWrite = {
  cat: NotificationFilterCategory;
  region: string;
  district: string;
  price_min: number;
  price_max: number;
  keyword: string;
};

export type NotificationFilterRead = NotificationFilterWrite & {
  id: number;
  created_at: number;
};
