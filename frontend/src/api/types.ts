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
  note: string;
  image_url: string;
  group_name: string;
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
