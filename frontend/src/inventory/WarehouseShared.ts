export type MoveMode = "receipt" | "outflow";

export type IngredientDraft = {
  item_id: number;
  name: string;
  unit: string;
  qty: string;
};

export function money(value: number) {
  return `${Number(value || 0).toLocaleString("uz-UZ")} so‘m`;
}

export function quantity(value: number) {
  return Number(value || 0).toLocaleString("uz-UZ", {
    maximumFractionDigits: 3,
  });
}

export function dateTime(value: number) {
  return value ? new Date(value * 1000).toLocaleString("uz-UZ") : "—";
}
