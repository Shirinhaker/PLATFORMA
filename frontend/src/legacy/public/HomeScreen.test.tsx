import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { HomeScreen } from "./HomeScreen";

function renderHome(currentDistrict?: string) {
  const actions = {
    onSearch: vi.fn(),
    onOpenCatalog: vi.fn(),
    onOpenLocation: vi.fn(),
  };

  render(<HomeScreen currentDistrict={currentDistrict} {...actions} />);

  return actions;
}

describe("HomeScreen", () => {
  it("shows the approved v1656 discovery copy", () => {
    renderHome();

    expect(
      screen.getByRole("heading", {
        name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Hudud tanlanmagan")).toBeInTheDocument();
  });

  it("searches a trimmed query from the Qidirish button", async () => {
    const { onSearch } = renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "  telefon ta’miri  ",
    );
    await userEvent.click(screen.getByRole("button", { name: "Qidirish" }));

    expect(onSearch).toHaveBeenCalledWith("telefon ta’miri");
  });

  it("searches from Enter", async () => {
    const { onSearch } = renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "usta{enter}",
    );

    expect(onSearch).toHaveBeenCalledWith("usta");
  });

  it("does not navigate for a blank search", async () => {
    const { onSearch } = renderHome();

    await userEvent.type(
      screen.getByPlaceholderText("Nima qidiryapsiz?"),
      "   {enter}",
    );
    await userEvent.click(screen.getByRole("button", { name: "Qidirish" }));

    expect(onSearch).not.toHaveBeenCalled();
  });

  it("opens the full catalog", async () => {
    const { onOpenCatalog } = renderHome();

    await userEvent.click(
      screen.getByRole("button", { name: "Katalog bo‘yicha" }),
    );

    expect(onOpenCatalog).toHaveBeenCalledOnce();
  });

  it("shows the selected district and opens location selection", async () => {
    const { onOpenLocation } = renderHome("Qumqo‘rg‘on tumani");

    expect(screen.getByText("Qumqo‘rg‘on tumani")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Manzilni tanlash" }),
    );

    expect(onOpenLocation).toHaveBeenCalledOnce();
  });

  it("does not expose fake public actions", () => {
    renderHome();

    expect(screen.queryByRole("button", { name: /xaritada ko‘rish/i }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reklama/i }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /takliflar/i }))
      .not.toBeInTheDocument();
  });
});
