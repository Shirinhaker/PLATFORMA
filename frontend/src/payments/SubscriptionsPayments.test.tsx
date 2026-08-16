import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  BusinessSubscriptionSummary,
  PaymentCatalog,
  PaymentRequestRecord,
} from "../api/types";
import {
  BusinessSubscriptions,
  Payments,
} from "./SubscriptionsPayments";

const CATALOG: PaymentCatalog = {
  prices: [
    {
      price_code: "subscription_plus_1m",
      service_type: "subscription",
      amount_uzs: 99_000,
      plan_code: "plus",
      duration_months: 1,
    },
  ],
  methods: [
    {
      id: 1,
      method_type: "manual_card",
      name: "Bank kartasi",
      recipient_name: "Ko'prik",
      instructions: "Chekni yuboring",
      details: {},
    },
  ],
};

const SUMMARY: BusinessSubscriptionSummary = {
  current: {
    id: 8,
    plan_code: "plus",
    duration_months: 1,
    starts_at: 1_785_000_000,
    expires_at: 1_787_000_000,
    status: "active",
    is_demo: false,
    is_virtual: false,
    created_at: 1_785_000_000,
  },
  history: [],
};

const REJECTED: PaymentRequestRecord = {
  id: 41,
  request_code: "PAY-ABC",
  service_type: "subscription",
  status: "rejected",
  plan_code: "plus",
  duration_months: 1,
  quantity: 1,
  amount: 99_000,
  currency: "UZS",
  price_code: "subscription_plus_1m",
  public_reason: "Chek xira",
  created_at: 1_785_000_000,
  updated_at: 1_785_000_000,
  attempts: [],
};

describe("K23 typed obuna va to'lov ekranlari", () => {
  it("obuna holati va katalogini typed endpointlardan oladi", async () => {
    const api = {
      getBusinessSubscription: vi.fn().mockResolvedValue(SUMMARY),
      getPaymentCatalog: vi.fn().mockResolvedValue(CATALOG),
      createPaymentRequest: vi.fn(),
      createUploadGrant: vi.fn(),
      uploadGrantedFile: vi.fn(),
    };

    render(
      <BusinessSubscriptions
        api={api as never}
        onBack={vi.fn()}
        onOpenPayments={vi.fn()}
      />,
    );

    expect((await screen.findAllByText("Plus"))[0]).toBeVisible();
    expect(api.getBusinessSubscription).toHaveBeenCalledTimes(1);
    expect(api.getPaymentCatalog).toHaveBeenCalledTimes(1);
  });

  it("rad etilgan to'lov chekini R2 orqali typed resubmit qiladi", async () => {
    const api = {
      getMyPayments: vi.fn().mockResolvedValue([REJECTED]),
      resubmitPayment: vi.fn().mockResolvedValue({
        ...REJECTED,
        status: "pending",
        public_reason: "",
      }),
      createUploadGrant: vi.fn().mockResolvedValue({
        object_key: "private/user/5/receipt/new.png",
        upload_url: "https://r2.test/upload",
        method: "PUT",
        headers: {},
        expires_in_seconds: 900,
      }),
      uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    };

    render(<Payments api={api as never} onBack={vi.fn()} />);

    expect(await screen.findByText("Chek xira")).toBeVisible();
    const file = new File(["new receipt"], "new.png", { type: "image/png" });
    fireEvent.change(document.querySelector('input[type="file"]')!, {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Qayta yuborish" }));

    await waitFor(() =>
      expect(api.createUploadGrant).toHaveBeenCalledWith({
        purpose: "payment_receipt",
        filename: "new.png",
        content_type: "image/png",
        size_bytes: file.size,
      }),
    );
    await waitFor(() =>
      expect(api.resubmitPayment).toHaveBeenCalledWith(
        41,
        expect.objectContaining({
          object_key: "private/user/5/receipt/new.png",
          filename: "new.png",
          mime: "image/png",
        }),
      ),
    );
  });
});
