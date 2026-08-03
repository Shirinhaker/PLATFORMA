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

export type StaffScheduleDay = {
  on: boolean;
  start: string;
  end: string;
};

export type StaffSchedule = Record<string, StaffScheduleDay>;

export type StaffMember = {
  id: number;
  name: string;
  profession: string;
  phone: string;
  salary: number;
  hire_date: string | null;
  status: "active" | "fired";
  note: string;
  login: string;
  can_login: boolean;
  has_password: boolean;
  permissions: string[];
  schedule: StaffSchedule;
  created_at: string;
  fired_at: string | null;
};

export type StaffMemberWrite = {
  name: string;
  profession: string;
  phone: string;
  salary: number;
  hire_date: string | null;
  note: string;
};

export type StaffPermission = { key: string; label: string; icon: string };
export type StaffPermissionTemplate = {
  key: string;
  label: string;
  permissions: string[];
};

export type StaffSetup = {
  active: StaffMember[];
  fired: StaffMember[];
  active_count: number;
  fired_count: number;
  total_salary: number;
  firm_login: string;
  business_direction: string;
  professions: string[];
  permission_definitions: StaffPermission[];
  permission_templates: StaffPermissionTemplate[];
};

export type StaffAccessWrite = {
  can_login: boolean;
  login: string;
  password: string;
  permissions: string[];
};

export type StaffAttendanceRow = {
  id: number;
  name: string;
  profession: string;
  status: string;
  time_in: string;
  time_out: string;
  sched_on: boolean;
  sched_start: string;
  sched_end: string;
  month_present: number;
  month_minutes: number;
};

export type StaffAttendance = {
  date: string;
  weekday: number;
  staff: StaffAttendanceRow[];
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

export type UserProfile = {
  account_id: number;
  name: string;
  phone: string;
  public_username: string;
  region: string;
  district: string;
  mahalla: string;
  latitude: number | null;
  longitude: number | null;
  location_exact: boolean;
  avatar_object_key: string;
  avatar_x: number;
  avatar_y: number;
  avatar_zoom: number;
  followers_count: number;
  following_count: number;
  has_business: boolean;
  dashboard_snapshot: Record<string, number>;
  recent_activity: CabinetActivity[];
  specialist_profile: Record<string, unknown>;
  cabinet_payload: CabinetPayload;
};

export type UserProfilePatch = Partial<Pick<
  UserProfile,
  | "name"
  | "phone"
  | "public_username"
  | "region"
  | "district"
  | "mahalla"
  | "latitude"
  | "longitude"
  | "location_exact"
  | "specialist_profile"
>>;

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

export type BusinessProfilePatch = Partial<Pick<
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
>>;

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

export type MediaPurpose = (
  "avatar" | "logo" | "payment_qr" | "listing_photo" | "listing_video"
  | "order_chat_image"
);

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

export type QueueProviderStatus = "active" | "inactive";
export type QueueProviderMode = "live" | "slot";
export type QueueEntryStatus = (
  "waiting" | "called" | "in_service" | "done" | "no_show"
  | "cancelled" | "skipped"
);

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

export type QueueNotificationRead = {
  id: number;
  medical_queue_id: number;
  is_read: boolean;
};

export type QueueOptions = {
  business_public_id: string;
  item_public_id: string;
  queue_date: string;
  providers: BusinessQueueProvider[];
};

export type QueueSlots = {
  mode: QueueProviderMode;
  slots: string[];
};

export type QueueCreate = {
  business_public_id: string;
  item_public_id: string;
  provider_id: number;
  queue_date: string;
  slot_time: string;
  note: string;
};

export type PublicResultKind = (
  "user" | "business" | "product" | "service" | "listing"
);
export type PublicResultType = "all" | PublicResultKind;

export type PublicSearchParams = {
  q?: string;
  result_type?: PublicResultType;
  direction?: string;
  activity_type?: string;
  region?: string;
  district?: string;
  mahalla?: string;
  page?: number;
  page_size?: number;
};

export type PublicSearchMapPoint = {
  business_public_id: string;
  business_name: string;
  latitude: number;
  longitude: number;
};

export type PublicSearchItem = {
  kind: PublicResultKind;
  public_id: string;
  name: string;
  public_username: string;
  description: string;
  direction: string;
  activity_type: string;
  region: string;
  district: string;
  mahalla: string;
  image_url: string;
  price_text?: string;
  owner_state?: "linked" | "unlinked";
  owner_label?: string;
  can_order?: boolean;
  can_chat?: boolean;
  map_point?: PublicSearchMapPoint;
};

export type PublicSearchResponse = {
  items: PublicSearchItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type PublicCatalogParams = {
  kind?: "product" | "service";
  q?: string;
  direction?: string;
  activity_type?: string;
  region?: string;
  district?: string;
  mahalla?: string;
  page?: number;
  page_size?: number;
};

export type PublicCatalogItem = {
  kind: "product" | "service";
  public_id: string;
  name: string;
  price_text: string;
  unit: string;
  note: string;
  owner_state: "linked" | "unlinked";
  owner_public_id: string;
  owner_name: string;
  owner_label: string;
  direction: string;
  activity_type: string;
  region: string;
  district: string;
  mahalla: string;
  image_url: string;
  can_order: boolean;
  can_chat: boolean;
  queue_enabled: boolean;
  queue_provider_count?: number;
};

export type PublicCatalogResponse = {
  items: PublicCatalogItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type PublicAdvertisementParams = {
  placement?: string;
  region?: string;
  district?: string;
};

export type PublicAdvertisement = {
  public_id: string;
  title: string;
  caption: string;
  owner_public_id: string;
  owner_kind?: "user" | "business";
  desktop_image_url: string;
  mobile_image_url: string;
  crop_x: number;
  crop_y: number;
  crop_zoom: number;
};

export type PublicHomeBusinessPin = {
  id: number;
  public_id: string;
  name: string;
  yon: string;
  tur: string;
  lat: number;
  lng: number;
  logo_file: string;
  logo_x: number;
  logo_y: number;
  logo_zoom: number;
  address: string;
  source: string;
};

export type PublicHomeSpecialistPin = {
  user_id: number;
  public_id: string;
  name: string;
  kasb: string;
  is_gov: boolean;
  lat: number;
  lng: number;
  avatar_file: string;
  avatar_x: number;
  avatar_y: number;
  avatar_zoom: number;
  source: string;
};

export type PublicHomeMapResponse = {
  businesses: PublicHomeBusinessPin[];
  specialists: PublicHomeSpecialistPin[];
};

export type PublicHomeMapParams = { district: string };

export type PublicDistrictOffer = {
  kind: "product" | "service" | "listing";
  business_id: number;
  business_public_id: string;
  content_id: number;
  content_public_id: string;
  title: string;
  business_name: string;
  image: string;
  business_logo: string;
  price: string;
  unit: string;
};

export type PublicDistrictOffersResponse = {
  needs_district: boolean;
  items: PublicDistrictOffer[];
  slot?: number;
};

export type PublicFollowedProfile = {
  kind: "user" | "business";
  public_id: string;
  name: string;
  image_url: string;
  crop_x: number;
  crop_y: number;
  crop_zoom: number;
};

export type PublicProfileItem = {
  kind: "product" | "service";
  public_id: string;
  name: string;
  price_text: string;
  unit: string;
  note: string;
  image_url: string;
  group_name: string;
  queue_enabled: boolean;
  queue_provider_count?: number;
  today_queue_count?: number;
  course_mode?: "" | "offline" | "online" | "hybrid";
  course_duration?: string;
  lesson_duration?: number;
  age_from?: number;
  age_to?: number;
  course_level?: "" | "beginner" | "intermediate" | "advanced" | "all";
  enrollment_status?: "open" | "closed";
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

export type OrderCreate = {
  provider_kind: "user" | "business";
  provider_public_id: string;
  items: Array<{ public_id: string; qty: number }>;
  listing_public_id: string;
  title: string;
  phone: string;
  order_type: "delivery" | "pickup" | "booking";
  address: string;
  desired_time: string;
  delivery_lat: number | null;
  delivery_lng: number | null;
  note: string;
};

export type OrderCreateResponse = { id: number };

export type OrderStatus = (
  "new" | "accepted" | "preparing" | "tayyor"
  | "handoff_waiting_seller" | "pickup_waiting_customer"
  | "delivered_waiting_customer" | "in_delivery" | "done"
  | "delivered" | "cancelled" | "rejected" | string
);

export type OrderPaymentStatus = (
  "pending" | "submitted" | "recheck" | "disputed"
  | "confirmed" | "rejected" | "debt" | string
);

export type OrderItemRead = {
  id: number;
  public_id: string;
  name: string;
  price: string;
  qty: number;
  unit: string;
  line_total: number;
  note: string;
  kind: string;
};

export type OrderMessageRead = {
  id: number;
  text: string;
  media_type: string;
  media_url: string;
  file_name: string;
  reply_to_id: number | null;
  reply: {
    id: number;
    text: string;
    media_type: string;
    is_deleted: boolean;
    sender_name: string;
  } | null;
  edited_at: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
  mine: boolean;
  sender_name: string;
  sender_kind: string;
  created_at: string;
};

export type OrderRead = {
  id: number;
  view: "customer" | "provider";
  title: string;
  customer_name: string;
  customer_public_id: string;
  provider_name: string;
  provider_kind: string;
  provider_public_id: string;
  item_public_id: string;
  listing_public_id: string;
  order_type: string;
  order_category: string;
  address: string;
  desired_time: string;
  delivery_lat: number | null;
  delivery_lng: number | null;
  note: string;
  phone: string;
  qty: number;
  total_amount: number;
  total_text: string;
  status: OrderStatus;
  payment_status: OrderPaymentStatus;
  pay_type: string;
  receipt_message_id: number | null;
  problem_open: boolean;
  problem_reason: string;
  problem_note: string;
  problem_solution: string;
  problem_opened_at: string | null;
  problem_resolved_at: string | null;
  seller_completed_at: string | null;
  customer_received_at: string | null;
  last_event: string;
  chat_count: number;
  last_chat: string;
  last_chat_at: string | null;
  pay_card: string;
  pay_holder: string;
  pay_qr_url: string;
  provider_address: string;
  provider_phone: string;
  provider_work_hours: Record<string, unknown>;
  provider_lat: number | null;
  provider_lng: number | null;
  customer_seen_at: string | null;
  provider_seen_at: string | null;
  seen_at: string | null;
  is_unread: boolean;
  created_at: string;
  updated_at: string;
  items: OrderItemRead[];
};

export type OrderProblemReason = (
  "not_received" | "amount_short" | "receipt_mismatch"
  | "receipt_unreadable" | "wrong_receipt" | "other"
);

export type OrderProblemSolution = "pickup" | "wait" | "new_receipt";

export type OrderChatRead = {
  ok: boolean;
  side: "customer" | "provider";
  seen_at: string;
  other: {
    side: "customer" | "provider";
    kind: "user" | "business";
    public_id: string;
    name: string;
  };
  order: OrderRead;
  messages: OrderMessageRead[];
};

export type PublicProfileListing = {
  public_id: string;
  title: string;
  price_text: string;
  description: string;
  address: string;
  image_url: string;
};

export type PublicProfileDetail = {
  kind: "user" | "business";
  public_id: string;
  name: string;
  public_username: string;
  description: string;
  direction: string;
  activity_type: string;
  address: string;
  phone: string;
  image_url: string;
  crop_x: number;
  crop_y: number;
  crop_zoom: number;
  followers_count: number;
  queue_total?: number;
  specialist: {
    profession: string;
    description: string;
  } | null;
  items: PublicProfileItem[];
  listings: PublicProfileListing[];
};

export type ListingCategory = (
  "uy" | "ish" | "moshina" | "hayvon" | "texnika" | "boshqa"
);

export type ListingMedia = {
  type: "photo" | "video";
  url: string;
};

export type ListingMediaAttachment = {
  type: "photo" | "video";
  object_key: string;
};

export type ListingRead = {
  public_id: string;
  cat: ListingCategory;
  title: string;
  price: string;
  descr: string;
  address: string;
  lat: number | null;
  lng: number | null;
  visibility: "all" | "own";
  status: "active" | "inactive";
  created_at: string;
  media: ListingMedia[];
  owner_kind: "user" | "business";
  owner_public_id: string;
  owner_name: string;
  is_saved: boolean;
};

export type ListingCreate = {
  cat: ListingCategory;
  title: string;
  price: string;
  descr: string;
  address: string;
  lat: number;
  lng: number;
  visibility: "all" | "own";
  media: ListingMediaAttachment[];
};

export type ListingPatch = Partial<ListingCreate> & {
  status?: "active" | "inactive";
};

export type PublicListingParams = { cat?: ListingCategory; q?: string };

export type PublicFeatures = {
  listings: boolean;
  stories: boolean;
  chat: boolean;
  systemization: boolean;
  taxi: boolean;
};
