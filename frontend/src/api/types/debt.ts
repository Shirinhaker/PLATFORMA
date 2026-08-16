// `api/types.ts` dan ajratildi — domen bo'yicha.

export type Debtor = {
  id: number;
  name: string;
  phone: string;
  note: string;
  due: string;
  balance: number;
};

export type DebtTransaction = {
  id: number;
  type: "debt" | "payment";
  amount: number;
  date: string;
  note: string;
  order_id: number | null;
  cash_receipt_id: number | null;
  created_at: string;
};

export type DebtorDetail = Debtor & {
  tx: DebtTransaction[];
};

export type DebtorCreate = {
  name: string;
  phone: string;
  note: string;
  due: string;
  initial_debt: number;
};

export type DebtTransactionCreate = {
  type: "debt" | "payment";
  amount: number;
  date?: string | null;
  note: string;
};

export type DebtMutation = {
  ok: true;
  transaction_id: number;
  balance: number;
};
