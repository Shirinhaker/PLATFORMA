import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  AdminAccountDetail,
  AdminAccountRow,
  AuditDetail,
  AuditRow,
  ReportRow,
} from "./admin-client";
import { AdminAccounts, type AdminAccountsApi } from "./AdminAccounts";
import { AdminAudit, type AdminAuditApi } from "./AdminAudit";
import { AdminReports, type AdminReportsApi } from "./AdminReports";


function accountRow(
  overrides: Partial<AdminAccountRow> = {},
): AdminAccountRow {
  return {
    actor_type: "business",
    account_id: 7,
    login: "choyxona",
    telegram_user_id: 900007,
    name: "Choyxona",
    phone: "+998901112233",
    restrictions: [],
    ...overrides,
  };
}

function accountDetail(
  overrides: Partial<AdminAccountDetail> = {},
): AdminAccountDetail {
  return {
    ...accountRow(),
    status: "active",
    created_at: 1_785_000_000,
    restrictions: [],
    notes: [],
    ...overrides,
  };
}

function report(overrides: Partial<ReportRow> = {}): ReportRow {
  return {
    id: 3,
    reporter_account_id: 11,
    content_kind: "listing",
    content_id: 42,
    reason_code: "fraud",
    comment: "Pul olib mahsulot bermadi",
    status: "open",
    assigned_admin_tg_id: null,
    resolution: "",
    created_at: 1_785_000_000,
    updated_at: 1_785_000_000,
    ...overrides,
  };
}

function auditRow(overrides: Partial<AuditRow> = {}): AuditRow {
  return {
    id: 12,
    admin_tg_id: 1423181561,
    action: "account.restrict",
    target_kind: "business",
    target_id: "7",
    reason: "Shikoyat tasdiqlandi",
    created_at: 1_785_000_000,
    ...overrides,
  };
}


describe("admin — profil va bizneslar", () => {
  function makeApi(overrides: Partial<AdminAccountsApi> = {}) {
    return {
      accounts: vi.fn().mockResolvedValue([accountRow()]),
      account: vi.fn().mockResolvedValue(accountDetail()),
      restrict: vi.fn().mockResolvedValue({ id: 1, already_active: false }),
      unrestrict: vi.fn().mockResolvedValue({ id: 1, already_active: false }),
      addNote: vi.fn().mockResolvedValue({
        id: 1, note: "Izoh", admin_tg_id: 1, created_at: 1_785_000_000,
      }),
      ...overrides,
    } as unknown as AdminAccountsApi;
  }

  it("qidiruvsiz ro'yxat yuklanmaydi", () => {
    const api = makeApi();
    render(<AdminAccounts api={api} />);

    expect(screen.getByText("Qidiruvni boshlang.")).toBeVisible();
    expect(api.accounts).not.toHaveBeenCalled();
  });

  it("tur, matn va holat bo'yicha qidiradi", async () => {
    const api = makeApi();
    render(<AdminAccounts api={api} />);

    fireEvent.change(screen.getByLabelText("Akkaunt turi"), {
      target: { value: "user" },
    });
    fireEvent.change(screen.getByLabelText("Qidiruv"), {
      target: { value: "anvar" },
    });
    fireEvent.change(screen.getByLabelText("Holat"), {
      target: { value: "account_blocked" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Qidirish" }));

    await waitFor(() => {
      expect(api.accounts).toHaveBeenCalledWith(
        "user", "anvar", "account_blocked",
      );
    });
  });

  it("cheklov sababsiz qo'yilmaydi", async () => {
    const api = makeApi();
    render(<AdminAccounts api={api} />);
    fireEvent.click(screen.getByRole("button", { name: "Qidirish" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("Cheklov bo‘lmagan.");

    fireEvent.click(
      screen.getByRole("button", { name: "Publicdan yashirilgan" }),
    );

    expect(await screen.findByText("Sabab kiritilishi shart.")).toBeVisible();
    expect(api.restrict).not.toHaveBeenCalled();
  });

  it("sabab bilan cheklov qo'yiladi", async () => {
    const api = makeApi();
    render(<AdminAccounts api={api} />);
    fireEvent.click(screen.getByRole("button", { name: "Qidirish" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("Cheklov bo‘lmagan.");

    fireEvent.change(screen.getByLabelText("Sabab"), {
      target: { value: "Firibgarlik" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Bloklangan" }));

    await waitFor(() => {
      expect(api.restrict).toHaveBeenCalledWith("business", 7, {
        restriction: "account_blocked",
        reason: "Firibgarlik",
      });
    });
  });

  it("faol cheklov olib tashlanadi", async () => {
    const api = makeApi({
      account: vi.fn().mockResolvedValue(accountDetail({
        restrictions: [{
          id: 1,
          restriction: "content_hidden",
          status: "active",
          reason: "Tekshiruv",
          created_by_tg_id: 1,
          created_at: 1_785_000_000,
          revoked_reason: "",
          revoked_at: 0,
        }],
      })),
    });
    render(<AdminAccounts api={api} />);
    fireEvent.click(screen.getByRole("button", { name: "Qidirish" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    fireEvent.change(await screen.findByLabelText("Sabab"), {
      target: { value: "Asossiz edi" },
    });
    fireEvent.click(screen.getByRole("button", {
      name: "Publicdan yashirilgan — olib tashlash",
    }));

    await waitFor(() => {
      expect(api.unrestrict).toHaveBeenCalledWith("business", 7, {
        restriction: "content_hidden",
        reason: "Asossiz edi",
      });
    });
    expect(api.restrict).not.toHaveBeenCalled();
  });

  it("bo'sh izoh saqlanmaydi", async () => {
    const api = makeApi();
    render(<AdminAccounts api={api} />);
    fireEvent.click(screen.getByRole("button", { name: "Qidirish" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("Cheklov bo‘lmagan.");

    fireEvent.click(screen.getByRole("button", { name: "Izoh qo‘shish" }));

    expect(await screen.findByText("Izoh bo‘sh bo‘lmasin.")).toBeVisible();
    expect(api.addNote).not.toHaveBeenCalled();
  });
});


describe("admin — shikoyatlar", () => {
  function makeApi(overrides: Partial<AdminReportsApi> = {}) {
    return {
      reports: vi.fn().mockResolvedValue([report()]),
      assignReport: vi.fn().mockResolvedValue(
        report({ status: "reviewing", assigned_admin_tg_id: 1 }),
      ),
      decideReport: vi.fn().mockResolvedValue(report({ status: "resolved" })),
      setContentStatus: vi.fn().mockResolvedValue({}),
      ...overrides,
    } as unknown as AdminReportsApi;
  }

  it("ochiq shikoyatlar birinchi ko'rsatiladi", async () => {
    const api = makeApi();
    render(<AdminReports api={api} />);

    await waitFor(() => expect(api.reports).toHaveBeenCalledWith("open"));
    expect(await screen.findByText("listing #42")).toBeVisible();
    expect(screen.getByText("Firibgarlik")).toBeVisible();
  });

  it("shikoyatni o'ziga biriktiradi", async () => {
    const api = makeApi();
    render(<AdminReports api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    fireEvent.click(
      screen.getByRole("button", { name: "O‘zimga biriktirish" }),
    );

    await waitFor(() => expect(api.assignReport).toHaveBeenCalledWith(3));
  });

  it("qaror sababsiz qabul qilinmaydi", async () => {
    const api = makeApi();
    render(<AdminReports api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    fireEvent.click(screen.getByRole("button", { name: "Hal qilindi" }));

    expect(await screen.findByText("Sabab kiritilishi shart.")).toBeVisible();
    expect(api.decideReport).not.toHaveBeenCalled();
  });

  it("kontentni yashirish ham sabab talab qiladi", async () => {
    const api = makeApi();
    render(<AdminReports api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    fireEvent.click(
      screen.getByRole("button", { name: "Kontentni yashirish" }),
    );
    expect(await screen.findByText("Sabab kiritilishi shart.")).toBeVisible();
    expect(api.setContentStatus).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Qaror sababi"), {
      target: { value: "Noqonuniy mahsulot" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Kontentni yashirish" }),
    );

    await waitFor(() => {
      expect(api.setContentStatus).toHaveBeenCalledWith(
        "listing", 42, "hide", "Noqonuniy mahsulot",
      );
    });
  });

  it("hal qilingan shikoyatda tugmalar yo'q", async () => {
    const api = makeApi({
      reports: vi.fn().mockResolvedValue([
        report({ status: "resolved", resolution: "E'lon olib tashlandi" }),
      ]),
    });
    render(<AdminReports api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    expect(
      await screen.findByText(
        "Qaror: Hal qilingan · E'lon olib tashlandi",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Hal qilindi" })).toBeNull();
  });
});


describe("admin — audit tarixi", () => {
  function makeApi(overrides: Partial<AdminAuditApi> = {}) {
    return {
      audit: vi.fn().mockResolvedValue([auditRow()]),
      auditDetail: vi.fn().mockResolvedValue({
        ...auditRow(),
        before: { status: "none" },
        after: { status: "active" },
        ip_hash: "a".repeat(64),
        user_agent: "AdminPanel/1.0",
      } as AuditDetail),
      auditExportUrl: vi.fn().mockReturnValue(
        "https://api.test/api/v1/admin/audit/export.csv",
      ),
      ...overrides,
    } as unknown as AdminAuditApi;
  }

  it("jurnal ro'yxati va o'zgarmasligi haqidagi izoh", async () => {
    render(<AdminAudit api={makeApi()} />);

    expect(await screen.findByText("account.restrict")).toBeVisible();
    expect(
      screen.getByText("Bu jurnal o‘zgartirilmaydi va o‘chirilmaydi."),
    ).toBeVisible();
  });

  it("amal bo'yicha filtrlaydi", async () => {
    const api = makeApi();
    render(<AdminAudit api={api} />);
    await screen.findByText("account.restrict");

    fireEvent.change(screen.getByLabelText("Amal"), {
      target: { value: "payment.approve" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ko‘rsatish" }));

    await waitFor(() => {
      expect(api.audit).toHaveBeenCalledWith("payment.approve");
    });
  });

  it("batafsilda oldingi va yangi holat ko'rinadi", async () => {
    const api = makeApi();
    render(<AdminAudit api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Batafsil" }));

    await waitFor(() => expect(api.auditDetail).toHaveBeenCalledWith(12));
    expect(await screen.findByText("Oldingi holat")).toBeVisible();
    expect(screen.getByText("Yangi holat")).toBeVisible();
    expect(screen.getByText(/"status": "active"/)).toBeVisible();
  });

  it("CSV havolasi filtrni saqlaydi", async () => {
    const api = makeApi();
    render(<AdminAudit api={api} />);
    await screen.findByText("account.restrict");

    fireEvent.change(screen.getByLabelText("Amal"), {
      target: { value: "report.resolved" },
    });

    await waitFor(() => {
      expect(api.auditExportUrl).toHaveBeenCalledWith("report.resolved");
    });
    expect(
      screen.getByRole("link", { name: "CSV yuklab olish" }),
    ).toHaveAttribute("href");
  });
});
