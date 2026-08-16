import { readFileSync } from "node:fs";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DriverCabinetV1656 } from "./DriverCabinetV1656";

const emptyDriver = {
  exists: false,
  id: null,
  name: "Ali",
  phone: "",
  car_model: "",
  car_color: "",
  car_plate: "",
  service: "taxi" as const,
  available: true,
  busy: false,
  rating_sum: 0,
  rating_count: 0,
  balance: 0,
  commission: 1000,
  status: "active",
};
const pricing = {
  pricing: {
    taxi: { base: 5000, per_km: 2000, min: 9000 },
    dostavka: { base: 10000, per_km: 2500, min: 15000 },
  },
  commission: 1000,
};

describe("DriverCabinetV1656", () => {
  it("keeps the form controls self-contained inside the v1656 driver screen", () => {
    const css = readFileSync("src/taxi/taxi-v1656.css", "utf8");

    expect(css).toContain(".taxi-driver-v1656 .field");
    expect(css).toContain(".taxi-driver-v1656 .input");
    expect(css).toContain(".taxi-driver-v1656 .sort-chip");
    expect(css).toContain(".taxi-driver-v1656 .panel-card");
    expect(css).toContain(".taxi-driver-v1656 .btn-primary");
    expect(css).toContain(".taxi-driver-v1656 .vis-card");
  });

  it("uses the app shell heading without adding a duplicate cabinet header", async () => {
    render(
      <DriverCabinetV1656
        api={{
          getTaxiDriver: vi.fn().mockResolvedValue(emptyDriver),
          getTaxiPricing: vi.fn().mockResolvedValue(pricing),
        }}
      />,
    );

    await screen.findByText("Akkaunt ismingiz — shu ishlatiladi");
    expect(
      screen.queryByRole("heading", { name: "Haydovchi kabineti" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Kabinetga qaytish" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Telefon")).toHaveClass("input");
    expect(screen.getByRole("button", { name: "🚖 Taxi" })).toHaveClass("on");
  });

  it("keeps taxi car fields required and saves the typed driver profile", async () => {
    const saveTaxiDriver = vi.fn().mockResolvedValue({ ...emptyDriver, exists: true });
    render(
      <DriverCabinetV1656
        api={{
          getTaxiDriver: vi.fn().mockResolvedValue(emptyDriver),
          getTaxiPricing: vi.fn().mockResolvedValue(pricing),
          saveTaxiDriver,
        }}
        onBack={vi.fn()}
      />,
    );
    await screen.findByText("Akkaunt ismingiz — shu ishlatiladi");
    await userEvent.type(screen.getByLabelText("Telefon"), "+998901234567");
    await userEvent.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Taxi uchun mashina rusumi, raqami va rangini to'ldiring.",
    );

    await userEvent.type(screen.getByLabelText(/Mashina rusumi/), "Cobalt");
    await userEvent.type(screen.getByLabelText(/Davlat raqami/), "01 A 123 BC");
    await userEvent.type(screen.getByLabelText(/Rangi/), "oq");
    await userEvent.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));

    await waitFor(() =>
      expect(saveTaxiDriver).toHaveBeenCalledWith({
        phone: "+998901234567",
        service: "taxi",
        car_model: "Cobalt",
        car_plate: "01 A 123 BC",
        car_color: "oq",
      }),
    );
  });
});
