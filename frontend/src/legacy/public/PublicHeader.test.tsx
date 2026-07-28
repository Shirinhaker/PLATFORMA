import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PublicHeader } from "./PublicHeader";

function renderHeader({
  authenticated = false,
  isHome = true,
}: {
  authenticated?: boolean;
  isHome?: boolean;
} = {}) {
  const actions = {
    onHome: vi.fn(),
    onLocation: vi.fn(),
    onAccount: vi.fn(),
    onBack: vi.fn(),
  };

  render(
    <PublicHeader
      authenticated={authenticated}
      isHome={isHome}
      title={isHome ? undefined : "Katalog"}
      {...actions}
    />,
  );

  return actions;
}

describe("PublicHeader", () => {
  it("opens Home from the Koprik brand", async () => {
    const { onHome } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "Koprik" }));

    expect(onHome).toHaveBeenCalledOnce();
  });

  it("opens the real location selection from Manzil", async () => {
    const { onLocation } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "Manzil" }));

    expect(onLocation).toHaveBeenCalledOnce();
  });

  it("shows Kirish for guests and opens Account", async () => {
    const { onAccount } = renderHeader();

    await userEvent.click(screen.getByRole("button", { name: "Kirish" }));

    expect(onAccount).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kabinet" }))
      .not.toBeInTheDocument();
  });

  it("shows Kabinet for authenticated sessions", async () => {
    const { onAccount } = renderHeader({ authenticated: true });

    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));

    expect(onAccount).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kirish" }))
      .not.toBeInTheDocument();
  });

  it("shows a working back action on subviews", async () => {
    const { onBack } = renderHeader({ isHome: false });

    await userEvent.click(screen.getByRole("button", { name: "Orqaga" }));

    expect(onBack).toHaveBeenCalledOnce();
    expect(screen.getByText("Katalog")).toBeInTheDocument();
  });

  it("does not expose unmigrated public actions", () => {
    renderHeader();

    expect(screen.queryByRole("button", { name: /e’lonlar/i }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /savat/i }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /taxi/i }))
      .not.toBeInTheDocument();
  });
});
