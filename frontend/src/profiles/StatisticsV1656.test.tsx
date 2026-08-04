import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { StatisticsReport } from "../api/types";
import { StatisticsV1656 } from "./StatisticsV1656";


function report(overrides: Partial<StatisticsReport> = {}): StatisticsReport {
  return {
    period: "oy",
    anchor: "",
    label: "Avg 2026",
    revenue: 1_350_000,
    cash_in: 1_250_000,
    cogs: 420_000,
    gross_profit: 930_000,
    expenses: 75_000,
    inventory_purchases: 200_000,
    profit: 855_000,
    qarzpay: 200_000,
    pay: { naqd: 650_000, karta: 400_000, qarz: 300_000, order: 0 },
    exp_by_cat: { Ijara: 75_000, "Tovar xaridi": 200_000 },
    trend: [
      { label: "1", rev: 1_350_000, exp: 75_000, cogs: 420_000, profit: 855_000 },
      { label: "2", rev: 0, exp: 0, cogs: 0, profit: 0 },
    ],
    top_products: [{
      name: "Olma", qty: 3, unit: "dona", total: 1_000_000,
      cost_total: 300_000, margin: 700_000,
    }],
    low_stock: [{ name: "Olma", unit: "dona", stock_qty: 3 }],
    source_split: {
      internal: { count: 1, total: 300_000 },
      external: { count: 1, total: 400_000 },
      manual: { count: 2, total: 650_000 },
    },
    cashiers: [{ name: "Kassir Ali", checks: 2, total: 650_000 }],
    waiters: [{ name: "Ofitsiant Lola", orders: 1, total: 300_000 }],
    sales_count: 4,
    can_next: false,
    ...overrides,
  };
}


function statisticsApi() {
  return {
    getStatistics: vi.fn().mockResolvedValue(report()),
    getStatisticsNav: vi.fn().mockResolvedValue({ anchor: "2026-07-01" }),
  };
}


describe("StatisticsV1656", () => {
  it("renders the complete v1656 financial, source and employee parity", async () => {
    const api = statisticsApi();
    render(<StatisticsV1656 api={api} onBack={vi.fn()} />);

    expect(await screen.findByText("1 250 000")).toBeInTheDocument();
    expect(screen.getByText("Haqiqiy pul tushumi").closest("article"))
      .toHaveTextContent("1 250 000");
    expect(screen.getByText(/Sof foyda/).closest("article"))
      .toHaveTextContent("855 000 so'm");
    expect(screen.getByText(/Qarzdan qaytgan pul/))
      .toHaveTextContent("200 000");
    expect(screen.getByText("To‘lov turlari")).toBeInTheDocument();
    expect(screen.getByText(/Savdo manbalari/)).toBeInTheDocument();
    const products = screen.getByText(/Eng ko‘p sotilganlar/).closest("section");
    expect(products).not.toBeNull();
    expect(screen.getByText(/Kam qolgan tovarlar/)).toBeInTheDocument();
    expect(screen.getByText(/Ofitsiantlar/)).toBeInTheDocument();
    expect(screen.getByText(/Kassirlar/)).toBeInTheDocument();
    expect(within(products as HTMLElement).getByText("Olma").closest("article"))
      .toHaveTextContent("foyda 700 000");
    expect(api.getStatistics).toHaveBeenCalledWith("oy", "");
  });

  it("changes period, metric and date without reloading unrelated resources", async () => {
    const user = userEvent.setup();
    const api = statisticsApi();
    api.getStatistics.mockImplementation(async (period: string, anchor: string) => (
      report({ period: period as StatisticsReport["period"], anchor, label: `${period}:${anchor}` })
    ));
    render(<StatisticsV1656 api={api} onBack={vi.fn()} />);

    await screen.findByText("oy:");
    await user.click(screen.getByRole("button", { name: "Kun" }));
    await waitFor(() => expect(api.getStatistics).toHaveBeenCalledWith("kun", ""));
    expect(await screen.findByText("kun:")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Xarajat" }));
    expect(screen.getByRole("img", { name: "Xarajat grafigi" }))
      .toBeInTheDocument();
    expect(api.getStatistics).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "Oldingi davr" }));
    expect(api.getStatisticsNav).toHaveBeenCalledWith("kun", -1, "");
    await waitFor(() => expect(api.getStatistics)
      .toHaveBeenCalledWith("kun", "2026-07-01"));
  });

  it("does not let an older delayed response overwrite the selected period", async () => {
    const user = userEvent.setup();
    let resolveMonth: ((value: StatisticsReport) => void) | undefined;
    const month = new Promise<StatisticsReport>((resolve) => { resolveMonth = resolve; });
    const api = {
      getStatistics: vi.fn()
        .mockImplementationOnce(() => month)
        .mockResolvedValueOnce(report({ period: "kun", label: "2026-08-04" })),
      getStatisticsNav: vi.fn(),
    };
    render(<StatisticsV1656 api={api} onBack={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Kun" }));
    expect(await screen.findByText("2026-08-04")).toBeInTheDocument();
    resolveMonth?.(report({ label: "Kechikkan oy" }));

    await waitFor(() => expect(screen.queryByText("Kechikkan oy"))
      .not.toBeInTheDocument());
    expect(screen.getByText("2026-08-04")).toBeInTheDocument();
  });

  it("does not apply delayed navigation after the period changes", async () => {
    const user = userEvent.setup();
    let resolveNavigation: ((value: { anchor: string }) => void) | undefined;
    const navigation = new Promise<{ anchor: string }>((resolve) => {
      resolveNavigation = resolve;
    });
    const api = statisticsApi();
    api.getStatistics.mockImplementation(async (period: string, anchor: string) => (
      report({
        period: period as StatisticsReport["period"],
        anchor,
        label: `${period}:${anchor}`,
      })
    ));
    api.getStatisticsNav.mockImplementationOnce(() => navigation);
    render(<StatisticsV1656 api={api} onBack={vi.fn()} />);

    await screen.findByText("oy:");
    await user.click(screen.getByRole("button", { name: "Oldingi davr" }));
    await user.click(screen.getByRole("button", { name: "Kun" }));
    expect(await screen.findByText("kun:")).toBeInTheDocument();
    resolveNavigation?.({ anchor: "2026-07-01" });

    await waitFor(() => expect(api.getStatistics)
      .not.toHaveBeenCalledWith("kun", "2026-07-01"));
    expect(screen.getByText("kun:")).toBeInTheDocument();
  });
});
