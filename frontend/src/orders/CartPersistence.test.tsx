import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AppSession } from "../auth/types";
import { readCart, usePersistentCart } from "./use-persistent-cart";
const account = (id = 5, status: "user" | "business" = "user"): AppSession => ({
  status,
  identity: {
    account_id: id,
    account_type: status,
    name: "Sinov",
    login: "test",
    csrf_token: "csrf",
    expires_at: "2099-01-01",
  },
});
const receipt = {
  b_store: {
    provider_public_id: "b_store",
    provider_name: "Do‘kon",
    items: {
      p_fruit: {
        public_id: "p_fruit",
        kind: "product" as const,
        name: "Meva",
        price_text: "25000",
        unit: "kg",
        qty: 1.5,
      },
    },
  },
};
beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());
describe("Savatni saqlash", () => {
  it("restores quantities and seller groups after remount and persists receipt removal", () => {
    const first = renderHook(() => usePersistentCart(account()));
    act(() => first.result.current[1](receipt));
    first.unmount();
    const next = renderHook(() => usePersistentCart(account()));
    expect(next.result.current[0]).toEqual(receipt);
    act(() => next.result.current[1]({}));
    next.unmount();
    expect(renderHook(() => usePersistentCart(account())).result.current[0]).toEqual(
      {},
    );
  });
  it("isolates ordinary, business and other accounts and does not erase a cart during session loading", () => {
    const hook = renderHook(({ session }) => usePersistentCart(session), {
      initialProps: { session: account() },
    });
    act(() => hook.result.current[1](receipt));
    hook.rerender({ session: { status: "loading" } });
    expect(hook.result.current[0]).toEqual({});
    hook.rerender({ session: account(5, "business") });
    expect(hook.result.current[0]).toEqual({});
    hook.rerender({ session: account(6) });
    expect(hook.result.current[0]).toEqual({});
    hook.rerender({ session: { status: "guest" } });
    expect(hook.result.current[0]).toEqual({});
    hook.rerender({ session: account() });
    expect(hook.result.current[0]).toEqual(receipt);
  });
  it("ignores corrupt storage and invalid quantities", () => {
    localStorage.setItem("koprik_cart_v1:user:5", "broken");
    expect(readCart("user:5")).toEqual({});
    localStorage.setItem(
      "koprik_cart_v1:user:5",
      JSON.stringify({
        ...receipt,
        b_bad: {
          provider_public_id: "b_bad",
          provider_name: "Bad",
          items: {
            p_bad: { ...receipt.b_store.items.p_fruit, public_id: "p_bad", qty: -10 },
          },
        },
      }),
    );
    expect(readCart("user:5")).toEqual(receipt);
  });
  it("continues working in memory when browser storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const hook = renderHook(() => usePersistentCart(account()));
    act(() => hook.result.current[1](receipt));
    expect(hook.result.current[0]).toEqual(receipt);
  });
});
