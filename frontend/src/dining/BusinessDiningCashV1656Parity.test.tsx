import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DiningOrder } from "../api/types";
import {
  BusinessDiningCashV1656,
  type BusinessDiningCashApi,
  supportsDiningCashApi,
} from "./BusinessDiningCashV1656";


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

function makeApi(rows: DiningOrder[], overrides: Partial<BusinessDiningCashApi> = {}) {
  return {
    getDiningOrders: vi.fn().mockResolvedValue(rows),
    confirmDiningPayment: vi.fn().mockResolvedValue({
      ok: true, pay_type: "naqd", receipt_no: 1, already_confirmed: false,
    }),
    updateDiningCashierItems: vi.fn().mockResolvedValue(order()),
    finalizeDiningOrder: vi.fn().mockResolvedValue(order({ status: "done" })),
    cancelDiningOrder: vi.fn().mockResolvedValue(order({ status: "cancelled" })),
    openDiningProblem: vi.fn().mockResolvedValue(order({ problem_open: true })),
    resolveDiningProblem: vi.fn().mockResolvedValue(order()),
    getDebtors: vi.fn().mockResolvedValue([
      { id: 901, name: "Anvar aka", phone: "", note: "", due: "", balance: 0 },
    ]),
    createDebtor: vi.fn(),
    ...overrides,
  } as unknown as BusinessDiningCashApi;
}


describe("kassa — ovqatlanish bo'limlari (v1656 pariteti)", () => {
  it("API to'liq bo'lsa qo'llab-quvvatlanadi", () => {
    expect(supportsDiningCashApi(makeApi([]))).toBe(true);
    expect(supportsDiningCashApi({ getDiningOrders: vi.fn() })).toBe(false);
  });

  it("uchta bo'lim v1656 nomlari bilan", async () => {
    render(<BusinessDiningCashV1656 api={makeApi([order()])} />);

    expect(await screen.findByRole("tab", { name: "Ochiq" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Muammoli" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Yakunlangan" })).toBeVisible();
  });

  it("ochiq hisob kartasi va amallar ko'rinadi", async () => {
    render(<BusinessDiningCashV1656 api={makeApi([order()])} />);

    expect(
      await screen.findByText("🍽️ Ochiq ichki hisoblar (1)"),
    ).toBeVisible();
    expect(screen.getByText("▸ 1-stol")).toBeVisible();
    expect(screen.getByText("Ofitsiant: Dilnoza")).toBeVisible();
    expect(screen.getByText("24 000 so‘m")).toBeVisible();

    // v1656 dagidek hisob yopiq turadi; kassir uni ochadi.
    const row = screen.getByText("▸ 1-stol").closest("details");
    expect(row).not.toBeNull();
    expect(screen.getByText("• Osh × 2 dona — 24 000")).not.toBeVisible();
    row!.open = true;

    expect(screen.getByText("• Osh × 2 dona — 24 000")).toBeVisible();

    for (const label of [
      "Tarkibni tahrirlash",
      "Naqd tasdiqlash",
      "Karta tasdiqlash",
      "📒 Qarzga rasmiylashtirish",
      "⚠️ Muammoli deb belgilash",
      "✕ Ichki buyurtmani bekor qilish",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeVisible();
    }
  });

  it("naqd to'lov tasdiqlashdan keyin yuboriladi", async () => {
    const api = makeApi([order()]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Naqd tasdiqlash" }),
    );
    // v1656 avval tasdiq so'raydi.
    expect(
      screen.getByText("To‘lov qabul qilinganini tasdiqlaysizmi?"),
    ).toBeVisible();
    expect(api.confirmDiningPayment).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    await waitFor(() => {
      expect(api.confirmDiningPayment).toHaveBeenCalledWith(1, {
        pay_type: "naqd",
      });
    });
    expect(await screen.findByText("To‘lov tasdiqlandi ✅")).toBeVisible();
  });

  it("karta to'lovi ham xuddi shunday", async () => {
    const api = makeApi([order()]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Karta tasdiqlash" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    await waitFor(() => {
      expect(api.confirmDiningPayment).toHaveBeenCalledWith(1, {
        pay_type: "karta",
      });
    });
  });

  it("qarzga rasmiylashtirishda qarzdor tanlanadi", async () => {
    const api = makeApi([order()]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "📒 Qarzga rasmiylashtirish" }),
    );

    expect(await screen.findByText("Ichki hisobni qarzga yozish")).toBeVisible();
    expect(api.confirmDiningPayment).not.toHaveBeenCalled();
  });

  it("bekor qilish sababsiz yuborilmaydi", async () => {
    const api = makeApi([order()]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "✕ Ichki buyurtmani bekor qilish" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Ha, bekor qilish" }));

    expect(screen.getByText("Bekor qilish sababini kiriting.")).toBeVisible();
    expect(api.cancelDiningOrder).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Bekor qilish sababi"), {
      target: { value: "Mijoz voz kechdi" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ha, bekor qilish" }));

    await waitFor(() => {
      expect(api.cancelDiningOrder).toHaveBeenCalledWith(1, "Mijoz voz kechdi");
    });
    expect(
      await screen.findByText("Ichki buyurtma bekor qilindi, stol bo‘shadi ✅"),
    ).toBeVisible();
  });

  it("muammoli deb belgilashda sabab va izoh yuboriladi", async () => {
    const api = makeApi([order()]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "⚠️ Muammoli deb belgilash" }),
    );
    fireEvent.change(screen.getByLabelText("Sabab"), {
      target: { value: "Noto‘g‘ri hisob" },
    });
    fireEvent.change(screen.getByLabelText("Izoh"), {
      target: { value: "Ikki marta yozilgan" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));

    await waitFor(() => {
      expect(api.openDiningProblem).toHaveBeenCalledWith(1, {
        reason: "Noto‘g‘ri hisob",
        note: "Ikki marta yozilgan",
      });
    });
  });

  it("hisobni tahrirlashda 0 ga tushirilgan qator yuboriladi", async () => {
    const api = makeApi([order()]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Tarkibni tahrirlash" }),
    );
    expect(
      screen.getByText("0 ga tushirilgan taom hisobdan o‘chadi."),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Osh kamaytirish" }));
    fireEvent.click(screen.getByRole("button", { name: "Osh kamaytirish" }));
    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));

    await waitFor(() => {
      expect(api.updateDiningCashierItems).toHaveBeenCalledWith(1, [
        { line_id: 11, qty: 0 },
      ]);
    });
  });

  it("muammoli bo'limda hal qilish tugmasi bor", async () => {
    const api = makeApi([
      order({ problem_open: true, problem_reason: "Mijoz e’tirozi", problem_note: "Sovuq" }),
    ]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Muammoli" }));

    expect(screen.getByText("⚠️ 1-stol")).toBeVisible();
    expect(screen.getByText("Ichki · Mijoz e’tirozi · Sovuq")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Muammo hal qilindi" }));
    fireEvent.click(screen.getByRole("button", { name: "Hal qilindi" }));

    await waitFor(() => {
      expect(api.resolveDiningProblem).toHaveBeenCalledWith(1);
    });
    expect(
      await screen.findByText("Hisob Ochiq bo‘limiga qaytdi ✅"),
    ).toBeVisible();
  });

  it("to'lovi tasdiqlangan, taomi tayyor hisob yakunlanadi", async () => {
    const api = makeApi([
      order({ payment_status: "confirmed", kitchen_status: "done" }),
    ]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Yakunlangan" }));

    expect(screen.getByText("✅ Yakunlash kutilmoqda (1)")).toBeVisible();
    expect(screen.getByText("Taom tayyor · to‘lov tasdiqlangan")).toBeVisible();

    fireEvent.click(screen.getByRole("button", {
      name: "✅ Hisobni yakunlash va stolni bo‘shatish",
    }));
    fireEvent.click(screen.getByRole("button", { name: "Yakunlash" }));

    await waitFor(() => {
      expect(api.finalizeDiningOrder).toHaveBeenCalledWith(1);
    });
    expect(
      await screen.findByText("Hisob yakunlandi, stol bo‘shadi ✅"),
    ).toBeVisible();
  });

  it("oshpaz tayyorlamagan hisobda yakunlash tugmasi yo'q", async () => {
    const api = makeApi([
      order({ payment_status: "confirmed", kitchen_status: "preparing" }),
    ]);
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Yakunlangan" }));

    expect(
      screen.getByText("⏳ Oshpaz tayyorlashi kutilmoqda"),
    ).toBeVisible();
    expect(screen.queryByRole("button", {
      name: "✅ Hisobni yakunlash va stolni bo‘shatish",
    })).toBeNull();
  });

  it("to'lovi tasdiqlangan hisob Ochiq bo'limda ko'rinmaydi", async () => {
    const api = makeApi([order({ payment_status: "confirmed" })]);
    render(<BusinessDiningCashV1656 api={api} />);

    expect(
      await screen.findByText("Ochiq ichki hisob yo‘q"),
    ).toBeVisible();
  });

  it("server xatosi ko'rsatiladi", async () => {
    const api = makeApi([order()], {
      confirmDiningPayment: vi.fn().mockRejectedValue(
        new Error("Muammoli zakaz to‘lovi tasdiqlanmaydi."),
      ),
    });
    render(<BusinessDiningCashV1656 api={api} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Naqd tasdiqlash" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    expect(
      await screen.findByText("Muammoli zakaz to‘lovi tasdiqlanmaydi."),
    ).toBeVisible();
  });
});
