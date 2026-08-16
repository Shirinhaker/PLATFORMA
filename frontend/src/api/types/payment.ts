// `api/types.ts` dan ajratildi — domen bo'yicha.

export type PaymentPrice = {
  price_code: string;
  service_type: string;
  amount_uzs: number;
  plan_code: string;
  duration_months: number;
};

export type PaymentMethod = {
  id: number;
  method_type: string;
  name: string;
  recipient_name: string;
  instructions: string;
  details: Record<string, unknown>;
};

export type PaymentCatalog = {
  prices: PaymentPrice[];
  methods: PaymentMethod[];
};

export type PaymentReceiptRef = {
  object_key: string;
  filename: string;
  mime: string;
  sha256: string;
};

export type PaymentRequestBody = {
  service_type: "subscription" | "advertisement" | "listing";
  price_code: string;
  payment_method_id: number;
  receipt: PaymentReceiptRef;
  plan_code?: string;
  duration_months?: number;
  quantity?: number;
  target_id?: number;
  /** E'lon uchun — ichki raqam ochiq kontraktda yo'q. */
  target_public_id?: string;
};

export type PaymentAttempt = {
  attempt_no: number;
  review_status: string;
  review_reason: string;
  submitted_at: number;
};

export type PaymentRequestRecord = {
  id: number;
  request_code: string;
  service_type: string;
  status: string;
  plan_code: string;
  duration_months: number;
  quantity: number;
  amount: number;
  currency: string;
  price_code: string;
  public_reason: string;
  created_at: number;
  updated_at: number;
  attempts: PaymentAttempt[];
};
