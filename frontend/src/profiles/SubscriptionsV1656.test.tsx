import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PaymentCatalog, PaymentRequestRecord } from "../api/types";
import { SubscriptionsV1656, type SubscriptionsApi } from "./SubscriptionsV1656";


const CATALOG: PaymentCatalog = {
  prices: [
    {
      price_code: "subscription_plus_1m",
      service_type: "subscription",
      amount_uzs: 99000,
      plan_code: "plus",
      duration_months: 1,
    },
    {
      price_code: "subscription_pro_3m",
      service_type: "subscription",
      amount_uzs: 419000,
      plan_code: "pro",
      duration_months: 3,
    },
  ],
  methods: [{
    id: 1,
    method_type: "manual_card",
    name: "Bank kartasi",
    recipient_name: "",
    instructions: "",
    details: {},
  }],
};

const PAYMENT: PaymentRequestRecord = {
  id: 5,
  request_code: "PAY-ABCDEF123456",
  service_type: "subscription",
  status: "pending",
  plan_code: "plus",
  duration_months: 1,
  quantity: 1,
  amount: 99000,
  currency: "UZS",
  price_code: "subscription_plus_1m",
  public_reason: "",
  created_at: 1785200000,
  updated_at: 1785200000,
  attempts: [],
};


function makeApi(overrides: Partial<SubscriptionsApi> = {}) {
  return {
    getPaymentCatalog: vi.fn().mockResolvedValue(CATALOG),
    getMyPayments: vi.fn().mockResolvedValue([PAYMENT]),
    createPaymentRequest: vi.fn().mockResolvedValue(PAYMENT),
    createUploadGrant: vi.fn().mockResolvedValue({
      object_key: "private/business/7/receipt/a.png",
      upload_url: "https://r2.example/upload",
      method: "PUT" as const,
      headers: {},
      expires_in_seconds: 900,
    }),
    uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as SubscriptionsApi;
}


describe("v1656 obuna ekrani", () => {
  it("tariflarni va joriy to'lovlarni ko'rsatadi", async () => {
    render(<SubscriptionsV1656 api={makeApi()} onBack={() => {}} />);

    expect(await screen.findByText("Bepul")).toBeVisible();
    expect(screen.getByText("Plus")).toBeVisible();
    expect(screen.getByText("Pro")).toBeVisible();
    expect(screen.getByText("99 000 so‘m")).toBeVisible();
    expect(screen.getByText("PAY-ABCDEF123456")).toBeVisible();
    expect(screen.getByText("Tekshiruvda")).toBeVisible();
  });

  it("muddat tanlanganda narx o'zgaradi", async () => {
    render(<SubscriptionsV1656 api={makeApi()} onBack={() => {}} />);
    await screen.findByText("Plus");

    fireEvent.click(screen.getByRole("button", { name: "3 oy" }));

    expect(await screen.findByText("419 000 so‘m")).toBeVisible();
  });

  it("bepul tarif tugmasi to'lov oynasini ochmaydi", async () => {
    render(<SubscriptionsV1656 api={makeApi()} onBack={() => {}} />);
    await screen.findByText("Bepul");

    fireEvent.click(screen.getByRole("button", { name: "Joriy bepul tarif" }));

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Plus tugmasi to'lov oynasini ochadi", async () => {
    render(<SubscriptionsV1656 api={makeApi()} onBack={() => {}} />);
    await screen.findByText("Plus");

    fireEvent.click(
      screen.getByRole("button", { name: "Plus uchun to‘lov qilish" }),
    );

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeVisible();
    expect(screen.getByText("To‘lov so‘rovini yuborish", {
      selector: "h2",
    })).toBeVisible();
    expect(screen.getByText("Plus obuna · 1 oy")).toBeVisible();
  });

  it("kvitansiyasiz yuborilmaydi", async () => {
    const api = makeApi();
    render(<SubscriptionsV1656 api={api} onBack={() => {}} />);
    await screen.findByText("Plus");
    fireEvent.click(
      screen.getByRole("button", { name: "Plus uchun to‘lov qilish" }),
    );
    await screen.findByRole("dialog");

    fireEvent.click(
      screen.getByRole("button", { name: "To‘lov so‘rovini yuborish" }),
    );

    expect(await screen.findByText("To‘lov kvitansiyasini tanlang."))
      .toBeVisible();
    expect(api.createPaymentRequest).not.toHaveBeenCalled();
  });

  it("kvitansiya yuklab, so'rovni yuboradi", async () => {
    const api = makeApi();
    render(<SubscriptionsV1656 api={api} onBack={() => {}} />);
    await screen.findByText("Plus");
    fireEvent.click(
      screen.getByRole("button", { name: "Plus uchun to‘lov qilish" }),
    );
    await screen.findByRole("dialog");

    const file = new File(["chek"], "chek.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("To‘lov kvitansiyasi"), {
      target: { files: [file] },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "To‘lov so‘rovini yuborish" }),
    );

    await waitFor(() => {
      expect(api.createUploadGrant).toHaveBeenCalledWith({
        purpose: "payment_receipt",
        filename: "chek.png",
        content_type: "image/png",
        size_bytes: file.size,
      });
    });
    await waitFor(() => {
      expect(api.createPaymentRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          service_type: "subscription",
          price_code: "subscription_plus_1m",
          plan_code: "plus",
          duration_months: 1,
          payment_method_id: 1,
        }),
      );
    });
  });

  it("yuklab bo'lmasa xabar ko'rsatadi", async () => {
    const api = makeApi({
      createUploadGrant: vi.fn().mockRejectedValue(
        new Error("Rasm yuklanmadi."),
      ),
    });
    render(<SubscriptionsV1656 api={api} onBack={() => {}} />);
    await screen.findByText("Plus");
    fireEvent.click(
      screen.getByRole("button", { name: "Plus uchun to‘lov qilish" }),
    );
    await screen.findByRole("dialog");
    fireEvent.change(screen.getByLabelText("To‘lov kvitansiyasi"), {
      target: { files: [new File(["c"], "c.png", { type: "image/png" })] },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "To‘lov so‘rovini yuborish" }),
    );

    expect(await screen.findByText("Rasm yuklanmadi.")).toBeVisible();
  });

  it("katalog yuklanmasa qayta urinish tugmasi chiqadi", async () => {
    const api = makeApi({
      getPaymentCatalog: vi.fn().mockRejectedValue(new Error("Tarmoq xatosi.")),
    });
    render(<SubscriptionsV1656 api={api} onBack={() => {}} />);

    expect(await screen.findByText("Tariflarni yuklab bo‘lmadi")).toBeVisible();
    expect(screen.getByRole("button", { name: "Qayta urinish" })).toBeVisible();
  });
});
