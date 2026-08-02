import type { PublicProfileItem } from "../api/types";

export type CartProvider = { public_id: string; name: string };
export type CartItem = {
  public_id: string;
  kind: "product" | "service";
  name: string;
  price_text: string;
  unit: string;
  qty: number;
};
export type CartReceipt = {
  provider_public_id: string;
  provider_name: string;
  items: Record<string, CartItem>;
};
export type CartState = Record<string, CartReceipt>;

export const FRACTIONAL_UNITS = new Set([
  "kg", "g", "litr", "ml", "metr", "sm", "m²", "soat",
]);

export function unitAllowsFraction(unit: string): boolean {
  return FRACTIONAL_UNITS.has(unit);
}

export function parsePriceAmount(text: string): number {
  const digits = String(text || "").replace(/[^0-9]/g, "");
  if (!digits) return 0;
  const amount = Number.parseInt(digits, 10);
  return Number.isFinite(amount) ? amount : 0;
}

export function moneyText(amount: number): string {
  const rounded = Math.trunc(amount || 0);
  if (!rounded) return "";
  return `${String(rounded).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} so'm`;
}

export function formatQuantity(quantity: number): string {
  return String(Math.round(quantity * 1000) / 1000);
}

function cloneReceipt(receipt: CartReceipt): CartReceipt {
  return {
    ...receipt,
    items: Object.fromEntries(
      Object.entries(receipt.items).map(([key, item]) => [key, { ...item }]),
    ),
  };
}

export function addCartItem(
  carts: CartState,
  provider: CartProvider,
  item: PublicProfileItem,
): CartState {
  const current = carts[provider.public_id];
  const receipt = current
    ? cloneReceipt(current)
    : {
        provider_public_id: provider.public_id,
        provider_name: provider.name,
        items: {},
      };
  receipt.provider_name = provider.name || receipt.provider_name;
  const existing = receipt.items[item.public_id];
  receipt.items[item.public_id] = existing
    ? { ...existing, qty: Math.min(999, existing.qty + 1) }
    : {
        public_id: item.public_id,
        kind: item.kind,
        name: item.name || "Mahsulot/xizmat",
        price_text: item.price_text || "",
        unit: item.unit || "dona",
        qty: 1,
      };
  return { ...carts, [provider.public_id]: receipt };
}

export function setCartItemQuantity(
  carts: CartState,
  providerPublicId: string,
  itemPublicId: string,
  value: number,
  commit = false,
): CartState {
  const current = carts[providerPublicId];
  const currentItem = current?.items[itemPublicId];
  if (!current || !currentItem) return carts;
  const receipt = cloneReceipt(current);
  let quantity = Number.isFinite(value) ? Math.max(0, Math.min(999, value)) : 0;
  if (commit) {
    if (!unitAllowsFraction(currentItem.unit)) quantity = Math.floor(quantity + 0.5);
    quantity = Math.round(quantity * 1000) / 1000;
    if (quantity <= 0) {
      delete receipt.items[itemPublicId];
      return { ...carts, [providerPublicId]: receipt };
    }
  }
  receipt.items[itemPublicId] = { ...currentItem, qty: quantity };
  return { ...carts, [providerPublicId]: receipt };
}

export function changeCartItem(
  carts: CartState,
  providerPublicId: string,
  itemPublicId: string,
  direction: -1 | 1,
): CartState {
  const item = carts[providerPublicId]?.items[itemPublicId];
  if (!item) return carts;
  const step = unitAllowsFraction(item.unit) ? 0.5 : 1;
  return setCartItemQuantity(
    carts, providerPublicId, itemPublicId, item.qty + step * direction, true,
  );
}

export function setCartItemSum(
  carts: CartState,
  providerPublicId: string,
  itemPublicId: string,
  sum: number,
): CartState {
  const item = carts[providerPublicId]?.items[itemPublicId];
  if (!item) return carts;
  const price = parsePriceAmount(item.price_text);
  const amount = Math.max(0, Math.trunc(sum || 0));
  if (!price || !amount) return carts;
  const rawQuantity = amount / price;
  const quantity = unitAllowsFraction(item.unit)
    ? Math.round(rawQuantity * 1000) / 1000
    : Math.max(1, Math.floor(rawQuantity));
  return setCartItemQuantity(
    carts, providerPublicId, itemPublicId, quantity,
  );
}

export function clearCartReceipt(
  carts: CartState,
  providerPublicId: string,
): CartState {
  const receipt = carts[providerPublicId];
  if (!receipt) return carts;
  return { ...carts, [providerPublicId]: { ...receipt, items: {} } };
}

export function cartLineCount(carts: CartState): number {
  return Object.values(carts).reduce(
    (count, receipt) => count + Object.keys(receipt.items).length,
    0,
  );
}

export function cartReceiptTotal(receipt: CartReceipt): number {
  return Math.round(Object.values(receipt.items).reduce(
    (total, item) => total + parsePriceAmount(item.price_text) * item.qty,
    0,
  ));
}

export function cartQuantity(
  carts: CartState,
  providerPublicId: string,
  itemPublicId: string,
): number {
  return carts[providerPublicId]?.items[itemPublicId]?.qty ?? 0;
}
