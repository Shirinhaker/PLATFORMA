import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CatalogScreen } from "./CatalogScreen";

describe("CatalogScreen", () => {
  it("shows six search types and four search scopes", () => {
    render(<CatalogScreen initialQuery="" onOpenCategory={vi.fn()} />);

    for (const label of [
      "Barchasi",
      "Mahsulot",
      "Xizmat",
      "Biznes",
      "Mutaxassis",
      "Foydalanuvchi",
      "Mahalla",
      "Tuman",
      "Viloyat",
      "Respublika",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("uses the Home query and filters visible directions", () => {
    render(
      <CatalogScreen initialQuery="telefon ta’miri" onOpenCategory={vi.fn()} />,
    );

    expect(screen.getByDisplayValue("telefon ta’miri")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Xizmat ko‘rsatish/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Savdo/i }),
    ).not.toBeInTheDocument();
  });

  it("clearing a query restores all directions", async () => {
    render(<CatalogScreen initialQuery="dorixona" onOpenCategory={vi.fn()} />);

    await userEvent.clear(screen.getByRole("searchbox"));

    expect(screen.getByText("20 ta yo‘nalish")).toBeInTheDocument();
  });

  it("opens a selected direction", async () => {
    const onOpenCategory = vi.fn();
    render(<CatalogScreen initialQuery="" onOpenCategory={onOpenCategory} />);

    await userEvent.click(
      screen.getByRole("button", { name: /^Ta’lim faoliyati/i }),
    );

    expect(onOpenCategory).toHaveBeenCalledWith("education");
  });
});
