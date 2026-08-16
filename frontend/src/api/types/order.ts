// `api/types.ts` dan ajratildi — domen bo'yicha.

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

export type OrderStatus =
  | "new"
  | "accepted"
  | "preparing"
  | "tayyor"
  | "handoff_waiting_seller"
  | "pickup_waiting_customer"
  | "delivered_waiting_customer"
  | "in_delivery"
  | "done"
  | "delivered"
  | "cancelled"
  | "rejected"
  | string;

export type OrderPaymentStatus =
  | "pending"
  | "submitted"
  | "recheck"
  | "disputed"
  | "confirmed"
  | "rejected"
  | "debt"
  | string;

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
  debtor_id?: number | null;
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

export type OrderProblemReason =
  | "not_received"
  | "amount_short"
  | "receipt_mismatch"
  | "receipt_unreadable"
  | "wrong_receipt"
  | "other";

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
