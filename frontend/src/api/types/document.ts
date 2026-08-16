// `api/types.ts` dan ajratildi — domen bo'yicha.

export type DocumentDirection = "ichki" | "kiruvchi" | "chiquvchi";

export type DocumentCounterpartyWrite = {
  name: string;
  ctype: string;
  director: string;
  phone: string;
  address: string;
  inn: string;
  account: string;
  bank: string;
  mfo: string;
  note: string;
};

export type DocumentCounterparty = DocumentCounterpartyWrite & {
  id: number;
  created_at: string;
};

export type DocumentCounterpartyList = {
  counterparties: DocumentCounterparty[];
  count: number;
  types: string[];
};
