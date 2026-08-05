import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EducationStatisticsReport } from "../api/types";
import { EducationStatisticsV1656 } from "./EducationStatisticsV1656";


function report(overrides: Partial<EducationStatisticsReport> = {}): EducationStatisticsReport {
  return {
    period: {
      type: "month",
      date: "2026-08-04",
      start: "2026-08-01",
      end: "2026-08-31",
    },
    education: {
      active_students: 2,
      active_groups: 1,
      new_enrollments: 3,
      attendance_percent: 75,
    },
    student_finance: { calculated: 1_000, paid: 700, debt: 300 },
    teacher_finance: { calculated: 400, paid: 250, debt: 150 },
    result: { other_expenses: 100, cash_flow: 350, accrual_result: 500 },
    groups: [{
      id: 1,
      name: "Ingliz tili",
      active_students: 2,
      attendance_percent: 75,
      calculated: 1_000,
      paid: 700,
      debt: 300,
    }],
    ...overrides,
  };
}


describe("EducationStatisticsV1656", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-04T09:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the exact v1656 education dashboard blocks", async () => {
    const api = { getEducationStatistics: vi.fn().mockResolvedValue(report()) };

    render(<EducationStatisticsV1656 api={api} onBack={vi.fn()} />);

    expect(await screen.findByText("Ta'lim boshqaruv paneli")).toBeInTheDocument();
    expect(screen.getByText("Ta'lim jarayoni")).toBeInTheDocument();
    expect(screen.getByText("O'quvchi to'lovlari")).toBeInTheDocument();
    expect(screen.getByText("O'qituvchi maoshi")).toBeInTheDocument();
    expect(screen.getByText("Yakuniy natija")).toBeInTheDocument();
    expect(screen.getByText("Guruhlar kesimi")).toBeInTheDocument();
    expect(screen.getByText("2 nafar")).toBeInTheDocument();
    expect(screen.getAllByText("75%").length).toBeGreaterThan(0);
    expect(screen.getByText("Qoldiq · 350 so'm")).toBeInTheDocument();
    expect(screen.getByText("Foyda · 500 so'm")).toBeInTheDocument();
    expect(screen.getByText("Ingliz tili")).toBeInTheDocument();
    expect(api.getEducationStatistics).toHaveBeenCalledWith("month", "2026-08-04");
  });

  it("keeps only Kun Oy Yil and shifts the selected period like v1656", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const api = { getEducationStatistics: vi.fn().mockResolvedValue(report()) };

    render(<EducationStatisticsV1656 api={api} onBack={vi.fn()} />);
    await screen.findByText("Ta'lim boshqaruv paneli");

    expect(screen.getAllByRole("button", { name: /^(Kun|Oy|Yil)$/ })).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Kun" }));
    await waitFor(() => expect(api.getEducationStatistics).toHaveBeenCalledWith(
      "day", "2026-08-04",
    ));
    await user.click(screen.getByRole("button", { name: "Oldingi davr" }));
    await waitFor(() => expect(api.getEducationStatistics).toHaveBeenCalledWith(
      "day", "2026-08-03",
    ));
  });

  it("does not let a late old response replace the newly selected period", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let resolveMonth!: (value: EducationStatisticsReport) => void;
    let resolveDay!: (value: EducationStatisticsReport) => void;
    const month = new Promise<EducationStatisticsReport>((resolve) => {
      resolveMonth = resolve;
    });
    const day = new Promise<EducationStatisticsReport>((resolve) => {
      resolveDay = resolve;
    });
    const api = {
      getEducationStatistics: vi.fn()
        .mockReturnValueOnce(month)
        .mockReturnValueOnce(day),
    };

    render(<EducationStatisticsV1656 api={api} onBack={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Kun" }));
    resolveDay(report({
      period: { type: "day", date: "2026-08-04", start: "2026-08-04", end: "2026-08-04" },
      education: { active_students: 7, active_groups: 1, new_enrollments: 0, attendance_percent: 100 },
    }));
    expect(await screen.findByText("7 nafar")).toBeInTheDocument();

    resolveMonth(report({
      education: { active_students: 99, active_groups: 1, new_enrollments: 0, attendance_percent: 1 },
    }));
    await Promise.resolve();
    expect(screen.queryByText("99 nafar")).not.toBeInTheDocument();
    expect(screen.getByText("7 nafar")).toBeInTheDocument();
  });
});
