import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DiningOrder } from "../api/types";
import {
  BusinessKitchenV1656,
  type BusinessKitchenApi,
  supportsDiningKitchenApi,
} from "./BusinessKitchenV1656";


function order(overrides: Partial<DiningOrder> = {}): DiningOrder {
  return {
    id: 1,
    place_id: 7,
    place_name: "1-stol",
    place_kind: "table",
    kind: "order",
    customer_name: "",
    phone: "",
    booking_date: "",
    booking_time: "",
    guests: 0,
    note: "",
    total: 24000,
    waiter_staff_id: 3,
    waiter_name: "Dilnoza",
    problem_open: false,
    problem_reason: "",
    problem_note: "",
    problem_opened_at: 0,
    kitchen_status: "preparing",
    payment_status: "open",
    pay_type: "",
    debtor_id: null,
    receipt_no: null,
    status: "active",
    created_at: 1_785_000_000,
    updated_at: 1_785_000_000,
    items: [
      { id: 11, item_id: 5, name: "Osh", qty: 2, unit: "dona", price: 12000, total: 24000 },
    ],
    ...overrides,
  };
}

function makeApi(overrides: Partial<BusinessKitchenApi> = {}) {
  return {
    getDiningOrders: vi.fn().mockResolvedValue([order()]),
    setDiningKitchenStatus: vi.fn().mockImplementation(
      async (id: number) => order({ id, kitchen_status: "done" }),
    ),
    ...overrides,
  } as unknown as BusinessKitchenApi;
}


describe("oshpaz ekrani (v1656 pariteti)", () => {
  it("API to'liq bo'lsa qo'llab-quvvatlanadi", () => {
    expect(supportsDiningKitchenApi(makeApi())).toBe(true);
    expect(supportsDiningKitchenApi({ getDiningOrders: vi.fn() })).toBe(false);
  });

  it("bo'limlar va zakaz kartasi v1656 matnlari bilan", async () => {
    render(
      <BusinessKitchenV1656
        api={makeApi()}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("tab", { name: "Buyurtmalar (1)" }),
    ).toBeVisible();
    expect(screen.getByRole("tab", { name: "Muammoli (0)" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Yakunlangan (0)" })).toBeVisible();

    expect(screen.getByText("🪑 1-stol")).toBeVisible();
    expect(screen.getByText("Ofitsiant: Dilnoza")).toBeVisible();
    expect(screen.getByText("Osh · 2 dona")).toBeVisible();
    expect(screen.getByText("👨‍🍳 Tayyorlanmoqda")).toBeVisible();
    expect(screen.getByText("💳 Hisob ochiq")).toBeVisible();
    expect(screen.getByText("24 000 so‘m")).toBeVisible();
  });

  it("xona uchun boshqa belgi ko'rsatiladi", async () => {
    const api = makeApi({
      getDiningOrders: vi.fn().mockResolvedValue([
        order({ place_kind: "room", place_name: "VIP xona" }),
      ]),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("🚪 VIP xona")).toBeVisible();
  });

  it("'Tayyor bo'ldi' tugmasi oshxona holatini done qiladi", async () => {
    const api = makeApi();
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "✅ Tayyor bo‘ldi" }),
    );

    await waitFor(() => {
      expect(api.setDiningKitchenStatus).toHaveBeenCalledWith(1, "done");
    });
    expect(
      await screen.findByText("Taom tayyor deb belgilandi ✅"),
    ).toBeVisible();
    // Tayyor bo'lgach tugma yo'qoladi.
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "✅ Tayyor bo‘ldi" }),
      ).toBeNull();
    });
    expect(screen.getByText("👨‍🍳 Tayyor")).toBeVisible();
  });

  it("kitchen vakolati yo'q xodimga tugma ko'rsatilmaydi", async () => {
    render(
      <BusinessKitchenV1656
        api={makeApi()}
        permissions={["kassa"]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("🪑 1-stol")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "✅ Tayyor bo‘ldi" }),
    ).toBeNull();
  });

  it("tayyor bo'lgan zakazda tugma bo'lmaydi", async () => {
    const api = makeApi({
      getDiningOrders: vi.fn().mockResolvedValue([
        order({ kitchen_status: "done" }),
      ]),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("👨‍🍳 Tayyor")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "✅ Tayyor bo‘ldi" }),
    ).toBeNull();
  });

  it("muammoli zakaz alohida bo'limda", async () => {
    const api = makeApi({
      getDiningOrders: vi.fn().mockResolvedValue([
        order({ id: 2, problem_open: true }),
      ]),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("tab", { name: "Muammoli (1)" }),
    ).toBeVisible();
    expect(screen.getByRole("tab", { name: "Buyurtmalar (0)" })).toBeVisible();
    // Bo'sh bo'lmagan bo'limga avtomatik o'tadi.
    expect(screen.getByText("🪑 1-stol")).toBeVisible();
  });

  it("zakaz bo'lmasa v1656 bo'sh matni", async () => {
    const api = makeApi({
      getDiningOrders: vi.fn().mockResolvedValue([]),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("Buyurtma yo‘q")).toBeVisible();
  });

  it("stol bandligi (booking) oshpazga ko'rsatilmaydi", async () => {
    const api = makeApi({
      getDiningOrders: vi.fn().mockResolvedValue([
        order({ id: 3, kind: "booking", place_name: "Band stol" }),
      ]),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("Buyurtma yo‘q")).toBeVisible();
    expect(screen.queryByText("🪑 Band stol")).toBeNull();
  });

  it("xato bo'lsa sabab ko'rsatiladi", async () => {
    const api = makeApi({
      getDiningOrders: vi.fn().mockRejectedValue(new Error("Ulanmadi.")),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("Ulanmadi.")).toBeVisible();
  });

  it("tayyorlash so'rovi yiqilsa xabar chiqadi", async () => {
    const api = makeApi({
      setDiningKitchenStatus: vi.fn().mockRejectedValue(
        new Error("Muammoli zakazni avval kassada hal qiling."),
      ),
    });
    render(
      <BusinessKitchenV1656
        api={api}
        permissions={null}
        onBackHandlerChange={vi.fn()}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "✅ Tayyor bo‘ldi" }),
    );

    expect(
      await screen.findByText("Muammoli zakazni avval kassada hal qiling."),
    ).toBeVisible();
  });
});
