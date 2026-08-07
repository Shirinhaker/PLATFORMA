import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Advertisement } from "../api/advertisement-types";
import {
  BusinessAdvertisementsV1656,
  paymentTarget,
  supportsAdvertisementApi,
  type BusinessAdvertisementsApi,
} from "./BusinessAdvertisementsV1656";


function advertisement(overrides: Partial<Advertisement> = {}): Advertisement {
  return {
    id: 12,
    title: "Choyxona ochildi",
    caption: "Yangi taomlar",
    targets: [{
      level: "district", region: "Toshkent shahri", district: "Chilonzor",
    }],
    placement: "home",
    status: "payment_pending",
    daily_all_day: true,
    daily_start: "00:00",
    daily_end: "00:00",
    duration_days: 7,
    district_count: 1,
    hours_per_day: 24,
    district_hour_rate: 20000,
    billable_district_hours: 168,
    price: 3_360_000,
    price_code: "advertisement_district_hour",
    start_at: 1_786_000_000,
    end_at: 1_786_600_000,
    views: 0,
    clicks: 0,
    desktop_image_url: "https://r2.test/ad.png",
    mobile_image_url: "",
    created_at: 1_785_000_000,
    ...overrides,
  };
}

function makeApi(
  rows: Advertisement[],
  overrides: Partial<BusinessAdvertisementsApi> = {},
) {
  return {
    getMyAdvertisements: vi.fn().mockResolvedValue(rows),
    createAdvertisement: vi.fn().mockResolvedValue(advertisement()),
    deleteAdvertisement: vi.fn().mockResolvedValue(undefined),
    quoteAdvertisement: vi.fn().mockResolvedValue({
      district_count: 1,
      hours_per_day: 24,
      duration_days: 7,
      district_hour_rate: 20000,
      billable_district_hours: 168,
      total: 3_360_000,
      currency: "UZS",
    }),
    createUploadGrant: vi.fn().mockResolvedValue({
      object_key: "private/business/7/advertisement_image/a.png",
      upload_url: "https://r2.test/upload",
      method: "PUT" as const,
      headers: {},
      expires_in_seconds: 900,
    }),
    uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as BusinessAdvertisementsApi;
}


describe("reklama joylash yangi endpointlarga ulangan", () => {
  it("API to'liq bo'lsa qo'llab-quvvatlanadi", () => {
    expect(supportsAdvertisementApi(makeApi([]))).toBe(true);
    expect(
      supportsAdvertisementApi({ getMyAdvertisements: vi.fn() }),
    ).toBe(false);
  });

  it("reklamalar /api/v1/advertisements/my dan yuklanadi", async () => {
    const api = makeApi([advertisement()]);
    render(
      <BusinessAdvertisementsV1656 api={api} openPayment={vi.fn()} />,
    );

    await waitFor(() => expect(api.getMyAdvertisements).toHaveBeenCalled());
    expect(await screen.findByText("Choyxona ochildi")).toBeVisible();
  });

  it("to'lov kutayotgan reklamada to'lov tugmasi bor", async () => {
    const openPayment = vi.fn();
    render(
      <BusinessAdvertisementsV1656
        api={makeApi([advertisement()])}
        openPayment={openPayment}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    expect(openPayment).toHaveBeenCalledWith({
      serviceType: "advertisement",
      priceCode: "advertisement_district_hour",
      label: "Reklama · 1 tuman · 7 kun",
      quantity: 168,
      targetId: 12,
    });
  });

  it("faol reklamada to'lov tugmasi ko'rsatilmaydi", async () => {
    render(
      <BusinessAdvertisementsV1656
        api={makeApi([advertisement({ status: "active" })])}
        openPayment={vi.fn()}
      />,
    );

    await screen.findByText("Choyxona ochildi");
    expect(
      screen.queryByRole("button", { name: "To‘lov qilish" }),
    ).toBeNull();
  });

  it("yuklanmasa sabab ko'rsatiladi", async () => {
    const api = makeApi([], {
      getMyAdvertisements: vi.fn().mockRejectedValue(new Error("Ulanmadi.")),
    });
    render(
      <BusinessAdvertisementsV1656 api={api} openPayment={vi.fn()} />,
    );

    expect(await screen.findByText("Ulanmadi.")).toBeVisible();
  });

  it("to'lov maqsadi tuman-soat soniga ko'ra tuziladi", () => {
    const target = paymentTarget(advertisement({
      district_count: 3,
      duration_days: 30,
      billable_district_hours: 2160,
      id: 99,
    }));

    // Summa serverda tarif × miqdor bo'lib hisoblanadi.
    expect(target.quantity).toBe(2160);
    expect(target.targetId).toBe(99);
    expect(target.serviceType).toBe("advertisement");
    expect(target.label).toBe("Reklama · 3 tuman · 30 kun");
  });
});
