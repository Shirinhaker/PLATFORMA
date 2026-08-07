import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PaymentCatalog } from "../api/types";
import { BusinessOnlineScreen } from "./BusinessOnlineScreen";


const CATALOG: PaymentCatalog = {
  prices: [{
    price_code: "advertisement_district_hour",
    service_type: "advertisement",
    amount_uzs: 20000,
    plan_code: "",
    duration_months: 0,
  }],
  methods: [{
    id: 1,
    method_type: "manual_card",
    name: "Bank kartasi",
    recipient_name: "Bunyod",
    instructions: "",
    details: { card_number: "8600 1111 2222 3333" },
  }],
};

const ADVERTISEMENT = {
  id: 12,
  title: "Choyxona ochildi",
  caption: "",
  targets: [{
    level: "district" as const,
    region: "Toshkent shahri",
    district: "Chilonzor",
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
};

const PROFILE = {
  name: "Choyxona",
  direction: "Umumiy ovqatlanish",
  cabinet_payload: {},
} as never;


type FakeApi = Record<string, ReturnType<typeof vi.fn>>;

function makeApi(overrides: Record<string, unknown> = {}): FakeApi {
  return {
    getPaymentCatalog: vi.fn().mockResolvedValue(CATALOG),
    createPaymentRequest: vi.fn(),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    getMyAdvertisements: vi.fn().mockResolvedValue([ADVERTISEMENT]),
    createAdvertisement: vi.fn(),
    deleteAdvertisement: vi.fn(),
    quoteAdvertisement: vi.fn(),
    ...overrides,
  } as FakeApi;
}

function renderScreen(api: FakeApi) {
  return render(
    <BusinessOnlineScreen
      api={api as never}
      profile={PROFILE}
      view="advertisements"
      title="Reklamalarim"
      onBack={vi.fn()}
      onOpenOrder={vi.fn()}
    />,
  );
}


describe("to'lov katalogi obuna ekranidan tashqarida ham yuklanadi", () => {
  it("reklamada to'lov bosilganda oyna ochiladi", async () => {
    const api = makeApi();
    renderScreen(api);

    fireEvent.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    // Katalog aynan shu payt yuklanadi — ilgari u faqat obuna
    // ekranida yuklangani uchun oyna jimgina ochilmasdi.
    await waitFor(() => expect(api.getPaymentCatalog).toHaveBeenCalled());
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(screen.getByText("Reklama · 1 tuman · 7 kun")).toBeVisible();
  });

  it("summa tarif × tuman-soat bo'lib ko'rsatiladi", async () => {
    renderScreen(makeApi());
    fireEvent.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    // 20 000 × 168 = 3 360 000
    expect(await screen.findByText("3 360 000 so‘m")).toBeVisible();
  });

  it("rekvizitlar oynada ko'rinadi", async () => {
    renderScreen(makeApi());
    fireEvent.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    const details = await screen.findByText(/Qabul qiluvchi: Bunyod/);
    expect(details).toHaveTextContent("8600 1111 2222 3333");
  });

  it("katalog yuklanmasa sabab ko'rsatiladi, jim turmaydi", async () => {
    const api = makeApi({
      getPaymentCatalog: vi.fn().mockRejectedValue(
        new Error("Tariflar yuklanmadi."),
      ),
    });
    renderScreen(api);

    fireEvent.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    expect(await screen.findByText("Tariflar yuklanmadi.")).toBeVisible();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
