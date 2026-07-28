import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HOME_LOCATION_STORAGE_KEY } from "./location-storage";
import { LocationScreen } from "./LocationScreen";

describe("LocationScreen", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows the approved v1656 heading and privacy promise", () => {
    render(<LocationScreen onSaved={vi.fn()} />);

    expect(
      screen.getByRole("heading", { name: "Hududingizni tanlang" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Tanlangan tumandagi obunali profillar, mahsulotlar va xizmatlar ko‘rsatiladi.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Bu ma’lumot boshqa foydalanuvchilarga ko‘rsatilmaydi/),
    ).toBeInTheDocument();
  });

  it("requires a district before saving", async () => {
    render(<LocationScreen onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(
      screen.getByRole("alert"),
    ).toHaveTextContent("Iltimos, tumaningizni tanlang.");
  });

  it("resets an invalid district when the region changes", async () => {
    render(
      <LocationScreen
        initialLocation={{
          region: "Surxondaryo viloyati",
          district: "Qumqo'rg'on",
          neighborhood: "",
        }}
        onSaved={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Tuman")).toHaveValue("Qumqo'rg'on");
    await userEvent.selectOptions(
      screen.getByLabelText("Viloyat / shahar"),
      "Samarqand viloyati",
    );

    expect(screen.getByLabelText("Tuman")).toHaveValue("");
  });

  it("saves an optional neighborhood and reports the selected location", async () => {
    const onSaved = vi.fn();
    render(<LocationScreen onSaved={onSaved} />);

    await userEvent.selectOptions(
      screen.getByLabelText("Viloyat / shahar"),
      "Surxondaryo viloyati",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Tuman"),
      "Qumqo'rg'on",
    );
    await userEvent.type(
      screen.getByLabelText("Mahalla — ixtiyoriy"),
      "Yangi hayot",
    );
    await userEvent.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(onSaved).toHaveBeenCalledWith({
      region: "Surxondaryo viloyati",
      district: "Qumqo'rg'on",
      neighborhood: "Yangi hayot",
    });
    expect(
      JSON.parse(
        window.localStorage.getItem(HOME_LOCATION_STORAGE_KEY) ?? "null",
      ),
    ).toEqual({
      region: "Surxondaryo viloyati",
      district: "Qumqo'rg'on",
      mahalla: "Yangi hayot",
      lat: null,
      lng: null,
      exact: false,
    });
  });

  it("does not show fake automatic detection without a real map integration", () => {
    render(<LocationScreen onSaved={vi.fn()} />);

    expect(
      screen.queryByRole("button", { name: /Avtomatik aniqlash/i }),
    ).not.toBeInTheDocument();
  });
});
