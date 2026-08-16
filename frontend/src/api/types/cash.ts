// `api/types.ts` dan ajratildi — domen bo'yicha.

export type CashPayType = "naqd" | "karta" | "qarz";

export type CashCatalogItem = {
  id: number;
  name: string;
  price: number;
  price_text: string;
  unit: string;
  track_stock: boolean;
  stock_qty: number;
  low_stock: boolean;
};

export type CashReceiptLine = {
  id: number;
  catalog_item_id: number | null;
  item_name: string;
  qty: number;
  unit: string;
  price: number;
  total: number;
  cost_total: number;
};

export type CashReceipt = {
  id: number;
  receipt_no: number | null;
  source: string;
  order_id: number | null;
  pay_type: string;
  pay_text: string;
  debtor_name: string;
  note: string;
  who: string;
  created_at: string;
  total: number;
  can_delete: boolean;
  can_change_payment: boolean;
  lines: CashReceiptLine[];
};

export type CashTotals = {
  all: number;
  cash_in: number;
  naqd: number;
  karta: number;
  qarz: number;
  qarzpay: number;
  order: number;
};

export type CashRegister = {
  day: string;
  totals: CashTotals;
  receipts: CashReceipt[];
};

export type CashReceiptCreate = {
  items: Array<{
    catalog_item_id: number | null;
    name: string;
    qty: number;
    price: number;
  }>;
  pay_type: CashPayType;
  debtor_id?: number | null;
  note: string;
  sale_date: string | null;
};

export type CashReceiptCreated = {
  ok: true;
  id: number;
  receipt_no: number;
  count: number;
  total: number;
};
