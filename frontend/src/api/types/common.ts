// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { NotificationRead } from "./notification";
import type { StoryRead } from "./story";

export type AccountType = "user" | "business";

export type BuildInfo = {
  api_version: "v1";
  foundation: "phase1";
  legacy_build: "v1656";
};

export type ApiErrorBody = {
  code: string;
  message: string;
  request_id: string;
};

export type SessionIdentity = {
  account_id: number;
  account_type: AccountType;
  name: string;
  login: string;
  csrf_token: string;
  expires_at: string;
  actor_type?: "owner" | "staff";
  staff_id?: number | null;
  permissions?: string[];
};

export type Me = {
  account_id: number;
  account_type: AccountType;
  name: string;
  profile_complete: boolean;
};

export type RegistrationStart = {
  account_type: AccountType;
  name: string;
  phone?: string;
  direction?: string;
  address?: string;
};

export type ChallengeStarted = {
  request_id: number;
  deep_link: string;
  expires_in: number;
  resend_after: number;
  code_sent?: boolean;
};

export type ChallengeVerification = {
  request_id: number;
  code: string;
  device_name?: string;
};

export type Authenticated = {
  account_id: number;
  account_type: AccountType;
  csrf_token: string;
  expires_at: string;
  login?: string;
  password?: string;
};

export type ChallengeResent = {
  request_id: number;
  code_version: number;
  expires_in: number;
  resend_after: number;
};

export type CabinetActivity = {
  id: number;
  kind: string;
  title: string;
  status: string;
  amount: number;
  created_at: number;
};

export type CabinetPayload = Record<string, unknown>;

export type StatisticsPeriod = "kun" | "hafta" | "oy" | "chorak" | "yarim" | "yil";

export type StatisticsPayment = {
  naqd: number;
  karta: number;
  qarz: number;
  order: number;
};

export type StatisticsSource = { count: number; total: number };

export type StatisticsTrend = {
  label: string;
  rev: number;
  exp: number;
  cogs: number;
  profit: number;
};

export type StatisticsProduct = {
  name: string;
  qty: number;
  unit: string;
  total: number;
  cost_total: number;
  margin: number | null;
};

export type StatisticsReport = {
  period: StatisticsPeriod;
  anchor: string;
  label: string;
  revenue: number;
  cash_in: number;
  cogs: number;
  gross_profit: number;
  expenses: number;
  inventory_purchases: number;
  profit: number;
  qarzpay: number;
  pay: StatisticsPayment;
  exp_by_cat: Record<string, number>;
  trend: StatisticsTrend[];
  top_products: StatisticsProduct[];
  low_stock: Array<{ name: string; unit: string; stock_qty: number }>;
  source_split: {
    internal: StatisticsSource;
    external: StatisticsSource;
    manual: StatisticsSource;
  };
  cashiers: Array<{ name: string; checks: number; total: number }>;
  waiters: Array<{ name: string; orders: number; total: number }>;
  sales_count: number;
  can_next: boolean;
};

export type ReverseGeocodeResult = {
  address?: string;
  region?: string;
  district?: string;
};

export type CabinetSwitch = {
  account_id: number;
  account_type: AccountType;
  login: string;
  csrf_token: string;
  expires_at: string;
};

export type MediaPurpose =
  | "avatar"
  | "logo"
  | "payment_qr"
  | "listing_photo"
  | "listing_video"
  | "order_chat_image"
  | "chat_image"
  | "payment_receipt"
  | "advertisement_image"
  | "story_image"
  | "story_video"
  | "specialist_credential"
  | "specialist_offer_image"
  | "specialist_portfolio_image"
  | "specialist_portfolio_video"
  | "catalog_item_image";

export type FollowProfileRead = {
  kind: "user" | "business";
  public_id: string;
  name: string;
  info: string;
  image_url: string;
  crop_x: number;
  crop_y: number;
  crop_zoom: number;
  followed_at: number;
};

export type FollowListRead = {
  items: FollowProfileRead[];
  count: number;
};

export type ActionNotificationListRead = {
  items: NotificationRead[];
  count: number;
};

export type PushStatusRead = {
  provider: "firebase";
  configured: boolean;
  active_devices: number;
  pending: number;
};

export type PushDeviceWrite = {
  token: string;
  platform: "android" | "ios" | "web";
  device_name?: string;
  app_version?: string;
};

export type ManagedStoryRead = StoryRead & {
  view_count: number;
};

export type UploadGrantRequest = {
  purpose: MediaPurpose;
  filename: string;
  content_type: string;
  size_bytes: number;
};

export type UploadGrant = {
  object_key: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in_seconds: number;
};

export type ProfileImageAttachment = {
  object_key: string;
  x: number;
  y: number;
  zoom: number;
};

export type CourseEnrollmentCreate = {
  course_item_public_id: string;
  phone: string;
  note: string;
};

export type CourseEnrollmentCreated = {
  ok: boolean;
  id: number;
};
