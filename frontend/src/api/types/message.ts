// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { AccountType } from "./common";

export type MessageReplyRead = {
  id: number;
  text: string;
  media_type: string;
  is_deleted: boolean;
  sender_name: string;
};

export type MessageRead = {
  id: number;
  text: string;
  media_type: "text" | "photo" | string;
  media_url: string;
  file_name: string;
  reply_to_id: number | null;
  reply: MessageReplyRead | null;
  edited_at: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
  mine: boolean;
  sender_name: string;
  sender_kind: AccountType;
  created_at: string;
};

export type MessageProfileRead = {
  kind: AccountType;
  public_id: string;
  name: string;
  avatar_url: string;
};

export type MessageThreadRead = {
  other: MessageProfileRead;
  messages: MessageRead[];
};

export type MessageConversationRead = {
  target_kind: AccountType;
  target_public_id: string;
  name: string;
  avatar_url: string;
  last: string;
  created_at: string;
  unread: number;
};

export type MessageCreate = {
  target_kind: AccountType;
  target_public_id: string;
  text: string;
  reply_to_id?: number | null;
};

export type MessageImageCreate = Omit<MessageCreate, "text"> & {
  object_key: string;
  file_name: string;
  text?: string;
};
