import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { BusinessOnlineRecord } from "../api/business-online-types";
import type { DiningOrder, DiningPlace } from "../api/types";
import {
  BusinessDiningV1656,
  type BusinessDiningApi,
  supportsDiningApi,
} from "./BusinessDiningV1656";


function place(overrides: Partial<DiningPlace> = {}): DiningPlace {
  return {
    id: 700,
    kind: "table",
    name: "1-stol",
    seats: 4,
    x: 10,
    y: 20,
    locked: true,
    active_order_id: null,
    occupied: false,
    created_at: 1_785_000_000,
    updated_at: 1_785_000_000,
    ...overrides,
  };
}

function order(overrides: Partial<DiningOrder> = {}): DiningOrder {
  return {
    id: 5,
    place_id: 700,
    place_name: "1-stol",
    place_kind: "table",
    kind: "order",
    customer_name: "Mehmon",
    phone: "",
    booking_date: "",
    booking_time: "",
    guests: 0,
    note: "",
    total: 24000,
    waiter_staff_id: null,
    waiter_name: "Rahbar",
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

const MENU: BusinessOnlineRecord[] = [
  { id: 5, name: "Osh", price: "12000 so'm", unit: "dona" } as BusinessOnlineRecord,
];

function makeApi(
  places: DiningPlace[],
  orders: DiningOrder[],
  overrides: Partial<BusinessDiningApi> = {},
) {
  return {
    getDiningPlaces: vi.fn().mockResolvedValue(places),
    getDiningOrders: vi.fn().mockResolvedValue(orders),
    createDiningPlace: vi.fn().mockResolvedValue(place({ id: 701 })),
    updateDiningPlace: vi.fn().mockImplementation(
      async (id: number) => place({ id }),
    ),
    deleteDiningPlace: vi.fn().mockResolvedValue(undefined),
    clearDiningPlace: vi.fn().mockResolvedValue(undefined),
    bookDiningPlace: vi.fn().mockResolvedValue(order({ kind: "booking" })),
    createDiningOrder: vi.fn().mockResolvedValue(order()),
    addDiningOrderItems: vi.fn().mockResolvedValue(order()),
    ...overrides,
  } as unknown as BusinessDiningApi;
}


describe("ofitsiant zal rejasi yangi endpointlarga ulangan", () => {
  it("API to'liq bo'lsa qo'llab-quvvatlanadi", () => {
    expect(supportsDiningApi(makeApi([], []))).toBe(true);
    expect(supportsDiningApi({ getDiningPlaces: vi.fn() })).toBe(false);
  });

  it("stollar /api/v1/dining dan yuklanadi", async () => {
    const api = makeApi([place()], []);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("1-stol")).toBeVisible();
    expect(api.getDiningPlaces).toHaveBeenCalled();
    expect(api.getDiningOrders).toHaveBeenCalled();
  });

  it("faol zakaz stolda ko'rinadi — kassa bilan bitta manba", async () => {
    const api = makeApi([place({ occupied: true })], [order()]);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    // Stol bandligi zakazlar ro'yxatidan hisoblanadi, JSON payloaddan emas.
    expect(await screen.findByText(/Zakaz ·/)).toBeVisible();
  });

  it("bron ma'lumoti stol ostida ko'rinadi", async () => {
    const api = makeApi([place()], [
      order({
        id: 9,
        kind: "booking",
        booking_time: "19:30",
        customer_name: "Anvar",
        total: 0,
      }),
    ]);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText(/Bron · 19:30 Anvar/)).toBeVisible();
  });

  it("bo'sh stolda joy soni ko'rsatiladi", async () => {
    const api = makeApi([place()], []);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("4 joy")).toBeVisible();
  });

  it("yuklanmasa sabab ko'rsatiladi", async () => {
    const api = makeApi([], [], {
      getDiningPlaces: vi.fn().mockRejectedValue(new Error("Ulanmadi.")),
    });
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    expect(await screen.findByText("Ulanmadi.")).toBeVisible();
  });

  it("eski JSON yo'liga umuman murojaat qilmaydi", async () => {
    const api = makeApi([place()], [order()]);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );
    await screen.findByText("1-stol");

    // Konteynerda kabinet resurs metodlari yo'q — oqim faqat REST orqali.
    expect(
      Object.keys(api).some((name) => name.includes("BusinessOnline")),
    ).toBe(false);
    await waitFor(() => {
      expect(api.getDiningOrders).toHaveBeenCalled();
    });
  });

  it("zakaz ochish yangi endpointga yoziladi, JSON yo'liga emas", async () => {
    const api = makeApi([place()], []);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Menyu" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "🛒 Zakaz qilish" }),
    );
    // Menyudan bitta "Osh" tanlanadi.
    fireEvent.click((await screen.findAllByRole("button", { name: "+" }))[0]!);
    fireEvent.click(
      screen.getByRole("button", { name: "Zakazni saqlash" }),
    );

    await waitFor(() => {
      expect(api.createDiningOrder).toHaveBeenCalledWith(700, {
        items: [{ item_id: 5, qty: 1 }],
        customer_name: "",
        note: "",
      });
    });
    // Zakaz yaratilgach ro'yxat serverdan qayta o'qiladi.
    await waitFor(() => {
      expect(api.getDiningOrders).toHaveBeenCalledTimes(2);
    });
  });

  it("mavjud zakazga taom qo'shish add_items endpointiga boradi", async () => {
    const api = makeApi([place({ occupied: true })], [order()]);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Menyu" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "🛒 Zakazga taom qo‘shish" }),
    );
    fireEvent.click((await screen.findAllByRole("button", { name: "+" }))[0]!);
    fireEvent.click(
      screen.getByRole("button", { name: "Zakazga qo‘shish" }),
    );

    await waitFor(() => {
      expect(api.addDiningOrderItems).toHaveBeenCalledWith(5, [
        { item_id: 5, qty: 1 },
      ]);
    });
    expect(api.createDiningOrder).not.toHaveBeenCalled();
  });

  it("stolni bo'shatish clear endpointini chaqiradi", async () => {
    const api = makeApi([place({ occupied: true })], [order()]);
    render(
      <BusinessDiningV1656
        api={api}
        menuItems={MENU}
        groups={[]}
        onBackHandlerChange={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Menyu" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "✅ Bo'shatish" }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Bo'shatish" }));

    await waitFor(() => {
      expect(api.clearDiningPlace).toHaveBeenCalledWith(700);
    });
  });
});
