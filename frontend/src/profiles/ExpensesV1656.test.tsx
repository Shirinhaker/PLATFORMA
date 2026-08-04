import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExpensesV1656 } from "./ExpensesV1656";


function expenseApi() {
  return {
    getExpenses: vi.fn().mockResolvedValue({
      day: "2026-08-04",
      total: 275_000,
      by_category: { "Tovar xaridi": 200_000, Reklama: 75_000 },
      expenses: [
        {
          id: 11,
          category: "Tovar xaridi",
          amount: 200_000,
          note: "Un",
          source: "stock",
          who: "",
          created_at: "2026-08-04T08:00:00Z",
        },
        {
          id: 12,
          category: "Reklama",
          amount: 75_000,
          note: "Banner",
          source: "manual",
          who: "Ali",
          created_at: "2026-08-04T08:30:00Z",
        },
      ],
    }),
    getExpenseCategories: vi.fn().mockResolvedValue({
      categories: ["Ijara", "Boshqa"],
      defaults: ["Ijara", "Boshqa"],
    }),
    createExpenseCategory: vi.fn().mockResolvedValue({ ok: true, exists: false }),
    createExpense: vi.fn().mockResolvedValue({ id: 13 }),
    deleteExpense: vi.fn().mockResolvedValue(undefined),
  };
}


describe("ExpensesV1656", () => {
  it("shows daily totals and keeps stock expenses automatic", async () => {
    const api = expenseApi();
    render(<ExpensesV1656 api={api} onBack={vi.fn()} />);

    expect(await screen.findByText("275 000 so'm")).toBeInTheDocument();
    expect(screen.getByText("Bugungi xarajat").closest("section"))
      .toHaveTextContent("Tovar xaridi: 200 000");
    expect(screen.getByText("avtomatik")).toBeInTheDocument();
    expect(screen.getByText(/Ombor kirimi/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "O‘chirish" })).toHaveLength(1);
  });

  it("creates a new category before saving its expense", async () => {
    const user = userEvent.setup();
    const api = expenseApi();
    render(<ExpensesV1656 api={api} onBack={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "+ Xarajat yozish" }));
    const dialog = await screen.findByRole("dialog", { name: "Xarajat yozish" });
    await user.selectOptions(within(dialog).getByLabelText("Kategoriya"), "__new__");
    await user.type(within(dialog).getByLabelText("Yangi kategoriya nomi"), "Reklama");
    await user.type(within(dialog).getByLabelText("Summa (so‘m)"), "75000");
    await user.type(within(dialog).getByLabelText("Izoh (ixtiyoriy)"), "Banner");
    await user.click(within(dialog).getByRole("button", { name: "Saqlash" }));

    await waitFor(() => expect(api.createExpenseCategory).toHaveBeenCalledWith({
      name: "Reklama",
    }));
    expect(api.createExpenseCategory.mock.invocationCallOrder[0] ?? 0)
      .toBeLessThan(api.createExpense.mock.invocationCallOrder[0] ?? 0);
    expect(api.createExpense).toHaveBeenCalledWith({
      category: "Reklama",
      amount: 75_000,
      note: "Banner",
    });
  });
});
