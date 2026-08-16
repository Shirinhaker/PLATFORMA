// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { ListingCategory } from "./listing";

export type PublicResultKind = "user" | "business" | "product" | "service" | "listing";

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
  owner_public_id?: string;
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
    credentials?: Array<{ id: number; image_url: string }>;
    offers?: Array<{
      id: number;
      kind: "service" | "product";
      name: string;
      price_text: string;
      note: string;
      image_url: string;
    }>;
    portfolio?: Array<{
      id: number;
      media_type: "photo" | "video";
      media_url: string;
    }>;
  } | null;
  items: PublicProfileItem[];
  listings: PublicProfileListing[];
};

export type PublicListingParams = { cat?: ListingCategory; q?: string };

export type PublicFeatures = {
  listings: boolean;
  stories: boolean;
  chat: boolean;
  systemization: boolean;
  taxi: boolean;
};
