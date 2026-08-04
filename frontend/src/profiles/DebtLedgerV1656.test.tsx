import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DebtLedgerV1656 } from "./DebtLedgerV1656";


const debtor = {
  id: 30,
  name: "Ali Valiyev",
  phone: "+998901234567",
  note: "Doimiy mijoz",
  due: "",
  balance: 500,
};

const detail = {
  ...debtor,
  tx: [{
    id: 41,
    type: "debt" as const,
    amount: 500,
    date: "2026-08-04",
    note: "Olma",
    source: "manual",
    cash_receipt_id: null,
    order_id: null,
  }],
};

function debtApi() {
  return {
    getDebtors: vi.fn().mockResolvedValue([debtor]),
    createDebtor: vi.fn().mockResolvedValue({ id: 31 }),
    getDebtor: vi.fn().mockResolvedValue(detail),
    addDebtTransaction: vi.fn().mockResolvedValue({
      id: 42,
      type: "payment",
      amount: 200,
      date: "2026-08-04",
      note: "Qaytardi",
      source: "manual",
      cash_receipt_id: 12,
      order_id: null,
    }),
  };
}

describe("DebtLedgerV1656", () => {
  it("shows live balances and records a payment in the debtor history", async () => {
    const user = userEvent.setup();
    const api = debtApi();
    render(<DebtLedgerV1656 api={api} onBack={vi.fn()} />);

    expect(await screen.findByText("Ali Valiyev")).toBeInTheDocument();
    expect(screen.getByText("Umumiy qarz").closest("section")).toHaveTextContent("1 ta qarzdor");
    await user.click(screen.getByRole("button", { name: /Ali Valiyev/ }));
    expect(await screen.findByText("Amaliyotlar tarixi")).toBeInTheDocument();
    expect(screen.getByText(/Olma/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "− To‘lov" }));
    const dialog = screen.getByRole("dialog", { name: "To‘lov summasi" });
    await user.type(within(dialog).getByLabelText(/To‘lov summasi/), "200");
    await user.type(within(dialog).getByLabelText(/Izoh/), "Qaytardi");
    await user.click(within(dialog).getByRole("button", { name: "Saqlash" }));

    await waitFor(() => expect(api.addDebtTransaction).toHaveBeenCalledWith(30, {
      type: "payment",
      amount: 200,
      note: "Qaytardi",
    }));
    expect(api.getDebtor).toHaveBeenCalledTimes(2);
  });

  it("creates a debtor with an opening balance", async () => {
    const user = userEvent.setup();
    const api = debtApi();
    render(<DebtLedgerV1656 api={api} onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "+ Yangi qarzdor" }));
    const dialog = screen.getByRole("dialog", { name: "Yangi qarzdor" });
    await user.type(within(dialog).getByLabelText("Qarzdor ismi"), "Vali Karimov");
    await user.type(within(dialog).getByLabelText(/Telefon/), "+998909999999");
    await user.type(within(dialog).getByLabelText(/Boshlang‘ich qarz/), "75000");
    await user.click(within(dialog).getByRole("button", { name: "Qo‘shish" }));

    await waitFor(() => expect(api.createDebtor).toHaveBeenCalledWith({
      name: "Vali Karimov",
      phone: "+998909999999",
      note: "",
      due: "",
      initial_debt: 75000,
    }));
  });
});
