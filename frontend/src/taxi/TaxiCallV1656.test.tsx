import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TaxiCallV1656 } from "./TaxiCallV1656";


const pricing = {
  pricing: {
    taxi: { base: 5000, per_km: 2000, min: 9000 },
    dostavka: { base: 10000, per_km: 2500, min: 15000 },
  },
  commission: 1000,
};


describe("TaxiCallV1656", () => {
  it("opens for a guest but asks for login only when ordering", async () => {
    const onNeedLogin = vi.fn();
    const createTaxiRide = vi.fn();
    render(
      <TaxiCallV1656
        api={{ createTaxiRide, getTaxiPricing: vi.fn().mockResolvedValue(pricing) }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        onBack={vi.fn()}
        onNeedLogin={onNeedLogin}
      />,
    );

    expect(screen.getByRole("button", { name: "Zakaz qilish" }))
      .toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Zakaz qilish" }));

    expect(onNeedLogin).toHaveBeenCalledWith("Zakaz qilish");
    expect(createTaxiRide).not.toHaveBeenCalled();
  });

  it("keeps the exact Taxi and Dostavka fields", async () => {
    render(
      <TaxiCallV1656
        api={{ createTaxiRide: vi.fn(), getTaxiPricing: vi.fn().mockResolvedValue(pricing) }}
        authenticated={false}
        center={{ latitude: 41.3111, longitude: 69.2797 }}
        onBack={vi.fn()}
        onNeedLogin={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "📦 Dostavka" }));
    expect(screen.getByLabelText("Mashina turi")).toBeInTheDocument();
    expect(screen.getByLabelText("Yuk turi")).toHaveAttribute(
      "placeholder", "Masalan: mebel, quti, texnika",
    );
    expect(screen.getByRole("button", { name: "🗣 O'zim aytaman" }))
      .toBeInTheDocument();
  });
});
