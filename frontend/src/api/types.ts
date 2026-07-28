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
  director: string;
  tax_id: string;
  logo_object_key: string;
  logo_x: number;
  logo_y: number;
  logo_zoom: number;
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
  | "director"
  | "tax_id"
>>;

export type MediaPurpose = "avatar" | "logo";

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

export type PublicResultKind = "user" | "business";
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
};

export type PublicSearchResponse = {
  items: PublicSearchItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};
