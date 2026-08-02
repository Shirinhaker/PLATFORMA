import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PublicHeader } from "./PublicHeader";

function renderHeader({
  authenticated = false,
  isHome = true,
  features = { listings: true, taxi: false },
  theme = "light",
}: {
  authenticated?: boolean;
  isHome?: boolean;
  features?: { listings: boolean; taxi: boolean };
  theme?: "light" | "dark";
} = {}) {
  const actions = {
    onHome: vi.fn(),
    onLocation: vi.fn(),
    onAccount: vi.fn(),
    onBack: vi.fn(),
    onListings: vi.fn(),
    onCart: vi.fn(),
    onTaxi: vi.fn(),
    onToggleTheme: vi.fn(),
  };

  const rendered = render(
    <PublicHeader
      authenticated={authenticated}
      isHome={isHome}
      title={isHome ? undefined : "Katalog"}
      theme={theme}
      features={features}
      cartCount={2}
      {...actions}
    />,
  );

  return { ...actions, ...rendered };
}

describe("PublicHeader", () => {
  it("opens Home from the Koprik brand", async () => {
    const { onHome } = renderHeader();

    await userEvent.click(screen.getByRole("button", {
      name: "Koprik bosh sahifasi",
    }));

    expect(onHome).toHaveBeenCalledOnce();
  });

  it("opens the real location selection from Manzil", async () => {
    const { onLocation } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "Manzilim" }));

    expect(onLocation).toHaveBeenCalledOnce();
  });

  it("keeps the exact Kabinet label for guests and opens Account", async () => {
    const { onAccount } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(onAccount).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kirish" }))
      .not.toBeInTheDocument();
  });

  it("shows Kabinet for authenticated sessions", async () => {
    const { onAccount } = renderHeader({ authenticated: true });

    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(onAccount).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Kabinet" }))
      .toBeInTheDocument();
  });

  it("shows a working back action on subviews", async () => {
    const { onBack } = renderHeader({ isHome: false });

    await userEvent.click(screen.getByRole("button", { name: "Orqaga" }));

    expect(onBack).toHaveBeenCalledOnce();
    expect(screen.getByText("Katalog")).toBeInTheDocument();
  });

  it("renders the exact v1656 public actions and feature gates", async () => {
    const { onListings, onCart, onToggleTheme } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "E’lonlar" }));
    await userEvent.click(screen.getByRole("button", { name: "Savat" }));
    await userEvent.click(screen.getByRole("button", {
      name: "Rang rejimini almashtirish",
    }));

    expect(onListings).toHaveBeenCalledOnce();
    expect(onCart).toHaveBeenCalledOnce();
    expect(onToggleTheme).toHaveBeenCalledOnce();
    expect(screen.getByText("2")).toHaveClass("badge");
    expect(screen.getByRole("button", { name: "Koprik bosh sahifasi" }))
      .toHaveAttribute("id", "webBrandBtn");
    expect(screen.getByRole("button", { name: "E’lonlar" }))
      .toHaveAttribute("id", "webListingsBtn");
    expect(screen.getByRole("button", { name: "Manzilim" }))
      .toHaveAttribute("id", "locBtn");
    expect(screen.getByRole("button", { name: "Savat" }))
      .toHaveAttribute("id", "cartBtn");
    expect(screen.getByRole("button", { name: "Kabinet" }))
      .toHaveAttribute("id", "cabBtn");
    expect(screen.queryByRole("button", { name: /taxi/i }))
      .not.toBeInTheDocument();
  });

  it("shows Taxi only when its feature is enabled", async () => {
    const { onTaxi } = renderHeader({
      features: { listings: false, taxi: true },
    });

    expect(screen.queryByRole("button", { name: "E’lonlar" }))
      .not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Taxi bo'limi" }));
    expect(onTaxi).toHaveBeenCalledOnce();
  });

  it("caps the v1656 cart badge at 99+", () => {
    const actions = {
      onHome: vi.fn(), onLocation: vi.fn(), onAccount: vi.fn(), onBack: vi.fn(),
    };
    render(
      <PublicHeader
        authenticated
        cartCount={120}
        features={{ listings: false, taxi: false }}
        isHome
        onCart={vi.fn()}
        {...actions}
      />,
    );
    expect(screen.getByText("99+")).toHaveClass("badge");
  });

  it("uses the exact v1656 moon and sun icons for the current theme", () => {
    const { unmount } = renderHeader({ theme: "light" });
    const lightButton = screen.getByRole("button", {
      name: "Rang rejimini almashtirish",
    });
    expect(lightButton.querySelector("path"))
      .toHaveAttribute("d", "M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z");
    unmount();

    renderHeader({ theme: "dark" });
    const darkButton = screen.getByRole("button", {
      name: "Rang rejimini almashtirish",
    });
    expect(darkButton.querySelector("circle"))
      .toHaveAttribute("r", "4.5");
  });
});
