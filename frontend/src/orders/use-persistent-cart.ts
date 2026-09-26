import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type SetStateAction,
} from "react";
import type { AppSession } from "../auth/types";
import type { CartState } from "./order-store";

const PREFIX = "koprik_cart_v1:";
const safeId = (id: string) =>
  /^[a-zA-Z0-9_-]+$/.test(id) &&
  !["__proto__", "constructor", "prototype"].includes(id);

export function readCart(scope: string): CartState {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(PREFIX + scope) ?? "{}");
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    const result: CartState = {};
    for (const [id, receipt] of Object.entries(value)) {
      if (
        !safeId(id) ||
        !receipt ||
        receipt.provider_public_id !== id ||
        typeof receipt.provider_name !== "string" ||
        !receipt.items ||
        typeof receipt.items !== "object"
      )
        continue;
      const items = Object.fromEntries(
        Object.entries(receipt.items).filter(([key, raw]) => {
          if (!raw || typeof raw !== "object") return false;
          const item = raw as Record<string, unknown>;
          return (
            safeId(key) &&
            item.public_id === key &&
            (item.kind === "product" || item.kind === "service") &&
            typeof item.name === "string" &&
            typeof item.price_text === "string" &&
            typeof item.unit === "string" &&
            typeof item.qty === "number" &&
            Number.isFinite(item.qty) &&
            item.qty > 0 &&
            item.qty <= 999
          );
        }),
      );
      if (Object.keys(items).length)
        result[id] = {
          provider_public_id: id,
          provider_name: receipt.provider_name,
          items,
        } as CartState[string];
    }
    return result;
  } catch {
    return {};
  }
}

function saveCart(scope: string, carts: CartState) {
  try {
    localStorage.setItem(PREFIX + scope, JSON.stringify(carts));
  } catch {
    // Saqlash bloklansa ham joriy savat ishlashda davom etadi.
  }
}

export function usePersistentCart(session: AppSession) {
  const scope =
    session.status === "loading"
      ? null
      : session.status === "guest"
        ? "guest"
        : `${session.status}:${session.identity.account_id}`;
  const loaded = useRef<string | null>(null);
  const [carts, update] = useState<CartState>({});
  const current = useRef(carts);
  useLayoutEffect(() => {
    if (!scope || loaded.current === scope) return;
    const next = readCart(scope);
    loaded.current = scope;
    current.current = next;
    update(next);
  }, [scope]);
  const setCarts = useCallback(
    (action: SetStateAction<CartState>) => {
      if (!scope || loaded.current !== scope) return;
      const next = typeof action === "function" ? action(current.current) : action;
      current.current = next;
      saveCart(scope, next);
      update(next);
    },
    [scope],
  );
  return [scope && loaded.current === scope ? carts : {}, setCarts] as const;
}
