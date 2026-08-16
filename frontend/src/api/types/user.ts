// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { CabinetActivity, CabinetPayload } from "./common";

export type UserProfile = {
  account_id: number;
  public_id: string;
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
  avatar_url: string;
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

export type UserProfilePatch = Partial<
  Pick<
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
  >
>;
