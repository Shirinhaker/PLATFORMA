import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PaymentCatalog } from "../api/types";
import {
  PaymentRequestModal,
  type PaymentRequestApi,
} from "./PaymentRequestModal";
import { SubscriptionsView } from "./BusinessOnlineViews";


const CATALOG: PaymentCatalog = {
  prices: [{
    price_code: "subscription_plus_1m",
    service_type: "subscription",
    amount_uzs: 99000,
    plan_code: "plus",
    duration_months: 1,
  }],
  methods: [{
    id: 1,
    method_type: "manual_card",
    name: "Bank kartasi",
    recipient_name: "",
    instructions: "",
    details: {},
  }],
};

const TARGET = {
  priceCode: "subscription_plus_1m",
  label: "Plus obuna · 1 oy",
  planCode: "plus",
  durationMonths: 1,
};


function makeApi(overrides: Partial<PaymentRequestApi> = {}) {
  return {
    getPaymentCatalog: vi.fn().mockResolvedValue(CATALOG),
    createPaymentRequest: vi.fn().mockResolvedValue({}),
    createUploadGrant: vi.fn().mockResolvedValue({
      object_key: "private/business/7/receipt/a.png",
      upload_url: "https://r2.example/upload",
      method: "PUT" as const,
      headers: {},
      expires_in_seconds: 900,
    }),
    uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as PaymentRequestApi;
}


describe("obuna tarifini sotib olish", () => {
  it("tarif tugmasi to'lov oynasini ochadi, request_plan emas", () => {
    const openPayment = vi.fn();
    render(
      <SubscriptionsView
        rows={[]}
        duration={1}
        setDuration={vi.fn()}
        busy={false}
        openPayment={openPayment}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Plus uchun to‘lov qilish" }),
    );

    expect(openPayment).toHaveBeenCalledWith("plus");
  });

  it("oynada narx va to'lov usuli ko'rinadi", () => {
    render(
      <PaymentRequestModal
        api={makeApi()}
        catalog={CATALOG}
        target={TARGET}
        onClose={vi.fn()}
        onSubmitted={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByText("99 000 so‘m")).toBeVisible();
    expect(screen.getByText("Plus obuna · 1 oy")).toBeVisible();
    expect(screen.getByLabelText("To‘lov usuli")).toHaveValue("1");
    expect(screen.getByText("Bank kartasi")).toBeInTheDocument();
  });

  it("kvitansiyasiz yuborilmaydi", () => {
    const api = makeApi();
    render(
      <PaymentRequestModal
        api={api}
        catalog={CATALOG}
        target={TARGET}
        onClose={vi.fn()}
        onSubmitted={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "To‘lov so‘rovini yuborish" }),
    );

    expect(screen.getByText("To‘lov kvitansiyasini tanlang.")).toBeVisible();
    expect(api.createPaymentRequest).not.toHaveBeenCalled();
  });

  it("kvitansiya R2'ga yuklanib, so'rov yuboriladi", async () => {
    const api = makeApi();
    const onSubmitted = vi.fn();
    const onClose = vi.fn();
    render(
      <PaymentRequestModal
        api={api}
        catalog={CATALOG}
        target={TARGET}
        onClose={onClose}
        onSubmitted={onSubmitted}
      />,
    );

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
    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it("yuklashda xato bo'lsa xabar ko'rsatiladi", async () => {
    const api = makeApi({
      createUploadGrant: vi.fn().mockRejectedValue(new Error("Yuklanmadi.")),
    });
    render(
      <PaymentRequestModal
        api={api}
        catalog={CATALOG}
        target={TARGET}
        onClose={vi.fn()}
        onSubmitted={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("To‘lov kvitansiyasi"), {
      target: { files: [new File(["c"], "c.png", { type: "image/png" })] },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "To‘lov so‘rovini yuborish" }),
    );

    expect(await screen.findByText("Yuklanmadi.")).toBeVisible();
    expect(api.createPaymentRequest).not.toHaveBeenCalled();
  });
});
