// `api/types.ts` dan ajratildi — domen bo'yicha.

export type Expense = {
  id: number;
  category: string;
  amount: number;
  note: string;
  source: string;
  who: string;
  created_at: string;
};

export type ExpenseDay = {
  day: string;
  expenses: Expense[];
  total: number;
  by_category: Record<string, number>;
};

export type ExpenseCategories = {
  categories: string[];
  defaults: string[];
};

export type ExpenseCreate = {
  category: string;
  amount: number;
  note: string;
};

export type ExpenseCategoryCreate = {
  name: string;
};
