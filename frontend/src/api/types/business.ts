// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { CabinetActivity, CabinetPayload } from "./common";
import type { DocumentDirection } from "./document";
import type { QueueEntryStatus, QueueProviderMode, QueueProviderStatus } from "./queue";

export type BusinessCredentials = {
  ok: boolean;
  login: string;
};

export type BusinessCredentialsUpdate = {
  new_login: string;
  new_password: string;
};

export type BusinessDocumentWrite = {
  direction: DocumentDirection;
  doc_type: string;
  title: string;
  number: string;
  doc_date: string;
  contractor_id: number | null;
  body: string;
};

export type BusinessDocument = BusinessDocumentWrite & {
  id: number;
  contractor_name: string;
  sender_name: string;
  receiver_inn: string;
  status: "" | "yuborilgan" | "kutilmoqda" | "qabul qilindi" | "rad etildi";
  created_at: string;
};

export type BusinessDocumentList = {
  documents: BusinessDocument[];
  count: number;
};

export type BusinessProfile = {
  account_id: number;
  name: string;
  phone: string;
  description: string;
  public_username: string;
  direction: string;
  activity_type: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  work_hours: Record<string, unknown>;
  pay_card: string;
  pay_holder: string;
  pay_qr_object_key: string;
  pay_qr_url: string;
  director: string;
  tax_id: string;
  logo_object_key: string;
  logo_url: string;
  logo_x: number;
  logo_y: number;
  logo_zoom: number;
  followers_count: number;
  following_count: number;
  rating_sum: number;
  rating_count: number;
  map_visible: boolean;
  dashboard_snapshot: Record<string, number>;
  recent_activity: CabinetActivity[];
  cabinet_payload: CabinetPayload;
};

export type BusinessProfilePatch = Partial<
  Pick<
    BusinessProfile,
    | "name"
    | "phone"
    | "description"
    | "public_username"
    | "direction"
    | "activity_type"
    | "address"
    | "latitude"
    | "longitude"
    | "work_hours"
    | "pay_card"
    | "pay_holder"
    | "pay_qr_object_key"
    | "director"
    | "tax_id"
    | "map_visible"
  >
>;

export type BusinessOpeningWrite = {
  name: string;
  direction: string;
  activity_type: string;
  phone: string;
  address: string;
};

export type BusinessOpeningRead = {
  ok: true;
  business_account_id: number;
  biz_login: string;
  biz_password: string;
};

export type BusinessQueueService = {
  public_id: string;
  name: string;
  price_text: string;
};

export type BusinessQueueStaff = {
  id: number;
  name: string;
  profession: string;
};

export type BusinessQueueSetup = {
  services: BusinessQueueService[];
  staff: BusinessQueueStaff[];
};

export type BusinessQueueProviderWrite = {
  staff_id: number;
  item_public_ids: string[];
  specialty: string;
  experience_years: number;
  qualification: string;
  work_days: string;
  work_start: string;
  work_end: string;
  avg_minutes: number;
  room: string;
  bio: string;
  status: QueueProviderStatus;
  mode: QueueProviderMode;
};

export type BusinessQueueProvider = BusinessQueueProviderWrite & {
  id: number;
  name: string;
  profession: string;
  queue_count: number;
};

export type BusinessQueueOfflineCreate = {
  item_public_id: string;
  provider_id: number;
  queue_date: string;
  patient_name: string;
  phone: string;
  note: string;
  slot_time: string;
};

export type BusinessQueueEntry = {
  id: number;
  business_account_id: number;
  business_name: string;
  business_direction: string;
  customer_account_id: number | null;
  item_public_id: string;
  provider_id: number;
  patient_name: string;
  phone: string;
  service_name: string;
  provider_name: string;
  queue_date: string;
  queue_no: number;
  queue_code: string;
  source: string;
  status: QueueEntryStatus;
  note: string;
  slot_time: string;
  ahead_count: number;
  avg_minutes: number;
  wait_minutes: number;
  created_at: string;
  updated_at: string;
};

export type BusinessSubscriptionRecord = {
  id: number | null;
  plan_code: "free" | "plus" | "pro";
  duration_months: number;
  starts_at: number;
  expires_at: number;
  status: "active" | "superseded" | "expired";
  is_demo: boolean;
  is_virtual: boolean;
  created_at: number;
};

export type BusinessSubscriptionSummary = {
  current: BusinessSubscriptionRecord;
  history: BusinessSubscriptionRecord[];
};
