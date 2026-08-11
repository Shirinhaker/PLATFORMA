import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AdminTaxiDrivers } from "./AdminTaxiDrivers";


it("tops up a driver with an audit reason and reloads the balance", async () => {
  const taxiDrivers = vi.fn().mockResolvedValue([{
    id: 7, name: "Ali", phone: "+99890", balance: 1000,
    service: "taxi", available: true,
  }]);
  const topupTaxiDriver = vi.fn().mockResolvedValue({ id: 7, balance: 6000 });
  render(<AdminTaxiDrivers api={{ taxiDrivers, topupTaxiDriver }} />);
  await screen.findByText("Ali");
  await userEvent.type(screen.getByLabelText("Summa (so‘m)"), "5000");
  await userEvent.type(screen.getByLabelText(/Sabab/), "Bank o'tkazmasi");
  await userEvent.click(screen.getByRole("button", { name: "Balansni qo‘shish" }));
  await waitFor(() => expect(topupTaxiDriver).toHaveBeenCalledWith(
    7, 5000, "Bank o'tkazmasi",
  ));
  expect(taxiDrivers).toHaveBeenCalledTimes(2);
});
