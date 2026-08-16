// `api/types.ts` dan ajratildi — domen bo'yicha.

export type DiningPlaceKind = "table" | "room";

export type DiningKitchenStatus = "new" | "preparing" | "done";

export type DiningPaymentStatus = "open" | "confirmed";

export type DiningOrderStatus = "active" | "done" | "cancelled";

export type DiningPayType = "naqd" | "karta" | "qarz";

export type DiningPlace = {
  id: number;
  kind: DiningPlaceKind;
  name: string;
  seats: number;
  x: number;
  y: number;
  locked: boolean;
  active_order_id: number | null;
  occupied: boolean;
  created_at: number;
  updated_at: number;
};

export type DiningPlaceWrite = {
  kind: DiningPlaceKind;
  name: string;
  seats: number;
  x: number;
  y: number;
  locked: boolean;
};

export type DiningPlaceMove = {
  x: number;
  y: number;
  locked?: boolean;
};

export type DiningOrderItem = {
  id: number;
  item_id: number | null;
  name: string;
  qty: number;
  unit: string;
  price: number;
  total: number;
};

export type DiningOrder = {
  id: number;
  place_id: number;
  place_name: string;
  place_kind: DiningPlaceKind;
  kind: "order" | "booking";
  customer_name: string;
  phone: string;
  booking_date: string;
  booking_time: string;
  guests: number;
  note: string;
  total: number;
  waiter_staff_id: number | null;
  waiter_name: string;
  problem_open: boolean;
  problem_reason: string;
  problem_note: string;
  problem_opened_at: number;
  kitchen_status: DiningKitchenStatus;
  payment_status: DiningPaymentStatus;
  pay_type: string;
  debtor_id: number | null;
  receipt_no: number | null;
  status: DiningOrderStatus;
  created_at: number;
  updated_at: number;
  items: DiningOrderItem[];
};

export type DiningItemInput = {
  item_id: number;
  qty: number;
};

export type DiningBookingBody = {
  customer_name: string;
  booking_date: string;
  booking_time: string;
  phone?: string;
  guests?: number;
  note?: string;
};

export type DiningOrderBody = {
  items: DiningItemInput[];
  customer_name?: string;
  note?: string;
};

export type DiningCashierLine = {
  line_id: number;
  qty: number;
};

export type DiningPaymentBody = {
  pay_type: DiningPayType;
  debtor_id?: number | null;
};

export type DiningPaymentResult = {
  ok: boolean;
  pay_type: string;
  receipt_no: number | null;
  already_confirmed: boolean;
};
