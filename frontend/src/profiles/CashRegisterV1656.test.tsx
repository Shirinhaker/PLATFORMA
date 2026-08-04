import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CashRegisterV1656 } from "./CashRegisterV1656";


const receipt = {
  id: 10,
  receipt_no: 7,
  source: "manual",
  order_id: null,
  pay_type: "naqd",
  pay_text: "Naqd",
  debtor_name: "",
  note: "",
  who: "Rahbar",
  created_at: "2026-08-04T09:30:00Z",
  total: 600,
  can_delete: true,
  can_change_payment: false,
  lines: [{
    id: 11,
    catalog_item_id: 20,
    item_name: "Olma",
    qty: 2,
    unit: "dona",
    price: 300,
    total: 600,
    cost_total: 200,
  }],
};

const register = {
  day: "2026-08-04",
  totals: {
    all: 600,
    cash_in: 600,
    naqd: 600,
    karta: 0,
    qarz: 0,
    qarzpay: 0,
    order: 0,
  },
  receipts: [receipt],
};

function cashApi() {
  return {
    getCashRegister: vi.fn().mockResolvedValue(register),
    getCashCatalog: vi.fn().mockResolvedValue([{
      id: 20,
      name: "Olma",
      price: 300,
      price_text: "300 so‘m",
      unit: "dona",
      track_stock: true,
      stock_qty: 5,
      low_stock: false,
    }]),
    createCashReceipt: vi.fn().mockResolvedValue({
      ok: true,
      id: 12,
      receipt_no: 8,
      count: 1,
      total: 600,
    }),
    deleteCashReceipt: vi.fn().mockResolvedValue(undefined),
    updateCashOrderPayment: vi.fn().mockResolvedValue(receipt),
    getDebtors: vi.fn().mockResolvedValue([{
      id: 30,
      name: "Ali Valiyev",
      phone: "+998901234567",
      note: "",
      due: "",
      balance: 500,
    }]),
    createDebtor: vi.fn().mockResolvedValue({ id: 31 }),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CashRegisterV1656", () => {
  it("renders the v1656 daily totals and grouped receipts", async () => {
    const api = cashApi();
    render(<CashRegisterV1656 api={api} onBack={vi.fn()} />);

    expect(await screen.findByText("🧾 Chek #7")).toBeInTheDocument();
    expect(screen.getByText(/Haqiqiy tushum/)).toBeInTheDocument();
    expect(screen.getByText(/Olma × 2/)).toBeInTheDocument();
    expect(api.getCashRegister).toHaveBeenCalledWith("");
  });

  it("creates a multi-line receipt from the live catalog", async () => {
    const user = userEvent.setup();
    const api = cashApi();
    render(<CashRegisterV1656 api={api} onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "+ Savdo yozish" }));
    const appleButton = await screen.findByRole("button", {
      name: /Omborda: 5 dona/,
    });
    await user.click(appleButton);
    await user.click(appleButton);
    await user.click(screen.getByRole("button", { name: "Savdoni saqlash" }));

    await waitFor(() => expect(api.createCashReceipt).toHaveBeenCalledWith(
      expect.objectContaining({
        items: [{
          catalog_item_id: 20,
          name: "",
          qty: 2,
          price: 300,
        }],
        pay_type: "naqd",
      }),
    ));
  });

  it("writes a debt sale to the selected debtor", async () => {
    const user = userEvent.setup();
    const api = cashApi();
    render(<CashRegisterV1656 api={api} onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "+ Savdo yozish" }));
    await user.click(await screen.findByRole("button", { name: /Omborda: 5 dona/ }));
    await user.selectOptions(screen.getByLabelText("To‘lov turi"), "qarz");
    await user.selectOptions(screen.getByLabelText("Qarzdor"), "30");
    await user.click(screen.getByRole("button", { name: "Savdoni saqlash" }));

    await waitFor(() => expect(api.createCashReceipt).toHaveBeenCalledWith(
      expect.objectContaining({
        pay_type: "qarz",
        debtor_id: 30,
      }),
    ));
  });

  it("blocks an over-stock sale before the API and restores on confirmed delete", async () => {
    const user = userEvent.setup();
    const api = cashApi();
    api.getCashCatalog.mockResolvedValueOnce([{
      id: 20,
      name: "Olma",
      price: 300,
      price_text: "300 so‘m",
      unit: "dona",
      track_stock: true,
      stock_qty: 0,
      low_stock: true,
    }]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<CashRegisterV1656 api={api} onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "+ Savdo yozish" }));
    await user.click(await screen.findByRole("button", { name: /Olma/ }));
    await user.click(screen.getByRole("button", { name: "Savdoni saqlash" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Omborda yetarli emas");
    expect(api.createCashReceipt).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "← Kassa" }));
    await user.click(await screen.findByRole("button", { name: "O‘chirish" }));
    await waitFor(() => expect(api.deleteCashReceipt).toHaveBeenCalledWith(10));
  });
});
