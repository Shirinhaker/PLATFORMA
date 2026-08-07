import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AdminMethodRow, AdminPriceRow } from "./admin-client";
import { AdminPricing, priceLabel, type AdminPricingApi } from "./AdminPricing";


function price(overrides: Partial<AdminPriceRow> = {}): AdminPriceRow {
  return {
    id: 1,
    price_code: "subscription_plus_1m",
    service_type: "subscription",
    amount_uzs: 99000,
    config: { plan_code: "plus", duration_months: 1 },
    active: true,
    updated_at: 1_785_000_000,
    ...overrides,
  };
}

function method(overrides: Partial<AdminMethodRow> = {}): AdminMethodRow {
  return {
    id: 5,
    method_type: "manual_card",
    name: "bunyod",
    recipient_name: "Bunyod Rahimov",
    instructions: "Chekni yuboring.",
    details: { card_number: "5614681918687751" },
    sort_order: 0,
    active: true,
    ...overrides,
  };
}

function makeApi(overrides: Partial<AdminPricingApi> = {}) {
  return {
    prices: vi.fn().mockResolvedValue([price()]),
    methods: vi.fn().mockResolvedValue([method()]),
    updatePrice: vi.fn().mockImplementation(
      async (id: number, body: { amount_uzs: number; active: boolean }) =>
        price({ id, ...body }),
    ),
    createMethod: vi.fn().mockResolvedValue(method({ id: 6 })),
    updateMethod: vi.fn().mockImplementation(
      async (id: number, body: Record<string, unknown>) =>
        ({ ...method(), id, ...body }),
    ),
    ...overrides,
  } as unknown as AdminPricingApi;
}


describe("narx nomlari o'zbekcha", () => {
  it("obuna tariflari tushunarli nom oladi", () => {
    expect(priceLabel(price())).toBe("Plus obuna · 1 oy");
    expect(priceLabel(price({
      price_code: "subscription_pro_12m",
      config: { plan_code: "pro", duration_months: 12 },
    }))).toBe("Pro obuna · 12 oy");
  });

  it("reklama va e'lon ham tarjima qilinadi", () => {
    expect(priceLabel(price({
      price_code: "advertisement_district_day",
      service_type: "advertisement",
      config: {},
    }))).toBe("Reklama · tumanda · bir kun");
    expect(priceLabel(price({
      price_code: "listing_publish",
      service_type: "listing",
      config: {},
    }))).toBe("E’lon joylash");
  });

  it("notanish kod bo'lsa kodning o'zi qoladi", () => {
    expect(priceLabel(price({
      price_code: "kelajakdagi_tarif",
      service_type: "listing",
      config: {},
    }))).toBe("kelajakdagi_tarif");
  });

  it("ro'yxatda kod emas, nom ko'rsatiladi", async () => {
    render(<AdminPricing api={makeApi()} />);

    expect(await screen.findByText("Plus obuna · 1 oy")).toBeVisible();
    expect(screen.queryByText("subscription_plus_1m")).toBeNull();
  });
});


/** Narx qatorlarida ham "Saqlash" bor — formani ajratib olamiz. */
function methodForm() {
  return within(screen.getByRole("group", { name: "To‘lov usuli formasi" }));
}


describe("to'lov rekvizitlarini tahrirlash", () => {
  it("har bir usulda tahrirlash tugmasi bor", async () => {
    render(<AdminPricing api={makeApi()} />);

    expect(
      await screen.findByRole("button", { name: "Tahrirlash" }),
    ).toBeVisible();
  });

  it("tahrirlash formasi mavjud qiymatlar bilan ochiladi", async () => {
    render(<AdminPricing api={makeApi()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Tahrirlash" }));

    expect(screen.getByLabelText("Usul nomi")).toHaveValue("bunyod");
    expect(screen.getByLabelText("Qabul qiluvchi"))
      .toHaveValue("Bunyod Rahimov");
    expect(screen.getByLabelText("Karta raqami"))
      .toHaveValue("5614681918687751");
    expect(screen.getByLabelText("Ko‘rsatma")).toHaveValue("Chekni yuboring.");
  });

  it("o'zgartirilgan rekvizit saqlanadi", async () => {
    const api = makeApi();
    render(<AdminPricing api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Tahrirlash" }));

    fireEvent.change(screen.getByLabelText("Karta raqami"), {
      target: { value: "8600 1234 5678 9012" },
    });
    fireEvent.change(screen.getByLabelText("Qabul qiluvchi"), {
      target: { value: "Yangi egasi" },
    });
    fireEvent.click(methodForm().getByRole("button", { name: "Saqlash" }));

    await waitFor(() => {
      expect(api.updateMethod).toHaveBeenCalledWith(5, expect.objectContaining({
        name: "bunyod",
        recipient_name: "Yangi egasi",
        details: { card_number: "8600 1234 5678 9012" },
      }));
    });
    expect(
      await screen.findByText("To‘lov usuli saqlandi ✅"),
    ).toBeVisible();
  });

  it("nomsiz usul saqlanmaydi", async () => {
    const api = makeApi();
    render(<AdminPricing api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Yangi usul" }));

    fireEvent.click(methodForm().getByRole("button", { name: "Saqlash" }));

    expect(await screen.findByText("Usul nomini kiriting.")).toBeVisible();
    expect(api.createMethod).not.toHaveBeenCalled();
  });

  it("yangi usul yaratiladi", async () => {
    const api = makeApi();
    render(<AdminPricing api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Yangi usul" }));

    fireEvent.change(screen.getByLabelText("Usul nomi"), {
      target: { value: "Uzcard" },
    });
    fireEvent.change(screen.getByLabelText("Karta raqami"), {
      target: { value: "8600111122223333" },
    });
    fireEvent.click(methodForm().getByRole("button", { name: "Saqlash" }));

    await waitFor(() => {
      expect(api.createMethod).toHaveBeenCalledWith(expect.objectContaining({
        name: "Uzcard",
        details: { card_number: "8600111122223333" },
      }));
    });
    expect(api.updateMethod).not.toHaveBeenCalled();
  });

  it("karta raqami bo'shatilsa rekvizitdan o'chadi", async () => {
    const api = makeApi();
    render(<AdminPricing api={api} />);
    fireEvent.click(await screen.findByRole("button", { name: "Tahrirlash" }));

    fireEvent.change(screen.getByLabelText("Karta raqami"), {
      target: { value: "" },
    });
    fireEvent.click(methodForm().getByRole("button", { name: "Saqlash" }));

    await waitFor(() => {
      expect(api.updateMethod).toHaveBeenCalledWith(5, expect.objectContaining({
        details: {},
      }));
    });
  });
});


describe("tugmalar faqat o'z qatorida kutadi", () => {
  it("bir narx saqlanayotganda boshqasi o'chmaydi", async () => {
    const deferred: { resolve?: (value: AdminPriceRow) => void } = {};
    const api = makeApi({
      prices: vi.fn().mockResolvedValue([
        price({ id: 1 }),
        price({
          id: 2,
          price_code: "subscription_pro_1m",
          config: { plan_code: "pro", duration_months: 1 },
          amount_uzs: 149000,
        }),
      ]),
      updatePrice: vi.fn().mockImplementation(
        () => new Promise<AdminPriceRow>((resolve) => {
          deferred.resolve = resolve;
        }),
      ),
    });
    render(<AdminPricing api={api} />);
    await screen.findByText("Plus obuna · 1 oy");

    const saveButtons = screen.getAllByRole("button", { name: "Saqlash" });
    fireEvent.click(saveButtons[0]!);

    await waitFor(() => expect(saveButtons[0]).toBeDisabled());
    // Ikkinchi qator tegilmaydi.
    expect(saveButtons[1]).not.toBeDisabled();

    deferred.resolve?.(price({ id: 1 }));
    await waitFor(() => expect(saveButtons[0]).not.toBeDisabled());
  });

  it("narx noldan katta bo'lishi kerak", async () => {
    const api = makeApi();
    render(<AdminPricing api={api} />);
    await screen.findByText("Plus obuna · 1 oy");

    fireEvent.change(screen.getByLabelText("Plus obuna · 1 oy narxi"), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(
      await screen.findByText("Narx noldan katta bo‘lishi kerak."),
    ).toBeVisible();
    expect(api.updatePrice).not.toHaveBeenCalled();
  });
});
