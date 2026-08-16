// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { AccountType } from "./common";

export type StoryState = "active" | "archived";

export type StoryCreate = {
  object_key: string;
  content_type: string;
  size_bytes: number;
  caption: string;
};

export type StoryRead = {
  id: number;
  owner_type: AccountType;
  owner_public_id: string;
  media_type: "image" | "video";
  media_url: string;
  thumbnail_url: string;
  caption: string;
  duration_seconds: number;
  created_at: string;
  expires_at: string;
  viewed: boolean;
  state: StoryState;
};

export type StoryGroup = {
  owner_type: AccountType;
  owner_public_id: string;
  name: string;
  avatar_url: string;
  is_own: boolean;
  is_followed: boolean;
  has_unseen: boolean;
  distance_km: number | null;
  stories: StoryRead[];
};

export type StoryViewer = {
  account_public_id: string;
  name: string;
  viewed_at: string;
};

export type StoryViewResult = { ok: true; counted: boolean };

export type StoryCreated = { ok: true; story: StoryRead };
