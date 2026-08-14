import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ListingRead, PaymentCatalog } from "../api/types";
import { OwnerListingsV1656 } from "./OwnerListingsV1656";


// Xarita tanlovi formaning majburiy qadami — u Leafletsiz ishlamaydi.
const leaflet = vi.hoisted(() => {
  const state = { center: { lat: 41.311, lng: 69.28 }, zoom: 14 };
  const map = {
    getCenter: vi.fn(() => ({ ...state.center })),
    getZoom: vi.fn(() => state.zoom),
    invalidateSize: vi.fn(),
    remove: vi.fn(),
    setView: vi.fn(() => map),
  };
  const tileLayer = { addTo: vi.fn() };
  return {
    mapFactory: vi.fn(() => map),
    state,
    tileLayerFactory: vi.fn(() => tileLayer),
  };
});

vi.mock("leaflet", () => ({
  default: {
    map: leaflet.mapFactory,
    tileLayer: leaflet.tileLayerFactory,
  },
}));


const CATALOG: PaymentCatalog = {
  prices: [{
    price_code: "listing_publish",
    service_type: "listing",
    amount_uzs: 10000,
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

const PENDING: ListingRead = {
  public_id: "l_00000000000000ab",
  cat: "moshina",
  title: "Nexia sotiladi",
  price: "Kelishilgan",
  descr: "Yili 2024",
  address: "Toshkent",
  lat: 41.3,
  lng: 69.2,
  visibility: "all",
  status: "payment_pending",
  created_at: "2026-08-07T12:00:00Z",
  media: [],
  owner_kind: "user",
  owner_public_id: "u_1",
  owner_name: "Foydalanuvchi",
  is_saved: false,
};


function makeApi(overrides: Record<string, unknown> = {}) {
  return {
    getMyListings: vi.fn().mockResolvedValue([PENDING]),
    createListing: vi.fn(),
    deleteListing: vi.fn(),
    createUploadGrant: vi.fn(),
    uploadGrantedFile: vi.fn(),
    getPaymentCatalog: vi.fn().mockResolvedValue(CATALOG),
    createPaymentRequest: vi.fn(),
    ...overrides,
  };
}


describe("e'lon to'lovsiz ko'rinmaydi", () => {
  it("kutilayotgan e'lon holati ko'rsatiladi", async () => {
    render(
      <OwnerListingsV1656 api={makeApi()} actor="user" onBack={vi.fn()} />,
    );

    expect(await screen.findByText(/To‘lov kutilmoqda/)).toBeInTheDocument();
  });

  it("«To‘lov qilish» oynani ochadi va tarifni ko'rsatadi", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    await waitFor(() => expect(api.getPaymentCatalog).toHaveBeenCalled());
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(screen.getByText("E'lon joylash · Nexia sotiladi")).toBeVisible();
    expect(screen.getByText("10 000 so‘m")).toBeVisible();
  });

  it("joylangan e'lon uchun to'lov oynasi darhol ochiladi", async () => {
    const user = userEvent.setup();
    const api = makeApi({
      getMyListings: vi.fn().mockResolvedValue([]),
      createListing: vi.fn().mockResolvedValue(PENDING),
    });
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: "+ E'lon joylash" }),
    );
    await user.type(
      screen.getByPlaceholderText("Masalan: Nexia 3 sotiladi"),
      "Nexia sotiladi",
    );
    await user.click(
      screen.getByRole("button", { name: "📍 Xaritada joy belgilash" }),
    );
    await waitFor(() => expect(leaflet.mapFactory).toHaveBeenCalled());
    await user.click(
      screen.getByRole("button", { name: "✅ Shu joyni tanlash" }),
    );
    await user.click(screen.getByRole("button", { name: "Joylash" }));

    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(screen.getByText("E'lon saqlandi. To'lovdan so'ng ko'rinadi."))
      .toBeVisible();
  });

  it("so'rovda e'lon kaliti yuboriladi", async () => {
    const user = userEvent.setup();
    const api = makeApi({
      createUploadGrant: vi.fn().mockResolvedValue({
        object_key: "private/user/7/payment/chek.png",
        upload_url: "https://r2.example/upload",
        method: "PUT" as const,
        headers: { "Content-Type": "image/png" },
        expires_in_seconds: 900,
      }),
      uploadGrantedFile: vi.fn().mockResolvedValue(undefined),
      createPaymentRequest: vi.fn().mockResolvedValue({}),
    });
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );
    await user.upload(
      await screen.findByLabelText("To‘lov kvitansiyasi"),
      new File(["chek"], "chek.png", { type: "image/png" }),
    );
    await user.click(
      screen.getByRole("button", { name: "To‘lov so‘rovini yuborish" }),
    );

    await waitFor(() => expect(api.createPaymentRequest).toHaveBeenCalled());
    expect(api.createPaymentRequest).toHaveBeenCalledWith(expect.objectContaining({
      service_type: "listing",
      price_code: "listing_publish",
      target_public_id: PENDING.public_id,
    }));
    expect(
      await screen.findByText(
        "To'lov so'rovi yuborildi. Admin tasdiqlagach e'lon ko'rinadi.",
      ),
    ).toBeVisible();
  });

  it("katalog yuklanmasa sabab ko'rsatiladi, jim turmaydi", async () => {
    const user = userEvent.setup();
    const api = makeApi({
      getPaymentCatalog: vi.fn().mockRejectedValue(
        new Error("Tariflar yuklanmadi."),
      ),
    });
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: "To‘lov qilish" }),
    );

    expect(await screen.findByRole("alert"))
      .toHaveTextContent("Tariflar yuklanmadi.");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("to'lov API'si yo'q kabinetda tugma ko'rsatilmaydi", async () => {
    const api = makeApi();
    delete (api as Record<string, unknown>).getPaymentCatalog;
    delete (api as Record<string, unknown>).createPaymentRequest;
    render(<OwnerListingsV1656 api={api} actor="user" onBack={vi.fn()} />);

    expect(await screen.findByText(/To‘lov kutilmoqda/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "To‘lov qilish" })).toBeNull();
  });
});
