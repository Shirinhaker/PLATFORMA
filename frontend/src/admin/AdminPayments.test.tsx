import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  AdminPaymentDetail,
  AdminPaymentRow,
} from "./admin-client";
import { AdminPayments, type AdminPaymentsApi } from "./AdminPayments";


function row(overrides: Partial<AdminPaymentRow> = {}): AdminPaymentRow {
  return {
    id: 1,
    request_code: "PAY-A1B2C3",
    actor_type: "business",
    account_id: 7,
    account_login: "choyxona",
    service_type: "subscription",
    plan_code: "plus",
    duration_months: 1,
    quantity: 1,
    amount: 99000,
    currency: "UZS",
    price_code: "subscription_plus_1m",
    status: "pending",
    public_reason: "",
    reviewed_by_admin_tg_id: null,
    created_at: 1_785_200_000,
    updated_at: 1_785_200_000,
    ...overrides,
  };
}

function detail(
  overrides: Partial<AdminPaymentDetail> = {},
): AdminPaymentDetail {
  return {
    ...row(),
    target_id: null,
    payment_method_id: 1,
    payment_method_name: "Bank kartasi",
    internal_note: "",
    approved_at: 0,
    rejected_at: 0,
    cancelled_at: 0,
    attempts: [{
      attempt_no: 1,
      review_status: "pending",
      review_reason: "",
      submitted_at: 1_785_200_000,
      receipt_mime: "image/png",
      receipt_sha256: "a".repeat(64),
      has_receipt: true,
    }],
    ...overrides,
  };
}

function makeApi(overrides: Partial<AdminPaymentsApi> = {}) {
  return {
    payments: vi.fn().mockResolvedValue([row()]),
    payment: vi.fn().mockResolvedValue(detail()),
    receipt: vi.fn().mockResolvedValue({
      url: "https://r2.example/receipt.png?sig=x",
      mime: "image/png",
      expires_in: 300,
    }),
    decide: vi.fn().mockResolvedValue({}),
    ...overrides,
  } as unknown as AdminPaymentsApi;
}


describe("admin to'lov navbati", () => {
  it("kutilayotgan to'lovlar birinchi ko'rsatiladi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);

    await waitFor(() => {
      expect(api.payments).toHaveBeenCalledWith("pending", "");
    });
    const code = await screen.findByText("PAY-A1B2C3");
    const line = code.closest("tr")!;
    expect(line).toHaveTextContent("Obuna");
    expect(line).toHaveTextContent("99 000 so‘m");
    expect(line).toHaveTextContent("Kutilayotgan");
  });

  it("holat va xizmat bo'yicha filtrlaydi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);
    await screen.findByText("PAY-A1B2C3");

    fireEvent.change(screen.getByLabelText("Holat"), {
      target: { value: "approved" },
    });
    fireEvent.change(screen.getByLabelText("Xizmat"), {
      target: { value: "subscription" },
    });

    await waitFor(() => {
      expect(api.payments).toHaveBeenCalledWith("approved", "subscription");
    });
  });

  it("tafsilotda egasi, tarif va usul ko'rinadi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);

    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    expect(await screen.findByText("choyxona")).toBeVisible();
    expect(screen.getByText("Obuna · plus · 1 oy")).toBeVisible();
    expect(screen.getByText("Bank kartasi")).toBeVisible();
  });

  it("kvitansiya faqat so'ralganda yuklanadi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("choyxona");

    expect(api.receipt).not.toHaveBeenCalled();
    expect(screen.queryByAltText("To‘lov kvitansiyasi")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "🧾 Kvitansiyani ko‘rish" }),
    );

    await waitFor(() => expect(api.receipt).toHaveBeenCalledWith(1));
    const image = await screen.findByAltText("To‘lov kvitansiyasi");
    expect(image).toHaveAttribute(
      "src", "https://r2.example/receipt.png?sig=x",
    );
  });

  it("tasdiqlash qarorni yuboradi va ro'yxatni yangilaydi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("choyxona");

    fireEvent.change(screen.getByLabelText("Ichki izoh"), {
      target: { value: "chek to‘g‘ri" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Tasdiqlash" }));

    await waitFor(() => {
      expect(api.decide).toHaveBeenCalledWith(1, "approve", {
        reason: "",
        internal_note: "chek to‘g‘ri",
      });
    });
    expect(await screen.findByText("To‘lov tasdiqlandi ✅")).toBeVisible();
    expect(api.payments).toHaveBeenCalledTimes(2);
  });

  it("rad etish sababsiz yuborilmaydi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("choyxona");

    fireEvent.click(screen.getByRole("button", { name: "Rad etish" }));

    expect(await screen.findByText("Sabab kiritilishi shart.")).toBeVisible();
    expect(api.decide).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Sabab (mijozga ko‘rinadi)"), {
      target: { value: "Chek o‘qilmadi" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Rad etish" }));

    await waitFor(() => {
      expect(api.decide).toHaveBeenCalledWith(1, "reject", {
        reason: "Chek o‘qilmadi",
        internal_note: "",
      });
    });
  });

  it("bekor qilish ham sabab talab qiladi", async () => {
    const api = makeApi();
    render(<AdminPayments api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));
    await screen.findByText("choyxona");

    fireEvent.click(screen.getByRole("button", { name: "Bekor qilish" }));
    expect(await screen.findByText("Sabab kiritilishi shart.")).toBeVisible();
    expect(api.decide).not.toHaveBeenCalled();
  });

  it("qaror qabul qilingan to'lovda tugmalar ko'rsatilmaydi", async () => {
    const api = makeApi({
      payments: vi.fn().mockResolvedValue([row({ status: "approved" })]),
      payment: vi.fn().mockResolvedValue(detail({ status: "approved" })),
    });
    render(<AdminPayments api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ko‘rish" }));

    expect(
      await screen.findByText("Qaror qabul qilingan: Tasdiqlangan"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Tasdiqlash" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Rad etish" })).toBeNull();
  });

  it("bo'sh navbat uchun xabar", async () => {
    const api = makeApi({ payments: vi.fn().mockResolvedValue([]) });
    render(<AdminPayments api={api} />);

    expect(await screen.findByText("To‘lov yo‘q.")).toBeVisible();
  });

  it("server xatosi ko'rsatiladi", async () => {
    const api = makeApi({
      payments: vi.fn().mockRejectedValue(
        new Error("Admin sessiyasi topilmadi yoki tugagan."),
      ),
    });
    render(<AdminPayments api={api} />);

    expect(
      await screen.findByText("Admin sessiyasi topilmadi yoki tugagan."),
    ).toBeVisible();
  });
});
