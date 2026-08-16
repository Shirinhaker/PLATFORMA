// `api/types.ts` dan ajratildi — domen bo'yicha.

import type { BusinessQueueProvider } from "./business";

export type QueueProviderStatus = "active" | "inactive";

export type QueueProviderMode = "live" | "slot";

export type QueueEntryStatus =
  "waiting" | "called" | "in_service" | "done" | "no_show" | "cancelled" | "skipped";

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
